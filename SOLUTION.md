# 🚂 火车显示问题解决方案

## 问题诊断

你遇到的问题是地图上只显示默认的几个火车，主要原因是：

1. **API服务配置问题** - uvicorn启动参数错误
2. **火车数据不足** - 原始API只有3-5个火车
3. **更新间隔太长** - 默认5分钟更新一次

## 🔧 立即解决方案

### 方案1：使用简单启动脚本（推荐）

```bash
python simple_start.py
```

这会：
- 启动包含15个火车的简单API服务器
- 启动Web服务器
- 自动打开浏览器

### 方案2：手动启动

```bash
# 终端1：启动API
python train_api.py

# 终端2：启动Web服务器
python -m http.server 8080

# 然后访问: http://localhost:8080/enhanced-train-tracker.html
```

### 方案3：使用修复后的Darwin服务

```bash
# 修复启动脚本后
python start_darwin.py --update-interval 10
```

## 🎯 现在应该看到什么

运行解决方案后，你应该在地图上看到：

- **15个火车** 分布在英国各地
- **实时移动** 的火车位置
- **不同状态** 的火车（运行中、停靠、延误等）
- **🚉 车站图标** 而不是蓝色方块
- **黑色铁路线** 而不是灰色

## 🔍 验证系统正常工作

### 1. 检查API
```bash
curl http://localhost:8000/positions
```
应该返回15个火车的JSON数据。

### 2. 检查前端
访问 `http://localhost:8080/enhanced-train-tracker.html`，应该看到：
- 地图加载正常
- 控制面板显示 "🚉 显示车站"、"🚂 显示火车"、"🛤️ 显示线路"
- 地图上有多个红色火车图标在移动

### 3. 使用调试工具
```bash
# 检查API状态
python debug_api.py

# 运行完整诊断
python diagnose_train_issue.py
```

## 🚨 如果仍有问题

### 检查浏览器控制台
1. 打开浏览器开发者工具 (F12)
2. 查看Console标签页是否有错误
3. 查看Network标签页确认API请求成功

### 常见错误和解决方案

**错误**: `Failed to fetch`
**解决**: 确保API服务在8000端口运行

**错误**: `CORS policy`
**解决**: API已配置CORS，重启服务即可

**错误**: `Google Maps API key`
**解决**: 使用提供的测试密钥或申请新的API密钥

## 📱 推荐访问顺序

1. **测试页面**: `http://localhost:8080/train_test.html`
   - 简单的火车列表，验证API工作
   
2. **增强版地图**: `http://localhost:8080/enhanced-train-tracker.html`
   - 完整功能的地图应用
   
3. **原版地图**: `http://localhost:8080/index.html`
   - 原始版本的地图应用

## 🎉 成功标志

当系统正常工作时，你会看到：

- ✅ 地图上有15个红色火车图标
- ✅ 火车图标每2秒更新位置
- ✅ 点击火车显示详细信息
- ✅ 车站显示为🚉图标
- ✅ 铁路线显示为黑色线条
- ✅ 控制面板可以切换显示选项

## 💡 进一步优化

如果你想要更多火车或不同的行为：

1. **修改火车数量**: 编辑 `train_api.py` 中的 `self.trains` 字典
2. **调整更新频率**: 修改前端的 `setInterval` 时间
3. **添加真实数据**: 配置Darwin实时服务的Kafka连接

现在运行 `python simple_start.py` 就应该能看到满地图的火车了！🚂