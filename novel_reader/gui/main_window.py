"""主窗口 —— 选项卡式桌面应用"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading

from ..config import config
from .search_tab import SearchTab
from .library_tab import LibraryTab
from .settings_tab import SettingsTab


class NovelReaderApp:
    """novel-reader 桌面应用主窗口

    Parameters:
        font_family: 从 init_check 检测到的可用字体族。为 None 时使用 TkDefaultFont。
    """

    def __init__(self, font_family: str = None):
        self._ui_thread_id = threading.get_ident()
        self._shutting_down = False
        self.font_family = font_family or 'TkDefaultFont'

        self.root = tk.Tk()
        self.root.title("Novel Reader - 电子书阅读器")
        self.root.geometry("1040x720")
        self.root.minsize(860, 560)

        # 优雅关闭
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.colors = {
            'bg': '#f4f7fb',
            'panel': '#ffffff',
            'panel_alt': '#eef4ff',
            'text': '#172033',
            'muted': '#667085',
            'primary': '#2563eb',
            'primary_dark': '#1d4ed8',
            'border': '#d8e0ea',
            'success': '#16803c',
            'warning': '#b45309',
            'danger': '#b42318',
        }
        self.root.configure(bg=self.colors['bg'])

        # 样式
        self._setup_style()

        # 标题栏
        self._build_header()

        # 选项卡
        self.notebook = ttk.Notebook(self.root, style='App.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 12))

        self.search_tab = SearchTab(self.notebook, self)
        self.library_tab = LibraryTab(self.notebook, self)
        self.settings_tab = SettingsTab(self.notebook, self)

        self.notebook.add(self.search_tab.frame, text="  🔍 搜索  ")
        self.notebook.add(self.library_tab.frame, text="  📚 书架  ")
        self.notebook.add(self.settings_tab.frame, text="  ⚙ 设置  ")

        # 状态栏
        self._build_statusbar()

        # 启动时检查认证
        self.root.after(300, self._check_auth_on_start)

    # ---- 优雅关闭 ----

    def _on_close(self):
        """处理窗口关闭事件 —— 确认后退出"""
        self._shutting_down = True
        self.root.destroy()

    # ---- 样式 ----

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use('clam')
        except Exception:
            pass

        bg = self.colors['bg']
        panel = self.colors['panel']
        text = self.colors['text']
        muted = self.colors['muted']
        primary = self.colors['primary']
        border = self.colors['border']

        ff = self.font_family
        default_font = (ff, 10)
        self.root.option_add('*Font', default_font)

        style.configure('.', background=bg, foreground=text, font=default_font)
        style.configure('TFrame', background=bg)
        style.configure('Panel.TFrame', background=panel, relief='solid', borderwidth=1)
        style.configure('Soft.TFrame', background=self.colors['panel_alt'])
        style.configure('TLabelframe', background=panel, bordercolor=border,
                        relief='solid', borderwidth=1)
        style.configure('TLabelframe.Label', background=bg, foreground=text,
                        font=(ff, 11, 'bold'))

        style.configure('TLabel', background=bg, foreground=text)
        style.configure('Panel.TLabel', background=panel, foreground=text)
        style.configure('Muted.TLabel', background=bg, foreground=muted)
        style.configure('PanelMuted.TLabel', background=panel, foreground=muted)
        style.configure('Title.TLabel', background=bg, foreground=text,
                        font=(ff, 17, 'bold'))
        style.configure('Hero.TLabel', background=self.colors['panel_alt'],
                        foreground=text, font=(ff, 12, 'bold'))
        style.configure('Heading.TLabel', background=bg, foreground=text,
                        font=(ff, 12, 'bold'))
        style.configure('PanelHeading.TLabel', background=panel, foreground=text,
                        font=(ff, 12, 'bold'))
        style.configure('Status.TLabel', background=bg, foreground=muted,
                        font=(ff, 9))

        style.configure('TButton', font=default_font, padding=(12, 7),
                        background='#ffffff', foreground=text, bordercolor=border)
        style.map('TButton',
                  background=[('active', '#f2f6fc'), ('disabled', '#eef1f5')],
                  foreground=[('disabled', '#98a2b3')])
        style.configure('Primary.TButton', font=(ff, 10, 'bold'),
                        padding=(14, 8), background=primary, foreground='#ffffff',
                        bordercolor=primary, lightcolor=primary, darkcolor=primary)
        style.map('Primary.TButton',
                  background=[('active', self.colors['primary_dark']),
                              ('disabled', '#b9cdfa')],
                  foreground=[('disabled', '#f7f9ff')])
        style.configure('Small.TButton', font=(ff, 9),
                        padding=(9, 5))
        style.configure('Danger.TButton', font=(ff, 9),
                        padding=(9, 5), foreground=self.colors['danger'])

        style.configure('TEntry', padding=(8, 6), fieldbackground='#ffffff',
                        bordercolor=border, lightcolor=primary, darkcolor=border)
        style.configure('TCombobox', padding=(7, 5), fieldbackground='#ffffff',
                        bordercolor=border, arrowcolor=muted)
        style.configure('TSpinbox', padding=(7, 5), fieldbackground='#ffffff',
                        bordercolor=border)

        style.configure('App.TNotebook', background=bg, borderwidth=0, tabmargins=(0, 6, 0, 0))
        style.configure('App.TNotebook.Tab', padding=(18, 9),
                        font=(ff, 10, 'bold'),
                        background='#e8eef7', foreground=muted)
        style.map('App.TNotebook.Tab',
                  background=[('selected', panel), ('active', '#f6f9fe')],
                  foreground=[('selected', primary), ('active', text)])

        style.configure('Treeview', rowheight=34, borderwidth=0,
                        background='#ffffff', fieldbackground='#ffffff',
                        foreground=text, font=(ff, 9))
        style.configure('Treeview.Heading', padding=(8, 7),
                        background='#edf2f7', foreground='#344054',
                        font=(ff, 9, 'bold'),
                        relief='flat')
        style.map('Treeview', background=[('selected', '#dbeafe')],
                  foreground=[('selected', '#111827')])

        style.configure('Horizontal.TProgressbar', troughcolor='#e5edf7',
                        background=primary, bordercolor=border,
                        lightcolor=primary, darkcolor=primary)

    def _build_header(self):
        header = ttk.Frame(self.root, style='Soft.TFrame', padding=(18, 14))
        header.pack(fill=tk.X, padx=18, pady=(16, 10))

        left = ttk.Frame(header, style='Soft.TFrame')
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(left, text="📖 Novel Reader", style='Title.TLabel',
                  background=self.colors['panel_alt']).pack(anchor=tk.W)
        ttk.Label(left, text="搜索、下载、管理和阅读电子书",
                  style='Muted.TLabel', background=self.colors['panel_alt']).pack(
            anchor=tk.W, pady=(4, 0))

        self.auth_badge_var = tk.StringVar()
        ttk.Label(header, textvariable=self.auth_badge_var, style='Hero.TLabel',
                  padding=(14, 8)).pack(side=tk.RIGHT)
        self._refresh_auth_badge()

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="就绪")
        bar = ttk.Frame(self.root, padding=(12, 6))
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_label = ttk.Label(
            bar, textvariable=self.status_var, style='Status.TLabel')
        self.status_label.pack(side=tk.LEFT, padx=8, pady=3)

    def _check_auth_on_start(self):
        try:
            if not config.has_auth():
                self.notebook.select(self.settings_tab.frame)
                self.set_status("请先配置 Z-Library 认证令牌")
        except Exception as e:
            self.set_status(f"配置检查失败: {e}")
        self._refresh_auth_badge()

    # ---- 公共接口 ----

    def set_status(self, text: str):
        self.run_on_ui(lambda: self.status_var.set(text))

    def run_on_ui(self, callback):
        """在 Tk 主线程执行 UI 操作。"""
        if self._shutting_down:
            return
        if threading.get_ident() == self._ui_thread_id:
            callback()
        else:
            self.root.after(0, callback)

    def run_in_thread(self, target, args=(), callback=None, error_callback=None):
        """在后台线程运行任务，避免阻塞 UI"""
        def wrapper():
            try:
                result = target(*args)
                if callback and not self._shutting_down:
                    self.root.after(0, lambda result=result: callback(result))
            except Exception as e:
                msg = str(e) or e.__class__.__name__
                if error_callback and not self._shutting_down:
                    self.root.after(0, lambda msg=msg: error_callback(msg))
                elif not self._shutting_down:
                    self.root.after(0, lambda msg=msg: messagebox.showerror("错误", msg))
        t = threading.Thread(target=wrapper, daemon=True)
        t.start()

    def refresh_library(self):
        self.library_tab.refresh()

    def switch_to_library(self):
        self.notebook.select(self.library_tab.frame)

    def reset_crawler(self):
        if hasattr(self, 'search_tab'):
            self.search_tab.crawler = None
        self._refresh_auth_badge()

    def _refresh_auth_badge(self):
        if hasattr(self, 'auth_badge_var'):
            self.auth_badge_var.set("认证已配置" if config.has_auth() else "需要配置认证")

    def run(self):
        self.root.mainloop()
