"""终端美化输出 —— 颜色、分隔线、进度条、加载动画"""
import os
import re
import sys

# 初始化 colorama（Windows 终端 ANSI 支持）
if os.name == 'nt':
    try:
        import colorama
        colorama.init()
    except ImportError:
        pass


# ============================================================
# ANSI 样式常量
# ============================================================

class S:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    B_RED = '\033[91m'
    B_GREEN = '\033[92m'
    B_YELLOW = '\033[93m'
    B_BLUE = '\033[94m'
    B_MAGENTA = '\033[95m'
    B_CYAN = '\033[96m'
    B_WHITE = '\033[97m'


# ============================================================
# 颜色快捷函数
# ============================================================

def dye(text: str, color: str) -> str:
    return f"{color}{text}{S.RESET}"


def ok(text: str) -> str:
    return dye(text, S.GREEN)


def fail(text: str) -> str:
    return dye(text, S.RED)


def warn(text: str) -> str:
    return dye(text, S.YELLOW)


def tip(text: str) -> str:
    return dye(text, S.CYAN)


def hl(text: str) -> str:
    return dye(text, S.MAGENTA)


def strong(text: str) -> str:
    return dye(text, S.BOLD)


def mute(text: str) -> str:
    return dye(text, S.DIM)


def title(text: str) -> str:
    return dye(text, S.B_CYAN + S.BOLD)


def field(text: str) -> str:
    return dye(text, S.B_BLUE)


def val(text: str) -> str:
    return dye(text, S.B_WHITE)


# ============================================================
# 分隔线
# ============================================================

def rule(char: str = '─', width: int = 60) -> str:
    """水平分隔线"""
    return mute(char * width)


def header(text: str, width: int = 60) -> str:
    """带标题的顶部装饰 ── 标题 ──"""
    t = f"  {text}  "
    remaining = max(0, width - len(t))
    left = remaining // 2
    right = remaining - left
    return title('─' * left + t + '─' * right)


def box(lines: list, width: int = 58) -> str:
    """把多行文本放入装饰框"""
    out = [tip('╭' + '─' * (width) + '╮')]
    for line in lines:
        visible = _vlen(line)
        pad = max(0, width - visible)
        out.append(tip('│') + ' ' + line + ' ' * pad + tip('│'))
    out.append(tip('╰' + '─' * (width) + '╯'))
    return '\n'.join(out)


def _vlen(text: str) -> int:
    """可见字符宽度（忽略 ANSI 码，CJK 字符计为 2）"""
    clean = re.sub(r'\033\[[0-9;]*m', '', text)
    w = 0
    for ch in clean:
        if '一' <= ch <= '鿿' or '　' <= ch <= '〿' or '＀' <= ch <= '￯':
            w += 2
        else:
            w += 1
    return w


# ============================================================
# 进度条
# ============================================================

def progress(current: int, total: int, label: str = '', width: int = 36) -> str:
    """彩色进度条字符串（用于 \r 刷新）"""
    if total <= 0:
        return ''
    pct = current / total * 100
    filled = int(width * current / total)
    bar_color = S.B_GREEN if pct < 85 else S.B_CYAN
    bar = dye('█' * filled, bar_color) + mute('░' * (width - filled))
    size_info = ''
    if label:
        size_info = f'  {label}'
    return f"  {bar} {pct:5.1f}%{size_info}"


# ============================================================
# 旋转加载动画
# ============================================================

class Spinner:
    """终端旋转加载指示器"""

    def __init__(self, text: str = '加载中'):
        self.text = text
        self._f = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self._i = 0

    def tick(self):
        frame = dye(self._f[self._i], S.B_CYAN)
        sys.stdout.write(f"\r  {frame} {self.text}")
        sys.stdout.flush()
        self._i = (self._i + 1) % len(self._f)

    def end(self, msg: str = '完成', success: bool = True):
        mark = ok('✓') if success else fail('✗')
        sys.stdout.write(f"\r  {mark} {msg}" + ' ' * 30 + '\n')
        sys.stdout.flush()


# ============================================================
# 格式化表格
# ============================================================

def table(headers: list, rows: list, col_widths: list = None) -> str:
    """生成对齐的文本表格"""
    if not col_widths:
        col_widths = []
        for i, h in enumerate(headers):
            w = _vlen(str(h))
            for row in rows:
                if i < len(row):
                    w = max(w, _vlen(str(row[i])))
            col_widths.append(w + 2)

    lines = []
    # 表头（粗体）
    hdr = ''.join(strong(str(h).ljust(col_widths[i])) for i, h in enumerate(headers))
    lines.append(hdr)
    # 分隔线
    lines.append(mute('─' * sum(col_widths)))
    # 数据行
    for row in rows:
        parts = []
        for i in range(len(col_widths)):
            cell = str(row[i]) if i < len(row) else ''
            parts.append(cell[:col_widths[i]].ljust(col_widths[i]))
        lines.append(''.join(parts))

    return '\n'.join(lines)
