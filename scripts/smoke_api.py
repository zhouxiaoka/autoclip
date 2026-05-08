#!/usr/bin/env python3
"""
API 烟雾测试脚本 (Python 版本)
用于验证后端 API 的关键端点是否正常工作
"""

import argparse
import sys
import time
import requests
from typing import List, Tuple, Optional
from urllib.parse import urljoin

class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

class SmokeTest:
    def __init__(self, base_url: str, timeout: int = 10, verbose: bool = False):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verbose = verbose
        self.session = requests.Session()
        self.session.timeout = timeout
        
        # 测试用例定义
        self.test_cases = [
            {
                'endpoint': '/health',
                'expected_key': 'status',
                'description': '根健康检查',
                'required': True
            },
            {
                'endpoint': '/api/health',
                'expected_key': 'status',
                'description': 'API 健康检查',
                'required': True
            },
            {
                'endpoint': '/api/v1/video-categories',
                'expected_key': 'categories',
                'description': '视频分类配置',
                'required': True
            },
            {
                'endpoint': '/api/v1/projects',
                'expected_key': 'data',
                'description': '项目列表',
                'required': False  # 可能为空，但端点应该存在
            },
            {
                'endpoint': '/api/v1/settings',
                'expected_key': 'current_provider',
                'description': '设置信息',
                'required': False
            },
            {
                'endpoint': '/api/v1/settings/desktop-mode',
                'expected_key': 'is_desktop_mode',
                'description': '桌面模式检查',
                'required': False
            }
        ]
    
    def log(self, message: str, color: str = Colors.NC):
        """打印带颜色的日志"""
        print(f"{color}{message}{Colors.NC}")
    
    def test_endpoint(self, test_case: dict) -> Tuple[bool, str]:
        """测试单个端点"""
        endpoint = test_case['endpoint']
        expected_key = test_case['expected_key']
        description = test_case['description']
        required = test_case['required']
        
        url = urljoin(self.base_url, endpoint)
        
        if self.verbose:
            self.log(f"测试: {description}", Colors.YELLOW)
            self.log(f"URL: {url}", Colors.YELLOW)
        
        try:
            response = self.session.get(url)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if expected_key and expected_key not in data:
                        error_msg = f"响应中缺少期望的键: {expected_key}"
                        if self.verbose:
                            self.log(f"响应: {data}", Colors.RED)
                        return False, error_msg
                    
                    if self.verbose:
                        self.log(f"响应: {data}", Colors.GREEN)
                    return True, "成功"
                    
                except ValueError as e:
                    error_msg = f"响应不是有效的 JSON: {e}"
                    if self.verbose:
                        self.log(f"原始响应: {response.text}", Colors.RED)
                    return False, error_msg
            else:
                error_msg = f"HTTP {response.status_code}"
                if self.verbose:
                    self.log(f"响应: {response.text}", Colors.RED)
                return False, error_msg
                
        except requests.exceptions.Timeout:
            return False, "请求超时"
        except requests.exceptions.ConnectionError:
            return False, "连接失败"
        except requests.exceptions.RequestException as e:
            return False, f"请求异常: {e}"
    
    def run_tests(self) -> Tuple[int, int]:
        """运行所有测试"""
        self.log("🚀 开始 API 烟雾测试", Colors.YELLOW)
        self.log(f"目标地址: {self.base_url}", Colors.YELLOW)
        self.log(f"超时时间: {self.timeout}秒", Colors.YELLOW)
        self.log("")
        
        total_tests = 0
        passed_tests = 0
        failed_tests = []
        
        self.log("📋 执行测试用例...", Colors.YELLOW)
        self.log("")
        
        for test_case in self.test_cases:
            total_tests += 1
            success, message = self.test_endpoint(test_case)
            
            if success:
                passed_tests += 1
                self.log(f"✅ {test_case['description']}", Colors.GREEN)
            else:
                failed_tests.append((test_case['description'], message))
                if test_case['required']:
                    self.log(f"❌ {test_case['description']} - {message}", Colors.RED)
                else:
                    self.log(f"⚠️  {test_case['description']} - {message}", Colors.YELLOW)
        
        return total_tests, passed_tests, failed_tests
    
    def print_summary(self, total_tests: int, passed_tests: int, failed_tests: List[Tuple[str, str]]):
        """打印测试总结"""
        self.log("")
        self.log("📊 测试结果", Colors.YELLOW)
        self.log(f"总测试数: {total_tests}", Colors.YELLOW)
        self.log(f"通过: {passed_tests}", Colors.GREEN)
        self.log(f"失败: {len(failed_tests)}", Colors.RED)
        
        if total_tests > 0:
            success_rate = (passed_tests * 100) // total_tests
            self.log(f"成功率: {success_rate}%", Colors.YELLOW)
            
            if failed_tests:
                self.log("")
                self.log("失败的测试:", Colors.RED)
                for description, message in failed_tests:
                    self.log(f"  - {description}: {message}", Colors.RED)
            
            if passed_tests == total_tests:
                self.log("🎉 所有测试通过！API 运行正常", Colors.GREEN)
                return 0
            elif success_rate >= 80:
                self.log("⚠️  大部分测试通过，但有一些问题", Colors.YELLOW)
                return 1
            else:
                self.log("💥 测试失败率过高，API 可能存在问题", Colors.RED)
                return 2
        else:
            self.log("❌ 没有执行任何测试", Colors.RED)
            return 3

def main():
    parser = argparse.ArgumentParser(description='API 烟雾测试脚本')
    parser.add_argument('base_url', help='API 基础 URL')
    parser.add_argument('-t', '--timeout', type=int, default=10, help='超时时间（秒，默认: 10）')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    # 创建测试实例
    smoke_test = SmokeTest(args.base_url, args.timeout, args.verbose)
    
    # 运行测试
    total_tests, passed_tests, failed_tests = smoke_test.run_tests()
    
    # 打印总结
    exit_code = smoke_test.print_summary(total_tests, passed_tests, failed_tests)
    
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
