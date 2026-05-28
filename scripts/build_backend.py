#!/usr/bin/env python3
"""
构建后端二进制文件 - 桌面版
"""

import os
import sys
import subprocess
import shutil
import argparse
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="构建桌面版后端二进制文件")
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="构建前安装 requirements.txt 和 PyInstaller。默认只使用现有虚拟环境依赖。",
    )
    args = parser.parse_args()

    print("[BUILD] Starting desktop backend build...")

    # 设置路径
    project_root = Path(__file__).parent.parent
    backend_dir = project_root / "backend"
    resources_dir = project_root / "src-tauri" / "resources"

    # 确保资源目录存在
    resources_dir.mkdir(parents=True, exist_ok=True)

    # 检查虚拟环境（本地开发）或使用当前 Python（CI）
    venv_path = project_root / "venv"
    if venv_path.exists():
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    else:
        # CI 或无 venv 环境：使用当前 Python
        pip_path = sys.executable
        python_path = sys.executable
        # 将 pip install 改为 python -m pip
        print("[BUILD] No venv detected, using current Python environment")

    if args.install_deps:
        # 安装依赖
        print("📦 安装Python依赖...")
        try:
            # 如果 pip_path 就是 sys.executable，用 python -m pip
            if pip_path == sys.executable:
                subprocess.run([str(python_path), "-m", "pip", "install", "-r", "requirements.txt"],
                              check=True, cwd=project_root)
            else:
                subprocess.run([str(pip_path), "install", "-r", "requirements.txt"],
                              check=True, cwd=project_root)
            print("✅ Python依赖安装成功")
        except subprocess.CalledProcessError as e:
            print(f"❌ Python依赖安装失败: {e}")
            return 1

        # 安装PyInstaller
        print("📦 安装PyInstaller...")
        try:
            if pip_path == sys.executable:
                subprocess.run([str(python_path), "-m", "pip", "install", "pyinstaller"], check=True)
            else:
                subprocess.run([str(pip_path), "install", "pyinstaller"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ PyInstaller安装失败: {e}")
            return 1
    else:
        try:
            subprocess.run(
                [str(python_path), "-m", "PyInstaller", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError:
            print("❌ PyInstaller 不可用，请先运行: python scripts/build_backend.py --install-deps")
            return 1
    
    # 创建PyInstaller规格文件
    spec_content = f"""
# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

a = Analysis(
    ['{backend_dir}/desktop_main.py'],
    pathex=['{project_root}', '{backend_dir}'],
    binaries=[],
    datas=[
        ('{backend_dir}/core', 'backend/core'),
        ('{backend_dir}/api', 'backend/api'),
        ('{backend_dir}/models', 'backend/models'),
        ('{backend_dir}/services', 'backend/services'),
        ('{backend_dir}/repositories', 'backend/repositories'),
        ('{backend_dir}/schemas', 'backend/schemas'),
        ('{backend_dir}/utils', 'backend/utils'),
        ('{backend_dir}/tasks', 'backend/tasks'),
        ('{backend_dir}/pipeline', 'backend/pipeline'),
        ('{backend_dir}/prompt', 'backend/prompt'),
        ('{project_root}/data', 'data'),
    ],
    hiddenimports=[
        'uvicorn',
        'fastapi',
        'celery',
        'sqlalchemy',
        'pydantic',
        'psutil',
        'requests',
        'aiofiles',
        'multipart',
        'kombu.transport.filesystem',
        'sqlalchemy.dialects.sqlite',
        'backend',
        'backend.app_factory',
        'backend.desktop_celery',
        'backend.tasks.processing',
    ]
    + collect_submodules('celery')
    + collect_submodules('kombu')
    + collect_submodules('billiard')
    + collect_submodules('vine'),
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name='autoclip-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    exclude_binaries=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='autoclip-backend',
)
"""
    
    spec_file = backend_dir / "autoclip-backend.spec"
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    # 构建后端二进制
    print("🔨 构建后端二进制...")
    try:
        # 清理旧的构建产物
        print("🧹 清理旧的构建产物...")
        for stale_dir in [
            backend_dir / "dist",
            backend_dir / "build",
            project_root / "build",
        ]:
            if stale_dir.exists():
                shutil.rmtree(stale_dir)
        stale_dist = project_root / "dist" / "autoclip-backend"
        if stale_dist.exists():
            if stale_dist.is_dir():
                shutil.rmtree(stale_dist)
            else:
                stale_dist.unlink()
        resource_backend = resources_dir / "autoclip-backend"
        if resource_backend.exists():
            if resource_backend.is_dir():
                shutil.rmtree(resource_backend)
            else:
                resource_backend.unlink()
        
        # 在项目根目录执行构建，确保路径正确
        subprocess.run([
            str(python_path), "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_file)
        ], check=True, cwd=project_root)
        
        # 移动构建结果到资源目录
        # PyInstaller 输出到项目根目录的 dist 文件夹
        dist_dir = project_root / "dist" / "autoclip-backend"
        if dist_dir.exists():
            shutil.copytree(dist_dir, resources_dir / "autoclip-backend")
            print("✅ 后端二进制构建成功")
        else:
            print("❌ 构建文件不存在")
            return 1
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 后端二进制构建失败: {e}")
        return 1
    
    # 清理临时文件
    if spec_file.exists():
        spec_file.unlink()
    
    print("🎉 桌面版后端构建完成！")
    print(f"📁 二进制文件位置: {resources_dir / 'autoclip-backend'}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
