# 频道规范化修复总结

## 问题诊断

通过分析日志，发现了频道名"二次加前缀"的严重问题：

### 1. 频道名重复前缀
```
[Redis] SUB progress:progress:project_project_<id>   ← 重复了
```

**根本原因**：
- 前端传入：`["project_5da0b6a9-..."]`
- 网关处理：`f"progress:project_{pid}"` → `progress:project_project_5da0b6a9-...`
- 最终结果：`progress:progress:project_project_5da0b6a9-...`

### 2. 集合同步失效
```
批量取消订阅完成: 用户 homepage-user, 移除 3, 未订阅 0
订阅集同步完成: 用户 homepage-user, 新增 0, 移除 3, 未变 5
```

**根本原因**：
- 订阅时用的是：`progress:progress:project_project_<id>`
- 取消订阅时用的是：`progress:project_<id>`
- 两者不相等，导致永远无法正确取消订阅

### 3. 日志风暴
每10秒重复打印"移除3条"的日志，但Redis实际订阅集合根本没动。

## 修复方案

### 1. 频道规范化函数

```python
@staticmethod
def normalize_channel(raw: str) -> str:
    """
    把任意传入形态统一成 progress:project_<uuid>
    """
    s = (raw or "").strip()
    
    # 循环去掉重复的 progress: 前缀
    while s.startswith("progress:"):
        s = s[len("progress:"):]
    
    # 循环去掉重复的 project_ 前缀
    while s.startswith("project_"):
        s = s[len("project_"):]
    
    # 此时 s 应该就是 <uuid>，统一格式化为 progress:project_<uuid>
    return f"progress:project_{s}"
```

### 2. 幂等集合同步

```python
async def sync_user_subscriptions(self, user_id: str, channels: Set[str]) -> Dict[str, int]:
    async with self.lock:
        # 1) 规范化所有频道名
        desired = {self.normalize_channel(ch) for ch in channels}
        current = self.user_subscriptions.get(user_id, set())
        
        # 2) 计算差集
        to_add = desired - current
        to_remove = current - desired
        
        # 3) 处理新增订阅
        for channel in to_add:
            try:
                await self._subscribe_to_channel(channel)
                current.add(channel)  # 本地集合立即更新
                await self._replay_snapshot(user_id, channel)
            except Exception as e:
                logger.error(f"订阅频道失败 {channel}: {e}")
        
        # 4) 处理移除订阅
        for channel in to_remove:
            try:
                await self._unsubscribe_from_channel(channel)
                current.discard(channel)  # 本地集合立即删除
            except Exception as e:
                logger.error(f"取消订阅频道失败 {channel}: {e}")
        
        # 5) 更新用户订阅记录
        self.user_subscriptions[user_id] = current
        
        # 6) 日志降噪：只有变化时才INFO
        added, removed, same = len(to_add), len(to_remove), len(current & desired)
        if added or removed:
            logger.info(f"订阅集同步完成: 用户 {user_id}, 新增 {added}, 移除 {removed}, 未变 {same}")
        else:
            logger.debug(f"订阅集同步完成(无变更): 用户 {user_id}, 未变 {same}")
```

### 3. 统一频道名构造

**修复前**：
```python
# 各处手写频道名，容易重复前缀
channel = f"progress:project_{self.project_id}"
channels = {f"progress:project_{pid}" for pid in project_ids}
```

**修复后**：
```python
# 统一使用规范化函数
channel = WebSocketGatewayService.normalize_channel(self.project_id)
channels = set(project_ids)  # 让网关内部规范化
```

## 测试验证

### 1. 规范化函数测试

```python
# 测试用例
test_cases = [
    ("5da0b6a9-...", "progress:project_5da0b6a9-..."),
    ("project_5da0b6a9-...", "progress:project_5da0b6a9-..."),
    ("progress:project_5da0b6a9-...", "progress:project_5da0b6a9-..."),
    ("progress:progress:project_project_5da0b6a9-...", "progress:project_5da0b6a9-..."),
]

# 结果：✅ 全部通过
```

### 2. 一致性测试

```python
# 输入变体
variants = [
    "5da0b6a9-...",
    "project_5da0b6a9-...",
    "progress:project_5da0b6a9-...",
    "progress:progress:project_project_5da0b6a9-..."
]

# 输出结果：所有变体都规范化为同一个频道名
# ✅ 一致性验证通过
```

## 修复效果

### 1. 频道名统一
- **修复前**：`progress:progress:project_project_<id>`
- **修复后**：`progress:project_<id>`

### 2. 集合同步正确
- **修复前**：永远"移除3条"但实际没移除
- **修复后**：正确计算差集，实际执行订阅/取消订阅

### 3. 日志清洁
- **修复前**：每10秒重复"移除3条"日志
- **修复后**：只在真正变化时记录INFO日志

### 4. 快照回放正确
- **修复前**：快照key与订阅频道不一致
- **修复后**：使用统一的规范化频道名

## 核心原则

### 1. 单一数据源
系统的唯一合法频道格式：`progress:project_<uuid>`

### 2. 入口规范化
所有外部传入的频道名都在入口处统一规范化

### 3. 内部一致性
网关内部任何地方构造频道名都使用规范化函数

### 4. 幂等操作
集合同步操作是幂等的，多次调用相同参数结果一致

## 部署检查清单

- ✅ 频道规范化函数实现
- ✅ 幂等集合同步逻辑
- ✅ 统一频道名构造
- ✅ 日志降噪处理
- ✅ 快照回放修复
- ✅ 测试用例验证
- ✅ 模块导入正常

## 预期效果

修复后，系统应该：

1. **不再出现重复前缀**：所有频道名都是 `progress:project_<uuid>` 格式
2. **集合同步正确**：订阅和取消订阅操作正确执行
3. **日志清洁**：不再有重复的"移除3条"日志
4. **快照回放正常**：页面刷新后能正确显示当前进度
5. **连接稳定**：WebSocket连接不再频繁断开重连

这个修复解决了频道名管理的根本问题，为后续的进度条功能提供了稳定的基础。
