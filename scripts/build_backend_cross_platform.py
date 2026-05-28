#!/usr/bin/env python3
"""
构建跨平台后端二进制文件
"""

import os
import sys
import subprocess
import shutil
import platform
from pathlib import Path

def get_platform_info():
    """获取当前平台信息"""
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    if system == "darwin":
        if machine in ["arm64", "aarch64"]:
            return "macos-arm64"
        else:
            return "macos-x64"
    elif system == "windows":
        return "windows-x64"
    elif system == "linux":
        return "linux-x64"
    else:
        raise ValueError(f"不支持的平台: {system} {machine}")

def build_backend_for_platform(target_platform, project_root):
    """为指定平台构建后端"""
    print(f"🔨 构建 {target_platform} 平台后端...")
    
    backend_dir = project_root / "backend"
    resources_dir = project_root / "src-tauri" / "resources"
    
    # 确保资源目录存在
    resources_dir.mkdir(parents=True, exist_ok=True)
    
    # 检查虚拟环境
    venv_path = project_root / "venv"
    if not venv_path.exists():
        print("❌ 虚拟环境不存在，请先创建虚拟环境")
        return False
    
    # 安装依赖
    print("📦 安装Python依赖...")
    try:
        if target_platform.startswith("windows"):
            pip_path = venv_path / "Scripts" / "pip.exe"
            python_path = venv_path / "Scripts" / "python.exe"
        else:
            pip_path = venv_path / "bin" / "pip"
            python_path = venv_path / "bin" / "python"
        
        subprocess.run([str(pip_path), "install", "-r", "requirements.txt"], 
                      check=True, cwd=project_root)
        print("✅ Python依赖安装成功")
    except subprocess.CalledProcessError as e:
        print(f"❌ Python依赖安装失败: {e}")
        return False
    
    # 安装PyInstaller
    print("📦 安装PyInstaller...")
    try:
        subprocess.run([str(pip_path), "install", "pyinstaller"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ PyInstaller安装失败: {e}")
        return False
    
    # 创建PyInstaller规格文件
    spec_content = f"""
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['{backend_dir}/desktop_main.py'],
    pathex=['{backend_dir}'],
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
        'python-multipart',
        'whisper',
        'openai',
    ],
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
    a.binaries,
    a.zipfiles,
    a.datas,
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
)
"""
    
    spec_file = backend_dir / f"autoclip-backend-{target_platform}.spec"
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    # 构建后端二进制
    print("🔨 构建后端二进制...")
    try:
        subprocess.run([
            str(python_path), "-m", "PyInstaller",
            "--clean",
            str(spec_file)
        ], check=True, cwd=backend_dir)
        
        # 移动构建结果到资源目录
        if target_platform.startswith("windows"):
            dist_file = backend_dir / "dist" / "autoclip-backend.exe"
            target_file = resources_dir / f"autoclip-backend-{target_platform}.exe"
        else:
            dist_file = backend_dir / "dist" / "autoclip-backend"
            target_file = resources_dir / f"autoclip-backend-{target_platform}"
        
        if dist_file.exists():
            shutil.copy2(dist_file, target_file)
            print(f"✅ {target_platform} 后端二进制构建成功")
            
            # 设置执行权限（非Windows）
            if not target_platform.startswith("windows"):
                os.chmod(target_file, 0o755)
            
            return True
        else:
            print(f"❌ {target_platform} 构建文件不存在")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ {target_platform} 后端二进制构建失败: {e}")
        return False
    finally:
        # 清理临时文件
        if spec_file.exists():
            spec_file.unlink()

def build_all_platforms():
    """构建所有平台的后端"""
    print("🚀 开始构建跨平台后端...")
    
    project_root = Path(__file__).parent.parent
    platforms = ["macos-arm64", "macos-x64", "windows-x64", "linux-x64"]
    
    success_count = 0
    for platform_name in platforms:
        try:
            if build_backend_for_platform(platform_name, project_root):
                success_count += 1
        except Exception as e:
            print(f"❌ {platform_name} 平台构建失败: {e}")
            continue
    
    print(f"🎉 跨平台后端构建完成！成功构建 {success_count}/{len(platforms)} 个平台")
    
    # 显示构建结果
    resources_dir = project_root / "src-tauri" / "resources"
    for platform_name in platforms:
        if platform_name.startswith("windows"):
            backend_file = resources_dir / f"autoclip-backend-{platform_name}.exe"
        else:
            backend_file = resources_dir / f"autoclip-backend-{platform_name}"
        
        if backend_file.exists():
            size = backend_file.stat().st_size / (1024 * 1024)  # MB
            print(f"  📦 {platform_name}: {backend_file} ({size:.1f} MB)")

def build_current_platform():
    """构建当前平台的后端"""
    print("🚀 开始构建当前平台后端...")
    
    project_root = Path(__file__).parent.parent
    
    try:
        platform_name = get_platform_info()
        if build_backend_for_platform(platform_name, project_root):
            print(f"✅ 当前平台 {platform_name} 后端构建完成")
            return 0
        else:
            return 1
    except Exception as e:
        print(f"❌ 后端构建失败: {e}")
        return 1

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--all":
        build_all_platforms()
    else:
        return build_current_platform()

if __name__ == "__main__":
    sys.exit(main())
