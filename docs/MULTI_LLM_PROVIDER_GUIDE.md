# 多模型提供商接入指南

模型列表仅作为配置示例，不代表当前服务商仍提供全部模型。实际可用模型、权限和费用以所选服务商为准；先用短样本测试，再处理长视频。安装步骤见 [安装指南](USER_INSTALLATION_GUIDE.md)，英文用户可参阅 [English installation](USER_INSTALLATION_GUIDE.en.md)。

## 🎯 功能概述

系统现在支持多个AI模型提供商，用户可以根据需要选择不同的服务商和模型，实现更灵活的AI自动切片功能。

## 🏗️ 架构设计

### 支持的提供商

| 提供商 | 显示名称 | 主要模型 | 特点 |
|--------|----------|----------|------|
| `dashscope` | Qwen | qwen-plus, qwen-max, qwen-turbo | 国内访问稳定，中文理解好 |
| `openai` | OpenAI | gpt-3.5-turbo, gpt-4, gpt-4-turbo | 支持兼容接口与自定义 Base URL |
| `gemini` | Google Gemini | gemini-2.5-flash, gemini-1.5-pro | 多模态支持，上下文长 |
| `deepseek` | DeepSeek | 以设置页列出的为准 | 自备 API Key |
| `seed` | Doubao Seed | 以设置页列出的为准 | 自备 API Key |
| `kimi` | Kimi | 以设置页列出的为准 | 自备 API Key |
| `glm` | GLM | 以设置页列出的为准 | 自备 API Key |

上表模型名是配置示例，费用和是否仍可调用以服务商为准。

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端设置页面                              │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 提供商选择  │  │ API密钥输入 │  │  模型选择   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   后端API服务                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 设置管理API │  │ 连接测试API │  │ 模型查询API │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   LLM管理器                                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ 提供商工厂  │  │ 统一接口    │  │ 配置管理    │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                   具体提供商实现                            │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ DashScope   │  │   OpenAI    │  │   Gemini    │         │
│  │  Provider   │  │  Provider   │  │  Provider   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 运行依赖安装脚本
python install_llm_dependencies.py

# 或手动安装
python -m pip install -r requirements.txt
```

### 2. 启动系统

```bash
# 启动后端服务
python -m uvicorn backend.main:app --port 8000

# 启动前端服务
cd frontend && npm run dev
```

### 3. 配置API密钥

1. 访问系统设置页面
2. 选择AI模型提供商
3. 输入对应的API密钥
4. 选择模型
5. 测试连接
6. 保存配置

## 📋 详细配置说明

### Qwen (DashScope)

**获取API密钥:**
1. 访问 [阿里云控制台](https://dashscope.console.aliyun.com/)
2. 开通 Qwen 服务
3. 创建API密钥

**支持模型:**
- `qwen-plus`: Qwen Plus (推荐)
- `qwen-max`: Qwen Max (最强性能)
- `qwen-turbo`: Qwen Turbo (快速响应)

### OpenAI

**获取API密钥:**
1. 访问 [OpenAI Platform](https://platform.openai.com/)
2. 注册账号并充值
3. 创建API密钥

**支持模型:**
- `gpt-3.5-turbo`: GPT-3.5 Turbo (性价比高)
- `gpt-4`: GPT-4 (高质量)
- `gpt-4-turbo`: GPT-4 Turbo（历史配置示例）

### Google Gemini

**获取API密钥:**
1. 访问 [Google AI Studio](https://ai.google.dev/)
2. 登录Google账号
3. 创建API密钥

**支持模型:**
- `gemini-2.5-flash`: Gemini 2.5 Flash (快速)
- `gemini-1.5-pro`: Gemini 1.5 Pro (高质量)
- `gemini-1.5-flash`: Gemini 1.5 Flash (平衡)

### DeepSeek

在设置中选择 DeepSeek，填写自己的 API Key。可用模型以设置页列出的为准。

### Doubao Seed

在设置中选择 Doubao Seed，填写自己的 API Key。可用模型以设置页列出的为准。

### Kimi

在设置中选择 Kimi，填写自己的 API Key。可用模型以设置页列出的为准。

### GLM

在设置中选择 GLM，填写自己的 API Key。可用模型以设置页列出的为准。

### Ollama / LM Studio（本地，无需 API 密钥）

设置页「模型提供商」里直接选「Ollama（本地）」或「LM Studio（本地）」，底层是 OpenAI 兼容接口 + 预设 `base_url`：

| 预设 | 默认地址 | 默认模型 |
|---|---|---|
| Ollama | `http://localhost:11434/v1` | `qwen2.5:7b`（`ollama pull qwen2.5:7b`） |
| LM Studio | `http://localhost:1234/v1` | 以 Local Server 列出的为准 |

选中后会自动列出服务端可用的模型；地址可改成局域网机器。系统代理（Clash 等）不影响本地地址。
CLI 同样可用：`autoclip run video.mp4 --provider ollama`。详见 `docs/CLI_AND_MCP.md` 第 4 节。

## 🔧 技术实现

### 核心组件

#### 1. LLMProvider 抽象基类

```python
class LLMProvider(ABC):
    @abstractmethod
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用模型API"""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """测试API连接"""
        pass
    
    @abstractmethod
    def get_available_models(self) -> List[ModelInfo]:
        """获取可用模型列表"""
        pass
```

#### 2. 提供商工厂

```python
class LLMProviderFactory:
    _providers = {
        ProviderType.DASHSCOPE: DashScopeProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.GEMINI: GeminiProvider,
    }
    
    @classmethod
    def create_provider(cls, provider_type: ProviderType, api_key: str, model_name: str, **kwargs) -> LLMProvider:
        """创建提供商实例"""
        pass
```

#### 3. LLM管理器

```python
class LLMManager:
    def __init__(self, settings_file: Optional[Path] = None):
        """初始化管理器"""
        pass
    
    def set_provider(self, provider_type: ProviderType, api_key: str, model_name: str):
        """设置提供商"""
        pass
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> str:
        """调用LLM"""
        pass
```

### API接口

#### 设置管理

```http
GET /api/v1/settings
POST /api/v1/settings
```

#### 连接测试

```http
POST /api/v1/settings/test-api-key
```

#### 模型查询

```http
GET /api/v1/settings/available-models
GET /api/v1/settings/current-provider
```

## 🎨 前端界面

### 设置页面功能

1. **提供商选择**: 下拉选择AI模型提供商
2. **API密钥输入**: 动态显示对应提供商的密钥输入框
3. **模型选择**: 根据选择的提供商显示可用模型
4. **连接测试**: 测试API密钥和模型是否可用
5. **状态显示**: 显示当前使用的提供商和模型

### 界面特点

- 响应式设计，支持不同屏幕尺寸
- 深色主题，符合系统整体风格
- 实时状态反馈，操作结果即时显示
- 详细的使用说明和帮助信息

## 🔍 故障排除

### 常见问题

#### 1. API密钥无效

**症状**: 测试连接失败，提示"API Key无效"

**解决方案**:
- 检查API密钥是否正确复制
- 确认API密钥是否已激活
- 检查账户余额是否充足

#### 2. 网络连接问题

**症状**: 连接超时或网络错误

**解决方案**:
- 检查网络连接
- 确认防火墙设置
- 尝试使用代理（如需要）

#### 3. 模型不可用

**症状**: 选择的模型无法使用

**解决方案**:
- 检查模型名称是否正确
- 确认账户是否有权限使用该模型
- 尝试切换到其他可用模型

#### 4. 依赖包问题

**症状**: 导入错误或功能异常

**解决方案**:
```bash
# 重新安装依赖
python install_llm_dependencies.py

# 或手动安装
pip install --upgrade openai google-generativeai requests dashscope
```

### 日志查看

系统会在以下位置记录详细日志：

- 后端日志: `logs/backend.log`
- 前端日志: 浏览器开发者工具控制台

## 🚀 扩展开发

### 添加新的提供商

1. **创建提供商类**:
```python
class NewProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str, **kwargs):
        super().__init__(api_key, model_name, **kwargs)
    
    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        # 实现API调用逻辑
        pass
    
    def test_connection(self) -> bool:
        # 实现连接测试逻辑
        pass
    
    def get_available_models(self) -> List[ModelInfo]:
        # 返回可用模型列表
        pass
```

2. **注册到工厂**:
```python
# 在 llm_providers.py 中添加
class LLMProviderFactory:
    _providers = {
        # ... 现有提供商
        ProviderType.NEW_PROVIDER: NewProvider,
    }
```

3. **更新前端配置**:
```typescript
// 在 SettingsPage.tsx 中添加
const providerConfig = {
  // ... 现有配置
  new_provider: {
    name: '新提供商',
    icon: <RobotOutlined />,
    color: '#ff4d4f',
    description: '新提供商描述',
    apiKeyField: 'new_provider_api_key',
    placeholder: '请输入新提供商API密钥'
  }
}
```

## 模型选择

速度、费用和字幕分析效果取决于具体模型、输入长度、服务区域和本地硬件。本项目没有在此提供统一基准测试；请用同一段字幕比较候选模型，确认连接、时间轴和标题输出后再选择。

## 🎯 最佳实践

1. **选择合适的提供商**: 根据具体需求选择最适合的提供商
2. **定期测试连接**: 确保API密钥和模型始终可用
3. **监控使用量**: 避免超出配额限制
4. **备份配置**: 定期备份API密钥和配置信息
5. **安全存储**: 不要在代码中硬编码API密钥

## 📞 技术支持

如果在使用过程中遇到问题，可以通过以下方式获取帮助：

1. 查看系统日志文件
2. 检查API提供商官方文档
3. 查看 [常见问题](FAQ.md)，仍需帮助时邮件联系 [christine_zhouye@163.com](mailto:christine_zhouye@163.com)；个人业余维护，回复时间不固定

---

**注意**: 请妥善保管您的API密钥，不要在公共场所或不安全的环境中暴露。建议定期轮换API密钥以确保安全。
