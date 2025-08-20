# 调试说明

## 问题描述
前端显示项目有5个切片，但进入项目详情页时看不到切片数据。

## 调试步骤

1. **打开浏览器开发者工具**
   - 在Chrome中按F12或右键 -> 检查
   - 切换到"Console"标签页

2. **访问项目详情页面**
   - 访问: http://localhost:3000
   - 点击进入项目: "投资亏损别甩锅，认知水平才是决定成败的关键"

3. **查看控制台输出**
   查找以下日志信息：
   ```
   🔍 Calling clips API for project: 1fdb0bf1-7f3c-44f7-a69d-90c5a1d26fbe
   📦 Raw API response: {...}
   📋 Extracted clips: X clips found
   ✅ Converted clips: X clips
   📄 First clip sample: {...}
   🎬 Loaded clips in ProjectDetailPage: [...]
   📚 Loaded collections in ProjectDetailPage: [...]
   🎯 Final project with data: {...}
   ```

4. **API验证**
   可以直接在浏览器中访问API：
   http://localhost:8000/api/v1/clips/?project_id=1fdb0bf1-7f3c-44f7-a69d-90c5a1d26fbe

## 期望结果
- API应该返回5个切片
- 前端应该正确显示这5个切片

## 如果仍然有问题
请提供控制台的完整日志输出，特别是任何错误信息。

