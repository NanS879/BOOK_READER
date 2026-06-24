"""搜索选项卡 —— 搜索书籍、查看详情、下载"""
import os
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from ..config import config
from ..storage import Storage
from ..crawler import get_crawler
from ..crawler.base import BookMeta
from ..reader import Reader


# ============================================================
# 跨平台鼠标滚轮辅助
# ============================================================

def _bind_mousewheel(widget, on_scroll=None):
    """为指定 widget 绑定跨平台鼠标滚轮事件。

    Args:
        widget: 要绑定的 tkinter widget (Treeview / Text / Canvas 等)
        on_scroll: 可选的自定义滚动回调，签名为 callback(delta: int)
                   若为 None，则对 Treeview 调用 yview_scroll，
                   对 Text 调用 yview_scroll。
    """
    def _handler(event):
        if hasattr(event, 'delta'):
            # Windows: delta 通常为 ±120 每"格"
            delta = event.delta
        elif hasattr(event, 'num'):
            # Linux: Button-4=上滚(-1)  Button-5=下滚(+1)
            delta = -1 if event.num == 4 else 1
        else:
            return

        if on_scroll:
            on_scroll(delta)
            return 'break'

        # 默认行为：根据 widget 类型滚动
        if isinstance(widget, ttk.Treeview):
            amount = -1 if delta > 0 else 1
            widget.yview_scroll(amount, 'units')
        elif isinstance(widget, tk.Text):
            amount = -1 if delta > 0 else 1
            widget.yview_scroll(amount, 'units')
        elif isinstance(widget, tk.Canvas):
            amount = -1 if delta > 0 else 1
            widget.yview_scroll(amount, 'units')
        elif isinstance(widget, tk.Listbox):
            amount = -1 if delta > 0 else 1
            widget.yview_scroll(amount, 'units')

        return 'break'

    # Windows / macOS
    widget.bind('<MouseWheel>', _handler, add='+')
    # Linux
    widget.bind('<Button-4>', _handler, add='+')
    widget.bind('<Button-5>', _handler, add='+')


class SearchTab:
    """搜索 Z-Library 书籍"""

    def __init__(self, parent, app):
        self.app = app
        self.crawler = None
        self.storage = Storage(config.books_dir, config.progress_file)
        self.results = []  # List[BookInfo]
        self.busy = False

        self.frame = ttk.Frame(parent, padding=(14, 14))
        self._build_ui()

    def _ensure_crawler(self):
        if not config.has_auth():
            messagebox.showwarning("未配置认证", "请先在「设置」选项卡中配置 Z-Library 认证令牌。")
            return None
        if self.crawler is None:
            try:
                self.crawler = get_crawler()
            except RuntimeError as e:
                messagebox.showerror("错误", str(e))
                return None
        return self.crawler

    # ---- UI ----

    def _build_ui(self):
        # 搜索栏
        bar = ttk.Frame(self.frame, style='Panel.TFrame', padding=(14, 12))
        bar.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(bar, text="关键词", style='Panel.TLabel').pack(side=tk.LEFT)
        self.keyword_var = tk.StringVar()
        self.keyword_entry = ttk.Entry(bar, textvariable=self.keyword_var, width=34)
        self.keyword_entry.pack(side=tk.LEFT, padx=(6, 8))
        self.keyword_entry.bind('<Return>', lambda e: self._do_search())

        ttk.Label(bar, text="格式", style='Panel.TLabel').pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value='全部')
        fmt_combo = ttk.Combobox(bar, textvariable=self.format_var,
                                 values=['全部', 'epub', 'pdf', 'mobi'],
                                 state='readonly', width=6)
        fmt_combo.pack(side=tk.LEFT, padx=(4, 8))

        ttk.Label(bar, text="语言", style='Panel.TLabel').pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value='全部')
        lang_combo = ttk.Combobox(bar, textvariable=self.lang_var,
                                  values=['全部', 'english', 'chinese', 'russian',
                                          'spanish', 'french', 'german', 'japanese'],
                                  state='readonly', width=8)
        lang_combo.pack(side=tk.LEFT, padx=(4, 10))

        self.search_btn = ttk.Button(
            bar, text="🔍 搜索", command=self._do_search, style='Primary.TButton')
        self.search_btn.pack(side=tk.LEFT)

        self.result_count_var = tk.StringVar(value="尚未搜索")
        ttk.Label(bar, textvariable=self.result_count_var,
                  style='PanelMuted.TLabel').pack(side=tk.RIGHT)

        # 结果列表
        list_frame = ttk.Frame(self.frame, style='Panel.TFrame', padding=(1, 1))
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('#', 'title', 'author', 'format', 'size')
        self.tree = ttk.Treeview(list_frame, columns=columns,
                                 show='headings', selectmode='browse')
        self.tree.heading('#', text='#')
        self.tree.heading('title', text='书名')
        self.tree.heading('author', text='作者')
        self.tree.heading('format', text='格式')
        self.tree.heading('size', text='大小')

        self.tree.column('#', width=40, anchor='center')
        self.tree.column('title', width=320)
        self.tree.column('author', width=140)
        self.tree.column('format', width=60, anchor='center')
        self.tree.column('size', width=80, anchor='center')
        self.tree.tag_configure('odd', background='#fbfdff')
        self.tree.tag_configure('even', background='#ffffff')
        self.tree.tag_configure('empty', foreground='#667085')

        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.tree.bind('<Double-1>', lambda e: self._show_details())

        # 鼠标滚轮滚动
        _bind_mousewheel(self.tree)

        # 操作按钮
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        self.details_btn = ttk.Button(btn_frame, text="查看详情", command=self._show_details,
                                      style='Small.TButton')
        self.details_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.download_btn = ttk.Button(btn_frame, text="下载选中",
                                       command=self._download_selected,
                                       style='Primary.TButton')
        self.download_btn.pack(side=tk.LEFT, padx=(0, 8))

        # 进度条
        self.progress_frame = ttk.Frame(self.frame, style='Panel.TFrame', padding=(12, 10))
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            self.progress_frame, variable=self.progress_var, mode='determinate')
        self.progress_label = ttk.Label(self.progress_frame, text='',
                                        style='PanelMuted.TLabel')
        self.progress_label.pack(fill=tk.X, pady=(0, 6))
        self.progress_bar.pack(fill=tk.X)
        # 初始隐藏

    # ---- 搜索逻辑 ----

    def _do_search(self):
        if self.busy:
            return
        crawler = self._ensure_crawler()
        if not crawler:
            return

        keyword = self.keyword_var.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入搜索关键词")
            return

        self._set_busy(True, search_text='搜索中...')
        self.app.set_status(f"正在搜索「{keyword}」...")
        self._clear_results()
        self.result_count_var.set("搜索中...")

        filters = {}
        if self.format_var.get() != '全部':
            filters['extensions'] = [self.format_var.get()]
        if self.lang_var.get() != '全部':
            filters['languages'] = [self.lang_var.get()]

        def do():
            return crawler.search(keyword, **filters)

        def on_done(results):
            self._set_busy(False)
            self.results = results
            if not results:
                self.app.set_status("未找到相关书籍")
                self.result_count_var.set("0 个结果")
                self.tree.insert('', tk.END, values=('', '没有找到匹配的书籍', '', '', ''),
                                 tags=('empty',))
            else:
                self.app.set_status(f"找到 {len(results)} 个结果")
                self.result_count_var.set(f"{len(results)} 个结果")
                for i, book in enumerate(results, 1):
                    fmt_val = book.file_format or '?'
                    size_val = book.file_size or '?'
                    tag = 'odd' if i % 2 else 'even'
                    self.tree.insert('', tk.END, values=(
                        i, book.title, book.author or '未知', fmt_val, size_val),
                        tags=(tag,))

        def on_err(msg):
            self._set_busy(False)
            self.result_count_var.set("搜索失败")
            self.app.set_status(f"搜索失败: {msg}")
            messagebox.showerror("搜索失败", msg)

        self.app.run_in_thread(do, callback=on_done, error_callback=on_err)

    def _clear_results(self):
        self.results = []
        for item in self.tree.get_children():
            self.tree.delete(item)

    # ---- 详情和下载 ----

    def _show_details(self):
        if self.busy:
            return
        book = self._get_selected_book()
        if not book:
            return

        crawler = self._ensure_crawler()
        if not crawler:
            return

        self._set_busy(True, search_text='加载中...')
        self.app.set_status("正在获取书籍详情...")

        def do():
            return crawler.get_book_details(book.source_url)

        def on_done(details):
            self._set_busy(False)
            self.app.set_status("详情获取完成")
            DetailDialog(self.frame, details, self)

        def on_err(msg):
            self._set_busy(False)
            self.app.set_status(f"获取详情失败: {msg}")
            messagebox.showerror("错误", msg)

        self.app.run_in_thread(do, callback=on_done, error_callback=on_err)

    def _download_selected(self):
        book = self._get_selected_book()
        if not book:
            return
        self._start_download(book)

    def _start_download(self, book):
        if self.busy:
            return
        crawler = self._ensure_crawler()
        if not crawler:
            return

        # 先获取详情
        self._set_busy(True, search_text='下载中...')
        self.app.set_status("正在获取下载信息...")
        self._show_progress("正在获取下载信息...")

        def get_details():
            return crawler.get_book_details(book.source_url)

        def start_dl(details):
            self.app.set_status("正在下载...")
            fmt = (details.file_format or '').lstrip('.') or 'unknown'
            title = details.title
            dest_dir = self.storage._book_dir(title)
            os.makedirs(dest_dir, exist_ok=True)

            self.progress_var.set(0)
            self.progress_label.configure(text='准备下载...')
            last_update = [0.0]

            def prog_cb(current, total, status):
                now = time.monotonic()
                if now - last_update[0] < 0.1 and current != total:
                    return
                last_update[0] = now

                def update():
                    if total and total > 0:
                        pct = min(100, max(0, current / total * 100))
                        self.progress_var.set(pct)
                        size_mb = current / (1024 * 1024)
                        total_mb = total / (1024 * 1024)
                        self.progress_label.configure(
                            text=f"{size_mb:.1f} / {total_mb:.1f} MB ({pct:.0f}%)")
                    elif status:
                        self.progress_label.configure(text=str(status))

                self.app.run_on_ui(update)

            def do_dl():
                return crawler.download(book=details, dest_dir=dest_dir,
                                        progress_callback=prog_cb)

            def dl_done(filepath):
                self._hide_progress()
                self._set_busy(False)

                # 使用实际下载的文件扩展名
                actual_ext = os.path.splitext(filepath)[1].lstrip('.').lower()
                actual_size = self._format_file_size(filepath)

                # 保存元数据
                meta = BookMeta(
                    title=title, author=details.author,
                    description=details.description,
                    source_url=details.source_url,
                    file_format=actual_ext or details.file_format,
                    file_size=actual_size or details.file_size,
                    year=details.year, language=details.language,
                    isbn=details.isbn,
                    filename=os.path.basename(filepath),
                    downloaded_at=datetime.now().isoformat(),
                )
                self.storage.save_book_meta(meta)
                self.app.set_status(f"下载完成: {title}")
                self.app.refresh_library()

                if messagebox.askyesno("下载完成",
                                       f"《{title}》下载完成！\n\n是否打开阅读？"):
                    self._open_downloaded_book(title)

            def dl_err(msg):
                self._hide_progress()
                self._set_busy(False)
                self.app.set_status(f"下载失败: {msg}")
                messagebox.showerror("下载失败", msg)

            self.app.run_in_thread(do_dl, callback=dl_done, error_callback=dl_err)

        def details_err(msg):
            self._hide_progress()
            self._set_busy(False)
            self.app.set_status(f"获取详情失败: {msg}")
            messagebox.showerror("错误", msg)

        self.app.run_in_thread(get_details, callback=start_dl, error_callback=details_err)

    def _get_selected_book(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个搜索结果")
            return None
        values = self.tree.item(sel[0], 'values')
        if not values or not str(values[0]).isdigit():
            messagebox.showwarning("提示", "请先选择一个有效的搜索结果")
            return None
        idx = int(values[0]) - 1
        if 0 <= idx < len(self.results):
            return self.results[idx]
        messagebox.showwarning("提示", "搜索结果已过期，请重新搜索")
        return None

    def _set_busy(self, busy: bool, search_text: str = '🔍 搜索'):
        self.busy = busy
        state = 'disabled' if busy else 'normal'
        self.search_btn.configure(state=state, text=search_text if busy else '🔍 搜索')
        self.details_btn.configure(state=state)
        self.download_btn.configure(state=state)
        self.keyword_entry.configure(state=state)

    def _show_progress(self, text: str):
        self.progress_var.set(0)
        self.progress_label.configure(text=text)
        if not self.progress_frame.winfo_manager():
            self.progress_frame.pack(fill=tk.X, pady=(10, 0))

    def _hide_progress(self):
        self.progress_var.set(0)
        self.progress_label.configure(text='')
        if self.progress_frame.winfo_manager():
            self.progress_frame.pack_forget()

    @staticmethod
    def _format_file_size(filepath: str) -> str:
        """获取文件的人类可读大小"""
        try:
            size = os.path.getsize(filepath)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except OSError:
            return ''

    def _open_downloaded_book(self, title: str):
        reader = Reader(self.storage, page_size=config.get('page_size', 30))
        try:
            reader.open_book(title, interactive=False)
            self.app.set_status(f"已打开《{title}》")
        except Exception as e:
            self.app.set_status(f"打开失败: {e}")
            messagebox.showerror("打开失败", str(e))


class DetailDialog(tk.Toplevel):
    """书籍详情弹窗"""

    def __init__(self, parent, book, search_tab):
        super().__init__(parent)
        self.book = book
        self.search_tab = search_tab

        self.title(f"书籍详情 — {book.title[:40]}")
        self.geometry("620x500")
        self.minsize(560, 420)
        self.configure(bg=search_tab.app.colors['bg'])
        self.transient(parent)

        self._build()
        self._center()
        self.grab_set()
        self.focus_set()

    def _build(self):
        main = ttk.Frame(self, padding=18)
        main.pack(fill=tk.BOTH, expand=True)

        # 书名
        ttk.Label(main, text=self.book.title, style='Heading.TLabel',
                  wraplength=560).pack(anchor=tk.W, pady=(0, 12))

        # 信息行
        info_frame = ttk.Frame(main, style='Panel.TFrame', padding=12)
        info_frame.pack(fill=tk.X, pady=(0, 8))
        info_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)

        fields = [
            ('作者', self.book.author or '未知'),
            ('出版年份', self.book.year),
            ('语言', self.book.language),
            ('格式', self.book.file_format.upper() if self.book.file_format else '?'),
            ('文件大小', self.book.file_size),
            ('ISBN', self.book.isbn),
        ]
        for i, (label, value) in enumerate(fields):
            if value:
                row = i // 2
                col = i % 2
                f = ttk.Frame(info_frame, style='Panel.TFrame')
                f.grid(row=row, column=col, sticky='ew', padx=(0, 18), pady=3)
                ttk.Label(f, text=f"{label}: ", style='PanelMuted.TLabel').pack(side=tk.LEFT)
                ttk.Label(f, text=str(value), style='Panel.TLabel',
                          wraplength=210).pack(side=tk.LEFT)

        # 简介
        ttk.Label(main, text="简介", style='Heading.TLabel').pack(anchor=tk.W, pady=(8, 4))
        desc_frame = ttk.Frame(main, style='Panel.TFrame', padding=1)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 12))
        desc_text = tk.Text(desc_frame, height=10, wrap=tk.WORD, font=('Microsoft YaHei UI', 9),
                            bg='#ffffff', fg='#344054', relief='flat',
                            borderwidth=0, padx=10, pady=10)
        desc_scroll = ttk.Scrollbar(desc_frame, orient=tk.VERTICAL,
                                    command=desc_text.yview)
        desc_text.configure(yscrollcommand=desc_scroll.set)
        desc_text.insert('1.0', (self.book.description or '暂无简介')[:1200])
        desc_text.configure(state='disabled')
        desc_text.grid(row=0, column=0, sticky='nsew')
        desc_scroll.grid(row=0, column=1, sticky='ns')
        desc_frame.columnconfigure(0, weight=1)
        desc_frame.rowconfigure(0, weight=1)

        # 鼠标滚轮滚动
        _bind_mousewheel(desc_text)

        # 按钮
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="下载此书", style='Primary.TButton',
                   command=self._download).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="关闭", command=self.destroy).pack(side=tk.LEFT)

    def _download(self):
        self.destroy()
        self.search_tab._start_download(self.book)

    def _center(self):
        self.update_idletasks()
        parent = self.master.winfo_toplevel()
        x = parent.winfo_rootx() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_rooty() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")
