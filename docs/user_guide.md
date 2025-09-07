# 🚂 智能火车追踪系统使用指南

## 🎯 系统概述

智能火车追踪系统是一个三层架构的实时火车位置监控系统：

1. **Darwin API层** - 接收实时火车数据
2. **智能更新器层** - 优化数据获取和缓存
3. **Web界面层** - 用户交互和可视化

## 🚀 快速启动

### 1. 创建配置文件
```bash
python3 start_smart_system.py --create-env
```

### 2. 启动完整系统
```bash
python3 start_smart_system.py
```

### 3. 访问界面
- 🚂 **火车追踪**: http://localhost:3000/enhanced-train-tracker.html
- 📊 **系统统计**: http://localhost:8001/stats
- 🔗 **API文档**: http://localhost:8000/docs

## ⚙️ 环境变量配置

### 更新频率控制
```bash
# 正常时间更新间隔（秒）
NORMAL_UPDATE_INTERVAL=60

# 深夜时间更新间隔（秒）
SLOW_UPDATE_INTERVAL=300

# 初始化时更新间隔（秒）
INITIAL_UPDATE_INTERVAL=30
```

### 时间段配置
```bash
# 高峰时段（使用正常更新间隔）
PEAK_HOURS_START=6    # 早上6点开始
PEAK_HOURS_END=22     # 晚上10点结束
```

### 数据保留策略
```bash
# 位置数据保留时间（小时）
MAX_POSITION_AGE_HOURS=24

# 历史记录最大数量
MAX_HISTORY_RECORDS=10000
```

### 性能优化
```bash
# 最大并发API请求数
MAX_CONCURRENT_REQUESTS=10

# 批量处理大小
UPDATE_BATCH_SIZE=100
```

## 📊 系统工作原理

### 初始化阶段
1. **完整同步**: 获取所有可用的火车位置数据
2. **数据缓存**: 将位置信息存储在内存和数据库中
3. **坐标映射**: 使用CRS到TIPLOC映射确保位置准确性

### 运行时更新
1. **智能间隔**: 根据时间段自动调整更新频率
   - 高峰时段（6:00-22:00）: 60秒间隔
   - 深夜时段（22:00-6:00）: 300秒间隔
2. **增量更新**: 只获取有变化的火车位置
3. **变化检测**: 检测位置、状态、站台变化
4. **自动清理**: 定期清理过期数据

### 数据流程
```
Darwin Kafka → Darwin API → 智能更新器 → Web界面
     ↓              ↓            ↓
  实时数据      → 位置计算   → 智能缓存  → 用户显示
```

## 🎛️ 配置场景

### 开发环境（快速响应）
```bash
NORMAL_UPDATE_INTERVAL=30
SLOW_UPDATE_INTERVAL=60
MAX_POSITION_AGE_HOURS=6
```

### 生产环境（平衡性能）
```bash
NORMAL_UPDATE_INTERVAL=60
SLOW_UPDATE_INTERVAL=300
MAX_POSITION_AGE_HOURS=24
```

### 低资源环境（节省资源）
```bash
NORMAL_UPDATE_INTERVAL=120
SLOW_UPDATE_INTERVAL=600
MAX_POSITION_AGE_HOURS=12
MAX_CONCURRENT_REQUESTS=5
```

## 📈 监控和统计

### 系统统计API
```bash
curl http://localhost:8001/stats
```

返回信息：
- `total_trains`: 缓存中的总火车数
- `active_trains_1h`: 1小时内活跃的火车数
- `active_trains_6h`: 6小时内活跃的火车数
- `current_update_interval`: 当前更新间隔
- `last_full_sync`: 最后完整同步时间

### Web界面统计
在火车追踪界面右侧面板中显示：
- 实时火车数量
- 系统更新状态
- 最后同步时间

## 🔧 高级功能

### 手动强制同步
```bash
curl -X POST http://localhost:8001/sync
```

### 获取特定时间范围的火车
```bash
# 获取最近1小时的活跃火车
curl "http://localhost:8001/positions?max_age_minutes=60&limit=100"
```

### 系统健康检查
```bash
# Darwin API健康检查
curl http://localhost:8000/health

# 智能更新器健康检查
curl http://localhost:8001/
```

## 🐛 故障排除

### 常见问题

1. **没有火车显示**
   - 检查Darwin API是否正常: `curl http://localhost:8000/positions`
   - 检查智能更新器状态: `curl http://localhost:8001/stats`
   - 增加时间范围: `max_age_minutes=1440`

2. **更新太慢**
   - 减少更新间隔: `NORMAL_UPDATE_INTERVAL=30`
   - 增加并发数: `MAX_CONCURRENT_REQUESTS=20`

3. **内存使用过高**
   - 减少数据保留时间: `MAX_POSITION_AGE_HOURS=12`
   - 限制历史记录: `MAX_HISTORY_RECORDS=5000`

### 日志查看
```bash
# 查看Darwin API日志
tail -f darwin_api.log

# 查看智能更新器日志
tail -f smart_updater.log
```

## 🔄 系统维护

### 定期任务
- **数据清理**: 每30分钟自动清理过期数据
- **完整同步**: 每6小时执行一次完整同步
- **健康检查**: 每2秒检查进程状态

### 备份和恢复
```bash
# 备份数据库
cp train_positions.db train_positions_backup.db

# 恢复数据库
cp train_positions_backup.db train_positions.db
```

## 📱 API端点总览

### Darwin API (端口8000)
- `GET /positions` - 获取火车位置
- `GET /health` - 健康检查
- `GET /debug/stats` - 调试统计

### 智能更新器API (端口8001)
- `GET /positions` - 获取缓存的火车位置
- `GET /stats` - 系统统计信息
- `POST /sync` - 强制完整同步

### Web服务器 (端口3000)
- `/enhanced-train-tracker.html` - 主界面
- `/train-tracker.html` - 简化界面

## 🎉 最佳实践

1. **生产部署**
   - 使用反向代理（nginx）
   - 配置SSL证书
   - 设置日志轮转
   - 配置监控告警

2. **性能优化**
   - 根据实际需求调整更新间隔
   - 使用数据库索引优化查询
   - 配置适当的缓存策略

3. **安全考虑**
   - 限制API访问权限
   - 使用环境变量存储敏感信息
   - 定期更新依赖包

恭喜！你现在拥有一个完整的智能火车追踪系统！🚂✨