import cv2
import numpy as np
import time
import math
import base64

def read(img_path):
    img = cv2.imread(img_path, cv2.IMREAD_COLOR)
    return img

def write(img_path, img):
    cv2.imwrite(img_path, img)

def _crop(img, bound):
    (x1, y1), (x2, y2) = bound
    return img[y1:y2, x1:x2]

def encode_image(image, quality=85, max_size=(800, 1400)):
    # 获取原始图像尺寸
    height, width = image.shape[:2]
    
    # 计算缩放比例，保持宽高比
    if width > max_size[0] or height > max_size[1]:
        scale_w = max_size[0] / width
        scale_h = max_size[1] / height
        scale = min(scale_w, scale_h)
        
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        # 缩放图像
        resized_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
    else:
        resized_image = image
    
    # 使用JPEG编码并设置质量参数
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
    _, buffer = cv2.imencode('.jpg', resized_image, encode_params)
    encoded_image = base64.b64encode(buffer).decode('utf-8')
    return encoded_image

