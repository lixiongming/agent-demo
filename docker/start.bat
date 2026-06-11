@echo off
REM ============================================
REM Docker 一键启动脚本 (Windows)
REM ============================================

setlocal enabledelayedexpansion

REM 检查 Docker
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker 未安装，请先安装 Docker Desktop
    exit /b 1
)

docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose 未安装
    exit /b 1
)

echo [INFO] Docker 环境检查通过

REM 处理命令
set COMMAND=%1

if "%COMMAND%"=="" set COMMAND=start
if "%COMMAND%"=="start" goto :start
if "%COMMAND%"=="stop" goto :stop
if "%COMMAND%"=="logs" goto :logs
if "%COMMAND%"=="rebuild" goto :rebuild
if "%COMMAND%"=="status" goto :status
if "%COMMAND%"=="help" goto :help
goto :help

:start
echo [INFO] 启动 Docker 服务...
cd docker

REM 检查 .env 文件
if not exist "..\\.env" (
    echo [WARN] .env 文件不存在，从 .env.example 复制
    copy "..\\.env.example" "..\\.env" >nul
)

REM 构建镜像
echo [INFO] 构建镜像...
docker-compose build

REM 启动服务
echo [INFO] 启动服务...
docker-compose up -d

REM 等待服务启动
echo [INFO] 等待服务启动...
timeout /t 10 /nobreak >nul

REM 检查服务状态
docker-compose ps

echo.
echo ============================================
echo 服务地址:
echo   API:      http://localhost:8888
echo   Qdrant:   http://localhost:6333
echo   MySQL:    localhost:3306
echo   Redis:    localhost:6379
echo ============================================
echo.
echo 查看日志: docker\start.bat logs
echo 停止服务: docker\start.bat stop
goto :end

:stop
echo [INFO] 停止 Docker 服务...
cd docker
docker-compose down
echo [INFO] 服务已停止
goto :end

:logs
cd docker
docker-compose logs -f api
goto :end

:rebuild
echo [INFO] 重建 Docker 服务...
cd docker
docker-compose down
docker-compose build --no-cache
docker-compose up -d
echo [INFO] 重建完成
goto :end

:status
cd docker
docker-compose ps
goto :end

:help
echo 用法: docker\start.bat [命令]
echo.
echo 命令:
echo   start     启动所有服务
echo   stop      停止所有服务
echo   logs      查看 API 日志
echo   rebuild   重建服务
echo   status    查看服务状态
echo   help      显示帮助信息
goto :end

:end
endlocal