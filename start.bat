@echo off
setlocal enabledelayedexpansion

:: AstrumShell Smart Startup Script - Windows
cd /d "%~dp0"

:: Handle command line parameters
if "%1"=="--help" goto :show_help
if "%1"=="-h" goto :show_help
if "%1"=="--version" goto :show_version
if "%1"=="-v" goto :show_version

echo.
echo  ========================================
echo    AstrumShell Startup Script - Windows
echo  ========================================
echo.

:: Check if an instance is already running
call :check_pid
if %errorlevel% neq 0 (
    echo [ERROR] An instance is already running, please stop it first
    pause
    exit /b 1
)

:: 1. Detect Python (prefer the project virtualenv)
echo [INFO] Detecting Python...

set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"
if not defined PYTHON_CMD (
    for %%p in (python python3 py py3) do (
        if not defined PYTHON_CMD (
            where %%p >nul 2>&1
            if !errorlevel! equ 0 set "PYTHON_CMD=%%p"
        )
    )
)

if "%PYTHON_CMD%"=="" (
    echo [ERROR] Python not found, please install Python 3.10+
    echo [TIP] Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('%PYTHON_CMD% --version 2^>^&1') do set "PY_VER=%%i"
echo [SUCCESS] %PY_VER%

:: Display system info
echo [INFO] System Information:
echo   OS: Windows
echo   Working Directory: %CD%
echo   Time: %date% %time%

:: 2. Virtual Environment
echo.
echo [INFO] Configuring Python environment...

if exist ".venv" goto :venv_ready
echo [INFO] Creating virtual environment...
%PYTHON_CMD% -m venv .venv >nul 2>&1
if errorlevel 1 goto :venv_failed
echo [SUCCESS] Virtual environment created
goto :venv_ready

:venv_failed
echo [ERROR] Cannot create virtual environment
pause
exit /b 1

:venv_ready

call .venv\Scripts\activate.bat >nul 2>&1

:: Use the venv interpreter so packages installed there are used at runtime
if exist ".venv\Scripts\python.exe" set "PYTHON_CMD=.venv\Scripts\python.exe"

:: 3. Install Dependencies
echo.
echo [INFO] Installing Python dependencies...

set "DEPS=click pyyaml websockets psutil cryptography"
set "TOTAL=5"
set "CURRENT=0"

for %%d in (%DEPS%) do (
    set /a CURRENT+=1
    call :printProgress !CURRENT! !TOTAL! "Installing %%d"
    
    %PYTHON_CMD% -c "import %%d" 2>nul
    if errorlevel 1 pip install %%d -q 2>nul
)

echo.
echo [SUCCESS] Python dependencies installed

:: Install project dependencies
if exist "pyproject.toml" (
    echo [INFO] Installing project configuration dependencies...
    pip install -e . -q 2>nul
)

if exist "requirements.txt" (
    echo [INFO] Installing requirements.txt...
    pip install -r requirements.txt -q 2>nul
)

:: 4. Check PHP
echo.
echo [INFO] Checking PHP...

where php >nul 2>&1
if errorlevel 1 goto :no_php
for /f "tokens=*" %%i in ('php --version 2^>^&1') do set "PHP_VER=%%i"
if defined PHP_VER echo [SUCCESS] !PHP_VER!
goto :php_done

:no_php
echo [WARNING] PHP not installed, WebUI may not work properly
echo [TIP] Install: choco install php or download from https://windows.php.net/download/

:php_done

:: 5. Create Data Directories
echo.
echo [INFO] Initializing data directories...

set "DIRS=data data\html-render data\web-toolkit data\plugin-storage data\DCIM data\pkg data\signature-verifier\keys\private data\signature-verifier\keys\public logs"

for %%d in (%DIRS%) do if not exist "%%d" mkdir "%%d" >nul 2>&1

echo [SUCCESS] Data directories ready

:: 6. Start Service
echo.
echo ========================================
echo   Starting AstrumShell
echo ========================================
echo.

:: .pid is written and removed by the service itself (oss/cli.py)

if "%1"=="--daemon" goto :daemon_mode
if "%1"=="-d" goto :daemon_mode

:: Foreground mode
echo Running... Press Ctrl+C to stop
echo.

set "RESTART_DELAY=3"
set "RESTART_COUNT=0"
set "MAX_RESTARTS=10"

:loop
%PYTHON_CMD% -m oss.cli serve
set "EXIT_CODE=%errorlevel%"

if %EXIT_CODE% equ 0 (
    echo [SUCCESS] Service exited normally
    goto :end
)

:: Check if max restarts exceeded
if %RESTART_COUNT% geq %MAX_RESTARTS% (
    echo [ERROR] Reached maximum restart count (%MAX_RESTARTS%), stopping service
    goto :end
)

set /a RESTART_COUNT+=1
echo [WARNING] Service exited abnormally (code: %EXIT_CODE%), restarting in !RESTART_DELAY!s... (!RESTART_COUNT!/%MAX_RESTARTS%)
timeout /t !RESTART_DELAY! /nobreak >nul

:: Exponential backoff (max 60 seconds)
if !RESTART_DELAY! lss 60 (
    set /a RESTART_DELAY=!RESTART_DELAY! * 2
    if !RESTART_DELAY! gtr 60 set "RESTART_DELAY=60"
)

goto :loop

:daemon_mode
echo [WARNING] Windows daemon mode requires additional configuration
echo [TIP] Use Task Scheduler or nssm tool instead
echo.
echo [INFO] Starting background service...
start /b %PYTHON_CMD% -m oss.cli serve > logs\daemon.log 2>&1
goto :end

:end
call :cleanup
call .venv\Scripts\deactivate.bat >nul 2>&1
echo.
echo ========================================
echo   AstrumShell Stopped
echo ========================================
pause
exit /b 0

:: Progress bar function
:printProgress
set /a "pct=%1 * 100 / %2"
set /a "filled=pct / 2"
set /a "empty=50-filled"
set "bar="
for /l %%i in (1,1,%filled%) do set "bar=!bar!#"
for /l %%i in (1,1,%empty%) do set "bar=!bar!-"
echo   [!bar!] !pct!%% - %3
exit /b 0

:: Check if command exists
:command_exists
where %1 >nul 2>&1
exit /b %errorlevel%

:: Get current timestamp
:get_timestamp
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set "T_DATE=%%c-%%a-%%b"
for /f "tokens=1-3 delims=: " %%a in ('time /t') do set "T_TIME=%%a:%%b:%%c"
set "TIMESTAMP=%T_DATE% %T_TIME%"
exit /b 0

:: Print separator
:print_separator
echo ========================================
exit /b 0

:: Health check
:health_check
set "check_url=%~1"
set "max_retries=%~2"
if "%max_retries%"=="" set "max_retries=30"
set "retry_count=0"

:health_loop
set /a retry_count+=1
curl -s "%check_url%" >nul 2>&1
if %errorlevel% equ 0 (
    echo [HEALTH CHECK] Service is ready
    exit /b 0
)
if %retry_count% geq %max_retries% (
    echo [HEALTH CHECK] Service startup timeout
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :health_loop

:: Remove PID file
:remove_pid
if exist ".pid" del ".pid" >nul 2>&1
exit /b 0

:: Check PID file
:: NOTE: inside a parenthesized block always use !PID! (delayed expansion).
:: %PID% is expanded at parse time (empty), so tasklist would query "pid eq "
:check_pid
if not exist ".pid" exit /b 0
set "PID="
set /p PID=<.pid
echo(!PID!| findstr /r "^[0-9][0-9]*$" >nul 2>&1
if errorlevel 1 goto :pid_stale
tasklist /fi "pid eq !PID!" 2>nul | find "!PID!" >nul
if errorlevel 1 goto :pid_stale
echo [WARNING] Service already running (PID: !PID!)
exit /b 1

:pid_stale
echo [WARNING] Stale PID file without valid PID, cleaning up
if exist ".pid" del ".pid" >nul 2>&1
exit /b 0

:: Show help information
:show_help
echo.
echo AstrumShell Startup Script - Windows Version
echo.
echo Usage: start.bat [options]
echo.
echo Options:
echo   --daemon, -d    Run in background mode (Windows recommends Task Scheduler)
echo   --help, -h      Show this help message
echo   --version, -v   Show version information
echo.
echo Examples:
echo   start.bat           Foreground mode
echo   start.bat --daemon  Background mode
echo.
exit /b 0

:: Show version information
:show_version
set "APP_VER="
for /f "tokens=2 delims== " %%v in ('findstr /b "__version__" "oss\__init__.py" 2^>nul') do set "APP_VER=%%~v"
if "%APP_VER%"=="" set "APP_VER=1.2.0"
echo AstrumShell v%APP_VER%
echo Plugin-based runtime framework (Python)
echo.
exit /b 0

:: Cleanup function
:cleanup
echo [INFO] Cleaning up...
call :remove_pid
echo [SUCCESS] Cleanup completed
exit /b 0