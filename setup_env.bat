@echo off
REM ============================================================
REM OpenClaw Agent Harness - Conda 环境创建脚本
REM ============================================================
REM 使用方法: 双击运行或 .\setup_env.bat
REM ============================================================

echo.
echo ============================================================
echo   OpenClaw Agent Harness - 环境创建向导
echo ============================================================
echo.

REM 检查 conda 是否可用
where conda >nul 2>nul
if %errorlevel% neq 0 (
    echo [错误] 未找到 conda，请先安装 Anaconda 或 Miniconda
    echo 下载地址: https://docs.conda.io/en/latest/miniconda.html
    pause
    exit /b 1
)

REM 检查环境是否已存在
conda env list | findstr /i "agent-harness" >nul
if %errorlevel% equ 0 (
    echo [提示] 环境 'agent-harness' 已存在
    set /p recreate="是否删除并重新创建? (y/n): "
    if /i "%recreate%"=="y" (
        echo [删除] 正在删除旧环境...
        conda env remove -n agent-harness -y
    ) else (
        echo [跳过] 使用现有环境
        goto :activate
    )
)

REM 选择 Python 版本
echo.
echo 请选择 Python 版本:
echo   [1] Python 3.11 (推荐，兼容性最好)
echo   [2] Python 3.12 (最新，功能最多)
echo   [3] Python 3.10 (最稳定)
set /p py_version="请输入选项 (1-3，默认 1): "

if "%py_version%"=="" set py_version=1
if "%py_version%"=="1" set python_ver=3.11
if "%py_version%"=="2" set python_ver=3.12
if "%py_version%"=="3" set python_ver=3.10

echo.
echo [创建] 正在创建环境 (Python %python_ver%)...
conda create -n agent-harness python=%python_ver% -y

if %errorlevel% neq 0 (
    echo [错误] 环境创建失败
    pause
    exit /b 1
)

:activate
echo.
echo [成功] 环境创建完成！
echo.
echo ============================================================
echo   下一步操作:
echo ============================================================
echo.
echo 1. 激活环境:
echo    conda activate agent-harness
echo.
echo 2. 安装依赖:
echo    pip install -r requirements.txt
echo.
echo 3. 配置 API Key (二选一):
echo.
echo    # 方式 A: 环境变量
echo    export ANTHROPIC_API_KEY="your-key-here"  # Linux/Mac
echo    set ANTHROPIC_API_KEY=your-key-here        # Windows
echo.
echo    # 方式 B: 配置文件
echo    cp config.yaml.example config.yaml
echo    # 编辑 config.yaml 填入你的 API Key
echo.
echo 4. 启动应用:
echo.
echo    # CLI 模式
echo    python main.py
echo.
echo    # Web UI 模式
echo    python web.py
echo.
echo    # GUI 模式 (需要 PyQt6)
echo    python gui.py
echo.
echo ============================================================

pause
