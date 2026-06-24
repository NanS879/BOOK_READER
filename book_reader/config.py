import json
import os
import sys

DEFAULT_CONFIG = {
    'page_size': 30,
    'request_delay': 1.0,
    'preferred_format': 'epub',
    'remix_userid': '',
    'remix_userkey': '',
    # Z-Library 个人域名 —— 在 Z-Library 官网 → Z-access → Web Version 获取
    # 如: https://yourname.z-lib.id 或 https://downloads.你的域名.com
    'personal_domain': '',
    # 代理地址 —— 用于绕过网络封锁 (支持 http/socks5)
    # 如: http://127.0.0.1:7890 或 socks5://127.0.0.1:1080
    'proxy': '',
    'user_agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/120.0.0.0 Safari/537.36'
    ),
}


def _get_base_dir() -> str:
    """获取项目根目录（兼容 PyInstaller 打包后的 EXE）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后：使用 EXE 所在目录
        return os.path.dirname(os.path.abspath(sys.executable))
    else:
        # 正常 Python 运行：从 config.py 向上两级到项目根目录
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Config:
    """全局配置单例"""

    def __init__(self):
        self.base_dir = _get_base_dir()
        self.books_dir = os.path.join(self.base_dir, 'books')
        self.progress_file = os.path.join(self.base_dir, 'progress.json')
        self.config_file = os.path.join(self.base_dir, 'config.json')
        os.makedirs(self.books_dir, exist_ok=True)
        self.data: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
            except (json.JSONDecodeError, IOError):
                saved = {}
            return {**DEFAULT_CONFIG, **saved}
        return dict(DEFAULT_CONFIG)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self._save()

    def has_auth(self) -> bool:
        """检查是否已配置 Z-Library 认证令牌"""
        return bool(self.data.get('remix_userid') and self.data.get('remix_userkey'))

    def _save(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)


config = Config()
