from hmbot.explorer.llm import *
from hmbot.model.page import Page
from hmbot.device.device import Device
from langchain_core.messages import HumanMessage, AIMessage
from hmbot.explorer.action_parser import action_parser
from hmbot.model.event import *
from hmbot.utils.cv import encode_image
from loguru import logger
import json, time, re, os, cv2, threading, collections
from typing import Dict, List, Optional
from hmbot.explorer.prompt import *
from hmbot.app.app import App
import numpy as np


class PageNode:
    def __init__(self, index: int, page: Page, page_abstract: str="", widget_list: list = None, function_list: list = None):
        """
        页面节点的构造函数。
        
        Args:
            index (int): 页面的唯一序号。
            page (Page): 与此节点关联的页面对象。
            page_abstract (str): 由LLM生成的页面摘要。
            widget_list (list): 页面上所有控件的列表。
            function_list (list): 页面上所有功能的列表。
        """
        self.index = index
        self.page = page
        self.page_abstract = page_abstract
        self.explored_operations: List[Dict] = []
        self.widgets = list(widget_list) if widget_list else []
        self.functions = list(function_list) if function_list else []

    def describe(self) -> str:
        """
        生成节点的统一描述。
        现在会始终显示“已探索的操作”和“页面上的所有可用控件”。
        """
        # 总是先显示页面摘要
        description = f"Page {self.index} Summary: {self.page_abstract}\n\n"

        # 第一部分：固定显示已探索的操作
        if self.explored_operations:
            description += "Explored Operations:\n"
            for op in self.explored_operations:
                action_desc = op.get('operation')
                dest_index = op.get('dest_index')
                description += f"  - {action_desc} -> Jumps to Page {dest_index}\n"
        else:
            description += "Explored Operations: None\n"
        
        description += "\n"  # 增加一个空行用于分隔

        # 第二部分：固定显示页面上的所有控件
        if self.widgets:
            description += "Available Widgets on Page:\n"
            for widget_desc in self.widgets:
                description += f"  - {widget_desc}\n"
        else:
            description += "Available Widgets on Page: None\n"
            
        return description

    def add_explored_operation(self, operation: str, dest_index: int):
        """
        添加一个已探索的操作。
        """
        self.explored_operations.append({
            "operation": operation,
            "dest_index": dest_index
        })

def show_comparison(before_img: np.ndarray, after_img: np.ndarray, operation_text: str):
    """
    一个极简的函数，在单个窗口中并排显示操作前后的图片，
    并在图片顶部直接添加操作描述。
    
    Args:
        before_img (np.ndarray): 操作前的截图 (已由OpenCV加载)。
        after_img (np.ndarray): 操作后的截图 (已由OpenCV加载)。
        operation_text (str): 执行的操作描述。
    """
    # 1. 水平拼接两张图片
    comparison_img = cv2.hconcat([before_img, after_img])

    # 2. 在图片顶部画一个黑色背景条，以确保文字清晰可见
    # cv2.rectangle(图片, 左上角坐标, 右下角坐标, 颜色, 厚度(-1为填充))
    cv2.rectangle(comparison_img, (0, 0), (comparison_img.shape[1], 40), (0, 0, 0), -1)

    # 3. 在背景条上写上白色的操作描述文字
    cv2.putText(
        comparison_img,                      # 要绘制的图片
        f"Action: {operation_text}",         # 要显示的文本
        (10, 30),                            # 文字左下角的坐标 (x, y)
        cv2.FONT_HERSHEY_SIMPLEX,            # 字体
        1,                                   # 字体大小
        (255, 255, 255),                     # 字体颜色 (BGR格式的白色)
        2                                    # 字体粗细
    )

    # 4. 显示最终的图片
    cv2.imshow("Operation Comparison", comparison_img)

    # 5. 等待用户按键后，关闭所有OpenCV窗口
    print(">>> 验证操作：请查看弹出的图片对比窗口，然后在窗口上按任意键继续...")
    cv2.waitKey(0)  # 0表示无限期等待，直到有按键
    cv2.destroyAllWindows()

class BugExplorer:
    def __init__(self, device: Device, app: App = None):
        self.device = device
        self.app = app
        self.llm_flash = llm_flash
        self.llm_pro = llm_pro
        self.uitars = uitars
        self.app_bundle = ""
        self.last_page_index = -1
        self.curr_page_index = 0
        self.pages: list[PageNode] = []
        self.bugs_report: list[str] = []
        self.explored_abilities: list[str] = []

        # 最近的5次操作历史，包含截图和操作描述
        self.history: collections.deque[dict] = collections.deque(maxlen=5) 
        
        # 最近的3次指令历史，记录高级策略
        self.instruction_history: collections.deque[str] = collections.deque(maxlen=3) 

        # --- 为PTG构建器添加的线程安全属性 ---
        self.shared_ptg_data = collections.deque()
        self.ptg_data_lock = threading.Lock()
        self.ptg_thread_stop_event = threading.Event()
        self.is_ptg_builder_processing = False
        self.ptg_builder_thread = None
        self.ptg_idle_condition = threading.Condition(self.ptg_data_lock)

    def test(self):
        self.explore_coarse()
        # self._execute_instruction("将当前软件的主题调整成light模式")

    def explore_coarse(self, max_minutes: int = 60, output_dir: str = "output"):
        self.ptg_thread_stop_event.clear()
        self.ptg_builder_thread = threading.Thread(target=self._build_PTG, daemon=True)
        self.ptg_builder_thread.start()

        start_time = time.time()
        max_seconds = max_minutes * 60

        try:
            verification_feedback = ""
            logger.info(f"=========== 探索开始 (时长上限: {max_minutes} 分钟) ==========")
            
            initial_page = self.device.dump_page(refresh=True)
            self.app_bundle = initial_page.info.bundle if initial_page.info else ""
            current_page_node = self._get_page_info(initial_page, 0)
            self.pages.append(current_page_node)
            self.curr_page_index = current_page_node.index

            while True:
                elapsed_time = time.time() - start_time
                if elapsed_time >= max_seconds:
                    logger.info(f"探索已达到设定的 {max_minutes} 分钟时长上限，正在停止...")
                    break  # 跳出 while 循环

                current_page_node = self.pages[self.curr_page_index]
                
                elapsed_minutes = elapsed_time / 60
                logger.info(f"当前位于页面 (索引 {self.curr_page_index}) | 已运行: {elapsed_minutes:.1f}/{max_minutes} 分钟")

                # 更新页面状态
                page = self.device.dump_page(refresh=True)
                current_page_node.page = page    

                instruction = self._get_next_instruction(verification_feedback)
                logger.info(f"下一步指令: {instruction}")
                
                self.instruction_history.append(instruction)

                records = self._execute_instruction(instruction)

                verification_feedback = self._verify_instruction(records, instruction)
                
                with self.ptg_data_lock:
                    while len(self.shared_ptg_data) > 0 or self.is_ptg_builder_processing:
                        queue_size = len(self.shared_ptg_data)
                        processing_status = "是" if self.is_ptg_builder_processing else "否"
                        logger.info(f"主线程等待中... 队列剩余: {queue_size}, PTG是否正在处理: {processing_status}")
                        self.ptg_idle_condition.wait()
                
                logger.info("主线程收到通知：PTG构建器已处理完毕。继续下一次循环。")

        finally:
            # --- 修改日志: 明确探索结束的原因 ---
            logger.info("=========== 探索结束，正在保存Bug报告... ==========")
            self.ptg_thread_stop_event.set()
            with self.ptg_data_lock:
                self.ptg_idle_condition.notify_all()
            if self.ptg_builder_thread:
                self.ptg_builder_thread.join()
            logger.info("PTG构建器后台线程已停止。")
            self._save_bugs_report(output_dir=output_dir)

    def _build_PTG(self):
        """构建程序测试图 (PTG)"""
        logger.info("PTG构建器线程已启动，等待数据...")
        while not self.ptg_thread_stop_event.is_set():
            data_item = None
            with self.ptg_data_lock:
                if self.shared_ptg_data:
                    data_item = self.shared_ptg_data.popleft()
                    self.is_ptg_builder_processing = True
            
            if data_item:
                current_page_node = self.pages[self.curr_page_index]
                page_index_after = self._is_page_exist(data_item["page"])
                current_page_node.add_explored_operation(data_item["operation"], page_index_after)
                self.curr_page_index = page_index_after

                # 判断是新页面还是旧页面，并更新当前页面节点
                if page_index_after == len(self.pages):
                    # 发现新页面
                    logger.info(f"发现新页面 (索引 {page_index_after})")
                    new_page_node = self._get_page_info(data_item["page"], page_index_after)
                    self.pages.append(new_page_node)
                else:
                    # 跳转至已知页面
                    logger.info(f"跳转至已知页面 (索引 {page_index_after})")


                # 处理完成后，更新状态并通知主线程
                with self.ptg_data_lock:
                    self.is_ptg_builder_processing = False
                    # 关键点: 如果队列空了，就通知正在等待的主线程
                    if not self.shared_ptg_data:
                        logger.debug("PTG队列已清空，通知主线程可以继续。")
                        self.ptg_idle_condition.notify_all()
            else:
                time.sleep(0.5)
        logger.info("PTG构建器线程接收到停止信号，即将退出。")

    def _get_next_instruction(self, verification_feedback: str = "") -> str:
        """根据验证反馈获取下一步指令"""
        current_page_node = self.pages[self.curr_page_index]

        exploration_map_str = self._get_localized_map_str(self.curr_page_index)

        feedback_prompt_section = ""
        if verification_feedback:
            # 使用更符合 prompt 模板的格式
            feedback_prompt_section = f"### Feedback on Last Action\n{verification_feedback}"

        explored_ops_list = [op.get('operation', 'N/A') for op in current_page_node.explored_operations]
        explored_ops_str = "\n".join(f"- \"{op}\"" for op in explored_ops_list) if explored_ops_list else "None"

        # 格式化指令历史
        instruction_history_str = ""
        if self.instruction_history:
            instruction_entries = []
            for i, instruction in enumerate(self.instruction_history):
                instruction_entries.append(f"- Instruction {i+1}: {instruction}")
            instruction_history_str = "\n".join(instruction_entries)
        else:
            instruction_history_str = "No previous instructions yet."

        history_str = ""
        message_content = []

        if self.history:
            # 准备历史记录的文字描述 (从旧到新)
            history_entries = []
            for i, item in enumerate(self.history):
                history_entries.append(f"- Action {i+1}: {item['operation']}")
            history_str = "\n".join(history_entries)

            # 构建包含6张图片的消息体
            # 1. 添加“初始状态”截图，即第一个动作之前的截图
            initial_state_img = self.history[0]['before'].img
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(initial_state_img)}"}
            })

            # 2. 依次添加5个动作之后的“结果状态”截图
            for item in self.history:
                result_state_img = item['after'].img
                message_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encode_image(result_state_img)}"}
                })
        else:
            # 如果历史记录为空（即第一步），则只提供当前截图
            history_str = "This is the first action. No history yet."
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(current_page_node.page.img)}"}
            })

        logger.debug(f"当前页面已探索的操作: {explored_ops_str}")
        logger.debug(f"指令历史: {instruction_history_str}")
        logger.debug(f"操作历史: {history_str}")
        
        prompt_text = next_operation_prompt.format(
            exploration_map_str=exploration_map_str,
            instruction_history_str=instruction_history_str,
            history_str=history_str,
            curr_page_index=self.curr_page_index,
            explored_ops_str=explored_ops_str,
            feedback_prompt_section=feedback_prompt_section
        )

        # 将文本 Prompt 作为消息列表的第一个元素
        message_content.insert(0, {"type": "text", "text": prompt_text})
        message = HumanMessage(content=message_content)

        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                response = self.llm_pro.invoke([message])
                return response.text()
            except Exception as e:
                logger.error(f"处理 LLM 响应时发生未知错误: {e}")
            
            # 如果失败，则会继续下一次循环尝试
        
        # 如果所有尝试都失败了，则抛出异常
        raise RuntimeError(f"在 {MAX_RETRIES} 次尝试后，仍未能从 LLM 获取有效的操作指令。")
        
    def _execute_instruction(self, instruction: str):
        """根据给定的指令执行一系列连续动作"""
        page = self.device.dump_page(refresh=True)
        base64_image = encode_image(page.img)

        records = []

        conversation_history = [
            HumanMessage(content=[
                {
                    "type": "text",
                    "text": event_llm_prompt.format(language="English", instruction=instruction)
                }
            ]),
            HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image}",
                    }
                }
            ])
        ]
        
        parsed_output = None
        MAX_PARSE_RETRIES = 3
        parse_retry_count = 0
        
        while True:
            response = self.uitars.invoke(conversation_history)
            logger.debug(f"LLM response: {response.text()}")
            conversation_history.append(AIMessage(content=response.text()))

            try:
                parsed_output = action_parser.parse_action_output(response.text(), page.img.shape[1], page.img.shape[0])
                if not (parsed_output and parsed_output.get("action") in ["click", "type", "scroll", "press_back", "finished"]):
                    raise ValueError(f"无效或不支持的操作: {parsed_output.get('action')}")
                parse_retry_count = 0 
            except Exception as e:
                logger.error(f"解析或验证LLM响应失败 (尝试 {parse_retry_count + 1}/{MAX_PARSE_RETRIES})，错误: {e}")        
                parse_retry_count += 1
                # 检查是否已达到最大重试次数
                if parse_retry_count >= MAX_PARSE_RETRIES:
                    logger.error("已达到最大重试次数，任务失败。")
                    break
                time.sleep(1)  # 等待1秒后重试
                continue

            page_before_operation = page

            action_type = parsed_output.get("action")   
            # 检查解析出的操作是否为 "finished"
            if action_type == "finished":
                logger.info("Task finished as per LLM instruction.")
                break
            elif action_type == "click" and parsed_output.get("point"):
                center_pos = parsed_output["point"]
                logger.debug(f"Executing click at coordinates: {center_pos}")
                self.device.click(center_pos[0], center_pos[1])
            elif action_type == "type" and parsed_output.get("content"):
                self.device.input(parsed_output["content"])
            elif action_type == "scroll" and parsed_output.get("point") and parsed_output.get("direction"):
                SwipeExtEvent(self.device, page, parsed_output["direction"]).execute()
            elif action_type == "press_back":
                KeyEvent(self.device, page, "back").execute()
            time.sleep(3)

            # 获取操作后页面
            page = self.device.dump_page(refresh=True) 
            base64_image = encode_image(page.img)

            with self.ptg_data_lock:
                if parsed_output.get("status") == "success":
                    self.history.append({
                        "before": page_before_operation,
                        "operation": parsed_output.get("description"),
                        "after": page
                    })
                    self.shared_ptg_data.append({
                        "operation": parsed_output.get("description"),
                        "page": page
                    })
                    records.append({
                        "before": page_before_operation,
                        "operation": parsed_output.get("description"),
                        "after": page
                    })


            # 将新截图作为新的用户消息添加到对话历史中，为下一次决策做准备
            conversation_history.append(
                HumanMessage(content=[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}",
                        }
                    }
                ])
            )

            new_history = []
            image_count = 0

            # 从后往前遍历历史记录
            for message in reversed(conversation_history):
                # 检查消息是否包含图片
                is_image_message = False
                if isinstance(message, HumanMessage):
                    for part in message.content:
                        if part.get("type") == "image_url":
                            is_image_message = True
                            break
                
                if is_image_message:
                    # 如果是图片消息，只有在图片计数未满时才保留
                    if image_count < 5:
                        new_history.append(message)
                        image_count += 1
                else:
                    # 如果不是图片消息（即纯文本消息），则直接保留
                    new_history.append(message)
            
            conversation_history = list(reversed(new_history))

        return records

    def _verify_instruction(self, records: list, instruction: str) -> str:
        """
        根据一系列操作记录和高阶指令，验证其执行结果是否符合预期。

        该函数会构建一个包含操作前后截图、操作描述的序列，
        并结合 `verify_operation_prompt` 指令，调用多模态LLM进行分析。
        LLM会判断操作序列中是否存在“严重故障”，并以指定的JSON格式返回分析结果。

        Args:
            records (list): 一个包含多个字典的列表，每个字典代表一个操作步骤，
                            结构为 {'before': Page, 'operation': str, 'after': Page}。
            instruction (str): 执行此次操作序列的原始高阶指令。

        Returns:
            str: 从LLM返回的feedback字符串。如果操作成功，它是一个总结；
                如果失败，它会详细描述每一个发现的故障。
        """
        # 如果记录为空，说明没有执行任何操作，直接返回成功。
        if not records:
            logger.info("验证记录为空，无需验证，默认成功。")
            return "Success: No actions were executed, so no failures to report."

        # message_content 将用于构建发送给LLM的完整多模态消息
        message_content = []

        # 1. 添加核心指令
        message_content.append({"type": "text", "text": verify_operation_prompt})

        # 2. 添加正在执行的高阶指令作为上下文，帮助LLM理解整体目标
        message_content.append({
            "type": "text",
            "text": f"### High-Level User Instruction Being Executed:\n\"{instruction}\"\n\n### Detailed Steps for Analysis:"
        })

        # 3. 按照 "初始截图 -> 操作1 -> 结果截图1 -> 操作2 -> 结果截图2..." 的顺序构建图文序列
        try:
            # 添加初始状态截图
            initial_state_img = records[0]['before'].img
            message_content.append({"type": "text", "text": "Initial State (Screenshot 0):"})
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(initial_state_img)}"}
            })
        except (IndexError, AttributeError, KeyError) as e:
            logger.error(f"无法从记录中获取初始状态截图，错误: {e}")
            return "Verification Error: Could not process the initial state from the records."

        # 循环添加每个操作及其结果截图
        for i, record in enumerate(records):
            step_num = i + 1
            operation_desc = record.get('operation', 'No description available')
            after_page = record.get('after')

            if not after_page or not hasattr(after_page, 'img'):
                logger.warning(f"第 {step_num} 步缺少操作后的页面或截图，该步骤将在验证中被跳过。")
                continue
            
            # 添加操作描述
            message_content.append({"type": "text", "text": f"\nStep {step_num} Operation: {operation_desc}"})
            # 添加操作后的截图
            message_content.append({"type": "text", "text": f"Post-Operation State (Screenshot {step_num}):"})
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(after_page.img)}"}
            })

        # 4. 调用LLM进行分析，并加入重试机制以提高稳定性
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"正在调用LLM验证 {len(records)} 个操作步骤... (第 {attempt + 1}/{MAX_RETRIES} 次尝试)")
                message = HumanMessage(content=message_content)
                response = self.llm_pro.invoke([message])
                raw_content = response.content

                # 5. 清理并解析LLM返回的JSON响应
                if raw_content.strip().startswith("```json"):
                    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', raw_content)
                    if json_match:
                        raw_content = json_match.group(1)
                    else: # 处理没有闭合```的情况
                        raw_content = raw_content.strip()[7:].strip()
                
                parsed_json = json.loads(raw_content)
                
                status = parsed_json.get('status')
                feedback = parsed_json.get('feedback')

                # 检查关键字段是否存在
                if status not in ['success', 'error'] or feedback is None:
                    logger.warning(f"LLM响应格式不完整，缺少 'status' 或 'feedback'。响应: {parsed_json}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2)  # 等待后重试
                        continue
                    return f"Verification Error: LLM response was malformed. Raw content: {raw_content}"

                logger.info(f"验证完成。状态: {status}")
                
                # 如果发现错误，将其记录到全局Bug报告中
                if status == 'error':
                    self.bugs_report.append(f"Instruction: '{instruction}'\nFailure Details: {feedback}")

                return feedback

            except json.JSONDecodeError:
                logger.warning(f"无法解析LLM返回的JSON (第 {attempt + 1}/{MAX_RETRIES} 次尝试)。响应: {raw_content}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue
                return f"Verification Error: Could not parse the LLM's JSON response. Raw response: {raw_content}"
            except Exception as e:
                logger.error(f"验证过程中发生未知错误 (第 {attempt + 1}/{MAX_RETRIES} 次尝试): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2)
                    continue
                return f"Verification Error: An unexpected error occurred: {e}"
        
        # 如果所有重试都失败了
        return "Verification Error: After multiple retries, failed to get a valid response from the LLM."

    def _get_page_info(self, page: Page, index: int):
        content = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": page_info_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(page.img)}"
                    }
                }
            ]
        )
        response = self.llm_flash.invoke([content]).content
        # 处理可能包含```json前缀和后缀的返回数据
        if response.strip().startswith('```json'):
            # 使用正则表达式提取JSON内容
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if json_match:
                response = json_match.group(1)
            else:
                # 如果没有找到结束标记，就去掉开头的```json
                response = response.strip()[7:].strip()
        elif response.strip().startswith('```'):
            # 处理只有```的情况
            json_match = re.search(r'```\s*([\s\S]*?)\s*```', response)
            if json_match:
                response = json_match.group(1)
            else:
                response = response.strip()[3:].strip()
        
        response_json = json.loads(response)

        # 构造新的PageNode对象
        page_node = PageNode(
            index=index,
            page=page,
            page_abstract=response_json.get('page_description', ''),
            widget_list=response_json.get('clickable_elements', []),
            function_list=response_json.get('page_functions', [])
        )
        
        return page_node

    def print_PTG(self):
        for page_node in self.pages:
            print(page_node.describe())
    
    def _get_localized_map_str(self, current_page_index: int) -> str:
        """
        根据新的 PageNode 结构，生成一个局部化的探索地图字符串。
        它只包含当前页面及其直接邻居（出邻居和入邻居）的信息。
        """
        if not self.pages:
            return "No pages explored yet."

        current_page_node = self.pages[current_page_index]
        # 使用集合来自动去重，并首先包含当前页面自身的索引
        neighbor_indices = {current_page_index}

        # 步骤 1: 找出所有“出邻居” (Outgoing Neighbors)
        # 遍历当前页面的所有已探索操作
        for op in current_page_node.explored_operations:
            dest_index = op.get('dest_index', -1)
            if dest_index != -1 and dest_index < len(self.pages):
                neighbor_indices.add(dest_index)

        # 步骤 2: 找出所有“入邻居” (Incoming Neighbors)
        # 遍历地图中的所有页面
        for page_node in self.pages:
            # 遍历每个页面的所有操作
            for op in page_node.explored_operations:
                # 如果某个操作的目标是当前页面，那么这个页面就是“入邻居”
                if op.get('dest_index') == current_page_index:
                    neighbor_indices.add(page_node.index)
                    # 优化：一旦找到，就无需再检查该页面的其他操作
                    break 

        # 步骤 3: 根据收集到的邻居索引，生成最终的描述字符串
        localized_descriptions = []
        # 对索引进行排序以保证输出顺序的稳定性
        for index in sorted(list(neighbor_indices)):
            page_to_describe = self.pages[index]
            # 调用新的 describe 方法，该方法不再需要任何参数
            description = page_to_describe.describe()
            
            # 为了保持可读性，我们手动为当前页面的描述添加一个特殊标记
            if index == current_page_index:
                marked_description = f"(*** THIS IS THE CURRENT PAGE ***)\n{description}"
                localized_descriptions.append(marked_description)
            else:
                localized_descriptions.append(description)
                    
        return "\n---\n".join(localized_descriptions)

    def _is_page_exist(self, page: Page) -> int:
        """
        判断当前页面是否已存在于页面列表中。
        首先判断Activity是否为新，若是则为新页面；否则，与同Activity的页面进行LLM视觉对比。
        """
        # 初始情况：如果还没有任何页面，则当前页面是第一个
        if not self.pages:
            self.explored_abilities.append(page.info.ability)
            return 0
        
        if page.info is None:
            # self.explored_abilities.append(self.pages[self.last_page_index].page.info.ability + "--PopupWindow")
            return len(self.pages)
        elif page.info.ability not in self.explored_abilities:
            self.explored_abilities.append(page.info.ability)
            return len(self.pages)

        # 快速筛选：根据 ability 找到所有可能的候选页面索引
        found_indices = [
            p.index for p in self.pages
            if p.page and p.page.info and page and page.info and p.page.info.ability == page.info.ability
        ]

        for index in found_indices:
            candidate_node = self.pages[index]
            # 检查图像感知哈希
            if page.img_hash and candidate_node.page.img_hash:
                distance = page.img_hash - candidate_node.page.img_hash
                if distance <= 5: 
                    logger.info(f"图像感知哈希与 Page {index} 高度相似 (距离: {distance})。确认为同一页面。")
                    return index

        # 准备Prompt和图像内容
        prompt_text = page_exist_prompt
        content = [{"type": "text", "text": prompt_text}]

        content.append({"type": "text", "text": "--- \n## 1. New Screenshot"})
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{encode_image(page.img)}"}
        })

        content.append({"type": "text", "text": "\n## 2. Known Candidate Pages"})
        for index in found_indices:
            candidate_node = self.pages[index]
            content.append({"type": "text", "text": f"--- \n### Candidate Index: {index}"})
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{encode_image(candidate_node.page.img)}"}
            })
        # 调用LLM进行视觉判断
        try:
            message = HumanMessage(content=content)
            response_text = self.llm_flash.invoke([message]).content
            
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if json_match:
                response_text = json_match.group(1)
            
            response_json = json.loads(response_text)

            if response_json.get("is_new", True):
                return len(self.pages)
            else:
                existing_index = response_json.get("existing_index", -1)
                if existing_index in found_indices:
                    return existing_index
                else:
                    return len(self.pages)

        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            logger.error(f"处理LLM多图对比响应时出错: {e}。将默认视为新页面。")
            return len(self.pages)

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
