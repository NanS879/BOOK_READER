"""主入口 —— CLI 命令解析与调度"""
import argparse
import os
import sys
import time
from datetime import datetime
from typing import List

from .config import config
from .storage import Storage
from .crawler.base import BookInfo, BookMeta
from .crawler import get_crawler
from .reader import Reader
from .console import (
    ok, fail, warn, tip, hl, strong, mute, title, field, val, dye, S,
    rule, header, box, progress, Spinner, table,
)


def _get_storage() -> Storage:
    return Storage(config.books_dir, config.progress_file)


def _get_crawler():
    return get_crawler()


# ============================================================
# 命令: setup
# ============================================================

def cmd_setup(args):
    """配置 Z-Library 认证令牌"""
    print()
    print(header('Z-Library 认证设置'))
    print()
    print(box([
        f"{field('使用说明')}",
        f"",
        f"  需要你的 Z-Library {hl('remix 令牌')} 才能使用本工具。",
        f"",
        f"  {strong('获取方法：')}",
        f"    1. 在浏览器中登录 Z-Library（可通过 {mute('singlelogin.re')} 跳转)",
        f"    2. 按 {strong('F12')} 打开开发者工具",
        f"    3. 进入 {tip('Application')} > {tip('Cookies')}",
        f"    4. 复制 {hl('remix_userid')} 和 {hl('remix_userkey')} 的值",
        f"",
        f"  {strong('提示：')}",
        f"    如果你在中国大陆无法访问，需要先配置代理或使用 VPN。",
        f"    也可在 Z-Library 官网获取 {hl('个人域名')} 提高访问成功率。",
        f"",
        f"  {warn('⚠ 令牌是个人敏感信息，请勿分享给他人。')}",
    ]))
    print()

    try:
        uid = input(f"  {field('remix_userid')}    : ").strip()
        ukey = input(f"  {field('remix_userkey')}   : ").strip()
    except (EOFError, KeyboardInterrupt):
        print(f"\n{warn('设置已取消')}")
        return

    if not uid or not ukey:
        print(f"\n{warn('设置已取消 —— 两个值都是必需的。')}")
        return

    config.set('remix_userid', uid)
    config.set('remix_userkey', ukey)

    # 可选: 个人域名
    print(f"\n  {mute('--- 以下为可选配置，按回车跳过 ---')}")
    domain = input(f"  {field('个人域名 URL')}  : ").strip()
    if domain:
        if not (domain.startswith('http://') or domain.startswith('https://')):
            domain = 'https://' + domain
        config.set('personal_domain', domain)

    # 可选: 代理
    proxy = input(f"  {field('代理地址')}     : ").strip()
    if proxy:
        config.set('proxy', proxy)

    # 验证
    print(f"\n  {tip('⠏')} 正在验证认证信息...", end='', flush=True)
    try:
        crawler = _get_crawler()
        if crawler.is_authenticated():
            sys.stdout.write(f"\r  {ok('✓')} 认证成功！        \n")
        else:
            sys.stdout.write(f"\r  {warn('⚠')} 无法验证，请检查令牌是否正确\n")
            print(f"    {mute('可能原因: 令牌过期 / 网络不可达 / 需要个人域名或代理')}")
            print(f"    {mute('令牌已保存，可重新运行 setup 更新。')}")
    except Exception as e:
        sys.stdout.write(f"\r  {warn('⚠')} 验证出错: {e}\n")
        print(f"    {mute('令牌已保存，可重新运行 setup 更新。')}")
    print()


# ============================================================
# 命令: search
# ============================================================

def cmd_search(args):
    """搜索 Z-Library 书籍"""
    keyword = args.keyword
    print()
    print(f"  {tip('🔍')} 正在搜索 {hl(keyword)} ...")
    print()

    try:
        crawler = _get_crawler()
    except RuntimeError as e:
        print(f"  {fail('✗')} {e}")
        return

    filters = {}
    if args.format:
        filters['extensions'] = [args.format]
    if args.language:
        filters['languages'] = [args.language]

    spinner = Spinner('搜索中...')
    # 简单加载动画
    import threading
    stop_spin = threading.Event()
    def spin():
        while not stop_spin.is_set():
            spinner.tick()
            time.sleep(0.08)
    t = threading.Thread(target=spin, daemon=True)
    t.start()

    try:
        results = crawler.search(keyword, **filters)
        stop_spin.set()
        t.join(timeout=0.5)
    except RuntimeError as e:
        stop_spin.set()
        t.join(timeout=0.5)
        sys.stdout.write(f"\r  {fail('✗')} 搜索失败: {e}" + ' ' * 30 + '\n')
        return

    if not results:
        sys.stdout.write(f"\r  {warn('!')} 未找到相关书籍" + ' ' * 30 + '\n')
        print(f"  {mute('提示: 可尝试更换关键词或调整过滤条件')}")
        return

    sys.stdout.write(f"\r  {ok('✓')} 找到 {hl(str(len(results)))} 个结果" + ' ' * 30 + '\n')
    print()

    # 表格展示结果
    print(f"  {'序号':<6}{'书名':<42}{'作者'}")
    print(f"  {mute('─' * 65)}")
    for i, book in enumerate(results, 1):
        t = book.title[:40] + '..' if len(book.title) > 42 else book.title
        a = book.author[:16] if book.author else '未知'
        print(f"  {dye(str(i), S.B_GREEN):<6}{t:<42}{a}")
    print(f"  {mute('─' * 65)}")
    print(f"  {tip('输入序号查看详情并下载')}  {mute('输入 q 返回')}")

    try:
        choice = input(f"\n  {field('>')} ").strip()
        if choice.lower() == 'q':
            print()
            return
        idx = int(choice) - 1
        if 0 <= idx < len(results):
            _download_from_search(results[idx])
        else:
            print(f"  {warn('无效序号')}")
    except (ValueError, EOFError):
        print(f"  {mute('已取消')}")
    print()


def _download_from_search(book: BookInfo):
    """从搜索结果获取详情并下载"""
    crawler = _get_crawler()
    storage = _get_storage()

    print()
    spinner = Spinner('获取书籍详情...')
    spinner.tick()
    try:
        details = crawler.get_book_details(book.source_url)
        spinner.end('详情获取成功')
    except RuntimeError as e:
        spinner.end(str(e), success=False)
        return

    _print_book_details(details)

    fmt = details.file_format or config.get('preferred_format', 'epub')
    print(f"\n  {field('格式')}: {hl(fmt)}")
    choice = input(f"  {tip('是否下载?')} {mute('(Y/n)')}: ").strip().lower()
    if choice == 'n':
        return

    _do_download(crawler, storage, details)


def _print_book_details(book: BookInfo):
    """打印书籍详情卡片"""
    print()
    lines = [
        f"{field('书名')}: {strong(book.title)}",
        f"{field('作者')}: {book.author or '未知'}",
    ]
    if book.year:
        lines.append(f"{field('出版')}: {book.year}")
    if book.language:
        lines.append(f"{field('语言')}: {book.language}")
    if book.file_format:
        lines.append(f"{field('格式')}: {hl(book.file_format.upper())}")
    if book.file_size:
        lines.append(f"{field('大小')}: {book.file_size}")
    if book.isbn:
        lines.append(f"{field('ISBN')}: {book.isbn}")
    if book.description:
        desc = book.description[:280] + '...' if len(book.description) > 280 else book.description
        lines.append(f"{field('简介')}: {mute(desc)}")
    print(box(lines, width=60))


def _do_download(crawler, storage, book: BookInfo):
    """执行下载流程"""
    title = book.title
    dest_dir = storage._book_dir(title)
    os.makedirs(dest_dir, exist_ok=True)

    print(f"\n  {tip('⬇')} 开始下载 {strong(title)} ...\n")

    last_update = [0]

    def prog_cb(current: int, total: int, status: str):
        # 限制刷新频率
        now = time.time()
        if total and total > 0 and now - last_update[0] < 0.15:
            return
        last_update[0] = now

        if total and total > 0:
            size_mb = current / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            label = f"{size_mb:.1f}/{total_mb:.1f} MB"
            sys.stdout.write(f"\r{progress(current, total, label)}")
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\r  {mute(status)}")
            sys.stdout.flush()

    try:
        filepath = crawler.download(
            book=book,
            dest_dir=dest_dir,
            progress_callback=prog_cb,
        )
        print()

        # 保存元数据（使用实际下载的文件扩展名）
        actual_ext = os.path.splitext(filepath)[1].lstrip('.').lower()
        try:
            actual_size = os.path.getsize(filepath)
            if actual_size < 1024:
                size_str = f"{actual_size} B"
            elif actual_size < 1024 * 1024:
                size_str = f"{actual_size / 1024:.1f} KB"
            else:
                size_str = f"{actual_size / (1024 * 1024):.1f} MB"
        except OSError:
            size_str = book.file_size

        meta = BookMeta(
            title=title,
            author=book.author,
            description=book.description,
            source_url=book.source_url,
            file_format=actual_ext or book.file_format,
            file_size=size_str,
            year=book.year,
            language=book.language,
            isbn=book.isbn,
            filename=os.path.basename(filepath),
            downloaded_at=datetime.now().isoformat(),
        )
        storage.save_book_meta(meta)

        print(f"\n  {ok('✓')} 下载完成！")
        print(f"  {mute('保存位置:')} {filepath}")

        choice = input(f"\n  {tip('是否打开阅读?')} {mute('(Y/n)')}: ").strip().lower()
        if choice != 'n':
            reader = Reader(storage, page_size=config.get('page_size', 30))
            reader.open_book(title)

    except RuntimeError as e:
        print(f"\n  {fail('✗')} {e}")


# ============================================================
# 命令: download
# ============================================================

def cmd_download(args):
    """从 Z-Library URL 下载书籍"""
    url = args.url

    try:
        crawler = _get_crawler()
    except RuntimeError as e:
        print(f"\n  {fail('✗')} {e}\n")
        return

    storage = _get_storage()

    print()
    spinner = Spinner('获取书籍信息...')
    spinner.tick()
    try:
        details = crawler.get_book_details(url)
        spinner.end('详情获取成功')
    except RuntimeError as e:
        spinner.end(str(e), success=False)
        return

    _print_book_details(details)

    choice = input(f"\n  {tip('是否下载?')} {mute('(Y/n)')}: ").strip().lower()
    if choice == 'n':
        print()
        return

    _do_download(crawler, storage, details)


# ============================================================
# 命令: read
# ============================================================

def cmd_read(args):
    """阅读已下载的书籍"""
    storage = _get_storage()

    if args.title:
        if storage.has_book(args.title):
            reader = Reader(storage, page_size=config.get('page_size', 30))
            reader.open_book(args.title, use_terminal=args.terminal)
        else:
            print(f"\n  {warn('未找到书籍')}「{args.title}」")
            print(f"  {mute('提示: 使用 list 命令查看已下载的书籍')}\n")
    else:
        books = storage.list_books()
        if not books:
            print(f"\n  {warn('还没有下载任何书籍。')}")
            print(f"  {mute('提示: 使用 search 命令搜索并下载书籍')}\n")
            return

        print(f"\n  {title('📚 已下载的书籍')}")
        print(f"  {mute('共 ' + str(len(books)) + ' 本')}\n")

        # 表格
        headers = ['序号', '书名', '作者', '格式', '大小']
        widths = [6, 32, 16, 8, 10]
        rows = []
        for i, b in enumerate(books, 1):
            t = b['title'][:30] + '..' if len(b['title']) > 32 else b['title']
            a = b['author'][:14] + '..' if len(b['author']) > 16 else b['author']
            f = b['file_format'] or '?'
            s = b['file_size'] or '?'
            rows.append([dye(str(i), S.B_GREEN), t, a, hl(f.upper() if f != '?' else f), s])

        print(table(headers, rows, widths))
        print()

        try:
            choice = input(f"  {field('输入序号')} {mute('开始阅读')}  {mute('q 退出')}: ").strip()
            if choice.lower() == 'q':
                print()
                return
            idx = int(choice) - 1
            if 0 <= idx < len(books):
                reader = Reader(storage, page_size=config.get('page_size', 30))
                reader.open_book(books[idx]['title'], use_terminal=args.terminal)
            else:
                print(f"  {warn('无效序号')}")
        except (ValueError, EOFError):
            print(f"  {mute('已取消')}")
        print()


# ============================================================
# 命令: list
# ============================================================

def cmd_list(args):
    """列出已下载的书籍"""
    storage = _get_storage()
    books = storage.list_books()

    if not books:
        print(f"\n  {warn('还没有下载任何书籍。')}")
        print(f"  {mute('提示: 使用 search 命令搜索并下载书籍')}\n")
        return

    print(f"\n  {title('📚 我的书架')}  {mute('共 ' + str(len(books)) + ' 本')}\n")

    headers = ['书名', '作者', '格式', '大小', '下载时间', '最后阅读']
    widths = [28, 14, 8, 12, 18, 18]
    rows = []
    for b in books:
        t = b['title'][:26] + '..' if len(b['title']) > 28 else b['title']
        a = b['author'][:12] + '..' if len(b['author']) > 14 else b['author']
        f = hl(b['file_format'].upper()) if b['file_format'] else '?'
        s = b['file_size'] or '?'
        dl = b['downloaded_at'][:16] if b['downloaded_at'] else '?'
        lr = b['last_read'][:16] if b['last_read'] else mute('未阅读')
        rows.append([t, a, f, s, dl, lr])

    print(table(headers, rows, widths))
    print()


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        prog='book-reader',
        description='电子书爬虫与阅读器 —— Z-Library 搜索、下载、阅读',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python -m book_reader setup                             配置 Z-Library 认证
  python -m book_reader search "Python Programming"       搜索书籍
  python -m book_reader search "Python" --format epub     按格式搜索
  python -m book_reader search "Python" --language english 按语言搜索
  python -m book_reader download <Z-Library-URL>          下载书籍
  python -m book_reader read                              选择并阅读书籍
  python -m book_reader read "Python Cookbook"            直接阅读指定书籍
  python -m book_reader read --terminal "Python Cookbook" EPUB 终端阅读模式
  python -m book_reader list                              查看已下载书籍
        ''',
    )

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # setup
    subparsers.add_parser('setup', help='配置 Z-Library 认证令牌')

    # search
    p = subparsers.add_parser('search', help='搜索 Z-Library 书籍')
    p.add_argument('keyword', help='搜索关键词')
    p.add_argument('--format', choices=['epub', 'pdf', 'mobi'], default=None,
                   help='按文件格式过滤')
    p.add_argument('--language', default=None,
                   help='按语言过滤 (如 english, chinese)')

    # download
    p = subparsers.add_parser('download', help='从 Z-Library URL 下载书籍')
    p.add_argument('url', help='Z-Library 书籍页面 URL')

    # read
    p = subparsers.add_parser('read', help='阅读已下载的书籍')
    p.add_argument('title', nargs='?', default=None, help='书名（不指定则列出书架）')
    p.add_argument('--terminal', action='store_true',
                   help='EPUB 终端阅读模式（提取文本在终端显示）')

    # list
    subparsers.add_parser('list', help='列出已下载的书籍')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    dispatch = {
        'setup': cmd_setup,
        'search': cmd_search,
        'download': cmd_download,
        'read': cmd_read,
        'list': cmd_list,
    }

    handler = dispatch.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            print(f"\n\n  {mute('操作已取消')}\n")
        except Exception as e:
            print(f"\n  {fail('✗')} {e}\n")


if __name__ == '__main__':
    main()
