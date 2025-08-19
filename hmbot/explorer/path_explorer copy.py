from hmbot.device.device import Device
from hmbot.model.page import Page
from hmbot.explorer.llm import llm, phone_llm
from langchain_core.messages import HumanMessage, AIMessage
import json
import re
from hmbot.utils.cv import encode_image
from hmbot.explorer.prompt import event_llm_prompt
from hmbot.explorer.action_parser import action_parser
from loguru import logger
from hmbot.model.event import *
import time


class PageNode:
    """
    Represents a single page in the application map.
    It tracks the page's description, its available widgets, and its explored actions.
    """
    def __init__(self, index: int, page: Page = None, page_description: str = "", widget_list: list = None):
        self.index = index
        self.page = page
        self.page_description = page_description
        # All widgets on the page are initially available for interaction
        self.available_widgets = list(widget_list) if widget_list else []
        # No actions have been explored from this page yet
        self.explored_actions = []

    def add_explored_action(self, action_info: dict, to_page_index: int, is_effective: bool, reason: str = ""):
        """Moves a widget from the available list to an explored action record."""
        try:
            widget_index_to_move = int(action_info['index'])
            widget_to_move = None
            
            # Find and remove the widget from the available list
            remaining_widgets = []
            for widget in self.available_widgets:
                if int(widget['index']) == widget_index_to_move:
                    widget_to_move = widget
                else:
                    remaining_widgets.append(widget)
            
            if widget_to_move:
                self.available_widgets = remaining_widgets
                # Add the action taken on the widget to the explored list
                self.explored_actions.append({
                    'action_description': action_info['description'],
                    'widget': widget_to_move,
                    'to_page_index': to_page_index,
                    'is_effective': is_effective,
                    'reason': reason
                })
                log_msg = f"Moved widget {widget_index_to_move} to explored actions for page {self.index}."
                log_msg += f" Effective: {is_effective}."
                if not is_effective:
                    log_msg += f" Reason: {reason}"
                logger.info(log_msg)
            else:
                logger.warning(f"Widget with index {widget_index_to_move} not found in available_widgets for page {self.index}.")

        except (ValueError, TypeError) as e:
            logger.warning(f"Could not move widget to explored action on page {self.index}: {e}")

    def to_prompt_string(self) -> str:
        """Formats the node's data into a string for the LLM prompt."""
        prompt_str = f"Page {self.index} (Description: \"{self.page_description}\")\n"
        
        # Format explored actions
        prompt_str += "  - Explored Actions:\n"
        if not self.explored_actions:
            prompt_str += "    (No actions explored from this page yet)\n"
        else:
            for explored in self.explored_actions:
                action_desc = explored['action_description']
                widget_idx = explored['widget']['index']
                
                if explored['is_effective']:
                    to_page = explored['to_page_index']
                    prompt_str += f"    - [Action on Widget {widget_idx}: '{action_desc}'] -> Page {to_page}\n"
                else:
                    reason = explored.get('reason', 'No change detected')
                    prompt_str += f"    - [Action on Widget {widget_idx}: '{action_desc}'] -> (Ineffective: {reason})\n"

        # Format available widgets
        prompt_str += "  - Available Widgets:\n"
        if not self.available_widgets:
            prompt_str += "    (All widgets on this page have been interacted with)\n"
        else:
            for widget in self.available_widgets:
                widget_desc = widget['description']
                widget_idx = widget['index']
                prompt_str += f"    - Widget {widget_idx}: '{widget_desc}'\n"
        
        return prompt_str
 

class PathExplorer:
    def __init__(self, device: Device):
        self.device = device
        self.llm = llm
        self.phone_llm = phone_llm
        self.curr_page_index = 0
        # 页面列表
        self.pages = []
        self.current_path = []
        self.summarized_strategies = []

    def get_page_info(self, page: Page, index: int):
        prompt = f'''你是一位精通UI分析的专家。我会上传一张安卓App的界面截图，请严格按照以下规则分析这张图片：

1. **简短界面描述**：对整个页面进行简短描述，包括页面的主要功能、整体布局结构、页面所属的应用类型或功能模块，以及页面的独特特征（用于区分其他界面）。
2. **控件识别**：找出图片中所有可以被用户点击的控件，如按钮、图标、输入框、整行的列表项目等。
3. **忽略顶部**：完全忽略设备最顶部的系统状态栏（即显示时间、信号、电量的部分）。
4. **整合信息**：对于一个独立的、可点击的列表项（list item），请将其中的所有文字信息（如标题、摘要、价格、日期等）合并到同一个description中，不要将它们拆分成多个条目。对于非列表项的独立控件，如单个按钮、图标或输入框，则按其自身的功能进行描述，不与其他信息整合。

请将结果严格按照以下JSON格式返回：
{{
  "page_description": "对整个页面的详细描述，包含独特特征用于区分其他界面",
  "clickable_elements": [
    {{
      "index": 1,
      "description": "对控件的完整、整合后的描述"
    }}
  ]
}}

**示例:**
{{
  "page_description": "这是一个电商应用的商品详情页面，页面顶部有返回按钮和分享按钮，中间展示商品图片和详细信息，底部有加入购物车和立即购买按钮。页面背景为白色，商品图片占据页面上半部分。",
  "clickable_elements": [
    {{
      "index": 1,
      "description": "页面顶部左侧的返回箭头按钮"
    }},
    {{
      "index": 2,
      "description": "页面底部的蓝色'加入购物车'按钮"
    }}
  ]
}}

现在，请分析我上传的截图，并返回有效的JSON格式数据。'''
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
        response = self.llm.invoke([content]).content
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
            page_description=response_json.get('page_description', ''),
            widget_list=response_json.get('clickable_elements', [])
        )
        
        return page_node
    
    def get_next_operation(self, target: str, verification_feedback: dict = None):
        # 构建所有页面的详细信息，包括已探索和未探索的动作
        app_map_str = ""
        for page_node in self.pages:
            app_map_str += page_node.to_prompt_string() + "\n"

        # 获取当前页面
        current_page = self.pages[self.curr_page_index] if self.pages else None
        
        # 构建上一步操作的反馈信息
        feedback_section = ""
        if verification_feedback:
            feedback_section = f'''
## 上一步操作反馈
- **操作有效性**: {verification_feedback.get('operation_effective')} (原因: {verification_feedback.get('effectiveness_reason')})
'''

        # 构建已总结的策略信息
        strategies_section = ""
        if self.summarized_strategies:
            strategies_section = "## 已总结的成功策略\n"
            for i, strategy in enumerate(self.summarized_strategies):
                strategies_section += f"{i+1}. {strategy}\n"
        
        prompt = f'''你是一个专业的移动UI自动化测试专家，你的核心任务是根据探索目标，设计并执行一系列操作，以寻找所有可能到达目标的路径。

## 探索目标
你的核心目标是找到一条路径，以达到以下目标状态：
**{target}**
{feedback_section}
{strategies_section}
## App探索地图
{app_map_str}

## 当前状态
- **你当前位于**: Page {self.curr_page_index}

## 决策原则 (请严格遵守!)
1.  **键盘优先**: 如果当前界面中出现了键盘，请忽略其他所有规则，立即选择一个输入框，并将操作描述设为“文本框里输入”。
2.  **理解功能路径**: “已总结的成功策略”描述的是**功能性**路径，而非具体控件的路径。例如，策略“我是通过点击联系人列表中的一个用户头像进入其主页的”意味着“点击任意用户头像”这条**功能路径**已经被探索过了。
    *   你的首要任务是找到一条在**功能上**与“已总结的成功策略”和“已探索动作”**完全不同**的新路径来达成“{target}”。

3.  **杜绝功能重复**:
    *   **识别功能等价操作**: 在选择“Available Widgets”中的控件时，要先判断这个操作在功能上是否与已成功的策略重复。如果一个策略是“点击列表项进入详情页”，那么在当前页面点击任意一个相似的列表项都属于**功能重复**，应当避免。
    *   **禁止直接返回**: 避免选择一个会让你立即返回上一个页面的动作（例如，从Page 1到Page 2后，又在Page 2点击“返回”回到Page 1），除非当前页面没有其他任何可用的、有意义的控件。

4.  **优先目标**:
    *   在遵守上述规则的前提下，从当前页面的“Available Widgets”列表中，选择一个与探索目标“**{target}**”最相关的操作。

5.  **探索未知**:
    *   如果没有直接相关的控件，就从“Available Widgets”中选择一个最有可能带你进入**新界面**或**未探索功能区**的控件。

6.  **严格遵守列表**:
    *   你的选择**必须**严格来自当前页面的“Available Widgets”列表。

请严格按照以下JSON格式返回你的选择，不要包含任何额外的解释：

```json
{{
  "think": "在这里简要描述你的思考过程（50字以内），说明为什么选择这个操作，并确认它在功能上不是重复的。",
  "index": "选中的控件索引",
  "description": "对操作的描述，必须以动词开头，例如'点击返回按钮'、'输入用户名'或'滑动列表'。"
}}
```

**返回示例:**
```json
{{
  "think": "之前的策略是通过点击头像进入主页，现在我选择点击'设置'按钮，这是一个功能上全新的路径。",
  "index": "5",
  "description": "点击'设置'按钮"
}}
```
'''
        content = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encode_image(current_page.page.img)}"
                    }
                }
            ]
        )
        
        max_retries = 3
        for i in range(max_retries):
            try:
                response = self.llm.invoke([content]).content
                logger.debug(f"LLM response: {response}")
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
                return response_json
            except Exception as e:
                logger.error(f"Error parsing LLM response on attempt {i+1}/{max_retries}: {e}")
                if i < max_retries - 1:
                    logger.info("Retrying...")
                else:
                    logger.error("Failed to get a valid response after multiple retries.")
                    return None
    
    def execute_operation(self, page_node: PageNode, operation_description: str):
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
            response = self.phone_llm.invoke([message])
            logger.debug(f"LLM response: {response.text()}")

            parsed_output = action_parser.parse_action_output(response.text(), page.img.shape[1], page.img.shape[0])
            retry_count += 1
        
        # 执行解析出的操作
        if parsed_output and parsed_output.get("action"):
            new_event = None
            if parsed_output["action"] == "click" and parsed_output["point"]:
                center_pos = parsed_output["point"]
                logger.info(f"Click coordinates: {center_pos}")
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

            if new_event:
                new_event.execute()
                time.sleep(3)
            return f"操作成功完成：{parsed_output['action']}"
        else:
            logger.error("Failed to get a valid action after multiple retries.")
            return "操作失败：无法解析LLM响应"

    def is_page_exist(self, page: Page):
        """
        判断当前页面是否已存在于页面列表中
        如果是新页面，返回列表长度作为新页面的index
        如果是已存在的页面，返回已存在页面的index
        """
        # Base case: If no pages have been discovered yet, it's definitely a new page.
        if not self.pages:
            return 0

        # Build the description of existing pages for the prompt
        pages_description = ""
        for p in self.pages:
            pages_description += f"Page {p.index}: {p.page_description}\n"

        prompt = f'''你是一位精通UI对比分析的专家。你的任务是**极其严格地**判断我上传的新截图是否与任何一个已知的页面完全相同。

## 已知页面信息
以下是所有已经发现的页面的详细描述：
{pages_description}

## 严格判断标准
**你必须采用极其严格的标准来判断两个页面是否相同。只有当新截图与已知页面在以下所有方面都完全匹配时，才能判断为已存在页面：**

### 必须完全匹配的要素：
1. **主要UI布局**：页面的整体布局结构必须完全一致
2. **核心功能区域**：主要功能模块的位置和内容必须完全相同
3. **导航元素**：顶部导航栏、底部导航栏、侧边栏等必须完全一致
4. **按钮和控件**：所有主要按钮、输入框、图标的位置和样式必须相同
5. **文本内容**：主要的标题、标签、菜单项等文字内容必须基本一致
6. **页面状态**：弹窗、对话框、键盘等状态必须完全相同

### 判断为新页面的情况（任一条件满足即为新页面）：
- **软键盘状态变化**：软键盘的出现或消失
- **弹窗或对话框**：任何弹窗、对话框、提示框的出现或消失
- **页面内容更新**：列表内容、详情信息、搜索结果等发生变化
- **导航状态变化**：页面标题、导航栏内容发生变化
- **功能模块差异**：页面功能区域有任何明显差异
- **布局结构不同**：页面整体布局结构有任何差异
- **加载状态**：页面处于加载、刷新等不同状态
- **表单状态**：表单填写内容、选中状态等发生变化

## 判断原则
**宁可误判为新页面，也不要将不同页面误判为相同页面。** 当你对两个页面是否相同有任何疑虑时，请判断为新页面。

请仔细观察新截图的每一个细节，与已知页面描述进行逐一对比。只有当你100%确信新截图与某个已知页面完全相同时，才能判断为已存在页面。

请严格遵循以下JSON格式返回你的判断结果，不要包含任何理由或额外的解释：
{{
  "is_new": <true_or_false>,
  "existing_index": <如果is_new为false，请提供匹配的页面索引；如果为true，则为-1>
}}

**示例 1 (判断为已存在页面 - 仅在100%确信相同时):**
{{
  "is_new": false,
  "existing_index": 1
}}

**示例 2 (判断为新页面 - 任何细微差异都应判断为新页面):**
{{
  "is_new": true,
  "existing_index": -1
}}

现在，请**极其严格地**分析我上传的截图，并只返回有效的JSON格式数据。'''

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

        try:
            response_text = self.llm.invoke([content]).content
            
            # Clean up the response, removing markdown code blocks if present
            if response_text.strip().startswith('```json'):
                json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    response_text = json_match.group(1)
                else:
                    response_text = response_text.strip()[7:].strip()
            elif response_text.strip().startswith('```'):
                json_match = re.search(r'```\s*([\s\S]*?)\s*```', response_text)
                if json_match:
                    response_text = json_match.group(1)
                else:
                    response_text = response_text.strip()[3:].strip()
            
            response_json = json.loads(response_text)

            if response_json.get("is_new"):
                # The page is new, return the next available index.
                return len(self.pages)
            else:
                # The page exists, return its index.
                existing_index = response_json.get("existing_index", -1)
                if 0 <= existing_index < len(self.pages):
                    return existing_index
                else:
                    # If the LLM gives an invalid index, treat it as a new page as a fallback.
                    logger.warning(f"LLM returned an invalid existing_index: {existing_index}. Treating as a new page.")
                    return len(self.pages)

        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error processing LLM response for page existence check: {e}. Defaulting to new page.")
            # In case of any error, assume it's a new page to avoid getting stuck.
            return len(self.pages)

    def summarize_path(self, path: list, target: str):
        path_description = ""
        # The last step is 'Target Reached', handle it separately.
        for i, step in enumerate(path[:-1]):
            path_description += f"- **步骤 {i+1}**: 在页面 \"{step['page_description']}\" (索引 {step['page_index']}), **操作**: \"{step['action']}\".\n"
        
        last_step = path[-1]
        path_description += f"- **最后**: 成功到达目标页面 \"{last_step['page_description']}\" (索引 {last_step['page_index']}).\n"

        prompt = f'''你是一位专业的UI自动化测试路径总结专家。你的任务是分析一个成功的操作序列，并以第一人称的口吻，简洁地总结出是如何达成目标的。

## 探索目标
**{target}**

## 成功路径详情
{path_description}

## 任务
请结合“探索目标”和“成功路径详情”，用**一句话**总结出你是如何完成探索目标的。总结需要简洁、清晰，突出关键的页面和操作。

**总结要求:**
- 必须以“通过...”或类似的句式开头。
- 聚焦于关键的1-2个步骤。

**正例 (请这样总结):**
- "通过在微信的通讯录中点击某个人，然后进入他的主页后达到了目标。"
- "通过在设置页面点击‘账号管理’，然后选择‘退出登录’来达成目标的。"
'''
        summary = self.llm.invoke([HumanMessage(content=prompt)]).content
        return summary.strip()

    def verify_last_operation(self, page_node_before: PageNode, page_node_after: PageNode, operation: dict, target: str):
        """        
        验证上一次操作是否成功执行，并判断操作后的界面是否已达到目标场景。
        """
        prompt = f'''你是一位精通UI自动化测试分析的专家。你的任务是结合多方面信息，综合判断一次操作的结果。

## 综合信息
1.  **探索目标**: `{target}`
2.  **执行的操作**: `{operation['description']}`
3.  **操作前截图**: 这是执行操作前的界面。
4.  **操作后截图**: 这是执行操作后的界面。

## 你的任务
请基于以上所有信息，完成两项独立的判断：

1.  **判断操作有效性**: 比较“操作前”和“操作后”的截图。判断执行的操作是否对UI产生了**明显的变化**（如页面跳转、弹窗、内容刷新等）。忽略时间、电量等微小变化。
2.  **判断目标是否达成**: 分析“操作后”的截图。判断该截图所展示的界面是否已经**完全符合**“探索目标”中描述的场景。

请严格按照以下JSON格式返回你的综合判断结果，不要包含任何额外的解释：
```json
{{
  "operation_effective": <true_or_false>,
  "effectiveness_reason": "简要说明你判断操作是否有效的依据。例如：'点击按钮后，页面跳转到了新的登录界面' 或 '点击后，UI元素没有任何改变'。",
  "target_reached": <true_or_false>,
  "target_reason": "简要说明你判断目标是否达成的依据。例如：'截图显示了登录成功的欢迎页面，符合目标' 或 '截图依然停留在登录页面，未达到目标'。"
}}
```

现在，请分析我上传的截图，并返回有效的JSON格式数据。'''

        # 编码操作前后的图像
        base64_image_before = encode_image(page_node_before.page.img)
        base64_image_after = encode_image(page_node_after.page.img)

        content = HumanMessage(
            content=[
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image_before}"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{base64_image_after}"},
                },
            ]
        )

        max_retries = 3
        for i in range(max_retries):
            try:
                response_text = self.llm.invoke([content]).content
                
                # 清理响应，移除可能的Markdown代码块
                if response_text.strip().startswith('```json'):
                    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
                    if json_match:
                        response_text = json_match.group(1)
                    else:
                        response_text = response_text.strip()[7:].strip()
                elif response_text.strip().startswith('```'):
                    json_match = re.search(r'```\s*([\s\S]*?)\s*```', response_text)
                    if json_match:
                        response_text = json_match.group(1)
                    else:
                        response_text = response_text.strip()[3:].strip()

                response_json = json.loads(response_text)
                # logger.info(f"操作有效性: {response_json.get('operation_effective')} - {response_json.get('effectiveness_reason')}")
                # logger.info(f"目标达成检查: {response_json.get('target_reached')} - {response_json.get('target_reason')}")
                return response_json

            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"解析操作验证响应时出错 (尝试 {i+1}/{max_retries}): {e}")
                if i < max_retries - 1:
                    logger.info("正在重试...")
                else:
                    logger.error("多次重试后无法获取有效响应。")
                    return {"operation_effective": False, "target_reached": False, "reason": "无法解析模型响应"}
        return {"operation_effective": False, "target_reached": False, "reason": "多次重试后操作验证失败"}
        
    def explore_path(self, target: str, max_steps: int = 20):
        """
        通过循环与界面交互来探索并复现一个特定的path。
        """
        last_verification_feedback = None # 初始化上一步的反馈

        self.current_path = [] # 重置路径
        # --- 步骤 1: 循环前初始化 ---
        logger.info("=========== 探索开始，正在分析初始页面... ==========")
        initial_page = self.device.dump_page(refresh=True)
        initial_page_index = self.is_page_exist(initial_page)

        if initial_page_index == len(self.pages):
            current_page_node = self.get_page_info(initial_page, initial_page_index)
            self.pages.append(current_page_node)
            logger.info(f"探索始于新页面 (索引 {initial_page_index}): {current_page_node.page_description}")
        else:
            current_page_node = self.pages[initial_page_index]
            logger.info(f"探索始于已知页面 (索引 {initial_page_index}): {current_page_node.page_description}")
        
        self.curr_page_index = current_page_node.index

        # --- 步骤 2: 主探索循环 ---
        for step in range(max_steps):
            logger.info(f"=========== 探索步骤 {step + 1}/{max_steps} ==========")
            logger.info(f"当前位于页面 (索引 {self.curr_page_index}): {current_page_node.page_description}")

            # --- 2a: 决策 (传入上一步的反馈) ---
            action_info = self.get_next_operation(target, last_verification_feedback)
            
            if not action_info or 'index' not in action_info or 'description' not in action_info:
                logger.error("无法获取有效操作，探索终止。")
                break

            logger.info(f"下一步操作: {action_info['description']}")

            page_node_before_action = current_page_node

            # --- 2b: 执行操作 ---
            self.execute_operation(current_page_node, action_info['description'])
            
            # --- 2c: 验证操作有效性 ---
            page_after_action = self.device.dump_page(refresh=True)
            page_node_after_temp = PageNode(index=-1, page=page_after_action)
            
            verification = self.verify_last_operation(page_node_before_action, page_node_after_temp, action_info, target)
            last_verification_feedback = verification

            is_effective = verification.get('operation_effective', False)
            effectiveness_reason = verification.get('effectiveness_reason', 'No reason provided.')

            # --- 2d: 分析新页面状态 ---
            if is_effective:
                # 记录当前步骤
                self.current_path.append({
                    'page_index': self.curr_page_index,
                    'page_description': page_node_before_action.page_description,
                    'action': action_info['description']
                })
                logger.info("操作有效，正在分析新页面状态...")
                new_page_index = self.is_page_exist(page_after_action)

                if new_page_index == len(self.pages):
                    new_page_node = self.get_page_info(page_after_action, new_page_index)
                    self.pages.append(new_page_node)
                    logger.info(f"执行操作后到达新页面 (索引 {new_page_index})")
                else:
                    new_page_node = self.pages[new_page_index]
                    logger.info(f"执行操作后返回到已存在页面 (索引 {new_page_index})。")
                
                # 更新地图和状态
                page_node_before_action.add_explored_action(action_info, new_page_node.index, is_effective=True)
                current_page_node = new_page_node
                self.curr_page_index = current_page_node.index
            else:
                logger.warning(f"操作 '{action_info['description']}' 被判定为无效，原因: {effectiveness_reason}")
                # 记录无效操作，但停留在当前页面
                page_node_before_action.add_explored_action(
                    action_info, 
                    to_page_index=page_node_before_action.index, 
                    is_effective=False, 
                    reason=effectiveness_reason
                )
                continue
                # current_page_node 和 self.curr_page_index 保持不变

            # --- 2e: 检查是否到达目标 ---
            if verification.get('target_reached'):
                logger.success(f"成功找到一条到达目标的路径！原因: {verification.get('target_reason')}")
                
                # 将最后一个页面添加到路径中
                self.current_path.append({
                    'page_index': self.curr_page_index,
                    'page_description': current_page_node.page_description,
                    'action': 'Target Reached'
                })

                # 总结路径并存储
                summary = self.summarize_path(self.current_path, target)
                self.summarized_strategies.append(summary)
                logger.success(f"成功路径策略已总结: {summary}")

                logger.info("将继续探索其他可能的路径...")
                self.current_path = [] # 重置路径以便寻找新路径

        logger.info("=========== 探索结束 ===========")
        final_map_str = ""
        for page_node in self.pages:
            final_map_str += page_node.to_prompt_string() + "\n"
        logger.info(f"=========== 最终探索地图 ===========\n{final_map_str}")

    def execute_operations_continuous_dialogue(self, operation_description: str):
        page = self.device.dump_page(refresh=True)
        base64_image = encode_image(page.img)

        conversation_history = [
            HumanMessage(content=[
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
        ]
        
        parsed_output = None
        
        while True:
            response = self.phone_llm.invoke(conversation_history)
            logger.debug(f"LLM response: {response.text()}")
            
            conversation_history.append(AIMessage(content=response.text()))
            
            # 解析LLM的响应以获取操作建议
            try:
                # 注意：这里的 page.img 仍然是上一步操作前或初始的截图，用于坐标转换
                parsed_output = action_parser.parse_action_output(response.text(), page.img.shape[1], page.img.shape[0])
            except Exception as e:
                logger.error(f"Failed to parse LLM response: {response.text()}, Error: {e}")
                return "操作失败：无法解析LLM响应"

            # 检查解析出的操作是否为 "finished"
            if parsed_output and parsed_output.get("action") == "finished":
                logger.info("Task finished as per LLM instruction.")
                return "操作成功完成：任务已结束"
            
            # 执行解析出的操作
            if parsed_output and parsed_output.get("action") == "click" and parsed_output.get("point"):
                center_pos = parsed_output["point"]
                logger.info(f"Executing click at coordinates: {center_pos}")
                self.device.click(center_pos[0], center_pos[1])
                time.sleep(3) # 等待界面更新
                
                logger.info("Capturing screen after operation.")
                page = self.device.dump_page(refresh=True) # page对象在这里被更新
                base64_image = encode_image(page.img)
                
                # 5. 将新截图作为新的用户消息添加到对话历史中，为下一次决策做准备
                conversation_history.append(
                    HumanMessage(content=[
                        {
                           "type": "text",
                           "text": "操作已执行。这是当前界面。下一步做什么？"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                            }
                        }
                    ])
                )
            else:
                logger.error(f"Failed to get a valid action from LLM. LLM response was: {response.text()}")
                return "操作失败：无法解析LLM响应或LLM未给出有效操作"

    