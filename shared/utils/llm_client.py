"""
大模型客户端 - 封装通义千问API调用
"""
import json
import logging
import os
import re
from typing import Dict, Any, List
from dashscope import Generation
from dashscope.api_entities.dashscope_response import GenerationResponse
from collections.abc import Generator

# 修复导入问题
try:
    from config import MODEL_NAME
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    import sys
    from pathlib import Path
    shared_path = Path(__file__).parent.parent
    if str(shared_path) not in sys.path:
        sys.path.insert(0, str(shared_path))
    from config import MODEL_NAME

logger = logging.getLogger(__name__)

class LLMClient:
    """通义千问API客户端"""
    
    def __init__(self):
        self.model = MODEL_NAME
    
    def call(self, prompt: str, input_data: Any = None) -> str:
        """
        调用大模型API
        
        Args:
            prompt: 提示词
            input_data: 输入数据
            
        Returns:
            模型响应文本
        """
        # 首先尝试从环境变量获取API Key
        api_key = os.getenv("DASHSCOPE_API_KEY")
        
        # 如果环境变量中没有，尝试从设置文件读取
        if not api_key:
            try:
                from pathlib import Path
                # 尝试从项目根目录的data/settings.json读取
                # 修复路径计算：从shared/utils/llm_client.py到项目根目录
                current_file = Path(__file__)
                project_root = current_file.parent.parent.parent  # shared/utils -> shared -> project_root
                settings_file = project_root / "data" / "settings.json"
                
                if settings_file.exists():
                    with open(settings_file, 'r', encoding='utf-8') as f:
                        settings = json.load(f)
                        api_key = settings.get("dashscope_api_key", "")
                        if api_key:
                            logger.info(f"从设置文件读取到API密钥: {api_key[:10]}...")
                else:
                    logger.warning(f"设置文件不存在: {settings_file}")
            except Exception as e:
                logger.warning(f"无法从设置文件读取API Key: {e}")
        
        if not api_key:
            raise ValueError("请在Web界面的设置页面输入API密钥，然后重试。")

        try:
            # 构建完整的输入
            if input_data:
                if isinstance(input_data, dict):
                    full_input = f"{prompt}\n\n输入内容：\n{json.dumps(input_data, ensure_ascii=False, indent=2)}"
                else:
                    full_input = f"{prompt}\n\n输入内容：\n{input_data}"
            else:
                full_input = prompt
            
            # 调用API
            response_or_gen = Generation.call(
                model=self.model,
                prompt=full_input,
                api_key=api_key,
                stream=False, # 确保使用非流式调用
            )
            
            response: GenerationResponse
            if isinstance(response_or_gen, Generator):
                response = next(response_or_gen)
            else:
                response = response_or_gen

            # 详细检查API响应
            if response and response.status_code == 200:
                if response.output and response.output.text is not None:
                    return response.output.text
                else:
                    # API成功但输出为空，可能是内容安全过滤等原因
                    finish_reason = response.output.finish_reason if response.output else 'unknown'
                    error_msg = f"API请求成功，但输出为空。结束原因: {finish_reason}"
                    logger.warning(error_msg)
                    return "" # 返回空字符串，让上层处理
            else:
                # API调用失败
                code = response.code if hasattr(response, 'code') else 'N/A'
                message = response.message if hasattr(response, 'message') else '未知API错误'
                
                if "Invalid ApiKey" in str(message):
                    raise ValueError("API Key无效或不正确，请在设置页面重新输入。")

                error_msg = f"API调用失败 - Status: {response.status_code}, Code: {code}, Message: {message}"
                logger.error(error_msg)
                raise Exception(message)
                
        except StopIteration:
            # next(response_gen) 可能会在生成器为空时引发此异常
            error_msg = "API调用未返回任何响应。"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            logger.error(f"LLM调用发生未知异常: {str(e)}")
            raise
    
    def call_with_retry(self, prompt: str, input_data: Any = None, max_retries: int = 3) -> str:
        """
        带重试机制的API调用
        
        Args:
            prompt: 提示词
            input_data: 输入数据
            max_retries: 最大重试次数
            
        Returns:
            模型响应文本
        """
        for attempt in range(max_retries):
            try:
                return self.call(prompt, input_data)
            except ValueError: # 如果是API Key或参数错误，不重试
                raise
            except Exception as e:
                # 对于某些可重试的错误，可以添加特定逻辑，但目前对通用异常进行重试
                if attempt == max_retries - 1:
                    logger.error(f"LLM调用在{max_retries}次重试后彻底失败。")
                    raise
                logger.warning(f"第{attempt + 1}次调用失败，准备重试: {str(e)}")
                import time
                time.sleep(2 ** attempt)  # 指数退避
        return "" # 确保所有路径都有返回值
    
    def _preprocess_llm_response(self, response: str) -> str:
        """
        预处理LLM响应，移除常见的非JSON内容
        """
        # 移除开头的标题和说明文字
        lines = response.split('\n')
        json_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('[') or stripped.startswith('{'):
                json_start = i
                break
        
        if json_start >= 0:
            response = '\n'.join(lines[json_start:])
        
        # 移除末尾的非JSON内容
        if '```' in response:
            # 如果有多个```，取第一个之前的内容
            parts = response.split('```')
            if len(parts) > 1:
                response = parts[0]
        
        return response.strip()
    
    def _auto_fix_response(self, response: str) -> str:
        """
        自动修复常见的响应问题
        """
        # 移除BOM和特殊字符
        response = response.lstrip('\ufeff')
        response = response.strip()
        
        # 修复中文引号
        response = response.replace('"', '\"').replace('"', '\"')
        
        return response
    
    def _validate_json_structure(self, parsed_data: Any) -> bool:
        """
        验证JSON结构的有效性
        """
        try:
            if not isinstance(parsed_data, list):
                logger.error(f"响应不是数组格式，实际类型: {type(parsed_data)}")
                return False
            
            for i, item in enumerate(parsed_data):
                if not isinstance(item, dict):
                    logger.error(f"第{i}个元素不是对象格式，实际类型: {type(item)}")
                    return False
                    
                # 检查基本字段（可根据具体需求调整）
                if 'outline' in item or 'start_time' in item or 'end_time' in item:
                    required_fields = ['outline', 'start_time', 'end_time']
                    for field in required_fields:
                        if field not in item:
                            logger.error(f"第{i}个元素缺少必需字段: {field}")
                            return False
        except Exception as e:
            logger.error(f"验证JSON结构时出错: {e}")
            return False
        
        return True
    
    def parse_json_response(self, response: str) -> Any:
        """
        从可能包含Markdown格式的文本中解析JSON对象。
        该函数具有多层容错机制：
        1. 预处理响应，移除非JSON内容
        2. 优先从Markdown代码块提取。
        3. 如果失败，则尝试直接解析整个响应（在净化后）。
        4. 如果再次失败，则使用通用正则表达式寻找并解析JSON。
        5. 最后尝试修复常见JSON错误后再解析。
        """
        
        def sanitize_string(s: str) -> str:
            """增强的净化函数，移除可能导致JSON解析失败的字符"""
            # 移除BOM标记
            s = s.lstrip('\ufeff')
            # 移除前后空白符
            s = s.strip()
            # 移除可能的控制字符（保留必要的换行和制表符）
            s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
            return s
        
        def fix_common_json_errors(json_str: str) -> str:
            """修复常见的JSON格式错误"""
            # 记录原始字符串用于调试
            original_str = json_str
            
            # 1. 修复缺少逗号的问题
            json_str = re.sub(r'}\s*{', '},{', json_str)
            json_str = re.sub(r']\s*\[', '],[', json_str)
            
            # 2. 修复对象之间缺少逗号的问题（更精确的模式）
            json_str = re.sub(r'}\s*\n\s*{', '},\n{', json_str)
            
            # 3. 修复多余的逗号
            json_str = re.sub(r',\s*}', '}', json_str)
            json_str = re.sub(r',\s*]', ']', json_str)
            
            # 4. 修复单引号为双引号
            json_str = re.sub(r"'([^']*?)'\s*:", r'"\1":', json_str)
            json_str = re.sub(r":\s*'([^']*?)'", r': "\1"', json_str)
            
            # 5. 修复字段名没有引号的问题
            json_str = re.sub(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'"\1":', json_str)
            
            # 6. 修复可能的换行符问题
            json_str = re.sub(r'\n\s*\n', '\n', json_str)
            
            # 7. 确保数组和对象的正确闭合
            # 统计括号和方括号的数量
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            open_brackets = json_str.count('[')
            close_brackets = json_str.count(']')
            
            # 如果括号不匹配，尝试修复
            if open_braces > close_braces:
                json_str += '}' * (open_braces - close_braces)
            if open_brackets > close_brackets:
                json_str += ']' * (open_brackets - close_brackets)
            
            # 记录修复过程
            if json_str != original_str:
                logger.debug(f"JSON修复前: {original_str[:100]}...")
                logger.debug(f"JSON修复后: {json_str[:100]}...")
            
            return json_str

        response = response.strip()
        
        # 0. 预处理响应，移除非JSON内容
        response = self._preprocess_llm_response(response)
        logger.debug(f"预处理后的响应: {response[:200]}...")
        
        # 1. 优先尝试从Markdown代码块中提取
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response, re.DOTALL)
        if match:
            json_str = sanitize_string(match.group(1))
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # 记录具体的错误位置和上下文
                error_pos = e.pos if hasattr(e, 'pos') else 0
                context_start = max(0, error_pos - 50)
                context_end = min(len(json_str), error_pos + 50)
                context = json_str[context_start:context_end]
                logger.error(f"JSON解析失败在位置{error_pos}，上下文: ...{context}...")
                logger.warning(f"从Markdown提取的内容解析失败: {e}。将尝试修复后解析。")
                
                # 尝试修复常见错误后再解析
                try:
                    fixed_json = fix_common_json_errors(json_str)
                    return json.loads(fixed_json)
                except json.JSONDecodeError:
                    logger.warning("修复后仍然解析失败，将尝试解析整个响应。")
        
        # 2. 如果没有Markdown，或Markdown解析失败，尝试整个响应
        try:
            sanitized_response = sanitize_string(response)
            return json.loads(sanitized_response)
        except json.JSONDecodeError:
            # 3. 如果整个响应直接解析也失败，做最后一次尝试，用通用正则寻找
            logger.warning("直接解析响应失败，尝试使用通用正则寻找JSON...")
            json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', response, re.DOTALL)
            if json_match:
                json_str = sanitize_string(json_match.group())
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    # 4. 最后尝试修复常见错误
                    try:
                        fixed_json = fix_common_json_errors(json_str)
                        return json.loads(fixed_json)
                    except json.JSONDecodeError as final_e:
                        logger.error(f"最终尝试解析失败: {final_e}")
                        # 保存原始响应以便调试
                        import tempfile
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
                            f.write(response)
                            logger.error(f"原始响应已保存到 {f.name} 以便调试")
                        raise ValueError(f"无法从响应中解析出有效的JSON: {response[:200]}...") from final_e
            
            # 如果连通用正则都找不到，就彻底失败
            raise ValueError(f"无法从响应中解析出有效的JSON: {response[:200]}...")