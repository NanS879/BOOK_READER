"""设置选项卡 —— 认证配置和应用设置"""
import tkinter as tk
from tkinter import ttk, messagebox

from ..config import config
from ..crawler import get_crawler


class SettingsTab:
    """应用设置"""

    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent, padding=(14, 14))
        self._build_ui()

    def _build_ui(self):
        # ==============================================
        # 认证部分
        # ==============================================
        auth_frame = ttk.LabelFrame(self.frame, text="Z-Library 认证", padding=14)
        auth_frame.pack(fill=tk.X, pady=(0, 12))

        # 说明
        info = ("在浏览器中登录 Z-Library 后，按 F12 → Application → Cookies，"
                "复制 remix_userid 和 remix_userkey 的值。")
        ttk.Label(auth_frame, text=info, wraplength=600,
                  style='PanelMuted.TLabel').pack(anchor=tk.W, pady=(0, 12))

        # remix_userid
        row1 = ttk.Frame(auth_frame)
        row1.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row1, text="remix_userid:", width=18).pack(side=tk.LEFT)
        self.uid_var = tk.StringVar(value=config.get('remix_userid', ''))
        ttk.Entry(row1, textvariable=self.uid_var, width=50).pack(side=tk.LEFT, padx=(4, 0))

        # remix_userkey
        row2 = ttk.Frame(auth_frame)
        row2.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(row2, text="remix_userkey:", width=18).pack(side=tk.LEFT)
        self.ukey_var = tk.StringVar(value=config.get('remix_userkey', ''))
        ttk.Entry(row2, textvariable=self.ukey_var, width=50, show='•').pack(
            side=tk.LEFT, padx=(4, 0))

        # 获取令牌的帮助链接
        help_note = (
            "提示: 如果你在中国大陆无法直接访问 Z-Library 网站，"
            "可能需要使用代理或 VPN 先登录获取令牌。"
        )
        ttk.Label(auth_frame, text=help_note, wraplength=600,
                  style='PanelMuted.TLabel').pack(anchor=tk.W, pady=(0, 4))

        # ---- 个人域名 ----
        domain_label = ttk.Label(auth_frame, text="个人域名 (可选):", width=18,
                                 style='Panel.TLabel')
        # 单独一行说明
        ttk.Label(auth_frame, text=(
            "登录 Z-Library 后，进入 Z-access → Web Version 可获取你的个人域名。\n"
            "填写后可大幅提高下载成功率。格式如: https://yourname.z-lib.id"
        ), wraplength=600, style='PanelMuted.TLabel').pack(anchor=tk.W, pady=(8, 2))

        row_domain = ttk.Frame(auth_frame)
        row_domain.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row_domain, text="域名地址:", width=18).pack(side=tk.LEFT)
        self.domain_var = tk.StringVar(value=config.get('personal_domain', ''))
        ttk.Entry(row_domain, textvariable=self.domain_var, width=50).pack(
            side=tk.LEFT, padx=(4, 0))

        # ---- 代理 ----
        ttk.Label(auth_frame, text=(
            "如果你在中国大陆等网络受限地区，需配置代理才能访问 Z-Library。\n"
            "支持 HTTP 代理 (如 http://127.0.0.1:7890) 或 SOCKS5 (如 socks5://127.0.0.1:1080)"
        ), wraplength=600, style='PanelMuted.TLabel').pack(anchor=tk.W, pady=(8, 2))

        row_proxy = ttk.Frame(auth_frame)
        row_proxy.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(row_proxy, text="代理地址:", width=18).pack(side=tk.LEFT)
        self.proxy_var = tk.StringVar(value=config.get('proxy', ''))
        ttk.Entry(row_proxy, textvariable=self.proxy_var, width=50).pack(
            side=tk.LEFT, padx=(4, 0))

        # 保存按钮行
        btn_row = ttk.Frame(auth_frame)
        btn_row.pack(fill=tk.X)
        self.save_auth_btn = ttk.Button(btn_row, text="保存并验证", command=self._save_auth,
                                        style='Primary.TButton')
        self.save_auth_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.auth_status_var = tk.StringVar()
        self._update_auth_status()
        ttk.Label(btn_row, textvariable=self.auth_status_var,
                  style='PanelMuted.TLabel').pack(side=tk.LEFT)

        # ==============================================
        # 偏好设置
        # ==============================================
        pref_frame = ttk.LabelFrame(self.frame, text="偏好设置", padding=14)
        pref_frame.pack(fill=tk.X, pady=(0, 12))

        row3 = ttk.Frame(pref_frame)
        row3.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row3, text="首选格式:", width=16).pack(side=tk.LEFT)
        self.fmt_var = tk.StringVar(value=config.get('preferred_format', 'epub'))
        fmt_combo = ttk.Combobox(row3, textvariable=self.fmt_var,
                                 values=['epub', 'pdf', 'mobi'],
                                 state='readonly', width=8)
        fmt_combo.pack(side=tk.LEFT, padx=(4, 0))

        row4 = ttk.Frame(pref_frame)
        row4.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(row4, text="请求间隔(秒):", width=16).pack(side=tk.LEFT)
        self.delay_var = tk.StringVar(value=str(config.get('request_delay', 1.0)))
        ttk.Spinbox(row4, textvariable=self.delay_var, from_=0.5, to=10.0,
                    increment=0.5, width=6).pack(side=tk.LEFT, padx=(4, 0))

        ttk.Button(pref_frame, text="保存偏好", command=self._save_prefs,
                   style='Small.TButton').pack(anchor=tk.W, pady=(6, 0))

        # ==============================================
        # 关于
        # ==============================================
        about_frame = ttk.LabelFrame(self.frame, text="关于", padding=14)
        about_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(about_frame, text="Book Reader v1.1",
                  style='PanelHeading.TLabel').pack(anchor=tk.W)
        ttk.Label(about_frame, text="Z-Library 电子书搜索下载工具 (eAPI)",
                  style='PanelMuted.TLabel').pack(anchor=tk.W, pady=(2, 0))
        ttk.Label(about_frame, text="基于 Z-Library Android 客户端 API 实现",
                  style='PanelMuted.TLabel').pack(anchor=tk.W)
        ttk.Label(about_frame, text="仅供个人学习使用，请尊重版权",
                  style='PanelMuted.TLabel').pack(anchor=tk.W, pady=(4, 0))

    def _update_auth_status(self):
        if config.has_auth():
            domain = config.get('personal_domain', '').strip()
            proxy = config.get('proxy', '').strip()
            extras = []
            if domain:
                extras.append("个人域名已配置")
            if proxy:
                extras.append("代理已配置")
            suffix = f" ({'; '.join(extras)})" if extras else ""
            self.auth_status_var.set(f"✅ 已配置{suffix}")
        else:
            self.auth_status_var.set("⚠ 未配置 — 请填写认证令牌")

    def _save_auth(self):
        uid = self.uid_var.get().strip()
        ukey = self.ukey_var.get().strip()
        domain = self.domain_var.get().strip()
        proxy = self.proxy_var.get().strip()

        if not uid or not ukey:
            messagebox.showwarning("提示", "remix_userid 和 remix_userkey 是必填项")
            return

        # 基本域名格式校验
        if domain and not (domain.startswith('http://') or domain.startswith('https://')):
            domain = 'https://' + domain
            self.domain_var.set(domain)

        config.set('remix_userid', uid)
        config.set('remix_userkey', ukey)
        config.set('personal_domain', domain)
        config.set('proxy', proxy)
        self.app.reset_crawler()

        self.app.set_status("正在验证认证信息...")
        self.save_auth_btn.configure(state='disabled', text='验证中...')

        def do():
            crawler = get_crawler()
            return crawler.is_authenticated()

        def on_done(ok):
            self.save_auth_btn.configure(state='normal', text='保存并验证')
            if ok:
                self.auth_status_var.set("✅ 认证成功")
                self.app.set_status("认证成功！")
                messagebox.showinfo("成功", "Z-Library 认证验证通过！")
            else:
                self.auth_status_var.set("⚠ 令牌已保存但验证未通过")
                self.app.set_status("令牌已保存（验证未通过）")
                messagebox.showwarning(
                    "警告",
                    "令牌已保存，但验证未通过。可能原因:\n\n"
                    "1. 令牌已过期 —— 请重新从浏览器获取\n"
                    "2. 网络不可达 —— 请检查个人域名和代理设置\n"
                    "3. 需要个人域名 —— 请在 Z-Library 官网获取"
                )
            self.app.reset_crawler()

        def on_err(msg):
            self.save_auth_btn.configure(state='normal', text='保存并验证')
            self.auth_status_var.set(f"❌ 错误: {msg}")
            self.app.set_status(f"验证失败: {msg}")
            messagebox.showerror("验证失败", f"验证失败:\n\n{msg}")
            self.app.reset_crawler()

        self.app.run_in_thread(do, callback=on_done, error_callback=on_err)

    def _save_prefs(self):
        fmt = self.fmt_var.get()
        try:
            delay = float(self.delay_var.get())
        except ValueError:
            messagebox.showwarning("提示", "请求间隔必须是数字")
            return
        if not 0.1 <= delay <= 30:
            messagebox.showwarning("提示", "请求间隔应在 0.1 到 30 秒之间")
            return

        config.set('preferred_format', fmt)
        config.set('request_delay', delay)
        self.app.reset_crawler()
        self.app.set_status("偏好设置已保存")
        messagebox.showinfo("成功", "偏好设置已保存！")
