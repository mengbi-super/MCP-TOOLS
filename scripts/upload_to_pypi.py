#!/usr/bin/env python3
"""
上传包到 PyPI 的辅助脚本
"""
import os
import subprocess
import sys
from pathlib import Path

def read_token_from_pypirc():
    """从 .pypirc 文件读取 token"""
    pypirc_path = Path.home() / ".pypirc"
    if not pypirc_path.exists():
        return None
    
    try:
        # 尝试多种编码读取
        for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'latin-1']:
            try:
                with open(pypirc_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    # 查找 password 行
                    for line in content.split('\n'):
                        if 'password' in line.lower() and '=' in line:
                            token = line.split('=', 1)[1].strip()
                            if token.startswith('pypi-'):
                                return token
            except (UnicodeDecodeError, UnicodeError):
                continue
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
    
    return None

def upload_to_pypi():
    """上传包到 PyPI"""
    # 检查 dist 目录
    dist_dir = Path("dist")
    if not dist_dir.exists():
        print("错误: dist 目录不存在，请先运行 'py -m build'")
        return False
    
    # 获取 token
    token = read_token_from_pypirc()
    if not token:
        print("错误: 无法从配置文件读取 token")
        print(f"请检查文件: {Path.home() / '.pypirc'}")
        return False
    
    # 设置环境变量
    os.environ['TWINE_USERNAME'] = '__token__'
    os.environ['TWINE_PASSWORD'] = token
    
    # 临时重命名 .pypirc 避免编码问题
    pypirc_path = Path.home() / ".pypirc"
    pypirc_backup = Path.home() / ".pypirc.bak"
    
    try:
        if pypirc_path.exists():
            pypirc_path.rename(pypirc_backup)
        
        # 上传
        print("开始上传到 PyPI...")
        result = subprocess.run(
            [sys.executable, "-m", "twine", "upload", "dist/*"],
            check=False
        )
        
        return result.returncode == 0
    finally:
        # 恢复配置文件
        if pypirc_backup.exists():
            pypirc_backup.rename(pypirc_path)

if __name__ == "__main__":
    success = upload_to_pypi()
    sys.exit(0 if success else 1)
