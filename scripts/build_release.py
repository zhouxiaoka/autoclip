#!/usr/bin/env python3
"""
发布版本构建脚本
用于构建所有平台的桌面应用发布版本
"""

import os
import sys
import subprocess
import shutil
import json
from pathlib import Path
from datetime import datetime

def get_version():
    """获取当前版本号"""
    try:
        with open("src-tauri/Cargo.toml", "r") as f:
            for line in f:
                if line.startswith("version ="):
                    return line.split('"')[1]
    except:
        return "1.0.0"

def clean_build_artifacts():
    """清理构建产物"""
    print("🧹 清理构建产物...")
    
    paths_to_clean = [
        "dist/",
        "build/",
        "src-tauri/target/",
        "frontend/dist/",
        "src-tauri/resources/autoclip-backend",
        "src-tauri/resources/autoclip-backend-macos-arm64",
    ]
    
    for path in paths_to_clean:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
                print(f"  ✓ 删除目录: {path}")
            else:
                os.remove(path)
                print(f"  ✓ 删除文件: {path}")

def build_frontend():
    """构建前端"""
    print("🎨 构建前端...")
    
    try:
        subprocess.run(["npm", "run", "build"], cwd="frontend", check=True)
        print("  ✓ 前端构建成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 前端构建失败: {e}")
        return False

def prepare_backend_resources():
    """准备后端资源"""
    print("🔧 准备后端资源...")
    
    try:
        subprocess.run([sys.executable, "prepare_resources.py"], cwd="scripts", check=True)
        print("  ✓ 后端资源准备完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 后端资源准备失败: {e}")
        return False

def build_desktop_app():
    """构建桌面应用"""
    print("🖥️ 构建桌面应用...")
    
    try:
        # 构建所有平台
        subprocess.run(["npm", "run", "tauri", "build"], cwd="src-tauri", check=True)
        print("  ✓ 桌面应用构建成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ❌ 桌面应用构建失败: {e}")
        return False

def create_release_package():
    """创建发布包"""
    print("📦 创建发布包...")
    
    version = get_version()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 创建发布目录
    release_dir = Path(f"releases/v{version}_{timestamp}")
    release_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制构建产物
    dist_dir = Path("src-tauri/target/release/bundle")
    if dist_dir.exists():
        for item in dist_dir.iterdir():
            if item.is_dir():
                shutil.copytree(item, release_dir / item.name)
                print(f"  ✓ 复制: {item.name}")
    
    # 复制文档
    docs_to_copy = [
        "README.md",
        "RELEASE_NOTES.md", 
        "CHANGELOG.md",
        "LICENSE",
        "env.example"
    ]
    
    for doc in docs_to_copy:
        if os.path.exists(doc):
            shutil.copy2(doc, release_dir)
            print(f"  ✓ 复制文档: {doc}")
    
    # 创建安装说明
    install_guide = release_dir / "INSTALL.md"
    with open(install_guide, "w", encoding="utf-8") as f:
        f.write(f"""# AutoClip 桌面版安装指南

## 版本: v{version}
## 构建时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

### 安装步骤

1. 根据您的操作系统选择对应的安装包：
   - Windows: 选择 .msi 文件
   - macOS: 选择 .dmg 文件  
   - Linux: 选择 .AppImage 或 .deb 文件

2. 运行安装包并按照提示完成安装

3. 首次启动时，系统会自动初始化

4. 在设置中配置通义千问API密钥（参考 env.example）

### 系统要求

- Windows 10+ / macOS 10.13+ / Linux
- 4GB+ RAM
- 10GB+ 可用存储空间
- 稳定的网络连接

### 获取帮助

- 查看 README.md 了解详细使用说明
- 查看 RELEASE_NOTES.md 了解新功能
- 提交问题到: https://github.com/zhouxiaoka/autoclip/issues

### 许可证

本项目采用 MIT 许可证，详见 LICENSE 文件。
""")
    
    print(f"  ✓ 发布包创建完成: {release_dir}")
    return release_dir

def generate_checksums(release_dir):
    """生成校验和"""
    print("🔐 生成校验和...")
    
    checksums = []
    for file_path in release_dir.rglob("*"):
        if file_path.is_file():
            try:
                import hashlib
                with open(file_path, "rb") as f:
                    sha256 = hashlib.sha256(f.read()).hexdigest()
                    relative_path = file_path.relative_to(release_dir)
                    checksums.append(f"{sha256}  {relative_path}")
            except Exception as e:
                print(f"  ⚠️ 跳过文件 {file_path}: {e}")
    
    checksum_file = release_dir / "checksums.txt"
    with open(checksum_file, "w") as f:
        f.write("\n".join(checksums))
    
    print(f"  ✓ 校验和文件: {checksum_file}")

def main():
    """主函数"""
    print("🚀 开始构建发布版本...")
    print(f"版本: {get_version()}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查环境
    if not os.path.exists("package.json"):
        print("❌ 请在项目根目录运行此脚本")
        return 1
    
    # 构建流程
    steps = [
        ("清理构建产物", clean_build_artifacts),
        ("构建前端", build_frontend),
        ("准备后端资源", prepare_backend_resources),
        ("构建桌面应用", build_desktop_app),
        ("创建发布包", create_release_package),
    ]
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        if not step_func():
            print(f"❌ {step_name}失败，构建终止")
            return 1
    
    # 生成校验和
    release_dir = create_release_package()
    generate_checksums(release_dir)
    
    print("\n🎉 发布版本构建完成！")
    print(f"📦 发布包位置: {release_dir}")
    print("\n📋 下一步:")
    print("1. 测试发布包在不同平台上的安装和运行")
    print("2. 创建 GitHub Release")
    print("3. 上传发布包到 GitHub Releases")
    print("4. 更新项目文档")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

