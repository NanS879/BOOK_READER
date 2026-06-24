# BOOK_READER

基于 Python 的电子书爬虫与阅读器，支持在 Z-Library 上搜索、下载电子书并阅读。提供 **桌面 GUI** 和 **彩色终端 CLI** 双模式。

## 功能特性

- **桌面 GUI** — Tkinter 选项卡式桌面界面，双击即用
- **启动自检** — 启动时自动检测运行环境、依赖、配置完整性，发现问题给出修复建议
- **在线搜索** — Z-Library 关键词搜索，支持格式（EPUB/PDF/MOBI）和语言过滤
- **一键下载** — 下载电子书到本地，彩色实时进度条
- **系统阅读** — 调用系统默认应用打开（支持任意格式）
- **终端阅读** — EPUB 格式支持终端彩色分页阅读，键盘导航
- **进度追踪** — 自动记录阅读时间和次数
- **彩色界面** — ANSI 颜色、装饰框、加载动画、格式化表格
- **独立 EXE** — 支持打包为单文件 Windows 可执行程序

## 安装

```bash
# 克隆项目
git clone <repo-url>
cd book-reader

# 安装依赖
pip install -r requirements.txt
```

## 快速开始

### 0. 启动 GUI（推荐）

无需任何命令行知识，双击 `book-reader.exe` 或直接运行：

```bash
python run.py
```

首次启动会运行 **GUI 初始化检查**，自动验证以下项目：

| 检查项      | 说明                                        | 失败时      |
| ----------- | ------------------------------------------- | ----------- |
| Python 版本 | 需要 ≥ 3.8                                 | 阻止启动    |
| Tkinter     | Tcl/Tk 运行时是否可用                       | 阻止启动    |
| 依赖包      | requests, ebooklib, bs4, colorama           | 功能不可用  |
| 配置文件    | config.json 格式校验                        | 警告 + 回退 |
| 书籍目录    | 可读写性测试                                | 阻止下载    |
| 磁盘空间    | 剩余空间检查                                | 警告        |
| 字体检测    | 自动匹配最佳中文字体                        | 降级到默认  |

检查通过后进入主界面；如遇错误会打印详细修复建议（如 `pip install ...`）。

### 1. 配置认证

首先配置 Z-Library 的 `remix` 令牌：

```bash
python -m book_reader setup
```

也可以在 GUI 的「设置」选项卡中直接填入并验证。

按提示输入 `remix_userid` 和 `remix_userkey`。获取方法：

1. 在浏览器中登录 Z-Library（[https://singlelogin.re](https://singlelogin.re/)）
2. 按 `F12` 打开开发者工具
3. 进入 **Application** → **Cookies**
4. 复制 `remix_userid` 和 `remix_userkey` 的值
5. （可选）在 Z-Library 官网 → Z-access → Web Version 获取你的个人域名
6. （可选）如网络受限，可配置 HTTP / SOCKS5 代理

### 2. 搜索书籍

**GUI：** 在「搜索」选项卡中输入关键词，选择格式/语言过滤，点击搜索。

**CLI：**

```bash
# 基本搜索
python -m book_reader search "Python Programming"

# 按格式过滤
python -m book_reader search "Python" --format epub

# 按语言过滤
python -m book_reader search "三体" --language chinese
```

### 3. 下载书籍

搜索结果中选择序号即可查看详情并下载，也可以直接指定 URL：

```bash
python -m book_reader download <Z-Library-URL>
```

GUI 中双击搜索结果可查看详情，点击「下载选中」即可，支持实时进度条。

### 4. 阅读书籍

**GUI：** 在「书架」选项卡中选中书籍，点击「打开阅读」（系统默认阅读器）或「终端阅读」（仅 EPUB）。

**CLI：**

```bash
# 从书架中选择
python -m book_reader read

# 直接打开指定书籍（系统默认阅读器）
python -m book_reader read "Python Cookbook"

# EPUB 终端彩色阅读模式
python -m book_reader read --terminal "Python Cookbook"
```

### 5. 查看书架

```bash
python -m book_reader list
```

## 终端阅读器快捷键（EPUB 模式）

| 按键                  | 功能           |
| --------------------- | -------------- |
| `Enter` / `Space` | 下一页         |
| `b`                 | 上一页         |
| `n`                 | 下一章         |
| `p`                 | 上一章         |
| `j`                 | 跳转到指定章节 |
| `t`                 | 查看目录       |
| `q` / `Esc`       | 退出           |

## 打包为 EXE

项目已包含构建脚本和 PyInstaller 规格文件，可一键打包：

```bash
# 安装打包依赖
pip install pyinstaller

# 构建 EXE
python build_exe.py
```

构建完成后，`dist/` 目录下会生成 `book-reader.exe`（约 15 MB），可直接双击运行或在终端中使用：

```cmd
rem 双击启动 GUI
book-reader.exe

rem CLI 模式
book-reader.exe setup
book-reader.exe search "Python"
book-reader.exe list
```

> **提示**：EXE 自带 Python 运行时，无需在目标电脑上安装 Python。

## 项目结构

```
book-reader/
├── README.md
├── requirements.txt
├── .gitignore
├── run.py                        # EXE 打包入口脚本（GUI/CLI 双模式）
├── build_exe.py                  # 一键构建脚本
├── book_reader.spec             # PyInstaller 规格文件
├── books/                        # 下载的电子书存放目录
├── progress.json                 # 阅读进度记录
├── config.json                   # 配置文件（含认证令牌）
└── book_reader/                 # 主程序包
    ├── __init__.py
    ├── __main__.py               # Python 模块入口
    ├── main.py                   # CLI 命令分发
    ├── config.py                 # 配置管理（单例）
    ├── console.py                # 终端美化（颜色、边框、进度条、动画）
    ├── storage.py                # 本地存储管理
    ├── reader.py                 # 阅读器（系统应用 + EPUB 终端模式）
    ├── crawler/                  # 爬虫模块
    │   ├── __init__.py           # 工厂函数
    │   ├── base.py               # 爬虫基类与数据模型
    │   └── zlibrary.py           # Z-Library eAPI 爬虫（直接调用 Android API）
    └── gui/                      # 桌面 GUI 模块
        ├── __init__.py           # GUI 包导出
        ├── init_check.py         # 启动自检（环境、依赖、配置、字体）
        ├── main_window.py        # 主窗口（选项卡容器）
        ├── search_tab.py         # 搜索选项卡
        ├── library_tab.py        # 书架选项卡
        └── settings_tab.py       # 设置选项卡
```

## 依赖

| 包                 | 用途                                       |
| ------------------ | ------------------------------------------ |
| `requests`       | HTTP 请求（支持代理）                      |
| `ebooklib`       | EPUB 文件解析                              |
| `beautifulsoup4` | HTML / EPUB 内容提取                       |
| `colorama`       | Windows 终端 ANSI 颜色支持                 |
| `pyinstaller`    | EXE 打包（可选，仅构建时需要）             |

> **说明**：Z-Library 接口基于 eAPI（Android 客户端 API）直接实现，无需额外第三方 Z-Library 包装库。认证通过 remix 令牌以 HTTP Header + Cookie 双通道发送，支持个人域名和多域名自动回退。

## 配置

运行 `setup` 后自动生成 `config.json`：

```json
{
  "page_size": 30,
  "request_delay": 1.0,
  "preferred_format": "epub",
  "remix_userid": "你的令牌",
  "remix_userkey": "你的令牌",
  "personal_domain": "https://yourname.z-lib.id",
  "proxy": "http://127.0.0.1:7890",
  "user_agent": "Mozilla/5.0 ..."
}
```

| 字段                 | 说明                                          |
| -------------------- | --------------------------------------------- |
| `page_size`        | 终端阅读每页行数                              |
| `request_delay`    | 请求间隔（秒），避免触发限流                  |
| `preferred_format` | 首选下载格式（epub / pdf / mobi）             |
| `remix_userid`     | Z-Library remix 认证令牌                      |
| `remix_userkey`    | Z-Library remix 认证密钥                      |
| `personal_domain`  | Z-Library 个人域名（可选，提高访问成功率）    |
| `proxy`            | HTTP / SOCKS5 代理地址（可选，用于绕过封锁）  |

## 注意事项

- Z-Library 需要注册账号才能使用（免费注册）
- 下载书籍仅供个人学习使用，请尊重版权
- 程序内置请求间隔，请勿调低 `request_delay` 以免触发限流
- `remix` 令牌是个人敏感信息，**请勿分享给他人**
- 如认证失效，重新运行 `python -m book_reader setup` 更新令牌
- GUI 首次启动自动运行初始化检查，确保环境就绪
- 中国大陆用户建议配置 **个人域名** 或 **代理** 以提高访问成功率
- 支持 HTTP / SOCKS5 代理，可在 `setup` 或 GUI 设置中配置

## License

MIT
