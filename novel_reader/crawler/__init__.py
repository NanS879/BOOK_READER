"""爬虫模块 —— Z-Library 书籍爬虫

基于 Z-Library eAPI (Android 客户端 API)，支持:
  - 个人域名
  - HTTP/SOCKS 代理
  - remix 令牌认证 (Header + Cookie 双通道)
"""
from .base import BaseCrawler, BookInfo, BookMeta


def get_crawler():
    """工厂函数：从配置中读取认证令牌，创建 Z-Library 爬虫实例

    Raises:
        RuntimeError: 未配置认证令牌或缺少依赖时抛出
    """
    from ..config import config

    try:
        from .zlibrary import ZLibraryCrawler
    except ImportError as e:
        raise RuntimeError(
            "缺少必要依赖，请先运行: pip install -r requirements.txt\n"
            f"详情: {e}"
        ) from e

    if not config.has_auth():
        raise RuntimeError(
            "尚未配置 Z-Library 认证令牌。\n"
            "请在「设置」选项卡中填写 remix_userid 和 remix_userkey。\n"
            "获取方法: 浏览器登录 Z-Library → F12 → Application → Cookies"
        )

    personal_domain = config.get('personal_domain', '').strip() or None
    proxy = config.get('proxy', '').strip() or None

    return ZLibraryCrawler(
        remix_userid=config.get('remix_userid'),
        remix_userkey=config.get('remix_userkey'),
        request_delay=config.get('request_delay', 1.0),
        base_url=personal_domain,
        proxy=proxy,
    )
