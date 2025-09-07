#!/bin/bash

# 火车追踪系统快速启动脚本

echo "🚂 火车实时追踪系统 - 快速启动"
echo "=================================="

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 未安装，请先安装 Python 3"
    exit 1
fi

echo "✅ Python 3 已安装"

# 安装依赖
echo "📦 安装依赖包..."
pip3 install -r requirements.txt

# 启动系统
echo "🚀 启动系统..."
python3 start_system.py

echo "🎉 启动完成!"