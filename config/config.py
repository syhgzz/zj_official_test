# -*- coding: utf-8 -*-
"""
配置加载模块
从INI文件加载API测试配置
"""
import configparser
import os
from typing import Dict, Any


class Config:
    """配置管理类"""

    def __init__(self, config_file: str = None):
        """
        初始化配置

        Args:
            config_file: 配置文件路径,默认为config/api_config.ini
        """
        if config_file is None:
            config_file = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'config',
                'api_config.ini'
            )

        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding='utf-8')

    @property
    def host(self) -> str:
        """获取API服务器地址"""
        return self.config.get('server', 'host')

    @property
    def timeout(self) -> int:
        """获取请求超时时间"""
        return self.config.getint('server', 'timeout', fallback=10)

    @property
    def app_key(self) -> str:
        """获取应用密钥ID"""
        return self.config.get('auth', 'app_key')

    @property
    def app_secret(self) -> str:
        """获取应用密钥"""
        return self.config.get('auth', 'app_secret')

    @property
    def verbose(self) -> bool:
        """是否打印详细响应"""
        return self.config.getboolean('test', 'verbose', fallback=True)

    @property
    def save_response(self) -> bool:
        """是否保存响应到文件"""
        return self.config.getboolean('test', 'save_response', fallback=False)

    @property
    def response_dir(self) -> str:
        """响应数据保存目录"""
        return self.config.get('test', 'response_dir', fallback='responses')


# 全局配置实例
config = Config()
