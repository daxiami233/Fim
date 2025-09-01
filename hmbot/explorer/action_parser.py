import re
from typing import Dict, Tuple, Optional, Any
from loguru import logger


class ActionParser:
    def __init__(self):
        self.supported_actions = {
            'click', 'long_click', 'type', 'scroll', 'press_back', 'finished',
        }
    
    def parse_action_output(self, output_text, image_width, image_height):
        # 1. Extract the Thought part (from "Thought:" to "Description:")
        thought_match = re.search(r'Thought:(.*?)\nDescription:', output_text, re.DOTALL)
        thought = thought_match.group(1).strip() if thought_match else ""
        
        # 2. Extract the Description part (from "Description:" to "Status:")
        description_match = re.search(r'Description:(.*?)\nStatus:', output_text, re.DOTALL)
        description = description_match.group(1).strip() if description_match else ""
        
        # 3. Extract the Status part (from "Status:" to "Action:")
        status_match = re.search(r'Status:(.*?)\nAction:', output_text, re.DOTALL)
        status = status_match.group(1).strip() if status_match else "success"
        
        # 4. Extract the Action part
        action_match = re.search(r'Action:(.*?)(?:\n|$)', output_text, re.DOTALL)
        action_text = action_match.group(1).strip() if action_match else ""
        
        # 5. Initialize the result dictionary with the new fields
        result = {
            "thought": thought,
            "description": description,
            "status": status,
            "action": "",
            "point": None,
            "content": None,
            "direction": None,
        }
        
        # 6. Parse the specific action and update the result (this logic remains the same)
        parsed_action = self._parse_specific_action(action_text)
        if parsed_action.get('point') is not None:
            parsed_action['point'] = (
                int(parsed_action['point'][0] / 1000 * image_width), 
                int(parsed_action['point'][1] / 1000 * image_height)
            )
        result.update(parsed_action)        
        return result
            
    
    def _parse_specific_action(self, action_text):
        result = {
            "action": "",
            "point": None,
            "content": None,
            "direction": None
        }
        
        # 提取动作类型
        action_type_match = re.match(r'(\w+)\s*\(', action_text)
        if not action_type_match:
            logger.warning(f"无法识别动作类型: {action_text}")
            return result
        
        action_type = action_type_match.group(1)
        result["action"] = action_type
        
        if action_type not in self.supported_actions:
            logger.warning(f"不支持的动作类型: {action_type}")
            return result
        
        # 根据动作类型解析参数
        if action_type == "click":
            result.update(self._parse_click_action(action_text))
        elif action_type == "long_click":
            result.update(self._parse_long_click_action(action_text))
        elif action_type == "type":
            result.update(self._parse_type_action(action_text))
        elif action_type == "scroll":
            result.update(self._parse_scroll_action(action_text))
        elif action_type == "press_back":
            # press_back没有额外参数
            pass
        elif action_type == "finished":
            result.update(self._parse_finished_action(action_text))
        
        return result
    
    def _parse_click_action(self, action_text: str) -> Dict[str, Any]:
        """
        解析点击动作
        格式: click(point='<point>x1 y1</point>')
        """
        result = {}
        
        # 提取point参数
        point_match = re.search(r'point=[\'"](.*?)[\'"]', action_text)
        if point_match:
            point_str = point_match.group(1)
            coordinates = self._extract_coordinates_from_point(point_str)
            if coordinates:
                result["point"] = coordinates
        
        return result

    def _parse_long_click_action(self, action_text: str) -> Dict[str, Any]:
        """
        解析长按动作
        格式: long_click(point='<point>x1 y1</point>')
        """
        result = {}

        # 提取point参数
        point_match = re.search(r'point=[\'"](.*?)[\'"]', action_text)
        if point_match:
            point_str = point_match.group(1)
            coordinates = self._extract_coordinates_from_point(point_str)
            if coordinates:
                result["point"] = coordinates

        return result

    def _parse_type_action(self, action_text: str) -> Dict[str, Any]:
        """
        解析输入动作
        格式: type(content='xxx')
        """
        result = {}
        
        # 提取content参数
        content_match = re.search(r'content=[\'"](.*?)[\'"]', action_text)
        if content_match:
            content = content_match.group(1)
            # 处理转义字符
            content = content.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
            result["content"] = content
        
        return result
    
    def _parse_scroll_action(self, action_text: str) -> Dict[str, Any]:
        """
        解析滚动动作
        格式: scroll(point='<point>x1 y1</point>', direction='down or up or right or left')
        """
        result = {}
        
        # 提取point参数
        point_match = re.search(r'point=[\'"](.*?)[\'"]', action_text)
        if point_match:
            point_str = point_match.group(1)
            coordinates = self._extract_coordinates_from_point(point_str)
            if coordinates:
                result["point"] = coordinates
        
        # 提取direction参数
        direction_match = re.search(r'direction=[\'"](.*?)[\'"]', action_text)
        if direction_match:
            direction = direction_match.group(1).strip()
            if direction in ['down', 'up', 'right', 'left']:
                result["direction"] = direction
        
        return result
    
    def _parse_finished_action(self, action_text: str) -> Dict[str, Any]:
        """
        解析完成动作
        格式: finished(content='xxx')
        """
        result = {}
        
        # 提取content参数
        content_match = re.search(r'content=[\'"](.*?)[\'"]', action_text)
        if content_match:
            content = content_match.group(1)
            # 处理转义字符
            content = content.replace('\\n', '\n').replace('\\"', '"').replace("\\'", "'")
            result["content"] = content
        
        return result
    
    def _extract_coordinates_from_point(self, point_str: str) -> Optional[Tuple[int, int]]:
        """
        从point字符串中提取坐标
        格式: '<point>x1 y1</point>' 或 'x1 y1'
        """
        try:
            # 尝试从<point>标签中提取
            point_tag_match = re.search(r'<point>(.*?)</point>', point_str)
            if point_tag_match:
                coords_str = point_tag_match.group(1).strip()
            else:
                coords_str = point_str.strip()
            
            # 提取数字
            coords = re.findall(r'\d+', coords_str)
            if len(coords) >= 2:
                return (int(coords[0]), int(coords[1]))
            
            return None
            
        except Exception as e:
            logger.error(f"提取坐标时出错: {e}")
            return None

# 全局解析器实例
action_parser = ActionParser()
