# -*- coding: utf-8 -*-
"""
API测试签名工具模块
实现与服务端一致的签名算法
"""

import hmac
import hashlib
import base64
from typing import Dict


def generate_signature(timestamp: str, app_secret: str) -> str:
    """
    生成HmacSHA256签名并Base64编码

    Args:
        timestamp: 毫秒级时间戳字符串
        app_secret: 应用密钥

    Returns:
        Base64编码的签名字符串
    """
    # 构造签名字符串: timestamp + "\n" + appSecret
    sign_string = f"{timestamp}\n{app_secret}"

    # 使用HmacSHA256加密
    signature = hmac.new(
        app_secret.encode('utf-8'),
        sign_string.encode('utf-8'),
        hashlib.sha256
    ).digest()

    # Base64编码
    sign = base64.b64encode(signature).decode('utf-8')

    return sign


def get_auth_headers(app_key: str, app_secret: str) -> Dict[str, str]:
    """
    获取验签所需的请求头

    Args:
        app_key: 应用密钥ID
        app_secret: 应用密钥

    Returns:
        包含appKey、timestamp、sign的字典
    """
    import time
    timestamp = str(int(time.time() * 1000))
    sign = generate_signature(timestamp, app_secret)

    return {
        'appKey': app_key,
        'timestamp': timestamp,
        'sign': sign
    }
