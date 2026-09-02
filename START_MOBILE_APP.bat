@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0python_runtime\python.exe"
if exist "%PYTHON_EXE%" goto python_ready
set "PYTHON_EXE="
for /f "delims=" %%P in ('powershell -NoProfile -Command "(Get-Command python -ErrorAction SilentlyContinue).Source"') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if defined PYTHON_EXE goto python_ready
for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if defined PYTHON_EXE goto python_ready
for /f "delims=" %%P in ('where py 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
if defined PYTHON_EXE goto python_ready

if not defined PYTHON_EXE (
  echo Python was not found.
  echo Keep python_runtime beside this file, or install Python 3.11 or newer.
  pause
  exit /b 1
)

:python_ready

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
set "MARKET_PULSE_PORT_START=%MARKET_PULSE_PORT%"
set "MARKET_PULSE_PORT="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$start=[int]$env:MARKET_PULSE_PORT_START; for($p=$start; $p -lt $start+100; $p++){ try { $listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Any, $p); $listener.Start(); $listener.Stop(); $p; break } catch {} }"`) do set "MARKET_PULSE_PORT=%%P"
if not defined MARKET_PULSE_PORT (
  echo No available port found in %MARKET_PULSE_PORT_START%-%MARKET_PULSE_PORT_START%+99.
  pause
  exit /b 1
)

for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$addresses=@([System.Net.Dns]::GetHostEntry([System.Net.Dns]::GetHostName()).AddressList); $best=$null; foreach($address in $addresses){ $ip=$address.IPAddressToString; if($address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and $ip -like '192.168.*'){ $best=$ip; break } }; if(-not $best){ foreach($address in $addresses){ $ip=$address.IPAddressToString; $parts=$ip.Split('.'); if($address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and (($ip -like '10.*') -or ($ip -like '172.*' -and $parts.Count -eq 4 -and [int]$parts[1] -ge 16 -and [int]$parts[1] -le 31))){ $best=$ip; break } } }; if($best){$best}else{'YOUR-PC-IP'}"`) do set "LOCAL_IP=%%I"

echo.
echo =====================================================
echo  Market Pulse mobile app
echo  Computer: http://127.0.0.1:%MARKET_PULSE_PORT%
echo  Phone:    http://%LOCAL_IP%:%MARKET_PULSE_PORT%
echo =====================================================
echo Connect the phone and computer to the same Wi-Fi.
echo Keep this window open. Press Ctrl+C to stop the app.
echo.

start "" powershell.exe -NoProfile -WindowStyle Hidden -Command "$url='http://127.0.0.1:' + $env:MARKET_PULSE_PORT + '/'; for($i=0; $i -lt 30; $i++){ try { $response=Invoke-WebRequest -Uri ($url + 'api/health') -UseBasicParsing -TimeoutSec 2; if([int]$response.StatusCode -eq 200){ Start-Process $url; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Market Pulse server did not become ready. Check this window for errors.','Market Pulse')"
"%PYTHON_EXE%" app.py

endlocal
