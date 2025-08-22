from hmbot.explorer.llm import llm, uitars
from hmbot.model.page import Page
from hmbot.device.device import Device
from langchain_core.messages import HumanMessage, AIMessage
from hmbot.explorer.action_parser import action_parser
from hmbot.model.event import *
from hmbot.utils.cv import encode_image
from loguru import logger
import json, time, re, os, cv2
from typing import Dict, List, Optional
from hmbot.explorer.prompt import *


class PageNode:
    def __init__(self, index: int, page: Page, page_abstract: str=""):
        """
        页面节点的构造函数。
        
        Args:
            index (int): 页面的唯一序号。
            page (Page): 与此节点关联的页面对象。
            page_abstract (str): 由LLM生成的页面摘要。
        """
        # 页面序号
        self.index = index
        self.page = page
        # 页面摘要
        self.page_abstract = page_abstract
        # 当前页面已经探索过的操作
        self.explored_operations: List[Dict] = []
    
    def describe(self) -> str:
        """生成并返回当前节点的详细描述字符串，包括其已探索的操作及跳转方向。"""
        description = f"Page {self.index} 摘要: {self.page_abstract}\n"

        if self.explored_operations:
            description += "已探索的操作:\n"
            for op in self.explored_operations:
                action_desc = op.get('operation')
                dest_index = op.get('dest_index')
                
                if dest_index == -1:
                    description += f"  - \"{action_desc}\" -> (操作无效)\n"
                else:
                    description += f"  - \"{action_desc}\" -> 跳转至 Page {dest_index}\n"
        else:
            description += "已探索的操作: 无\n"
            
        return description

    def add_explored_operation(self, operation: str, dest_index: int):
        """添加一个已探索的操作。"""
        self.explored_operations.append({
            "operation": operation,
            "dest_index": dest_index
        })


class BugExplorer:
    def __init__(self, device: Device):
        self.device = device
        self.llm = llm
        self.uitars = uitars
        self.curr_page_index = 0
        self.pages: list[PageNode] = []
        self.bugs_report: list[str] = []
        self.explored_abilities: list[str] = []

    def test(self, max_steps: int = 50, output_dir: str = "output"):
        self.explore_coarse(max_steps=max_steps, output_dir=output_dir)

    def explore_coarse(self, max_steps: int = 50, output_dir: str = "output"):
        """粗粒度探索"""
        verification_feedback = None

        logger.info("=========== 探索开始，正在分析初始页面... ==========")
        initial_page = self.device.dump_page(refresh=True)
        initial_page_index = self._is_page_exist(initial_page)
        if initial_page_index == len(self.pages):
            current_page_node = self._get_page_node(initial_page, initial_page_index)
            self.pages.append(current_page_node)
            logger.info(f"探索始于新页面 (索引 {initial_page_index})")
        else:
            current_page_node = self.pages[initial_page_index]
            logger.info(f"探索始于已知页面 (索引 {initial_page_index})")
        self.curr_page_index = current_page_node.index

        for step in range(max_steps):
            logger.info(f"=========== 探索步骤 {step + 1}/{max_steps} ==========")
            # 确保在每次循环开始时，我们都引用的是最新的当前页面节点
            current_page_node = self.pages[self.curr_page_index]
            logger.info(f"当前位于页面 (索引 {self.curr_page_index})")

            # 更新页面状态
            page = self.device.dump_page(refresh=True)
            current_page_node.page = page

            # 更新页面摘要
            # current_page_node.page_abstract = self._get_page_abstract(page)

            # 获取下一步操作
            operation = self._get_next_operation(verification_feedback)
            logger.info(f"下一步操作: {operation}")

            page_node_before_operation = current_page_node

            # 执行操作
            result = self._execute_operation(current_page_node, operation)
            if result == "noop":
                logger.info("操作无效，重新选择操作")
                # 记录无效操作，目标索引设为 -1
                page_node_before_operation.add_explored_operation(operation, -1)
                continue

            # 操作后获取新页面截图
            page_after_operation = self.device.dump_page(refresh=True)
            # 创建一个临时的页面节点用于验证，此时它还没有正式的索引
            page_node_after_temp = PageNode(index=-1, page=page_after_operation)

            # 验证操作结果
            verification_result = self._verify_operation(page_node_before_operation, page_node_after_temp, operation)
            
            # 提取状态和消息，消息将作为下一次决策的反馈
            status = verification_result.get("status")
            message = verification_result.get("message")
            verification_feedback = message

            # 先处理逻辑独特的 "failure" 状态
            if status == "failure":
                logger.warning(f"操作失败: {message}")
                # 记录无效操作，目标索引设为 -1
                page_node_before_operation.add_explored_operation(operation, -1)
                # 留在当前页面
                continue

            # 处理 "success" 和 "error" 状态，它们有共同的页面跳转/更新逻辑
            if status == "success":
                logger.info(f"操作成功: {message}")
            elif status == "error":
                logger.error(f"操作导致错误: {message}")
                # error 状态特有的操作：添加 bug 报告
                self.bugs_report.append(f"Page {page_node_before_operation.index} -> Operation: '{operation}' -> Error: {message}")

            page_index_after = self._is_page_exist(page_after_operation)
            page_node_before_operation.add_explored_operation(operation, page_index_after)

            # 判断是新页面还是旧页面，并更新当前页面节点
            if page_index_after == len(self.pages):
                # 发现新页面
                logger.info(f"发现新页面 (索引 {page_index_after})")
                new_page_node = self._get_page_node(page_after_operation, page_index_after)
                self.pages.append(new_page_node)
                current_page_node = new_page_node
            else:
                # 跳转至已知页面
                logger.info(f"跳转至已知页面 (索引 {page_index_after})")
                current_page_node = self.pages[page_index_after]

            # 更新当前页面的索引，为下一次循环做准备
            self.curr_page_index = current_page_node.index
        self._save_bugs_report(output_dir=output_dir)

    def _get_page_node(self, page: Page, index: int) -> PageNode:
        page_node = PageNode(
            index=index,
            page=page,
        )
        return page_node

    def _get_page_abstract(self, page: Page) -> str:
        """获取页面摘要"""
        prompt = page_abstract_prompt
        content = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(page.img)}"
                    }
                }
            ]
        )
        page_abstract = self.llm.invoke([content]).content
        return page_abstract

    def _get_page_info(self, page: Page, index: int) -> PageNode:
        """获取页面信息"""
        page_abstract = self._get_page_abstract(page)

        # 构造新的PageNode对象
        page_node = PageNode(
            index=index,
            page=page,
            page_abstract=page_abstract
        )
        
        return page_node

    def _is_page_exist(self, page: Page) -> int:
        """判断当前页面是否已存在于页面列表中。"""
        # 初始情况：如果还没有任何页面，则当前页面是第一个
        if not self.pages:
            return 0

        # logger.debug(page.info.ability)
        if page.info.ability not in self.explored_abilities:
            self.explored_abilities.append(page.info.ability)

        # 快速筛选：根据 ability 找到所有可能的候选页面索引
        found_indices = [
            p.index for p in self.pages
            if p.page.info and p.page.info.ability == page.info.ability
        ]

        # 如果没有找到任何相同 ability 的候选页面，直接判断为新页面
        # 这里修改成了每一个 ability 就代表一个页面，有效避免了错误判断为新界面时的情况
        if not found_indices:
            return len(self.pages)
        else:
            return found_indices[0]

        # 如果找到了候选页面，进入LLM视觉对比阶段
        prompt_text = page_exist_prompt
        content = [{"type": "text", "text": prompt_text}]

        # 添加新页面的截图
        content.append({"type": "text", "text": "--- \n## 1. 新截图 (New Screenshot)"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{encode_image(page.img)}"}
        })

        # 依次添加所有候选页面的截图
        content.append({"type": "text", "text": "\n## 2. 已知候选页面 (Candidate Pages)"})
        for index in found_indices:
            candidate_node = self.pages[index]
            content.append({"type": "text", "text": f"--- \n### 候选页面索引 (Candidate Index): {index}"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(candidate_node.page.img)}"}
            })

        # 调用LLM进行判断
        try:
            message = HumanMessage(content=content)
            response_text = self.llm.invoke([message]).content
            
            # 解析LLM返回的JSON结果
            if response_text.strip().startswith('```json'):
                response_text = re.search(r'```json\s*([\s\S]*?)\s*```', response_text).group(1)
            
            response_json = json.loads(response_text)

            if response_json.get("is_new", True):
                # LLM判断为新页面
                return len(self.pages)
            else:
                # LLM判断为已存在页面
                existing_index = response_json.get("existing_index", -1)
                if existing_index in found_indices:
                    return existing_index
                else:
                    logger.warning(f"LLM返回了一个无效或非候选的索引: {existing_index}。候选列表为 {found_indices}。将此页面视为新页面。")
                    return len(self.pages)

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"处理LLM多图对比响应时出错: {e}。将默认视为新页面。")
            return len(self.pages)

    def _get_next_operation(self, verification_feedback: Optional[str] = None) -> str:
        """
        根据当前页面的截图、已探索操作和上一步反馈，获取下一步操作。
        """
        # 获取当前页面节点
        current_page_node = self.pages[self.curr_page_index]

        # 如果有上一步操作的反馈，准备要插入到Prompt中的文本
        feedback_prompt_section = ""
        if verification_feedback:
            feedback_prompt_section = f'''### 2. 上一步操作反馈
{verification_feedback}'''

        # 获取并格式化当前页面已探索的操作列表
        explored_ops_list = [op.get('operation', 'N/A') for op in current_page_node.explored_operations]
        explored_ops_str = "\n".join(f"- \"{op}\"" for op in explored_ops_list) if explored_ops_list else "无"

        logger.debug(f"当前页面已探索的操作: {explored_ops_str}")

        prompt_text = next_operation_prompt.format(
            curr_page_index=self.curr_page_index,
            explored_ops_str=explored_ops_str,
            feedback_prompt_section=feedback_prompt_section
        )

        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": prompt_text
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(current_page_node.page.img)}"
                    }
                }
            ]
        )
        response = self.llm.invoke([message])
        return response.content

    def _execute_operation(self, page_node: PageNode, operation_description: str):
        page = self.device.dump_page(refresh=True)
        page_node.page = page
        base64_image = encode_image(page.img)
        
        parsed_output = None
        max_retries = 3
        retry_count = 0

        while not (parsed_output and parsed_output.get("action")) and retry_count < max_retries:
            if retry_count > 0:
                logger.info(f"Retrying to get a valid action ({retry_count}/{max_retries})...")
                time.sleep(2)  # 等待2秒后重试

            # 创建包含图片和文本的消息
            message = HumanMessage(content=[
                {
                    "type": "text",
                    "text": event_llm_prompt.format(language="Chinese", instruction=operation_description)
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                    }
                }
            ])
            response = self.uitars.invoke([message])
            logger.debug(f"LLM response: {response.text()}")

            parsed_output = action_parser.parse_action_output(response.text(), page.img.shape[1], page.img.shape[0])
            retry_count += 1
        
        # 执行解析出的操作
        if parsed_output and parsed_output.get("action"):
            new_event = None
            if parsed_output["action"] == "click" and parsed_output["point"]:
                center_pos = parsed_output["point"]
                logger.info(f"点击坐标: {center_pos}")
                self.device.click(center_pos[0], center_pos[1])
                time.sleep(3)
                
            elif parsed_output["action"] == "type" and parsed_output["content"]:
                nodes = page.vht._root(clickable='true', focused='true', enabled='true', type='android.widget.EditText')
                if nodes:
                    new_event = InputEvent(nodes[0], parsed_output["content"])
                else:
                    logger.error("No edit text node found")

            elif parsed_output["action"] == "scroll" and parsed_output["point"] and parsed_output["direction"]:
                new_event = SwipeExtEvent(self.device, page, parsed_output["direction"])

            elif parsed_output["action"] == "press_back":
                new_event = KeyEvent(self.device, page, "back")
            elif parsed_output["action"] == "noop":
                return "noop"

            if new_event:
                new_event.execute()
                time.sleep(3)
            return f"操作成功完成：{parsed_output['action']}"
        else:
            logger.error("Failed to get a valid action after multiple retries.")
            return "操作失败：无法解析LLM响应"

    def _verify_operation(self, page_node_before: PageNode, page_node_after: PageNode, operation: str) -> Dict[str, str]:
        """操作验证: 根据操作前后的界面截图，分析当前操作是否有效、是否符合预期以及是否引发错误。"""
        prompt = verify_operation_prompt.format(operation=operation)

        # The message payload includes the prompt and both before/after images for comparison.
        content = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "text",
                    "text": "\n--- 操作前截图 ---"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(page_node_before.page.img)}"
                    }
                },
                {
                    "type": "text",
                    "text": "\n--- 操作后截图 ---"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(page_node_after.page.img)}"
                    }
                }
            ]
        )

        try:
            # Invoke the LLM with the prepared content.
            response_text = self.llm.invoke([content]).content
            
            # Clean up the response to extract the JSON part, removing markdown code blocks if present.
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                clean_response_text = json_match.group(1)
            else:
                clean_response_text = response_text

            response_json = json.loads(clean_response_text)

            # Validate that the JSON contains the required keys.
            if "status" in response_json and "message" in response_json:
                return response_json
            else:
                logger.warning(f"LLM response for verification is missing required keys. Response: {response_text}")
                return {
                    "status": "error",
                    "message": "操作验证失败：模型返回了无效的JSON结构。"
                }

        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from LLM response. Response: {response_text}")
            return {
                "status": "error",
                "message": "操作验证失败：无法解析模型返回的JSON。"
            }
        except Exception as e:
            logger.error(f"An unexpected error occurred during operation verification: {e}")
            return {
                "status": "error",
                "message": f"操作验证失败，发生未知异常: {e}"
            }

    def _save_bugs_report(self, output_dir: str):
        """保存完整的探索报告，并根据要求调整输出格式。"""
        # 创建主输出目录和截图子目录
        screenshots_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)
        logger.info(f"报告将保存在目录: {os.path.abspath(output_dir)}")

        # 保存所有页面截图 
        logger.info("正在保存页面截图...")
        for node in self.pages:
            screenshot_path = os.path.join(screenshots_dir, f"page_{node.index}.png")
            try:
                cv2.imwrite(screenshot_path, node.page.img)
            except Exception as e:
                logger.error(f"无法保存截图 {screenshot_path}: {e}")
        logger.info(f"已成功保存 {len(self.pages)} 张截图到: {screenshots_dir}")

        # 保存Bug报告
        bug_report_path = os.path.join(output_dir, "bug_report.txt")
        if self.bugs_report:
            logger.info(f"发现 {len(self.bugs_report)} 个潜在bug，正在保存报告...")
            with open(bug_report_path, "w", encoding="utf-8") as f:
                f.write("="*20 + " Bug 报告 " + "="*20 + "\n\n")
                for i, bug_description in enumerate(self.bugs_report, 1):
                    f.write(f"{i}. {bug_description}\n")
            logger.info(f"Bug报告已保存到: {bug_report_path}")
        else:
            logger.info("未发现任何bug。")

        # 保存探索到的Abilities
        abilities_report_path = os.path.join(output_dir, "explored_abilities.txt")
        if self.explored_abilities:
            logger.info(f"探索到 {len(self.explored_abilities)} 个功能页面(Abilities)，正在保存列表...")
            with open(abilities_report_path, "w", encoding="utf-8") as f:
                f.write("="*20 + " 已探索的Abilities列表 " + "="*20 + "\n\n")
                for ability in self.explored_abilities:
                    f.write(f"- {ability}\n")
            logger.info(f"功能列表已保存到: {abilities_report_path}")

        # 保存详细的探索路径和动作报告
        path_report_path = os.path.join(output_dir, "exploration_path_report.json")
        logger.info("正在生成并保存JSON格式的详细探索路径报告...")
        
        exploration_data = []
        # 按页面索引排序，确保报告的顺序是正确的
        sorted_pages = sorted(self.pages, key=lambda p: p.index)
        for node in sorted_pages:
            page_data = {
                "page_index": node.index,
                # "page_summary": node.page_abstract,
                "screenshot_path": os.path.join("screenshots", f"page_{node.index}.png").replace("\\", "/"),
                "explored_operations": node.explored_operations
            }
            exploration_data.append(page_data)
            
        with open(path_report_path, "w", encoding="utf-8") as f:
            json.dump(exploration_data, f, ensure_ascii=False, indent=4)
        logger.info(f"探索路径报告已保存到: {path_report_path}")

        logger.info("=========== 所有报告保存完毕 ==========")

    def explore_fine(self):
        """细粒度探索"""
        pass
