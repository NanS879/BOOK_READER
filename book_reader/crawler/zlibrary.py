"""Z-Library 爬虫实现 —— 基于 Z-Library eAPI (Android 客户端 API)

直接调用 Z-Library 的 /eapi/ 端点，而非通过 HTML 爬取。
支持个人域名、代理配置，认证通过 remix 令牌以 HTTP Header + Cookie 双通道发送。

参考:
  - zlibrary-eapi-documentation (baroxyton)
  - sertraline/zlibrary (async 包，响应格式参考)
"""

import os
import re
import time
import json
from datetime import datetime
from typing import List, Optional, Callable, Dict, Any, Tuple
from urllib.parse import urljoin, urlparse

import requests

from .base import BaseCrawler, BookInfo, BookMeta


# ============================================================
# 默认值
# ============================================================

# 备用域名列表 —— 当用户未配置个人域名时依次尝试
_DEFAULT_DOMAINS = [
    "https://singlelogin.re",     # 官方统一登录入口 (推荐)
    "https://z-library.sk",       # 旧版兼容
    "https://1lib.fr",
    "https://z-lib.id",
]

# 兼容旧版 Cookie 方案的备用域名
_LEGACY_COOKIE_DOMAINS = [
    "https://z-library.sk",
]


class ZLibraryAPIError(Exception):
    """eAPI 调用异常"""


class ZLibraryCrawler(BaseCrawler):
    """Z-Library 书籍爬虫 —— 使用 eAPI

    认证方式:
      1. HTTP Header: remix-userid / remix-userkey
      2. Cookie:       remix_userid / remix_userkey

    支持:
      - 个人域名 (personal domain)
      - HTTP/SOCKS 代理
      - 多域名自动回退
    """

    name = 'zlibrary'

    # ---- 构造 ----

    def __init__(self, remix_userid: str, remix_userkey: str,
                 request_delay: float = 1.0,
                 base_url: Optional[str] = None,
                 proxy: Optional[str] = None):
        super().__init__(request_delay=request_delay)
        self._remix_userid = remix_userid
        self._remix_userkey = remix_userkey
        self._base_url_override = base_url   # 用户配置的个人域名
        self._proxy = proxy or None

        self._session: Optional[requests.Session] = None
        self._active_base_url: Optional[str] = None

    # ---- 内部: Session 管理 ----

    def _build_session(self) -> requests.Session:
        """创建一个配置好认证头和代理的 Session"""
        s = requests.Session()
        s.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Linux; Android 13; Pixel 7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Mobile Safari/537.36'
            ),
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Connection': 'keep-alive',
        })

        # HTTP Header 认证（eAPI 主通道）
        s.headers['remix-userid'] = self._remix_userid
        s.headers['remix-userkey'] = self._remix_userkey

        # 代理
        if self._proxy:
            s.proxies = {
                'http': self._proxy,
                'https': self._proxy,
            }

        return s

    def _inject_cookies(self, session: requests.Session, domain: str):
        """向 Session 注入认证 Cookie（兼容旧版站点）"""
        try:
            netloc = urlparse(domain).netloc
        except Exception:
            netloc = domain
        cookie_domain = '.' + netloc.lstrip('.')
        session.cookies.set('remix_userid', self._remix_userid,
                            domain=cookie_domain, path='/')
        session.cookies.set('remix_userkey', self._remix_userkey,
                            domain=cookie_domain, path='/')

    def _discover_domain(self) -> str:
        """按优先级确定 Z-Library 服务域名

        策略:
          1. 用户配置了个人域名 → 直接使用（不做连通性检测，因为可能需代理）
          2. 否则依次尝试内置备用域名
          3. 均不可用时给出清晰错误提示
        """
        # 用户配置的个人域名 → 直接使用
        if self._base_url_override:
            self._active_base_url = self._base_url_override.rstrip('/')
            return self._active_base_url

        # 创建临时 session（含代理）来检测可用域名
        test_session = requests.Session()
        test_session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36',
            'Accept': 'text/html, */*',
        })
        if self._proxy:
            test_session.proxies = {
                'http': self._proxy,
                'https': self._proxy,
            }

        for url in _DEFAULT_DOMAINS:
            try:
                r = test_session.head(url, timeout=4, allow_redirects=True,
                                      verify=True)
                if r.status_code < 500:
                    self._active_base_url = url
                    return url
            except Exception:
                continue

        raise RuntimeError(
            "无法连接到 Z-Library 服务器。\n\n"
            "请确认:\n"
            "  1. 是否已在「设置」中填写你的 Z-Library 个人域名\n"
            "     (登录 Z-Library → Z-access → Web Version 获取)\n"
            "  2. 是否已配置代理 (如你在中国大陆)\n"
            "  3. 网络是否正常 (可尝试使用 VPN)\n"
        )

    def _ensure_session(self) -> requests.Session:
        """懒初始化 —— 发现可用域名并创建 Session"""
        if self._session is None:
            self._active_base_url = self._discover_domain()
            self._session = self._build_session()
            self._inject_cookies(self._session, self._active_base_url)
        return self._session

    def _reset_session(self):
        """重置 Session（域名变更后调用）"""
        self._session = None
        self._active_base_url = None

    # ---- 内部: eAPI 请求 ----

    def _eapi_get(self, path: str, **kwargs) -> dict:
        """GET /eapi/... 返回 JSON"""
        s = self._ensure_session()
        url = urljoin(self._active_base_url, path)
        kwargs.setdefault('timeout', 30)
        try:
            resp = s.get(url, **kwargs)
            self._check_response(resp)
            return resp.json()
        except requests.RequestException as e:
            raise ZLibraryAPIError(f"请求失败 [{url}]: {e}") from e

    def _eapi_post(self, path: str, data: Optional[Dict[str, Any]] = None,
                   **kwargs) -> dict:
        """POST /eapi/... 返回 JSON"""
        s = self._ensure_session()
        url = urljoin(self._active_base_url, path)
        kwargs.setdefault('timeout', 30)

        # 序列化表单数据 —— 支持数组 (e.g. extensions[]=epub)
        if data:
            form_data = []
            for key, value in data.items():
                if isinstance(value, list):
                    for item in value:
                        form_data.append((f'{key}[]', str(item)))
                elif value is not None:
                    form_data.append((key, str(value)))
        else:
            form_data = None

        try:
            resp = s.post(url, data=form_data, **kwargs)
            self._check_response(resp)
            return resp.json()
        except requests.RequestException as e:
            raise ZLibraryAPIError(f"请求失败 [{url}]: {e}") from e

    @staticmethod
    def _check_response(resp: requests.Response):
        """检查响应状态并处理常见错误

        同时处理 JSON 错误响应（eAPI 可能返回 200 + error 字段），
        以及各种 HTTP 错误状态码。
        """
        content_type = resp.headers.get('content-type', '')
        text = resp.text[:500] if 'text/' in content_type else resp.text[:500]

        # ---- 先处理 HTTP 200 但包含 JSON 错误的情况 ----
        if resp.status_code == 200:
            # 尝试解析 JSON 错误
            if 'application/json' in content_type:
                try:
                    body = resp.json()
                    if isinstance(body, dict):
                        error_msg = body.get('error') or body.get('message') or ''
                        if error_msg:
                            raise ZLibraryAPIError(
                                f"API 返回错误: {error_msg}"
                            )
                except (json.JSONDecodeError, ValueError):
                    pass  # 不是 JSON 或解析失败，当作正常响应
            return

        # ---- 尝试从 JSON 响应体中提取错误信息 ----
        error_detail = ''
        if 'application/json' in content_type:
            try:
                body = resp.json()
                if isinstance(body, dict):
                    error_detail = (
                        body.get('error') or
                        body.get('message') or
                        body.get('detail') or
                        ''
                    )
            except (json.JSONDecodeError, ValueError):
                pass

        # ---- HTTP 错误处理 ----
        if resp.status_code == 401:
            raise ZLibraryAPIError(
                "认证失败 (401) —— 令牌无效或已过期。\n"
                "请重新获取 remix_userid 和 remix_userkey。"
                + (f"\n详情: {error_detail}" if error_detail else "")
            )
        elif resp.status_code == 403:
            raise ZLibraryAPIError(
                "访问被拒绝 (403)。可能原因:\n"
                "  - 域名被 Cloudflare 保护\n"
                "  - 需要使用个人域名\n"
                "  - 需要在「设置」中配置代理"
                + (f"\n详情: {error_detail}" if error_detail else "")
            )
        elif resp.status_code == 404:
            raise ZLibraryAPIError(
                "资源未找到 (404)。\n"
                "可能原因: 书籍已被移除或链接无效。"
            )
        elif resp.status_code == 429:
            raise ZLibraryAPIError(
                "请求过于频繁 (429)。\n"
                "请稍后重试或增大请求间隔。"
            )
        elif resp.status_code == 503:
            raise ZLibraryAPIError(
                "Z-Library 服务暂时不可用 (503)。\n"
                "请稍后重试或更换域名。"
            )
        elif 'login' in text.lower() or 'sign in' in text.lower():
            raise ZLibraryAPIError(
                "认证失败 —— 令牌无效或已过期。\n"
                "请重新获取 remix_userid 和 remix_userkey。"
            )
        elif 'captcha' in text.lower() or 'recaptcha' in text.lower():
            raise ZLibraryAPIError(
                "触发 CAPTCHA 验证。\n"
                "请稍后重试或降低请求频率。"
            )
        else:
            raise ZLibraryAPIError(
                f"服务器返回 {resp.status_code}: "
                f"{error_detail or text[:200] or resp.reason}"
            )

    # ---- 认证 ----

    def is_authenticated(self) -> bool:
        """通过请求用户资料端点来验证认证令牌

        /eapi/user/profile 需要有效的认证才能返回 200。
        如果令牌无效，Z-Library 会返回错误或登录页面。
        如果无法连接服务器，返回 False 并附带错误原因（可通过日志查看）。
        """
        try:
            self._ensure_session()
            result = self._eapi_get('/eapi/user/profile')
            # eAPI profile 响应包含 user 对象则认证成功
            if isinstance(result, dict) and (result.get('user') or result.get('success')):
                return True
            # 某些版本可能直接返回用户信息
            if isinstance(result, dict) and ('id' in result or 'name' in result or 'email' in result):
                return True
            return False
        except ZLibraryAPIError as e:
            msg = str(e).lower()
            if 'login' in msg or 'auth' in msg or '无效' in msg or '过期' in msg:
                return False
            # 网络错误/503 等不意味着令牌无效
            return True
        except RuntimeError:
            # 域名发现失败 —— 网络问题，不是令牌问题
            # 重新 raise 让调用方能看到具体错误
            raise
        except Exception:
            return False

    # ---- 搜索 ----

    def search(self, keyword: str, **filters) -> List[BookInfo]:
        """搜索 Z-Library 书籍 (使用 /eapi/book/search)

        可用的过滤器:
            extensions: List[str]  如 ['epub', 'pdf']
            languages: List[str]   如 ['english', 'chinese']
            order: str             默认 'relevance'
            year_from: int
            year_to: int
            page: int              默认 1
            limit: int             默认 20
        """
        self._rate_limit()
        self._ensure_session()

        # 构建搜索参数
        data: Dict[str, Any] = {
            'message': keyword,
        }

        # 解析扩展名
        extensions = filters.get('extensions')
        if extensions:
            data['extensions'] = [
                e.value if hasattr(e, 'value') else str(e).lower()
                for e in extensions
            ]

        # 解析语言
        languages = filters.get('languages')
        if languages:
            data['languages'] = [
                l.value if hasattr(l, 'value') else str(l).lower()
                for l in languages
            ]

        # 其他过滤条件
        order = filters.get('order')
        if order:
            data['order'] = order.value if hasattr(order, 'value') else str(order)
        else:
            data['order'] = 'relevance'

        year_from = filters.get('year_from')
        if year_from:
            data['yearFrom'] = str(year_from)

        year_to = filters.get('year_to')
        if year_to:
            data['yearTo'] = str(year_to)

        data['page'] = str(filters.get('page', 1))
        data['limit'] = str(filters.get('limit', 20))

        try:
            result = self._eapi_post('/eapi/book/search', data=data)
        except ZLibraryAPIError as e:
            raise RuntimeError(f"搜索失败: {e}") from e

        books_raw = self._extract_book_list(result)
        books = []
        for item in books_raw:
            # 提取字段 —— 兼容不同 API 版本的字段名
            title = (
                item.get('title') or
                item.get('name') or
                'Unknown'
            )
            source_url = (
                item.get('url') or
                item.get('book_url') or
                ''
            )
            author = item.get('author') or item.get('authors') or ''
            if isinstance(author, list):
                author = ', '.join(
                    a.get('author', '') if isinstance(a, dict) else str(a)
                    for a in author
                )
            elif isinstance(author, dict):
                author = author.get('author', author.get('name', ''))

            file_format = (
                item.get('extension') or
                item.get('filetype') or
                item.get('format') or
                ''
            )
            file_size = (
                item.get('filesize') or
                item.get('size') or
                ''
            )

            # 可能已有的额外字段
            book_id = str(item.get('id', ''))
            hashed = item.get('hash', '')
            if book_id and hashed and not source_url:
                source_url = urljoin(
                    self._active_base_url,
                    f'/eapi/book/{book_id}/{hashed}'
                )

            books.append(BookInfo(
                title=str(title).strip(),
                source_url=str(source_url).strip(),
                author=str(author).strip(),
                file_format=str(file_format).strip(),
                file_size=str(file_size).strip(),
                year=str(item.get('year', '')).strip(),
                language=str(item.get('language', '')).strip(),
                isbn=str(item.get('isbn', '')).strip(),
                cover_url=str(item.get('cover', '')).strip(),
            ))
        return books

    @staticmethod
    def _extract_book_list(result: dict) -> list:
        """从 eAPI 响应中提取书籍列表，兼容多种格式"""
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            # 优先取 books
            for key in ('books', 'results', 'data', 'items'):
                val = result.get(key)
                if isinstance(val, list):
                    return val
            # 退而求其次找嵌套
            pagination = result.get('pagination', {})
            if isinstance(pagination, dict):
                for key in ('books', 'results', 'data'):
                    val = pagination.get(key)
                    if isinstance(val, list):
                        return val
            # 单个结果?
            book = result.get('book')
            if isinstance(book, dict):
                return [book]
        return []

    # ---- 详情 ----

    def get_book_details(self, book_url: str) -> BookInfo:
        """获取书籍完整详情

        支持:
          - /eapi/book/{book_id}/{hash} (eAPI)
          - 完整 https:// URL (从搜索结果的 url 字段)
        """
        self._rate_limit()
        self._ensure_session()

        # 解析 URL: 尝试提取 book_id 和 hash
        book_id, book_hash = self._parse_book_ref(book_url)

        if book_id and book_hash:
            return self._get_details_via_eapi(book_id, book_hash)

        # 回退: 直接请求 URL
        return self._get_details_via_url(book_url)

    def _parse_book_ref(self, ref: str) -> tuple:
        """从 URL 或引用中提取 (book_id, hash)

        支持格式:
          /eapi/book/{id}/{hash}        (hash: 6-64位字母数字/连字符)
          /book/{id}/{hash}
          /book/{id}                    (仅 ID，无 hash)
          https://.../book/{id}/{hash}
        """
        book_id = None
        book_hash = None

        # /eapi/book/{id}/{hash} 或 /book/{id}/{hash}
        # hash 长度: 新旧 Z-Library 使用 6~64 位十六进制或字母数字
        m = re.search(r'/book/(\d+)/([a-zA-Z0-9][a-zA-Z0-9\-]{0,63})', ref)
        if m:
            book_id, book_hash = m.group(1), m.group(2)
        else:
            # /book/{id}（仅 ID，无 hash）
            m = re.search(r'/book/(\d+)', ref)
            if m:
                book_id = m.group(1)

        return book_id, book_hash

    def _get_details_via_eapi(self, book_id: str, book_hash: str) -> BookInfo:
        """通过 eAPI 获取详情 (/eapi/book/{id}/{hash})"""
        try:
            result = self._eapi_get(f'/eapi/book/{book_id}/{book_hash}')
        except ZLibraryAPIError as e:
            raise RuntimeError(f"获取书籍详情失败: {e}") from e

        book = result.get('book', result) if isinstance(result, dict) else {}

        # 下载链接 —— 尝试从 formats 端点获取
        download_url = book.get('download_url', '')
        cover_url = book.get('cover', '')

        # 合并 ISBN
        isbn = book.get('isbn') or book.get('isbn_13') or book.get('isbn_10') or ''

        author = book.get('author') or book.get('authors') or ''
        if isinstance(author, list):
            author = ', '.join(
                a.get('author', '') if isinstance(a, dict) else str(a)
                for a in author
            )

        title = book.get('title') or book.get('name') or 'Unknown'
        file_format = book.get('extension') or book.get('filetype') or ''
        file_size = book.get('filesize') or book.get('size') or ''

        # 补全封面 URL
        if cover_url and not cover_url.startswith('http'):
            cover_url = urljoin(self._active_base_url, cover_url)

        # 提取 Web 页面 URL (用于下载回退)
        web_href = book.get('href', '')

        result = BookInfo(
            title=str(title).strip(),
            author=str(author).strip(),
            description=str(book.get('description', '')).strip(),
            source_url=urljoin(
                self._active_base_url,
                f'/eapi/book/{book_id}/{book_hash}'
            ),
            file_format=str(file_format).strip(),
            file_size=str(file_size).strip(),
            year=str(book.get('year', '')).strip(),
            language=str(book.get('language', '')).strip(),
            isbn=str(isbn).strip(),
            download_url=str(download_url).strip(),
            cover_url=str(cover_url).strip(),
        )
        # 将 web href 附加到结果对象上（供下载时使用）
        if web_href:
            result._web_href = str(web_href).strip()
        return result

    def _get_details_via_url(self, book_url: str) -> BookInfo:
        """直接请求书籍 URL 获取详情（回退方案）"""
        s = self._ensure_session()
        try:
            resp = s.get(book_url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"获取书籍详情失败: {e}") from e

        # 简单解析 HTML（作为最后手段）
        title = book_url
        author = ''
        description = ''
        file_format = ''
        file_size = ''
        cover_url = ''
        download_url = ''

        # 尝试从 HTML 中提取基本信息
        text = resp.text
        # title
        m = re.search(r'<h1[^>]*itemprop="name"[^>]*>([^<]+)', text)
        if not m:
            m = re.search(r'<h1[^>]*class="[^"]*book-title[^"]*"[^>]*>([^<]+)', text)
        if not m:
            m = re.search(r'<title>([^<]+)', text)
        if m:
            title = m.group(1).strip()

        # author
        m = re.search(r'itemprop="author"[^>]*>([^<]+)', text)
        if m:
            author = m.group(1).strip()

        # description
        m = re.search(r'itemprop="description"[^>]*>([^<]+)', text)
        if m:
            description = m.group(1).strip()

        # download URL
        m = re.search(r'href="([^"]+/dl/[^"]+)"', text)
        if m:
            download_url = urljoin(book_url, m.group(1))

        # cover
        m = re.search(r'<img[^>]+class="[^"]*book-cover[^"]*"[^>]+src="([^"]+)"', text)
        if m:
            cover_url = urljoin(book_url, m.group(1))

        return BookInfo(
            title=str(title).strip(),
            author=str(author).strip(),
            description=str(description).strip(),
            source_url=book_url,
            file_format=str(file_format).strip(),
            file_size=str(file_size).strip(),
            download_url=str(download_url).strip(),
            cover_url=str(cover_url).strip(),
        )

    # ---- 下载 ----

    # MIME 类型 → 文件扩展名映射
    _MIME_TO_EXT = {
        'application/epub+zip': 'epub',
        'application/epub': 'epub',
        'application/pdf': 'pdf',
        'application/x-mobipocket-ebook': 'mobi',
        'application/x-mobi8-ebook': 'azw3',
        'application/octet-stream': None,   # 无法判断
        'text/plain': 'txt',
        'text/html': 'html',
    }

    @staticmethod
    def _parse_content_disposition(headers) -> Tuple[Optional[str], Optional[str]]:
        """从响应头解析 Content-Disposition，返回 (filename, extension)

        支持 RFC 6266 / RFC 5987 格式:
          attachment; filename="book.epub"
          attachment; filename="book title.epub"
          attachment; filename=book.epub
          attachment; filename*=UTF-8''%E4%B9%A6%E5%90%8D.epub
        """
        cd = headers.get('content-disposition', '')
        if not cd:
            return None, None

        raw = None

        # 优先尝试 filename*= (RFC 5987, URL-encoded)
        m = re.search(r"filename\*\s*=\s*UTF-8''([^;'\"]+)", cd, re.IGNORECASE)
        if m:
            from urllib.parse import unquote
            raw = unquote(m.group(1).strip())
        else:
            # 回退到 filename= (RFC 6266)
            # 先匹配带引号的（允许空格等特殊字符）
            m = re.search(r'filename\s*=\s*"([^"]*)"', cd, re.IGNORECASE)
            if m:
                raw = m.group(1).strip()
            else:
                # 再匹配不带引号的（直到分号或行尾）
                m = re.search(r'filename\s*=\s*([^;\s]+)', cd, re.IGNORECASE)
                if m:
                    raw = m.group(1).strip()

        if not raw:
            return None, None

        # 提取扩展名
        _, ext = os.path.splitext(raw)
        ext = ext.lstrip('.').lower() if ext else None
        return raw, ext

    @staticmethod
    def _guess_ext_from_response(resp) -> Optional[str]:
        """从响应头推断文件扩展名"""
        # 1. Content-Disposition
        _, ext = ZLibraryCrawler._parse_content_disposition(resp.headers)
        if ext:
            return ext

        # 2. Content-Type
        content_type = resp.headers.get('content-type', '')
        if content_type:
            mime = content_type.split(';')[0].strip().lower()
            ext = ZLibraryCrawler._MIME_TO_EXT.get(mime)
            if ext:
                return ext

        return None

    @staticmethod
    def _select_best_format(formats: list, preferred: str = 'epub') -> Optional[dict]:
        """从格式列表中选出最佳格式

        优先选择用户首选格式，其次选择第一个可用格式。
        返回格式字典或 None。
        """
        if not formats:
            return None

        preferred = preferred.lower()
        # 先找首选格式
        for fmt in formats:
            ext = (fmt.get('extension') or fmt.get('name') or '').lower()
            if ext == preferred:
                return fmt

        # 回退到第一个
        return formats[0]

    def download(self, book: BookInfo, dest_dir: str,
                 progress_callback: Optional[Callable] = None) -> str:
        """下载书籍文件到目标目录，返回本地文件路径

        下载流程:
          1. 若 book.download_url 已存在则直接使用
          2. 否则通过 /eapi/book/{id}/{hash}/formats 获取格式列表
          3. 从格式列表中按用户偏好选择，构造下载 URL
          4. 流式下载，检查响应是否为 JSON 重定向
          5. 从 Content-Disposition 或 Content-Type 推断扩展名
        """
        s = self._ensure_session()
        self._rate_limit()

        # ---- 1. 确定下载 URL ----
        download_url = self._resolve_download_url(book)

        if not download_url:
            raise RuntimeError(
                f"「{book.title}」没有可用的下载链接。\n"
                "请确认该书在 Z-Library 上仍有可下载的格式。"
            )

        # ---- 2. 确定目标路径（先创建目录） ----
        os.makedirs(dest_dir, exist_ok=True)
        safe_name = self._safe_filename(book.title)

        # ---- 3. 发起下载请求 ----
        try:
            resp = s.get(download_url, stream=True, timeout=60,
                        allow_redirects=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"下载请求失败: {e}") from e

        # ---- 4. 检查响应是否为 JSON（间接下载） ----
        content_type = resp.headers.get('content-type', '')
        if 'application/json' in content_type:
            # eAPI 文件端点返回 JSON，格式如:
            #   {"success":1,"file":{"downloadLink":"https://cdn.../file.epub"}}
            body = None
            try:
                body = resp.json()
            except Exception:
                resp.close()
                raise RuntimeError("下载接口返回了无法解析的 JSON 响应")
            resp.close()

            if not isinstance(body, dict):
                raise RuntimeError("下载接口返回了非预期的 JSON 格式")

            # 从 JSON 中提取真正的下载 URL（兼容多种响应结构）
            redirect_url = self._extract_redirect_url_from_json(body)
            if not redirect_url:
                raise RuntimeError(
                    f"下载接口返回 JSON 但未包含下载链接。\n"
                    f"响应: {json.dumps(body, ensure_ascii=False)[:300]}"
                )

            # 重新请求真正的下载 URL
            try:
                resp = s.get(redirect_url, stream=True, timeout=120,
                            allow_redirects=True)
                resp.raise_for_status()
            except requests.RequestException as e:
                raise RuntimeError(f"重定向下载失败: {e}") from e

        # ---- 5. 确定文件扩展名 ----
        ext = self._resolve_extension(book, resp)

        filepath = os.path.join(dest_dir, f"{safe_name}.{ext}")

        # ---- 6. 流式写入 ----
        total_size = None
        total_size_str = resp.headers.get('content-length')
        if total_size_str and total_size_str.isdigit():
            total_size = int(total_size_str)

        downloaded = 0
        try:
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(
                                downloaded, total_size,
                                f"正在下载 {os.path.basename(filepath)}"
                            )
        except Exception as e:
            # 清理不完整的文件
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except OSError:
                    pass
            raise RuntimeError(f"下载写入失败: {e}") from e
        finally:
            resp.close()

        # ---- 7. 验证 ----
        if not os.path.exists(filepath):
            raise RuntimeError(f"下载完成但未找到文件: {book.title}")

        actual_size = os.path.getsize(filepath)
        if actual_size == 0:
            os.remove(filepath)
            raise RuntimeError(f"下载的文件为空: {book.title}")

        if total_size and actual_size < total_size * 0.9:
            # 文件明显不完整（小于预期的 90%）
            # 但不删除，用户可能仍能使用
            pass

        return filepath

    # ---- 下载辅助方法 ----

    def _resolve_download_url(self, book: BookInfo) -> str:
        """解析书籍的下载 URL

        策略 (按优先级):
          1. 直接使用 book.download_url (若已有)
          2. 通过 eAPI formats 端点获取 (对部分服务器有效)
          3. 构造 eAPI file 端点 (对部分服务器有效)
          4. 通过 Web 页面解析下载链接 (最通用)
        """
        # 1. 已有直接下载链接
        if book.download_url:
            return book.download_url

        if not book.source_url:
            return ''

        book_id, book_hash = self._parse_book_ref(book.source_url)
        if not book_id or not book_hash:
            return ''

        from ..config import config
        preferred = config.get('preferred_format', 'epub')

        # 2. 尝试 eAPI formats 端点
        download_url = self._try_formats_endpoint(book_id, book_hash, preferred)
        if download_url:
            return download_url

        # 3. 构造 eAPI file 端点
        download_url = self._try_file_endpoint(book_id, book_hash, preferred)
        if download_url:
            return download_url

        # 4. Web 页面解析回退
        download_url = self._resolve_download_url_via_web(book, book_id, book_hash)
        if download_url:
            return download_url

        return ''

    def _try_formats_endpoint(self, book_id: str, book_hash: str,
                              preferred: str) -> str:
        """尝试通过 /eapi/book/{id}/{hash}/formats 获取下载链接"""
        try:
            formats_result = self._eapi_get(
                f'/eapi/book/{book_id}/{book_hash}/formats'
            )
        except ZLibraryAPIError:
            return ''

        # 兼容不同的响应键名: formats, books, files
        for key in ('formats', 'books', 'files', 'data'):
            fmt_list = formats_result.get(key, [])
            if fmt_list:
                chosen = self._select_best_format(fmt_list, preferred)
                if chosen:
                    url = (
                        chosen.get('download_url') or
                        chosen.get('url') or
                        chosen.get('downloadUrl') or
                        ''
                    )
                    if url:
                        return url
                    # 格式对象可能有 id
                    fmt_id = (chosen.get('id') or chosen.get('format_id') or
                              chosen.get('file_id'))
                    if fmt_id:
                        return urljoin(
                            self._active_base_url,
                            f'/eapi/book/{book_id}/{book_hash}/file/{fmt_id}'
                        )
        return ''

    def _try_file_endpoint(self, book_id: str, book_hash: str,
                           preferred: str) -> str:
        """尝试直接构造 eAPI file 端点 URL

        format_id 映射:
          1 = epub, 2 = pdf, 3 = mobi, 4 = azw3, 5 = txt, 6 = djvu

        注意: 此服务器对 HEAD 请求返回 404，但 GET 返回 200。
        因此不做预检，直接返回候选 URL，由 download() 负责错误处理。
        """
        fmt_id_map = {'epub': 1, 'pdf': 2, 'mobi': 3, 'azw3': 4, 'txt': 5, 'djvu': 6}
        fmt_ids = []

        # 先试首选格式
        pref_id = fmt_id_map.get(preferred.lower())
        if pref_id:
            fmt_ids.append(pref_id)
        # 再试其他格式
        for fid in fmt_id_map.values():
            if fid not in fmt_ids:
                fmt_ids.append(fid)

        # 返回首选格式的 file 端点 URL（不做 HEAD 预检）
        if fmt_ids:
            fmt_id = fmt_ids[0]
            return urljoin(
                self._active_base_url,
                f'/eapi/book/{book_id}/{book_hash}/file/{fmt_id}'
            )

        return ''

    def _resolve_download_url_via_web(self, book: BookInfo,
                                       book_id: str, book_hash: str) -> str:
        """通过 Web 页面解析下载链接（回退方案）

        访问 Z-Library 书籍 Web 页面，从页面源码中提取下载 URL。
        支持 Next.js 的 __NEXT_DATA__ 和传统 HTML 链接。

        如果主域名不可达，会尝试备用域名。
        """
        # 获取书籍的 Web 页面 URL
        href = getattr(book, '_web_href', None) or ''
        if not href:
            href = urljoin(self._active_base_url,
                           f'/book/{book_id}/{book_hash}')

        if not href:
            return ''

        s = self._ensure_session()

        # 尝试多个 URL 变体
        urls_to_try = [href]

        # 也尝试用数字 ID 构造 URL（某些域名可能不支持友好 URL）
        numeric_url = urljoin(self._active_base_url,
                             f'/book/{book_id}/{book_hash}')
        if numeric_url not in urls_to_try:
            urls_to_try.append(numeric_url)

        # 也要尝试备用域名
        alt_domains = [
            'https://singlelogin.re',
            'https://z-library.sk',
        ]
        for alt in alt_domains:
            alt_url = urljoin(alt, f'/book/{book_id}/{book_hash}')
            if alt_url not in urls_to_try:
                urls_to_try.append(alt_url)

        for url in urls_to_try:
            # 确保替代域名的 Cookie 也已注入
            try:
                parsed = urlparse(url)
                domain = f"{parsed.scheme}://{parsed.netloc}"
                self._inject_cookies(s, domain)
            except Exception:
                pass

            try:
                resp = s.get(url, timeout=20, allow_redirects=True)
            except requests.RequestException:
                continue

            if resp.status_code != 200:
                continue

            download_url = self._extract_download_url_from_page(resp.text)
            if download_url:
                return download_url

        return ''

    def _extract_download_url_from_page(self, text: str) -> str:
        # ---- 方法 1: Next.js __NEXT_DATA__ ----
        m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*type="application/json"[^>]*>(.*?)</script>',
                      text, re.DOTALL)
        if m:
            try:
                ndata = json.loads(m.group(1))
                # 遍历查找 downloadUrl
                found = self._find_download_url_in_json(ndata)
                if found:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # ---- 方法 2: 嵌入式 JSON-LD / schema.org ----
        m = re.search(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
                      text, re.DOTALL)
        if m:
            try:
                ld = json.loads(m.group(1))
                found = self._find_download_url_in_json(ld)
                if found:
                    return found
            except (json.JSONDecodeError, ValueError):
                pass

        # ---- 方法 3: 正则查找下载链接 ----
        patterns = [
            r'(/dl/\d+/[a-zA-Z0-9]+)',
            r'"(https?://[^"]+/dl/[^"]+)"',
            r'downloadLink["\s]*:["\s]*"([^"]+)"',
            r'downloadUrl["\s]*:["\s]*"([^"]+)"',
            r'"fileUrl"["\s]*:["\s]*"([^"]+)"',
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                dl = m.group(1)
                if dl.startswith('/'):
                    dl = urljoin(self._active_base_url, dl)
                return dl

        # ---- 方法 4: 查找所有可能的下载 endpoint ----
        # Z-Library 新版的下载 endpoint 可能是 /eapi/ 或其他路径
        api_matches = re.findall(r'["\']([^"\']*download[^"\']*)["\']', text, re.IGNORECASE)
        for match in api_matches[:5]:
            if match.startswith('http'):
                return match
            elif match.startswith('/'):
                return urljoin(self._active_base_url, match)

        return ''

    @staticmethod
    def _extract_redirect_url_from_json(body: dict) -> str:
        """从 eAPI 文件端点的 JSON 响应中提取真实下载 URL

        支持的响应格式:
          {"success":1,"file":{"downloadLink":"https://cdn.../file.epub"}}
          {"success":1,"file":{"download_url":"https://..."}}
          {"download_url":"https://..."}
          {"url":"https://..."}
        """
        # 1. file.downloadLink (eAPI 新版格式)
        file_obj = body.get('file')
        if isinstance(file_obj, dict):
            link = (file_obj.get('downloadLink') or
                    file_obj.get('download_url') or
                    file_obj.get('url') or
                    file_obj.get('link') or
                    '')
            if isinstance(link, str) and link:
                return link

        # 2. 顶层字段
        for key in ('downloadLink', 'download_url', 'downloadUrl',
                     'url', 'link', 'redirect_url'):
            val = body.get(key)
            if isinstance(val, str) and val:
                return val

        return ''

    @staticmethod
    def _find_download_url_in_json(obj, depth=0) -> str:
        """递归搜索 JSON 对象中的下载 URL"""
        if depth > 8 or obj is None:
            return ''

        if isinstance(obj, dict):
            # 检查是否有直接的下载链接字段
            for key in ('downloadUrl', 'download_url', 'downloadLink',
                        'fileUrl', 'file_url', 'bookUrl', 'dlUrl'):
                val = obj.get(key)
                if isinstance(val, str) and val:
                    return val

            # 递归搜索
            for val in obj.values():
                result = ZLibraryCrawler._find_download_url_in_json(val, depth + 1)
                if result:
                    return result

        elif isinstance(obj, list):
            for item in obj:
                result = ZLibraryCrawler._find_download_url_in_json(item, depth + 1)
                if result:
                    return result

        return ''

    def _resolve_extension(self, book: BookInfo, resp) -> str:
        """确定下载文件的扩展名

        优先级:
          1. 响应头 Content-Disposition
          2. 响应头 Content-Type
          3. book.file_format
          4. 'unknown'
        """
        # 1. 从 Content-Disposition 解析
        filename, ext = self._parse_content_disposition(resp.headers)
        if ext:
            return ext

        # 2. 从 Content-Type 推断
        ext = self._guess_ext_from_response(resp)
        if ext:
            return ext

        # 3. 使用书籍已知格式
        if book.file_format:
            return book.file_format.lstrip('.').lower()

        # 4. 从文件名中提取
        if filename:
            _, ext = os.path.splitext(filename)
            if ext:
                return ext.lstrip('.').lower()

        return 'unknown'

    # ---- 工具 ----

    @staticmethod
    def _safe_filename(name: str) -> str:
        safe = re.sub(r'[<>:"/\\|?*]', '_', name)
        return safe.strip() or 'unknown'
