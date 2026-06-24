#!/usr/bin/env python
"""构建 EXE 可执行文件"""
import subprocess
import sys
import os

def main():
    print("=" * 60)
    print("  book-reader EXE 构建工具")
    print("=" * 60)
    print()

    project_dir = os.path.dirname(os.path.abspath(__file__))
    spec_file = os.path.join(project_dir, 'book_reader.spec')
    dist_dir = os.path.join(project_dir, 'dist')

    print("[1/3] 清理旧构建...")
    for d in ['build', 'dist']:
        path = os.path.join(project_dir, d)
        if os.path.exists(path):
            import shutil
            shutil.rmtree(path)
            print(f"  已删除: {d}/")

    print("\n[2/3] PyInstaller 构建...")
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        spec_file,
    ]
    result = subprocess.run(cmd, cwd=project_dir)
    if result.returncode != 0:
        print("\n构建失败！")
        sys.exit(1)

    print("\n[3/3] 验证...")
    exe_path = os.path.join(dist_dir, 'book-reader.exe')
    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"  [OK] EXE generated: {exe_path}")
        print(f"  文件大小: {size_mb:.1f} MB")
        print(f"\n构建成功！运行方式:")
        print(f"  {exe_path}")
        print(f"  或直接双击 dist/book-reader.exe")
    else:
        print("  ✗ 未找到生成的 EXE 文件")
        sys.exit(1)


if __name__ == '__main__':
    main()
