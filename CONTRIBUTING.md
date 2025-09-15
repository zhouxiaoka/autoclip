# 贡献指南

感谢您对AutoClip项目的关注！我们欢迎所有形式的贡献，包括但不限于：

- 🐛 Bug修复
- ✨ 新功能开发
- 📚 文档改进
- 🧪 测试用例
- 💡 功能建议
- 🎨 UI/UX改进

## 开发环境设置

### 1. Fork并克隆项目

```bash
# Fork项目到您的GitHub账户，然后克隆
git clone https://github.com/your-username/autoclip.git
cd autoclip

# 添加上游仓库
git remote add upstream https://github.com/original-username/autoclip.git
```

### 2. 设置开发环境

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 配置环境变量
cp env.example .env
# 编辑.env文件，填入必要的配置
```

### 3. 启动开发服务器

```bash
# 启动Redis
brew services start redis  # macOS
# 或 sudo systemctl start redis-server  # Linux

# 启动后端
python -m uvicorn backend.main:app --reload --port 8000

# 启动Celery Worker
celery -A backend.core.celery_app worker --loglevel=info

# 启动前端
cd frontend && npm run dev
```

## 开发流程

### 1. 创建功能分支

```bash
# 从main分支创建新分支
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name
```

### 2. 开发规范

#### 代码风格

**Python (后端)**
- 遵循PEP 8规范
- 使用Black进行代码格式化
- 使用isort进行导入排序
- 函数和类需要添加docstring

```python
def example_function(param1: str, param2: int) -> bool:
    """
    示例函数的文档字符串
    
    Args:
        param1: 参数1的描述
        param2: 参数2的描述
        
    Returns:
        返回值的描述
    """
    pass
```

**TypeScript (前端)**
- 使用ESLint和Prettier
- 组件需要添加JSDoc注释
- 使用函数组件和Hooks
- 遵循Ant Design设计规范

```typescript
/**
 * 示例组件的描述
 */
interface ExampleProps {
  /** 属性描述 */
  title: string;
  /** 可选属性描述 */
  optional?: boolean;
}

const ExampleComponent: React.FC<ExampleProps> = ({ title, optional = false }) => {
  return <div>{title}</div>;
};
```

#### 提交信息规范

使用约定式提交格式：

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**类型 (type):**
- `feat`: 新功能
- `fix`: Bug修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 代码重构
- `test`: 测试相关
- `chore`: 构建过程或辅助工具的变动

**示例:**
```
feat(api): add video download endpoint
fix(ui): resolve upload modal display issue
docs(readme): update installation instructions
```

### 3. 测试

#### 后端测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_api.py

# 生成覆盖率报告
pytest --cov=backend --cov-report=html
```

#### 前端测试

```bash
cd frontend

# 运行测试
npm test

# 运行lint检查
npm run lint

# 类型检查
npm run type-check
```

### 4. 提交代码

```bash
# 添加更改
git add .

# 提交更改
git commit -m "feat(api): add video download endpoint"

# 推送分支
git push origin feature/your-feature-name
```

### 5. 创建Pull Request

1. 在GitHub上创建Pull Request
2. 填写PR模板
3. 确保所有检查通过
4. 等待代码审查

## 代码审查流程

### 审查标准

- ✅ 代码符合项目规范
- ✅ 功能正常工作
- ✅ 测试用例覆盖
- ✅ 文档已更新
- ✅ 无安全漏洞
- ✅ 性能影响评估

### 审查反馈

- 积极回应审查意见
- 及时修复问题
- 保持PR更新
- 与审查者保持沟通

## 问题报告

### Bug报告

使用GitHub Issues报告Bug时，请包含：

1. **环境信息**
   - 操作系统版本
   - Python版本
   - Node.js版本
   - 浏览器版本

2. **重现步骤**
   - 详细的操作步骤
   - 预期结果
   - 实际结果

3. **错误信息**
   - 完整的错误日志
   - 截图或录屏

4. **附加信息**
   - 相关配置文件
   - 网络环境
   - 其他可能相关的信息

### 功能建议

提出新功能建议时，请说明：

1. **功能描述**
   - 详细的功能说明
   - 使用场景
   - 预期效果

2. **实现方案**
   - 技术实现思路
   - 可能的挑战
   - 替代方案

3. **影响评估**
   - 对现有功能的影响
   - 性能影响
   - 用户体验影响

## 文档贡献

### 文档类型

- 📖 用户文档
- 🔧 开发者文档
- 🚀 部署指南
- ❓ 常见问题
- 📝 API文档

### 文档规范

- 使用Markdown格式
- 添加目录结构
- 包含代码示例
- 保持内容更新
- 使用清晰的标题层级

## 社区行为准则

### 我们的承诺

为了营造开放和友好的环境，我们承诺：

- 尊重所有贡献者
- 接受建设性批评
- 关注社区最佳利益
- 对其他社区成员表示同理心

### 不可接受的行为

- 使用性暗示的语言或图像
- 人身攻击或侮辱性评论
- 公开或私下骚扰
- 未经许可发布他人私人信息
- 其他在专业环境中不当的行为

## 联系方式

- **GitHub Issues**: [项目Issues](https://github.com/your-username/autoclip/issues)
- **GitHub Discussions**: [项目讨论](https://github.com/your-username/autoclip/discussions)
- **邮箱**: support@autoclip.com

## 致谢

感谢所有为AutoClip项目做出贡献的开发者！您的贡献让这个项目变得更好。

---

**再次感谢您的贡献！** 🎉
