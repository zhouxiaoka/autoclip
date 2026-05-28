#!/usr/bin/env python3
"""
优化的桌面应用构建脚本 - 减少构建产物大小
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def main():
    print("🚀 开始优化构建桌面应用...")
    
    # 设置路径
    project_root = Path(__file__).parent.parent
    backend_dir = project_root / "backend"
    resources_dir = project_root / "src-tauri" / "resources"
    venv_path = project_root / "venv"
    
    # 1. 彻底清理所有构建产物
    print("🧹 彻底清理所有构建产物...")
    
    for path in [
        backend_dir / "dist",
        backend_dir / "build", 
        project_root / "dist",
        project_root / "build",
        resources_dir / "autoclip-backend",
        resources_dir / "autoclip-backend-macos-arm64",
    ]:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                print(f"  ✓ 删除目录: {path}")
            else:
                path.unlink()
                print(f"  ✓ 删除文件: {path}")
    
    # 2. 创建精简的虚拟环境
    print("📦 创建精简的虚拟环境...")
    
    # 删除现有虚拟环境
    if venv_path.exists():
        shutil.rmtree(venv_path)
        print("  ✓ 删除现有虚拟环境")
    
    # 创建新的虚拟环境
    subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
    print("  ✓ 创建新虚拟环境")
    
    # 3. 安装最小依赖
    print("📦 安装最小依赖...")
    
    pip_path = venv_path / "bin" / "pip"
    
    # 核心依赖
    core_deps = [
        "fastapi",
        "uvicorn[standard]",
        "sqlalchemy",
        "pydantic",
        "pydantic-settings",
        "python-multipart",
        "websockets",
        "requests",
        "aiohttp",
        "aiofiles",
        "python-jose[cryptography]",
        "passlib[bcrypt]",
        "cryptography",
        "qrcode[pil]",
        "yt-dlp>=2024.12.13",
        "pysrt",
        "psutil",
        "pyinstaller",
    ]
    
    for dep in core_deps:
        try:
            subprocess.run([str(pip_path), "install", dep], check=True, capture_output=True)
            print(f"  ✓ 安装: {dep}")
        except subprocess.CalledProcessError as e:
            print(f"  ⚠️  安装失败: {dep}")
    
    # 4. 创建优化的 PyInstaller spec 文件
    print("🔧 创建优化的构建配置...")
    
    spec_content = f"""
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{backend_dir}/desktop_main.py'],
    pathex=['{project_root}', '{backend_dir}'],
    binaries=[],
    datas=[
        ('{backend_dir}/core', 'core'),
        ('{backend_dir}/api', 'api'),
        ('{backend_dir}/models', 'models'),
        ('{backend_dir}/services', 'services'),
        ('{backend_dir}/repositories', 'repositories'),
        ('{backend_dir}/schemas', 'schemas'),
        ('{backend_dir}/utils', 'utils'),
        ('{backend_dir}/tasks', 'tasks'),
        ('{backend_dir}/pipeline', 'pipeline'),
        ('{backend_dir}/prompt', 'prompt'),
        ('{project_root}/data', 'data'),
    ],
    hiddenimports=[
        'uvicorn',
        'fastapi',
        'sqlalchemy',
        'pydantic',
        'psutil',
        'requests',
        'aiofiles',
        'python-multipart',
        'websockets',
        'aiohttp',
        'cryptography',
        'yt_dlp',
        'pysrt',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[
        'pandas',
        'numpy', 
        'pyarrow',
        'cv2',
        'streamlit',
        'matplotlib',
        'seaborn',
        'plotly',
        'jupyter',
        'notebook',
        'ipython',
        'pytest',
        'pytest-cov',
        'pytest-mock',
        'celery',
        'redis',
        'alembic',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='autoclip-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""
    
    spec_file = backend_dir / "autoclip-backend-optimized.spec"
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    # 5. 构建后端
    print("🔨 构建优化的后端...")
    
    python_path = venv_path / "bin" / "python"
    
    try:
        subprocess.run([
            str(python_path), "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            str(spec_file)
        ], check=True, cwd=project_root)
        
        # 移动构建结果
        dist_file = project_root / "dist" / "autoclip-backend"
        if dist_file.exists():
            shutil.copy2(dist_file, resources_dir / "autoclip-backend")
            
            # 检查文件大小
            size_mb = dist_file.stat().st_size / (1024 * 1024)
            print(f"✅ 后端构建成功，大小: {size_mb:.1f} MB")
            
            if size_mb > 500:  # 如果还是太大
                print("⚠️  警告: 构建产物仍然较大，可能需要进一步优化")
        else:
            print("❌ 构建文件不存在")
            return 1
            
    except subprocess.CalledProcessError as e:
        print(f"❌ 后端构建失败: {e}")
        return 1
    
    # 6. 清理临时文件
    if spec_file.exists():
        spec_file.unlink()
    
    print("🎉 优化构建完成！")
    return 0

if __name__ == "__main__":
    sys.exit(main())
