# 🚂 Darwin实时火车位置服务

改进版的Darwin实时数据消费者，支持可配置的更新间隔、数据持久化和更全面的位置数据获取。

## ✨ 新功能特性

- 🔄 **可配置更新间隔**: 支持从1分钟到1小时的更新间隔设置
- 💾 **数据持久化**: 使用SQLite数据库存储位置数据和TIPLOC坐标
- 🧹 **自动数据清理**: 定期清理过期数据，避免数据库膨胀
- 📊 **增强统计**: 提供详细的运行统计和监控信息
- 🎯 **模拟数据支持**: 在没有Kafka配置时自动使用模拟数据
- 🔧 **动态配置**: 支持运行时调整配置参数
- 📍 **TIPLOC管理**: 支持动态添加和管理TIPLOC坐标

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install confluent_kafka fastapi uvicorn pydantic
```

### 2. 基础启动（使用模拟数据）

```bash
# 使用默认配置启动
python start_darwin.py

# 或直接启动
python -m uvicorn darwin_realtime_consumer:app --host 0.0.0.0 --port 8000
```

### 3. 使用真实Kafka数据

```bash
# 设置环境变量
export KAFKA_USERNAME="your_username"
export KAFKA_PASSWORD="your_password"
export KAFKA_GROUP="your_group_id"

# 启动服务
python start_darwin.py --kafka-username $KAFKA_USERNAME --kafka-password $KAFKA_PASSWORD
```

### 4. 自定义配置启动

```bash
# 设置5分钟更新间隔，保留48小时数据
python start_darwin.py \
  --update-interval 300 \
  --max-age-hours 48 \
  --log-level DEBUG \
  --port 8001
```

## 🔧 配置管理

### 使用配置工具

```bash
# 查看系统状态
python darwin_config.py status

# 设置更新间隔为10分钟
python darwin_config.py config --interval 600

# 查看当前配置
python darwin_config.py config

# 查看位置数据
python darwin_config.py data --positions 20

# 清理旧数据
python darwin_config.py data --cleanup

# 添加TIPLOC坐标
python darwin_config.py tiploc --add LONDON 51.5074 -0.1278 "London"
```

### 环境变量配置

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `KAFKA_USERNAME` | - | Kafka用户名（必需） |
| `KAFKA_PASSWORD` | - | Kafka密码（必需） |
| `KAFKA_GROUP` | `SC-062cd84d-...` | Kafka消费者组ID |
| `UPDATE_INTERVAL` | `300` | 更新间隔（秒） |
| `MAX_AGE_HOURS` | `24` | 最大数据年龄（小时） |
| `DB_PATH` | `train_positions.db` | 数据库文件路径 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 📡 API端点

### 核心端点

- `GET /` - 服务信息和端点列表
- `GET /positions` - 获取所有火车位置
- `GET /positions/{rid}` - 获取特定火车位置
- `GET /health` - 健康检查

### 配置端点

- `GET /config` - 获取当前配置
- `POST /config/update-interval/{seconds}` - 设置更新间隔

### TIPLOC管理

- `GET /tiplocs` - 获取所有TIPLOC坐标
- `POST /tiplocs/{tiploc}` - 添加/更新TIPLOC坐标

### 调试端点

- `GET /debug/stats` - 系统统计信息
- `GET /debug/last-wrapper` - 最后的Kafka包装器
- `GET /debug/last-payload` - 最后的Darwin载荷
- `GET /debug/last-error` - 最后的错误信息
- `POST /debug/cleanup` - 手动清理数据

## 📊 API使用示例

### 获取所有火车位置

```bash
# 获取最新1000个位置（默认）
curl "http://localhost:8000/positions"

# 获取最近30分钟内的前50个位置
curl "http://localhost:8000/positions?limit=50&max_age_minutes=30"

# 只获取运行中的火车
curl "http://localhost:8000/positions?state=enroute"
```

### 获取特定火车位置

```bash
curl "http://localhost:8000/positions/T001"
```

### 动态调整更新间隔

```bash
# 设置为10分钟更新一次
curl -X POST "http://localhost:8000/config/update-interval/600"
```

### 添加TIPLOC坐标

```bash
curl -X POST "http://localhost:8000/tiplocs/LONDON?lat=51.5074&lon=-0.1278&name=London"
```

## 🗄️ 数据库结构

### train_positions表

| 字段 | 类型 | 说明 |
|------|------|------|
| rid | TEXT | 火车运行ID（主键） |
| uid | TEXT | 火车唯一ID |
| ts | TEXT | 时间戳 |
| from_tpl | TEXT | 起始TIPLOC |
| to_tpl | TEXT | 目标TIPLOC |
| lat | REAL | 纬度 |
| lon | REAL | 经度 |
| ratio | REAL | 进度比例（0-1） |
| state | TEXT | 状态（enroute/dwell/stopped） |
| platform | TEXT | 站台信息 |
| updated_at | TEXT | 更新时间 |
| raw_data | TEXT | 原始JSON数据 |

### tiploc_coords表

| 字段 | 类型 | 说明 |
|------|------|------|
| tiploc | TEXT | TIPLOC代码（主键） |
| lat | REAL | 纬度 |
| lon | REAL | 经度 |
| name | TEXT | 站点名称 |
| source | TEXT | 数据来源 |
| updated_at | TEXT | 更新时间 |

## 🔍 监控和调试

### 查看系统状态

```bash
# 使用配置工具
python darwin_config.py status

# 或直接访问API
curl "http://localhost:8000/debug/stats"
```

### 日志监控

服务使用标准Python logging，可以通过设置`LOG_LEVEL`环境变量或启动参数来调整日志级别：

```bash
# 启用调试日志
python start_darwin.py --log-level DEBUG
```

### 性能监控

系统提供以下监控指标：

- 内存中火车数量
- 总处理消息数
- 错误计数
- 消费者活跃状态
- 最后更新时间

## 🚨 故障排除

### 常见问题

1. **Kafka连接失败**
   - 检查用户名和密码是否正确
   - 确认网络连接正常
   - 查看错误日志获取详细信息

2. **数据库锁定错误**
   - 确保只有一个服务实例在运行
   - 检查数据库文件权限
   - 考虑使用不同的数据库路径

3. **内存使用过高**
   - 减少`MAX_AGE_HOURS`设置
   - 增加数据清理频率
   - 监控火车数量

4. **位置数据不准确**
   - 检查TIPLOC坐标是否正确
   - 添加缺失的TIPLOC坐标
   - 验证时间同步

### 日志分析

```bash
# 查看最近的错误
python darwin_config.py status

# 获取详细错误信息
curl "http://localhost:8000/debug/last-error"
```

## 🔄 数据流程

1. **数据接收**: 从Kafka接收Darwin实时数据
2. **数据解析**: 解析JSON格式的火车位置信息
3. **位置估算**: 基于TIPLOC坐标和时间进行位置插值
4. **数据存储**: 同时存储到内存和SQLite数据库
5. **数据清理**: 定期清理过期数据
6. **API服务**: 通过REST API提供数据访问

## 📈 性能优化

- 使用内存缓存提高查询速度
- 数据库索引优化查询性能
- 批量数据库操作减少I/O
- 异步处理提高并发性能
- 定期数据清理控制存储大小

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 📄 许可证

MIT License