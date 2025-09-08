# AutoClip 系统重建指南

## 🎯 重建目标

经过数据清理后，系统已经回到完全干净的状态。现在可以重新开始，建立一个干净、一致、可维护的系统。

## 📋 当前状态

### **✅ 已完成**
- [x] 数据库完全清空（所有表记录为0）
- [x] 文件系统清理完成
- [x] 临时文件和日志清理完成
- [x] 干净的目录结构已创建
- [x] 数据库备份已保存

### **🏗️ 需要重建**
- [ ] 数据库表结构验证
- [ ] 系统配置检查
- [ ] 前端状态重置
- [ ] 新项目创建测试

## 🔧 重建步骤

### **第一步：验证系统基础**

1. **检查数据库表结构**
   ```bash
   sqlite3 data/autoclip.db ".schema"
   ```

2. **检查目录结构**
   ```bash
   tree data/ -L 3
   ```

3. **验证配置文件**
   - `backend/core/config.py`
   - `backend/core/unified_paths.py`

### **第二步：系统启动测试**

1. **启动后端服务**
   ```bash
   cd backend
   python main.py
   ```

2. **启动前端服务**
   ```bash
   cd frontend
   npm run dev
   ```

3. **检查服务状态**
   - 后端API: http://localhost:8000/health
   - 前端页面: http://localhost:3000

### **第三步：创建测试项目**

1. **上传测试视频**
   - 使用前端界面上传一个短视频
   - 验证项目创建流程

2. **检查数据一致性**
   - 验证数据库记录
   - 验证文件系统结构
   - 验证前端显示

## 📁 新的目录结构

```
data/
├── autoclip.db                 # 干净的数据库
├── autoclip_backup_*.db        # 数据库备份
├── projects/                   # 空的项目目录
├── output/                     # 空的输出目录
│   ├── clips/                  # 切片视频
│   ├── collections/            # 合集视频
│   └── metadata/               # 元数据
├── temp/                       # 临时文件
├── cache/                      # 缓存文件
├── uploads/                    # 上传文件
└── backups/                    # 备份文件
```

## 🚀 最佳实践

### **1. 数据管理**
- 每个项目完成后立即同步元数据到数据库
- 定期运行数据一致性检查
- 及时清理临时文件和缓存

### **2. 路径管理**
- 使用统一的路径管理器
- 避免硬编码路径
- 定期验证路径配置

### **3. 状态同步**
- 确保文件系统、数据库、前端状态一致
- 使用WebSocket实时更新状态
- 提供手动同步机制

## 🔍 监控和检查

### **1. 定期检查项目**
```bash
# 检查数据库状态
python scripts/check_database_status.py

# 检查文件系统一致性
python scripts/validate_paths.py

# 检查前端状态
python scripts/check_frontend_state.py
```

### **2. 数据同步**
```bash
# 同步所有项目元数据
python scripts/sync_complete_metadata.py

# 同步特定项目
python scripts/sync_complete_metadata.py <project_id>
```

### **3. 路径验证**
```bash
# 验证所有路径配置
python scripts/validate_paths.py
```

## 🚨 注意事项

### **1. 开发阶段**
- 每次测试前备份重要数据
- 使用小文件进行功能测试
- 及时清理测试数据

### **2. 生产环境**
- 定期备份数据库和重要文件
- 监控磁盘空间使用
- 设置日志轮转和清理

### **3. 故障恢复**
- 保留数据库备份
- 记录系统配置变更
- 建立故障恢复流程

## 📚 相关文档

- [系统架构说明](SYSTEM_ARCHITECTURE.md)
- [路径修复总结](PATH_FIX_SUMMARY.md)
- [快速开始指南](../QUICK_START_GUIDE.md)

## 🎉 重建完成检查清单

- [ ] 系统启动正常
- [ ] 数据库连接正常
- [ ] 前端显示正常
- [ ] 项目创建流程正常
- [ ] 数据一致性检查通过
- [ ] 路径配置验证通过
- [ ] 文档更新完成

---

**重建完成后，系统将具备：**
- 清晰的数据存储架构
- 一致的数据同步机制
- 可靠的路径管理
- 完善的监控和检查工具
- 详细的文档和指南
