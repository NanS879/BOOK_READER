"""GUI 初始化检查模块 —— 在启动时验证运行环境、依赖和配置

在 NovelReaderApp 创建之前运行，确保所有必要条件都已满足。
发现问题时给出清晰的修复建议，而非直接崩溃。
"""

import os
import sys
import json
import shutil
from dataclasses import dataclass, field
from typing import List, Callable, Optional

# 复用 config 模块的目录推导（避免重复维护路径逻辑）
from ..config import config as _app_config


# ============================================================
# 检查结果模型
# ============================================================

class CheckLevel:
    OK = 'ok'          # (R) normal
    WARN = 'warn'      # (!!) risk warning
    ERROR = 'error'    # (XX) blocking issue
    FATAL = 'fatal'    # (XX) cannot continue


@dataclass
class CheckResult:
    """(R) single check result"""
    name: str                    # human-readable check name
    level: str                   # ok / warn / error / fatal
    message: str                 # short description
    key: str = ''                # machine-readable ID for programmatic lookup
    detail: str = ''             # extra info / fix suggestion
    exception: Optional[Exception] = None

    @property
    def is_ok(self) -> bool:
        return self.level == CheckLevel.OK

    @property
    def is_blocking(self) -> bool:
        return self.level in (CheckLevel.ERROR, CheckLevel.FATAL)


@dataclass
class InitReport:
    """(R) full initialization check report"""
    results: List[CheckResult] = field(default_factory=list)
    python_version: str = ''
    platform: str = ''
    base_dir: str = ''

    @property
    def all_ok(self) -> bool:
        return all(r.level == CheckLevel.OK for r in self.results)

    @property
    def blocking(self) -> List[CheckResult]:
        return [r for r in self.results if r.is_blocking]

    @property
    def warnings(self) -> List[CheckResult]:
        return [r for r in self.results if r.level == CheckLevel.WARN]


# ============================================================
# check functions
# ============================================================

def _check_python_version() -> CheckResult:
    """Check Python version >= 3.8"""
    vi = sys.version_info
    version_str = f"{vi.major}.{vi.minor}.{vi.micro}"
    if vi < (3, 8):
        return CheckResult(
            name="Python Version", key="python_version",
            level=CheckLevel.FATAL,
            message=f"Python {version_str} too old (need >= 3.8)",
            detail="Install Python 3.8+: https://www.python.org/downloads/",
        )
    return CheckResult(
        name="Python Version", key="python_version",
        level=CheckLevel.OK,
        message=f"Python {version_str}",
    )


def _check_tkinter() -> CheckResult:
    """Check if Tkinter is available"""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        tk_version = root.tk.call('info', 'patchlevel')
        tcl_version = root.tk.call('info', 'tclversion')
        root.destroy()
        return CheckResult(
            name="Tkinter", key="tkinter",
            level=CheckLevel.OK,
            message=f"Tk {tk_version}, Tcl {tcl_version}",
        )
    except ImportError:
        return CheckResult(
            name="Tkinter", key="tkinter",
            level=CheckLevel.FATAL,
            message="tkinter not installed",
            detail=(
                "Windows: Reinstall Python and check 'tcl/tk and IDLE'.\n"
                "Linux:   sudo apt install python3-tk\n"
                "macOS:   tkinter is included with the official installer."
            ),
        )
    except Exception as e:
        return CheckResult(
            name="Tkinter", key="tkinter",
            level=CheckLevel.FATAL,
            message=f"Tkinter init failed: {e}",
            detail="Check that Tcl/Tk runtime is installed.",
            exception=e,
        )


def _check_required_packages() -> CheckResult:
    """Check core dependencies are installed"""
    packages = {
        'requests': 'requests>=2.28.0',
        'ebooklib': 'ebooklib>=0.18',
        'bs4': 'beautifulsoup4>=4.11.0',
        'colorama': 'colorama>=0.4.6',
    }
    missing = []
    for import_name, pip_name in packages.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pip_name)

    if missing:
        return CheckResult(
            name="Dependencies", key="dependencies",
            level=CheckLevel.ERROR,
            message=f"Missing {len(missing)} package(s)",
            detail=f"Run: pip install {' '.join(missing)}",
        )
    return CheckResult(
        name="Dependencies", key="dependencies",
        level=CheckLevel.OK,
        message="All core dependencies installed",
    )


def _check_config_integrity(base_dir: str) -> CheckResult:
    """Check config.json exists and is valid JSON"""
    config_file = os.path.join(base_dir, 'config.json')
    if not os.path.exists(config_file):
        return CheckResult(
            name="Config", key="config",
            level=CheckLevel.OK,
            message="Config file not found, will use defaults",
        )
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("config.json is not a JSON object")
        return CheckResult(
            name="Config", key="config",
            level=CheckLevel.OK,
            message=f"Config OK ({len(data)} keys)",
        )
    except (json.JSONDecodeError, ValueError, IOError) as e:
        return CheckResult(
            name="Config", key="config",
            level=CheckLevel.WARN,
            message=f"Config corrupted: {e}",
            detail="Will use defaults and overwrite. Backup the old file first.",
            exception=e if isinstance(e, Exception) else None,
        )


def _check_books_dir(base_dir: str) -> CheckResult:
    """Check books directory is writable"""
    books_dir = os.path.join(base_dir, 'books')
    try:
        os.makedirs(books_dir, exist_ok=True)
        test_file = os.path.join(books_dir, '._write_test_')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        return CheckResult(
            name="Books Dir", key="books_dir",
            level=CheckLevel.OK,
            message=f"Writable: {books_dir}",
        )
    except PermissionError:
        return CheckResult(
            name="Books Dir", key="books_dir",
            level=CheckLevel.ERROR,
            message="No write permission",
            detail=f"Cannot write to: {books_dir}\nTry running as administrator.",
        )
    except OSError as e:
        return CheckResult(
            name="Books Dir", key="books_dir",
            level=CheckLevel.ERROR,
            message=f"Directory access failed: {e}",
            detail=f"Path: {books_dir}",
            exception=e,
        )


def _check_disk_space(base_dir: str) -> CheckResult:
    """Check free disk space (warn if < 100MB)"""
    try:
        usage = shutil.disk_usage(base_dir)
        free_mb = usage.free / (1024 * 1024)
        if free_mb < 50:
            return CheckResult(
                name="Disk Space", key="disk_space",
                level=CheckLevel.WARN,
                message=f"Low disk space ({free_mb:.1f} MB free)",
                detail="Free up disk space before downloading books.",
            )
        return CheckResult(
            name="Disk Space", key="disk_space",
            level=CheckLevel.OK,
            message=f"{free_mb:.1f} MB free",
        )
    except Exception as e:
        return CheckResult(
            name="Disk Space", key="disk_space",
            level=CheckLevel.WARN,
            message=f"Cannot check: {e}",
            detail="Not critical, but monitor your disk space.",
        )


def _check_font_availability() -> CheckResult:
    """Check preset fonts and return the best available"""
    import tkinter as tk
    from tkinter import font as tkfont

    try:
        root = tk.Tk()
        root.withdraw()
        available = set(tkfont.families())
        root.destroy()
    except Exception:
        available = set()

    # font candidates by priority
    candidates = [
        ('Microsoft YaHei UI', 'Microsoft YaHei'),
        ('PingFang SC', 'PingFang'),
        ('Noto Sans CJK SC', 'Noto Sans CJK'),
        ('WenQuanYi Micro Hei', 'WenQuanYi'),
    ]

    for font_name, font_label in candidates:
        if font_name in available:
            return CheckResult(
                name="Font", key="font",
                level=CheckLevel.OK,
                message=f"Using: {font_name} ({font_label})",
                detail=font_name,
            )

    default = tkfont.nametofont('TkDefaultFont')
    default_name = default.actual('family') if default else 'TkDefaultFont'
    return CheckResult(
        name="Font", key="font",
        level=CheckLevel.WARN,
        message=f"Recommended font not found, fallback to {default_name}",
        detail=default_name,
    )


# ============================================================
# main entry point
# ============================================================

def run_init_checks(
    base_dir: Optional[str] = None,
    progress_callback: Optional[Callable[[str, str], None]] = None,
) -> InitReport:
    """Run all GUI initialization checks

    Args:
        base_dir: Project root dir. Auto-detected if None.
        progress_callback: Progress callback (check_name, status). For splash screen.

    Returns:
        InitReport with all check results.
    """
    if base_dir is None:
        base_dir = _app_config.base_dir

    report = InitReport(
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        platform=sys.platform,
        base_dir=base_dir,
    )

    checks: List[Callable[[], CheckResult]] = [
        _check_python_version,
        _check_tkinter,
        _check_required_packages,
        lambda: _check_config_integrity(base_dir),
        lambda: _check_books_dir(base_dir),
        lambda: _check_disk_space(base_dir),
        _check_font_availability,
    ]

    for check_fn in checks:
        name = check_fn.__name__.replace('_check_', '').title()
        if progress_callback:
            progress_callback(name, 'running')

        try:
            result = check_fn()
        except Exception as e:
            # If we reach here, the check itself crashed due to a code bug
            result = CheckResult(
                name=name,
                level=CheckLevel.ERROR,
                message=f"Check crashed: {e}",
                exception=e,
            )

        report.results.append(result)
        if progress_callback:
            progress_callback(name, result.level)

        if result.level == CheckLevel.FATAL:
            break

    return report


def format_report(report: InitReport) -> str:
    """Format the report as human-readable text"""
    lines = []
    lines.append("=" * 60)
    lines.append("  Book Reader - GUI Init Check Report")
    lines.append("=" * 60)
    lines.append(f"  Python:  {report.python_version}")
    lines.append(f"  Platform: {report.platform}")
    lines.append(f"  Directory: {report.base_dir}")
    lines.append("-" * 60)

    level_icons = {
        CheckLevel.OK: '[OK]',
        CheckLevel.WARN: '[!!]',
        CheckLevel.ERROR: '[XX]',
        CheckLevel.FATAL: '[XX]',
    }

    for r in report.results:
        icon = level_icons.get(r.level, '?')
        lines.append(f"  {icon} {r.name}: {r.message}")
        if r.detail:
            for dline in r.detail.split('\n'):
                lines.append(f"     {dline}")

    lines.append("-" * 60)
    ok_count = sum(1 for r in report.results if r.is_ok)
    warn_count = len(report.warnings)
    err_count = len(report.blocking)
    lines.append(f"  Total: {ok_count} OK, {warn_count} warnings, {err_count} errors")
    lines.append("=" * 60)

    return '\n'.join(lines)


def can_launch_gui(report: InitReport) -> bool:
    """Check if the GUI can be launched based on report"""
    return len(report.blocking) == 0


def get_recommended_font(report: InitReport) -> str:
    """Extract recommended font name from the report"""
    for r in report.results:
        if r.key == 'font' and r.level in (CheckLevel.OK, CheckLevel.WARN):
            if r.detail:
                return r.detail
    return 'TkDefaultFont'
