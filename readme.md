# 🚂 火车实时追踪系统

## 📁 项目结构

```
├── main.py                 # 主启动脚本
├── backend/               # 后端代码
│   ├── api/              # API服务
│   ├── services/         # 业务服务
│   ├── utils/            # 工具类
│   └── config/           # 配置文件
├── frontend/             # 前端代码
│   ├── templates/        # HTML模板
│   └── static/          # 静态资源
├── data/                # 数据文件
│   ├── database/        # 数据库文件
│   ├── logs/           # 日志文件
│   └── cache/          # 缓存文件
├── config/             # 配置文件
├── scripts/            # 脚本文件
└── docs/              # 文档
```

## 🚀 快速启动

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp config/env.example .env

# 3. 启动系统
python main.py
```

## 📱 访问界面

- 🚂 高性能追踪: http://localhost:3000
- 📊 系统监控: http://localhost:8001/stats
- 🔗 API文档: http://localhost:8000/docs

## 📚 文档

- [用户指南](docs/user_guide.md)
- [性能对比](docs/performance.md)
- [解决方案总结](docs/solution_summary.md)
