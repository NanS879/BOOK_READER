"""阅读器 —— 系统默认应用打开 + EPUB 终端彩色阅读"""
import os
import subprocess
import sys
from typing import Optional

from .storage import Storage
from .console import (
    ok, fail, warn, tip, hl, strong, mute, title, field, dye, S,
    rule, header,
)


# ---- 跨平台单键输入 ----

def _getch() -> str:
    """读取单个字符（跨平台）"""
    if os.name == 'nt':
        import msvcrt
        ch = msvcrt.getch()
        try:
            return ch.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return ch.decode('gbk')
            except UnicodeDecodeError:
                return '?'
    else:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')


def _term_height() -> int:
    """获取终端高度"""
    try:
        return os.get_terminal_size().lines
    except (ValueError, OSError):
        return 40


class Reader:
    """电子书阅读器 —— 支持系统默认阅读器或终端 EPUB 阅读"""

    def __init__(self, storage: Storage, page_size: int = 30):
        self.storage = storage
        self.page_size = page_size

    # ---- 打开书籍 ----

    def open_book(self, title: str, use_terminal: bool = False,
                  interactive: bool = True) -> bool:
        """打开已下载的书籍"""
        meta = self.storage.load_book_meta(title)
        if not meta:
            return self._unavailable(
                f"未找到书籍: {title}",
                "提示: 请先下载书籍",
                interactive,
            )

        filepath = self.storage.get_book_file_path(title)
        if not filepath or not os.path.exists(filepath):
            return self._unavailable(
                f"书籍文件未找到: {title}",
                None,
                interactive,
            )

        # 更新阅读进度
        self.storage.save_progress(title, {})

        file_format = meta.get('file_format', '').lower()

        if use_terminal and file_format == 'epub':
            self._read_epub_terminal(filepath, title)
            return True
        elif use_terminal:
            if interactive:
                print(f"\n  {warn('终端阅读模式仅支持 EPUB')}  当前格式: {file_format}")
                print(f"  {tip('将使用系统默认应用打开...')}")
                self._pause("按 Enter 继续...")
            return self._open_system(filepath, interactive=interactive)
        else:
            return self._open_system(filepath, interactive=interactive)

    # ---- 系统默认应用 ----

    def _open_system(self, filepath: str, interactive: bool = True) -> bool:
        """用系统默认应用打开文件"""
        if interactive:
            print(f"\n  {tip('📖')} 正在打开: {strong(os.path.basename(filepath))}")
        try:
            if os.name == 'nt':
                os.startfile(filepath)
            elif sys.platform == 'darwin':
                subprocess.run(['open', filepath], check=True)
            else:
                subprocess.run(['xdg-open', filepath], check=True)
            if interactive:
                print(f"  {ok('✓')} 书籍已在默认阅读器中打开。\n")
            return True
        except Exception as e:
            if not interactive:
                raise RuntimeError(f"无法打开文件: {e}") from e
            print(f"  {fail('✗')} 无法打开: {e}")
            print(f"  {mute('文件位置:')} {filepath}\n")
            return False

    def _unavailable(self, message: str, hint: Optional[str],
                     interactive: bool) -> bool:
        if not interactive:
            raise FileNotFoundError(message)
        print(f"\n  {warn(message)}")
        if hint:
            print(f"  {mute(hint)}")
        self._pause("按 Enter 返回...")
        return False

    @staticmethod
    def _pause(message: str):
        try:
            input(f"  {mute(message)}")
        except (EOFError, KeyboardInterrupt):
            pass

    # ---- EPUB 终端阅读 ----

    def _read_epub_terminal(self, filepath: str, title: str):
        """提取 EPUB 文本内容并在终端中分页阅读"""
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"\n  {fail('缺少依赖')}: ebooklib, beautifulsoup4")
            print(f"  {mute('请运行: pip install ebooklib beautifulsoup4')}")
            input(f"  {mute('按 Enter 返回...')}")
            return

        # 解析 EPUB
        print(f"\n  {tip('⠏')} 正在解析 EPUB...", end='', flush=True)
        try:
            book = epub.read_epub(filepath)
            sys.stdout.write(f"\r  {ok('✓')} EPUB 解析完成    \n")
        except Exception as e:
            sys.stdout.write(f"\r  {fail('✗')} 无法解析: {e}\n")
            input(f"  {mute('按 Enter 返回...')}")
            return

        # 提取文档项
        spine_items = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            spine_items.append(item)

        if not spine_items:
            print(f"  {warn('此 EPUB 中没有可读取的内容。')}")
            input(f"  {mute('按 Enter 返回...')}")
            return

        # 提取文本
        all_sections: list = []
        for item in spine_items:
            try:
                content = item.get_content().decode('utf-8')
            except UnicodeDecodeError:
                try:
                    content = item.get_content().decode('latin-1')
                except Exception:
                    continue

            soup = BeautifulSoup(content, 'html.parser')
            heading = ''
            for h in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                h_text = h.get_text(strip=True)
                if h_text:
                    heading = h_text
                    break
            if not heading:
                title_tag = soup.find('title')
                if title_tag:
                    heading = title_tag.get_text(strip=True)

            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if lines:
                all_sections.append({
                    'title': heading or f"章节 {len(all_sections) + 1}",
                    'lines': lines,
                })

        if not all_sections:
            print(f"  {warn('无法从此 EPUB 中提取文本内容。')}")
            input(f"  {mute('按 Enter 返回...')}")
            return

        # 终端阅读主循环
        section_idx = 0
        line_pos = 0
        running = True

        while running:
            _clear_screen()
            height = _term_height()
            page_lines = max(10, height - 6)

            section = all_sections[section_idx]
            lines = section['lines']
            total_pages = max(1, (len(lines) + page_lines - 1) // page_lines)
            current_page = line_pos // page_lines + 1

            # ---- 顶部信息栏 ----
            print(dye('╔' + '═' * 58 + '╗', S.B_CYAN))
            print(dye('║', S.B_CYAN) + f"  《{title}》".center(58) + dye('║', S.B_CYAN))
            print(dye('║', S.B_CYAN) + f"  {section['title'][:54]}".center(58) + dye('║', S.B_CYAN))
            info_line = f"章节 {section_idx + 1}/{len(all_sections)} | 第 {current_page}/{total_pages} 页"
            print(dye('║', S.B_CYAN) + f"  {mute(info_line)}".center(58) + dye('║', S.B_CYAN))
            print(dye('╚' + '═' * 58 + '╝', S.B_CYAN))

            # ---- 正文 ----
            start = (current_page - 1) * page_lines
            end = min(start + page_lines, len(lines))
            for line in lines[start:end]:
                print(line)

            # 填充空白
            remaining = page_lines - (end - start)
            for _ in range(remaining):
                print()

            # ---- 底部操作栏 ----
            print(dye('─' * 60, S.DIM))
            keys = [
                (tip('Enter/空格'), '下一页'),
                (tip('b'), '上页'),
                (tip('n'), '下章'),
                (tip('p'), '上章'),
                (tip('j'), '跳转'),
                (tip('t'), '目录'),
                (tip('q'), '退出'),
            ]
            hint = '  '.join(f"{k} {v}" for k, v in keys)
            print(dye(hint, S.DIM))
            print(dye('─' * 60, S.DIM))

            # 输入处理
            ch = _getch().lower()

            if ch in ('\r', '\n', ' '):
                new_pos = line_pos + page_lines
                if new_pos < len(lines):
                    line_pos = new_pos
                elif section_idx < len(all_sections) - 1:
                    section_idx += 1
                    line_pos = 0
            elif ch == 'b':
                line_pos = max(0, line_pos - page_lines)
            elif ch == 'n':
                if section_idx < len(all_sections) - 1:
                    section_idx += 1
                    line_pos = 0
            elif ch == 'p':
                if section_idx > 0:
                    section_idx -= 1
                    line_pos = 0
            elif ch == 'j':
                print(f"\n  请输入章节序号 (1-{len(all_sections)}): ", end='', flush=True)
                try:
                    num = int(input())
                    if 1 <= num <= len(all_sections):
                        section_idx = num - 1
                        line_pos = 0
                except (ValueError, EOFError):
                    pass
            elif ch == 't':
                self._show_epub_catalog(all_sections, title)
            elif ch in ('q', '\x1b'):
                running = False

        print(f"\n  {mute('已退出阅读。')}\n")

    def _show_epub_catalog(self, sections: list, title: str):
        """显示 EPUB 章节目录"""
        _clear_screen()
        height = _term_height()
        page_size = height - 5
        page = 0
        total_pages = max(1, (len(sections) + page_size - 1) // page_size)

        while True:
            _clear_screen()
            start = page * page_size
            end = min(start + page_size, len(sections))

            print(dye('╔' + '═' * 58 + '╗', S.B_CYAN))
            catalog_title = f"目录 - 《{title}》"
            print(dye('║', S.B_CYAN) + f"  {strong(catalog_title[:54])}".center(58) + dye('║', S.B_CYAN))
            print(dye('║', S.B_CYAN) + f"  {mute(f'第 {page + 1}/{total_pages} 页')}".center(58) + dye('║', S.B_CYAN))
            print(dye('╠' + '═' * 58 + '╣', S.B_CYAN))

            for i in range(start, min(end, len(sections))):
                sec = sections[i]
                line = f"[{i + 1:04d}] {sec['title'][:48]}"
                print(dye('║', S.B_CYAN) + f'  {line}'.ljust(58) + dye('║', S.B_CYAN))

            # 填充
            for _ in range(page_size - (end - start)):
                print(dye('║', S.B_CYAN) + ' ' * 58 + dye('║', S.B_CYAN))

            print(dye('╚' + '═' * 58 + '╝', S.B_CYAN))
            print(dye(f"  {tip('n')} 下一页  {tip('p')} 上一页  {tip('q')} 返回", S.DIM))

            ch = _getch().lower()
            if ch == 'n' and page < total_pages - 1:
                page += 1
            elif ch == 'p' and page > 0:
                page -= 1
            elif ch in ('q', '\x1b'):
                break
