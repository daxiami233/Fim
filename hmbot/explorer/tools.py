from hmbot.device.device import Device
from hmbot.utils.proto import OperatingSystem
from hmbot.utils.cv import encode_image
from hmbot.explorer.prompt import event_llm_prompt
from langchain_core.messages import HumanMessage
from hmbot.explorer.action_parser import action_parser
from loguru import logger
from hmbot.model.event import *
import time
from hmbot.explorer.llm import phone_llm

device = Device("211df697", OperatingSystem.ANDROID)


def get_screenshot() -> str:
    """
    捕获并返回当前移动设备屏幕的完整截图。

    此工具是代理唯一的“眼睛”，为所有后续的思考和行动提供关键的视觉上下文。
    在决定下一步操作（如点击、输入）之前，必须先调用此工具来观察和分析屏幕的当前状态。
    这构成了“观察-思考-行动”(Observe-Think-Act)循环中至关重要的第一步。

    Returns:
        str: 当前屏幕截图的PNG格式图片的Base64编码字符串。此字符串可直接用于多模态模型的视觉分析。
    """
    page = device.dump_page(refresh=True)
    return page.img


def execute_command(command: str) -> str:
    """
    根据一句高级、自然的语言指令，在移动设备上自主执行一个UI操作。

    这是一个高级、封装完善的工具。当你需要与手机屏幕进行交互（如点击、输入、滑动等），
    但不知道具体坐标或元素细节时，应该使用此工具。它内部封装了一个专门的视觉-语言
    子代理（GUI Agent），能够理解当前屏幕截图和指令，并自主完成操作。

    **重要工作流程**: 此工具仅返回操作的成功/失败状态。如果操作成功，你【必须】在下一步紧接着调用 `get_screenshot` 工具来观察屏幕发生的变化，以便进行后续决策。

    **使用示例**:
    - "点击标有'登录'的按钮"
    - "在页面顶部的搜索栏中输入'LangChain是什么'"
    - "向上滚动页面"
    - "返回到上一页"

    Args:
        command (str): 一个清晰、描述性的自然语言指令，说明你希望在当前屏幕上完成什么操作。

    Returns:
        str: 一个描述操作执行结果的状态字符串。
             - 如果成功: 返回一个确认信息，例如 "操作成功完成。"
             - 如果失败: 返回一个包含具体失败原因的描述，例如 "操作失败，原因：未能在屏幕上找到'登录'按钮。"
    """
    page = device.dump_page(refresh=True)
    base64_image = encode_image(page.img)
    
    # 创建包含图片和文本的消息
    message = HumanMessage(content=[
        {
            "type": "text",
            "text": event_llm_prompt.format(language="Chinese", instruction=command)
        },
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}",
            }
        }
    ])
    response = phone_llm.invoke([message])

    parsed_output = action_parser.parse_action_output(response.text(), page.img.shape[1], page.img.shape[0])
    
    # 执行解析出的操作
    if parsed_output:
        execute_event(parsed_output, page)  # 这里需要传入正确的page对象
        return f"操作成功完成：{parsed_output['action']}"
    else:
        return "操作失败：无法解析LLM响应"


def execute_event(parsed_output, page):
    """
    Execute the phone operation

    Args:
        parsed_output: dict, the parsed output of the action
        device: Device object, the device to execute the operation
        page: Page object, the page to execute the operation

    Returns:
        Event object, the event executed
    """
    new_event = None
    if parsed_output["action"] == "click" and parsed_output["point"]:
        center_pos = parsed_output["point"]
        logger.info(f"Click coordinates: {center_pos}")
        device.click(center_pos[0], center_pos[1])
        
    elif parsed_output["action"] == "type" and parsed_output["content"]:
        nodes = page.vht._root(clickable='true', focused='true', enabled='true', type='android.widget.EditText')
        if nodes:
            new_event = InputEvent(nodes[0], parsed_output["content"])
        else:
            logger.error("No edit text node found")

    elif parsed_output["action"] == "scroll" and parsed_output["point"] and parsed_output["direction"]:
        new_event = SwipeExtEvent(device, page, parsed_output["direction"])

    elif parsed_output["action"] == "press_back":
        new_event = KeyEvent(device, page, "back")

    if new_event:
        new_event.execute()
        time.sleep(3)


