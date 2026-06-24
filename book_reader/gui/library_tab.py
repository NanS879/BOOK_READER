"""书架选项卡 —— 查看和管理已下载的书籍"""
import json
import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox

from ..config import config
from ..storage import Storage
from ..reader import Reader


# ============================================================
# 跨平台鼠标滚轮辅助
# ============================================================

def _bind_mousewheel(widget):
    """为指定 widget 绑定跨平台鼠标滚轮事件。

    支持: Treeview, Text, Canvas, Listbox
    """
    def _handler(event):
        if hasattr(event, 'delta'):
            delta = event.delta  # Windows: ±120/格
        elif hasattr(event, 'num'):
            delta = -1 if event.num == 4 else 1  # Linux: 4=up, 5=down
        else:
            return

        if isinstance(widget, ttk.Treeview):
            widget.yview_scroll(-1 if delta > 0 else 1, 'units')
        elif isinstance(widget, tk.Text):
            widget.yview_scroll(-1 if delta > 0 else 1, 'units')
        elif isinstance(widget, tk.Canvas):
            widget.yview_scroll(-1 if delta > 0 else 1, 'units')
        elif isinstance(widget, tk.Listbox):
            widget.yview_scroll(-1 if delta > 0 else 1, 'units')

        return 'break'

    widget.bind('<MouseWheel>', _handler, add='+')
    widget.bind('<Button-4>', _handler, add='+')
    widget.bind('<Button-5>', _handler, add='+')


class LibraryTab:
    """书架管理"""

    def __init__(self, parent, app):
        self.app = app
        self.storage = Storage(config.books_dir, config.progress_file)
        self.book_items = {}

        self.frame = ttk.Frame(parent, padding=(14, 14))
        self._build_ui()

    def _build_ui(self):
        # 工具栏
        bar = ttk.Frame(self.frame, style='Panel.TFrame', padding=(14, 12))
        bar.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(bar, text="已下载的书籍", style='PanelHeading.TLabel').pack(side=tk.LEFT)
        self.count_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.count_var,
                  style='PanelMuted.TLabel').pack(side=tk.LEFT, padx=(10, 0))
        ttk.Button(bar, text="刷新", command=self.refresh,
                   style='Small.TButton').pack(side=tk.RIGHT)

        # 书籍列表
        list_frame = ttk.Frame(self.frame, style='Panel.TFrame', padding=(1, 1))
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('title', 'author', 'format', 'size', 'downloaded', 'last_read')
        self.tree = ttk.Treeview(list_frame, columns=columns,
                                 show='headings', selectmode='browse')
        self.tree.heading('title', text='书名')
        self.tree.heading('author', text='作者')
        self.tree.heading('format', text='格式')
        self.tree.heading('size', text='大小')
        self.tree.heading('downloaded', text='下载时间')
        self.tree.heading('last_read', text='最后阅读')

        self.tree.column('title', width=260)
        self.tree.column('author', width=130)
        self.tree.column('format', width=55, anchor='center')
        self.tree.column('size', width=70, anchor='center')
        self.tree.column('downloaded', width=130)
        self.tree.column('last_read', width=130)
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

        self.tree.bind('<Double-1>', lambda e: self._open_book())

        # 鼠标滚轮滚动
        _bind_mousewheel(self.tree)

        # 操作按钮
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(btn_frame, text="打开阅读", command=self._open_book,
                   style='Small.TButton').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="终端阅读 (EPUB)", command=self._open_terminal,
                   style='Small.TButton').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="打开目录", command=self._open_folder,
                   style='Small.TButton').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(btn_frame, text="删除", command=self._delete_book,
                   style='Danger.TButton').pack(side=tk.LEFT, padx=(0, 8))

    # ---- 数据加载 ----

    def refresh(self):
        self.book_items.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        books = self.storage.list_books()
        self.count_var.set(f"共 {len(books)} 本")

        if not books:
            self.tree.insert('', tk.END, values=(
                '书架是空的', '可在搜索页下载电子书', '', '', '', ''),
                tags=('empty',))
            self.app.set_status("书架暂无书籍")
            return

        for i, b in enumerate(books, 1):
            fmt = b['file_format'].lstrip('.').upper() if b['file_format'] else '?'
            dl = self._format_time(b['downloaded_at']) if b['downloaded_at'] else '?'
            lr = self._format_time(b['last_read']) if b['last_read'] else '未阅读'
            tag = 'odd' if i % 2 else 'even'
            iid = self.tree.insert('', tk.END, values=(
                b['title'], b['author'] or '?', fmt,
                b['file_size'] or '?', dl, lr), tags=(tag,))
            self.book_items[iid] = b['title']

        self.app.set_status(f"书架共 {len(books)} 本书")

    # ---- 操作 ----

    def _open_book(self):
        title = self._get_selected_title()
        if not title:
            return
        self.open_book_by_title(title)

    def open_book_by_title(self, title: str):
        self.app.set_status(f"正在打开《{title}》...")
        reader = Reader(self.storage, page_size=config.get('page_size', 30))
        try:
            reader.open_book(title, interactive=False)
            self.refresh()
            self.app.set_status(f"已打开《{title}》")
        except Exception as e:
            self.app.set_status(f"打开失败: {e}")
            messagebox.showerror("打开失败", str(e))

    def _open_terminal(self):
        title = self._get_selected_title()
        if not title:
            return

        meta = self.storage.load_book_meta(title)
        file_format = (meta or {}).get('file_format', '').lstrip('.').lower()
        if file_format != 'epub':
            messagebox.showwarning("提示", "终端阅读仅支持 EPUB 格式")
            return

        try:
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, 'read', '--terminal', title]
            else:
                cmd = [sys.executable, '-m', 'book_reader', 'read', '--terminal', title]

            kwargs = {'cwd': config.base_dir}
            if os.name == 'nt':
                kwargs['creationflags'] = subprocess.CREATE_NEW_CONSOLE
            subprocess.Popen(cmd, **kwargs)
            self.app.set_status(f"已在独立终端打开《{title}》")
        except Exception as e:
            self.app.set_status(f"终端阅读启动失败: {e}")
            messagebox.showerror("启动失败", str(e))

    def _open_folder(self):
        title = self._get_selected_title()
        if not title:
            return

        book_dir = self.storage._book_dir(title)
        if not os.path.isdir(book_dir):
            messagebox.showwarning("提示", "未找到该书籍的本地目录")
            return

        try:
            if os.name == 'nt':
                os.startfile(book_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', book_dir])
            else:
                subprocess.Popen(['xdg-open', book_dir])
            self.app.set_status(f"已打开《{title}》所在目录")
        except Exception as e:
            self.app.set_status(f"打开目录失败: {e}")
            messagebox.showerror("打开目录失败", str(e))

    def _delete_book(self):
        title = self._get_selected_title()
        if not title:
            return

        if not messagebox.askyesno("确认删除",
                                   f"确定要删除《{title}》吗？\n\n此操作不可恢复。"):
            return

        try:
            book_dir = os.path.abspath(self.storage._book_dir(title))
            books_dir = os.path.abspath(self.storage.books_dir)
            if os.path.commonpath([books_dir, book_dir]) != books_dir:
                raise RuntimeError("书籍目录不在书架目录内，已取消删除")

            if os.path.exists(book_dir):
                shutil.rmtree(book_dir)

            # 清理进度
            progress = self.storage.load_all_progress()
            if title in progress:
                del progress[title]
                with open(self.storage.progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.app.set_status(f"删除失败: {e}")
            messagebox.showerror("删除失败", str(e))
            return

        self.refresh()
        self.app.set_status(f"已删除《{title}》")

    def _get_selected_title(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一本书")
            return None
        title = self.book_items.get(sel[0])
        if not title:
            messagebox.showwarning("提示", "请选择一本有效的书")
            return None
        return title

    @staticmethod
    def _format_time(value: str) -> str:
        return value[:16].replace('T', ' ')
