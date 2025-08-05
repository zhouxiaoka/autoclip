#!/usr/bin/env python3
"""
修复backend目录下的导入路径
"""

import os
import re

def fix_imports_in_file(file_path):
    """修复单个文件中的导入路径"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换 from backend. 为相对导入
    original_content = content
    content = re.sub(r'from backend\.', 'from ', content)
    
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
        return True
    return False

def main():
    """主函数"""
    backend_dir = '/Users/zhoukk/autoclip/backend'
    fixed_count = 0
    
    for root, dirs, files in os.walk(backend_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                if fix_imports_in_file(file_path):
                    fixed_count += 1
    
    print(f"\nTotal files fixed: {fixed_count}")

if __name__ == '__main__':
    main()