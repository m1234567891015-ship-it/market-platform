@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0python_runtime\python.exe"
if not exist "%PYTHON_EXE%" (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=py"
)
if not exist "%PYTHON_EXE%" (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
  echo Python was not found.
  echo Keep python_runtime beside this file, or install Python 3.11 or newer.
  pause
  exit /b 1
)

"%PYTHON_EXE%" -c "import flask" >nul 2>nul
if errorlevel 1 (
  echo Installing required Python packages...
  "%PYTHON_EXE%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

set "MARKET_PULSE_HOST=0.0.0.0"
if not defined MARKET_PULSE_PORT set "MARKET_PULSE_PORT=5000"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$start=[int]$env:MARKET_PULSE_PORT; for($p=$start; $p -lt $start+100; $p++){ try { $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, $p); $listener.Start(); $listener.Stop(); $p; break } catch {} }"`) do set "MARKET_PULSE_PORT=%%P"
if not defined MARKET_PULSE_PORT set "MARKET_PULSE_PORT=5000"

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$ip=(Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object {$_.IPAddress -notlike '127.*' -and $_.InterfaceOperationalStatus -eq 'Up'} ^| Sort-Object InterfaceMetric ^| Select-Object -First 1 -ExpandProperty IPAddress); if($ip){$ip}else{'YOUR-PC-IP'}"`) do set "LOCAL_IP=%%I"

echo.
echo =====================================================
echo  Market Pulse mobile app
echo  Computer: http://127.0.0.1:%MARKET_PULSE_PORT%
echo  Phone:    http://%LOCAL_IP%:%MARKET_PULSE_PORT%
echo =====================================================
echo Connect the phone and computer to the same Wi-Fi.
echo Keep this window open. Press Ctrl+C to stop the app.
echo.

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process ('http://127.0.0.1:' + $env:MARKET_PULSE_PORT)"
"%PYTHON_EXE%" app.py

endlocal
