#!/bin/bash
# AI客服开源系统 - Linux/Mac 安装脚本

set -e

echo "═══════════════════════════════════════════════════════════"
echo "          AI客服开源系统 - 安装脚本"
echo "═══════════════════════════════════════════════════════════"
echo ""

# 检查Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未检测到 Node.js，请先安装 Node.js 18+"
    echo "下载地址: https://nodejs.org/"
    exit 1
fi

echo "[✓] Node.js 已安装 $(node --version)"

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3，请先安装 Python 3.10+"
    echo "下载地址: https://www.python.org/"
    exit 1
fi

echo "[✓] Python 已安装 $(python3 --version)"

echo ""
echo "───────────────────────────────────────"
echo "正在安装前端依赖..."
echo "───────────────────────────────────────"

npm install

echo "[✓] 前端依赖安装完成"

echo ""
echo "───────────────────────────────────────"
echo "正在安装后端依赖..."
echo "───────────────────────────────────────"

cd src/backend
pip3 install -r requirements.txt
cd ../..

echo "[✓] 后端依赖安装完成"

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "                   安装完成！"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "启动方式:"
echo "  1. 启动后端: cd src/backend && python3 main.py"
echo "  2. 启动前端: npm start"
echo ""
echo "访问地址: http://localhost:8000"
echo ""
