#!/bin/bash

# Obsidian Knowledge Assistant - Quick Run Script
# 快速运行脚本

cd "$(dirname "$0")"

echo "🚀 Starting Obsidian Knowledge Assistant..."
echo ""

# 加载环境变量
if [ -f "config/local.sh" ]; then
    echo "📝 Loading local configuration..."
    source config/local.sh
elif [ -f "config/set_env.sh" ]; then
    echo "📝 Loading default configuration..."
    source config/set_env.sh
else
    echo "❌ Error: No configuration file found"
    echo "   Please create config/set_env.sh or config/local.sh"
    exit 1
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Error: Python not found"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# 运行分析
$PYTHON_CMD src/main.py "$@"
