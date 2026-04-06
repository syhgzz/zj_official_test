# -*- coding: utf-8 -*-
"""
API客户端封装模块
提供统一的API请求接口
"""
import requests
import json
from typing import Dict, Any, Optional
from .signature import get_auth_headers


class APIClient:
    """API客户端类"""

    def __init__(self, host: str, app_key: str, app_secret: str, timeout: int = 10):
        """
        初始化API客户端

        Args:
            host: API服务器地址
            app_key: 应用密钥ID
            app_secret: 应用密钥
            timeout: 请求超时时间(秒)
        """
        self.host = host
        self.app_key = app_key
        self.app_secret = app_secret
        self.timeout = timeout
        self.session = requests.Session()

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        发送带签名的API请求

        Args:
            method: HTTP方法(GET/POST/PUT/DELETE)
            path: API路径
            params: URL查询参数
            data: 请求体数据

        Returns:
            响应数据字典,失败返回None
        """
        url = f"{self.host}{path}"

        # 生成签名请求头
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            **get_auth_headers(self.app_key, self.app_secret)
        }

        try:
            # 发送请求
            if method.upper() == 'GET':
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                )
            elif method.upper() == 'POST':
                response = self.session.post(
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=self.timeout
                )
            elif method.upper() == 'PUT':
                response = self.session.put(
                    url,
                    headers=headers,
                    params=params,
                    json=data,
                    timeout=self.timeout
                )
            elif method.upper() == 'DELETE':
                response = self.session.delete(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"不支持的HTTP方法: {method}")

            # 检查HTTP状态码
            if response.status_code == 200:
                return response.json()
            else:
                print(f"请求失败: HTTP {response.status_code}")
                print(f"响应内容: {response.text}")
                return None

        except requests.exceptions.Timeout:
            print(f"请求超时: {url}")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"连接失败: {e}")
            return None
        except Exception as e:
            print(f"请求异常: {e}")
            return None
