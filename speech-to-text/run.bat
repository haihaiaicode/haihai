@echo off
chcp 65001 >nul
title 会议语音转文字工具

cd /d "%~dp0"

:: ============================================
:: 检查 Python 环境
:: ============================================
python --version >nul 2>&1
if %errorlevel% equ 0 goto :python_ok

:: ---------- Python 未安装 ----------
echo.
echo ╔══════════════════════════════════════════╗
echo ║  [警告] 未检测到 Python 环境            ║
echo ║  本工具需要 Python 3.9 或更高版本       ║
echo ╚══════════════════════════════════════════╝
echo.
set /p INSTALL_PY="是否自动下载并安装 Python 3.12？[Y/N]: "
if /i "%INSTALL_PY%"=="Y" goto :install_python
if /i "%INSTALL_PY%"=="y" goto :install_python

echo.
echo [取消] 请手动安装 Python 3.9+ 后重新运行本程序
echo 下载地址: https://www.python.org/downloads/
pause
exit /b 1

:: ---------- 自动安装 Python ----------
:install_python
echo.
echo [信息] 正在下载 Python 3.12 安装包，请稍候...
echo [信息] （下载速度取决于网络，约 25MB）

set "PY_URL=https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
set "PY_EXE=%TEMP%\python-3.12.8-installer.exe"

powershell -Command "& { try { Invoke-WebRequest -Uri '%PY_URL%' -OutFile '%PY_EXE%' -ErrorAction Stop; Write-Host '[信息] 下载完成，正在静默安装...'; Start-Process -FilePath '%PY_EXE%' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0' -Wait -NoNewWindow; Remove-Item '%PY_EXE%'; Write-Host '[信息] Python 安装完成！' } catch { Write-Host ('[错误] 下载失败: ' + $_.Exception.Message); exit 1 } }"

if %errorlevel% neq 0 (
    echo.
    echo [错误] 自动安装失败，请手动安装 Python
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo.
echo ╔══════════════════════════════════════════╗
echo ║  Python 安装完成！                      ║
echo ║  请重新双击 run.bat 启动程序            ║
echo ╚══════════════════════════════════════════╝
echo.
pause
exit /b 0

:: ============================================
:: Python 已就绪，正常启动流程
:: ============================================
:python_ok

:: 虚拟环境
if not exist "venv\" (
    echo [信息] 正在创建虚拟环境...
    python -m venv venv
)

call venv\Scripts\activate.bat

:: 模型缓存目录（智能检测）
if exist "D:\ai-models\huggingface\" (
    echo [信息] 使用已有模型缓存: D:\ai-models\huggingface
    set HF_HOME=D:\ai-models\huggingface
    set HF_HUB_CACHE=D:\ai-models\huggingface\hub
) else (
    echo [信息] 模型将下载到默认缓存目录（首次约 1.5GB，请耐心等待）
)

:: 国内镜像加速
set HF_ENDPOINT=https://hf-mirror.com
set HF_HUB_ENABLE_HF_XET=0

:: 安装依赖 & 启动
echo [信息] 正在检查/安装依赖...
pip install -r requirements.txt -q

echo [信息] 启动中...
python main.py

pause
