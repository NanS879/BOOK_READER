"""book-reader 入口脚本 —— Z-Library 电子书爬虫与阅读器

用法:
  book-reader.exe             双击启动桌面 GUI 应用
  book-reader.exe search ...  CLI 命令行模式
  book-reader.exe list         CLI 命令行模式
"""
import sys
import os

# ============================================================
# 修复 Windows 控制台 Unicode 编码问题
# ============================================================

def _fix_console_encoding():
    """在 Windows 上将 stdout/stderr 重配置为 UTF-8。

    中文 Windows 默认使用 GBK 编码，无法输出 emoji 和部分
    Unicode 字符（如 ✓ ✗ ⚠ 🔍）。此函数在程序启动时修复该问题。
    """
    if os.name != 'nt':
        return

    # 方法 1: Python 3.7+ reconfigure
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    # 方法 2: 设置控制台代码页为 UTF-8 (cp65001)
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleCP(65001)
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

_fix_console_encoding()

# 确保项目目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 判断是否使用 GUI 模式（无命令行参数）
use_gui = len(sys.argv) == 1

if use_gui:
    # ---- GUI 初始化检查 ----
    print("正在启动 Book Reader GUI...")
    print("运行初始化检查...")

    try:
        from book_reader.gui.init_check import (
            run_init_checks, format_report, can_launch_gui, get_recommended_font,
        )

        # 带进度回调的运行检查
        def progress_cb(name, status):
            icon = {'ok': '[OK]', 'warn': '[!!]', 'error': '[XX]', 'fatal': '[XX]', 'running': '...'}
            print(f"  {icon.get(status, '?')} {name}")

        report = run_init_checks(progress_callback=progress_cb)

        # 打印摘要
        print()
        if report.all_ok:
            print("[OK] 所有检查通过！")
        else:
            if report.warnings:
                print(f"[!!] {len(report.warnings)} 个警告")
            if report.blocking:
                print(f"[XX] {len(report.blocking)} 个错误")

        if not can_launch_gui(report):
            # 严重错误 —— 显示详细信息并退出
            print()
            print(format_report(report))
            print()
            print("=" * 60)
            print("  请解决以上错误后重新启动。")
            print("=" * 60)
            print()
            input("按 Enter 退出...")
            sys.exit(1)

        # 获取推荐字体
        font_family = get_recommended_font(report)
        print()
        print(f"使用字体: {font_family}")

    except ImportError as e:
        print(f"[!!] 无法导入初始化检查模块: {e}")
        print("  跳过检查，直接启动 GUI...")
        font_family = None
    except Exception as e:
        print(f"[!!] 初始化检查异常: {e}")
        import traceback
        traceback.print_exc()
        print("  跳过检查，尝试启动 GUI...")
        font_family = None

    # ---- 启动 GUI ----
    from book_reader.gui.main_window import NovelReaderApp
    try:
        app = NovelReaderApp(font_family=font_family)
        app.run()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print()
        print("=" * 60)
        print("  GUI 启动失败！")
        print(f"  错误: {e}")
        print("=" * 60)
        print()
        input("按 Enter 退出...")

else:
    from book_reader.main import main
    try:
        main()
    except Exception as e:
        print(f"\n程序出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if len(sys.argv) == 1:
            try:
                input("\n按 Enter 键退出...")
            except (EOFError, KeyboardInterrupt):
                pass
