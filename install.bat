@echo off
chcp 65001 >nul
echo ═══════════════════════════════════════════════════════════
echo          AI客服开源系统 - Windows 安装脚本
echo ═══════════════════════════════════════════════════════════
echo.

:: 检查Node.js
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Node.js，请先安装 Node.js 18+
    echo 下载地址: https://nodejs.org/
    pause
    exit /b 1
)

echo [✓] Node.js 已安装
node --version

:: 检查Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/
    pause
    exit /b 1
)

echo [✓] Python 已安装
python --version

echo.
echo ────────────────────────────────────────
echo 正在安装前端依赖...
echo ────────────────────────────────────────

npm install

if %errorlevel% neq 0 (
    echo [错误] 前端依赖安装失败
    pause
    exit /b 1
)

echo [✓] 前端依赖安装完成

echo.
echo ────────────────────────────────────────
echo 正在安装后端依赖...
echo ────────────────────────────────────────

cd src\backend
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

cd ..\..

echo [✓] 后端依赖安装完成

echo.
echo ═══════════════════════════════════════════════════════════
echo                   安装完成！
echo ═══════════════════════════════════════════════════════════
echo.
echo 启动方式:
echo   1. 启动后端: cd src\backend ^&^& python main.py
echo   2. 启动前端: npm start
echo.
echo 访问地址: http://localhost:8000
echo.
pause
