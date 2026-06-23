"""本地存储管理 —— 书籍保存、读取、进度追踪"""
import json
import os
import re
import shutil
from datetime import datetime
from typing import Dict, List, Optional

from .crawler.base import BookMeta


class Storage:
    """管理书籍的本地存储和阅读进度"""

    def __init__(self, books_dir: str, progress_file: str):
        self.books_dir = books_dir
        self.progress_file = progress_file
        os.makedirs(self.books_dir, exist_ok=True)

    def _safe_name(self, name: str) -> str:
        """将书名转换为安全的目录名"""
        safe = re.sub(r'[<>:"/\\|?*]', '_', name)
        return safe.strip() or 'unknown'

    def _book_dir(self, title: str) -> str:
        return os.path.join(self.books_dir, self._safe_name(title))

    def _meta_path(self, title: str) -> str:
        return os.path.join(self._book_dir(title), 'meta.json')

    # ---- 书籍元数据 ----

    def save_book_meta(self, meta: BookMeta):
        """保存书籍元信息到本地"""
        d = self._book_dir(meta.title)
        os.makedirs(d, exist_ok=True)
        data = {
            'title': meta.title,
            'author': meta.author,
            'description': meta.description,
            'source_url': meta.source_url,
            'file_format': meta.file_format,
            'file_size': meta.file_size,
            'year': meta.year,
            'language': meta.language,
            'isbn': meta.isbn,
            'filename': meta.filename,
            'downloaded_at': meta.downloaded_at,
        }
        with open(self._meta_path(meta.title), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_book_meta(self, title: str) -> Optional[dict]:
        """加载书籍元信息"""
        path = self._meta_path(title)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def has_book(self, title: str) -> bool:
        return os.path.exists(self._meta_path(title))

    # ---- 书籍文件 ----

    def save_book_file(self, title: str, source_path: str, ext: str) -> str:
        """将下载的书籍文件复制到书籍目录，返回目标路径"""
        d = self._book_dir(title)
        os.makedirs(d, exist_ok=True)

        safe_title = self._safe_name(title)
        dest_path = os.path.join(d, f"{safe_title}.{ext}")

        # 如果源文件和目标文件相同则跳过
        if os.path.abspath(source_path) != os.path.abspath(dest_path):
            shutil.copy2(source_path, dest_path)

        return dest_path

    def get_book_file_path(self, title: str) -> Optional[str]:
        """获取书籍的实际文件路径（自动查找 epub/pdf/mobi 文件）"""
        d = self._book_dir(title)
        if not os.path.isdir(d):
            return None

        for name in os.listdir(d):
            if name.lower().endswith(('.epub', '.pdf', '.mobi', '.txt', '.azw3', '.djvu')):
                return os.path.join(d, name)
        return None

    def has_book_file(self, title: str) -> bool:
        return self.get_book_file_path(title) is not None

    # ---- 阅读进度 ----

    def save_progress(self, book_title: str, data: dict):
        """保存阅读进度（合并到已有数据）"""
        progress = self.load_all_progress()
        existing = progress.get(book_title, {})
        existing.update(data)
        existing['last_read'] = data.get('last_read', datetime.now().isoformat())
        existing.setdefault('read_count', 0)
        existing['read_count'] = existing.get('read_count', 0) + 1
        progress[book_title] = existing

        os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def load_progress(self, book_title: str) -> Optional[dict]:
        """加载指定书籍的阅读进度"""
        return self.load_all_progress().get(book_title)

    def load_all_progress(self) -> dict:
        """加载全部阅读进度"""
        if not os.path.exists(self.progress_file):
            return {}
        try:
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    # ---- 书籍列表 ----

    def list_books(self) -> List[dict]:
        """列出所有已下载的书籍及其进度"""
        books = []
        if not os.path.isdir(self.books_dir):
            return books

        all_progress = self.load_all_progress()

        for name in sorted(os.listdir(self.books_dir)):
            d = os.path.join(self.books_dir, name)
            if not os.path.isdir(d):
                continue
            meta_path = os.path.join(d, 'meta.json')
            if not os.path.exists(meta_path):
                continue

            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    meta = json.load(f)
            except (json.JSONDecodeError, IOError):
                continue

            title = meta.get('title', name)
            progress = all_progress.get(title, {})
            books.append({
                'title': title,
                'author': meta.get('author', '未知'),
                'file_format': meta.get('file_format', ''),
                'file_size': meta.get('file_size', ''),
                'source_url': meta.get('source_url', ''),
                'downloaded_at': meta.get('downloaded_at', ''),
                'last_read': progress.get('last_read', ''),
                'read_count': progress.get('read_count', 0),
            })

        return books
