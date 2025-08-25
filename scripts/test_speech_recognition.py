#!/usr/bin/env python3
"""
语音识别模块测试脚本
用于验证重新设计的语音识别功能
"""
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.utils.speech_recognizer import (
    SpeechRecognizer,
    SpeechRecognitionConfig,
    SpeechRecognitionMethod,
    LanguageCode,
    get_available_speech_recognition_methods,
    get_supported_languages,
    get_whisper_models,
    SpeechRecognitionError
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_speech_recognition_status():
    """测试语音识别状态查询"""
    print("🔍 测试语音识别状态查询...")
    
    try:
        # 获取可用方法
        available_methods = get_available_speech_recognition_methods()
        print(f"✅ 可用方法: {available_methods}")
        
        # 获取支持的语言
        supported_languages = get_supported_languages()
        print(f"✅ 支持的语言: {supported_languages}")
        
        # 获取Whisper模型
        whisper_models = get_whisper_models()
        print(f"✅ Whisper模型: {whisper_models}")
        
        return True
    except Exception as e:
        print(f"❌ 状态查询失败: {e}")
        return False


def test_speech_recognizer_initialization():
    """测试语音识别器初始化"""
    print("\n🔧 测试语音识别器初始化...")
    
    try:
        # 创建默认配置的识别器
        recognizer = SpeechRecognizer()
        print("✅ 默认配置识别器创建成功")
        
        # 创建自定义配置的识别器
        config = SpeechRecognitionConfig(
            method=SpeechRecognitionMethod.WHISPER_LOCAL,
            language=LanguageCode.CHINESE_SIMPLIFIED,
            model="base",
            timeout=300
        )
        recognizer = SpeechRecognizer(config)
        print("✅ 自定义配置识别器创建成功")
        
        return True
    except Exception as e:
        print(f"❌ 识别器初始化失败: {e}")
        return False


def test_configuration_validation():
    """测试配置验证"""
    print("\n⚙️ 测试配置验证...")
    
    try:
        # 测试有效配置
        config = SpeechRecognitionConfig(
            method=SpeechRecognitionMethod.WHISPER_LOCAL,
            language=LanguageCode.CHINESE_SIMPLIFIED,
            model="base"
        )
        print("✅ 有效配置验证通过")
        
        # 测试无效方法（应该抛出异常）
        try:
            invalid_config = SpeechRecognitionConfig(
                method="invalid_method",
                language=LanguageCode.CHINESE_SIMPLIFIED
            )
            print("❌ 无效方法配置应该抛出异常")
            return False
        except ValueError:
            print("✅ 无效方法配置正确抛出异常")
        
        return True
    except Exception as e:
        print(f"❌ 配置验证失败: {e}")
        return False


def test_error_handling():
    """测试错误处理"""
    print("\n🚨 测试错误处理...")
    
    try:
        recognizer = SpeechRecognizer()
        
        # 测试不存在的视频文件
        non_existent_video = Path("/path/to/non/existent/video.mp4")
        
        try:
            result = recognizer.generate_subtitle(non_existent_video)
            print("❌ 不存在的文件应该抛出异常")
            return False
        except SpeechRecognitionError as e:
            print(f"✅ 不存在的文件正确抛出异常: {e}")
        
        return True
    except Exception as e:
        print(f"❌ 错误处理测试失败: {e}")
        return False


def test_language_support():
    """测试语言支持"""
    print("\n🌍 测试语言支持...")
    
    try:
        # 测试中文配置
        config_zh = SpeechRecognitionConfig(
            language=LanguageCode.CHINESE_SIMPLIFIED
        )
        print("✅ 中文配置创建成功")
        
        # 测试英文配置
        config_en = SpeechRecognitionConfig(
            language=LanguageCode.ENGLISH
        )
        print("✅ 英文配置创建成功")
        
        # 测试自动检测
        config_auto = SpeechRecognitionConfig(
            language=LanguageCode.AUTO
        )
        print("✅ 自动检测配置创建成功")
        
        # 测试日文配置
        config_ja = SpeechRecognitionConfig(
            language=LanguageCode.JAPANESE
        )
        print("✅ 日文配置创建成功")
        
        return True
    except Exception as e:
        print(f"❌ 语言支持测试失败: {e}")
        return False


def test_method_availability():
    """测试方法可用性检查"""
    print("\n🔍 测试方法可用性检查...")
    
    try:
        recognizer = SpeechRecognizer()
        available_methods = recognizer.get_available_methods()
        
        print(f"✅ 可用方法检查成功: {available_methods}")
        
        # 检查是否有至少一个可用方法
        if any(available_methods.values()):
            print("✅ 至少有一个语音识别方法可用")
        else:
            print("⚠️ 没有可用的语音识别方法")
        
        return True
    except Exception as e:
        print(f"❌ 方法可用性检查失败: {e}")
        return False


def test_whisper_models():
    """测试Whisper模型配置"""
    print("\n🤖 测试Whisper模型配置...")
    
    try:
        models = ["tiny", "base", "small", "medium", "large"]
        
        for model in models:
            config = SpeechRecognitionConfig(
                method=SpeechRecognitionMethod.WHISPER_LOCAL,
                model=model
            )
            print(f"✅ {model} 模型配置创建成功")
        
        return True
    except Exception as e:
        print(f"❌ Whisper模型配置测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🎤 语音识别模块测试开始")
    print("=" * 50)
    
    tests = [
        ("状态查询", test_speech_recognition_status),
        ("识别器初始化", test_speech_recognizer_initialization),
        ("配置验证", test_configuration_validation),
        ("错误处理", test_error_handling),
        ("语言支持", test_language_support),
        ("方法可用性", test_method_availability),
        ("Whisper模型", test_whisper_models),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！语音识别模块工作正常")
        return 0
    else:
        print("⚠️ 部分测试失败，请检查配置和依赖")
        return 1


if __name__ == "__main__":
    sys.exit(main())

