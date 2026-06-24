"""爬虫基类 - 定义爬虫接口和通用数据模型"""
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Callable


@dataclass
class BookInfo:
    """书籍信息（来自搜索或详情接口）"""
    title: str
    author: str = ''
    description: str = ''
    source_url: str = ''           # Z-Library 书籍页面 URL
    file_format: str = ''          # epub, pdf, mobi
    file_size: str = ''            # 人类可读的文件大小
    file_size_bytes: int = 0       # 原始字节数
    year: str = ''                 # 出版年份
    language: str = ''
    isbn: str = ''                 # ISBN-10 或 ISBN-13
    download_url: str = ''         # 直接下载链接
    cover_url: str = ''            # 封面图片 URL


@dataclass
class BookMeta:
    """持久化到磁盘的书籍元数据"""
    title: str
    author: str = ''
    description: str = ''
    source_url: str = ''
    file_format: str = ''
    file_size: str = ''
    year: str = ''
    language: str = ''
    isbn: str = ''
    filename: str = ''             # 磁盘上的实际文件名
    downloaded_at: str = ''        # ISO 时间戳


class BaseCrawler(ABC):
    """爬虫抽象基类"""

    name: str = 'base'

    def __init__(self, request_delay: float = 1.0):
        self.request_delay = request_delay
        self._last_request_time = 0.0

    def _rate_limit(self):
        """请求频率控制"""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    @abstractmethod
    def search(self, keyword: str, **filters) -> List[BookInfo]:
        """按关键词搜索书籍"""
        ...

    @abstractmethod
    def get_book_details(self, book_url: str) -> BookInfo:
        """获取书籍详细信息"""
        ...

    @abstractmethod
    def download(self, book: BookInfo, dest_dir: str,
                 progress_callback: Optional[Callable] = None) -> str:
        """下载书籍文件，返回本地文件路径"""
        ...

    @abstractmethod
    def is_authenticated(self) -> bool:
        """检查认证是否有效"""
        ...
