param()

$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($env:MARKET_PULSE_REDIS_URL)) {
    throw 'MARKET_PULSE_REDIS_URL must be injected by the local shell or CI secret store.'
}

# Never echo the URL: it may contain credentials. The same wrapper can run
# against local Redis/Valkey or a secret-store-provided staging endpoint.
$env:MARKET_PULSE_SHARED_STATE_NAMESPACE = 'market-pulse:staging:td03-wrapper'
$env:MARKET_PULSE_RATE_LIMIT_MODE = 'redis'
$env:MARKET_PULSE_CACHE_L2_MODE = 'redis'
$env:MARKET_PULSE_SINGLE_FLIGHT_MODE = 'redis'
$env:MARKET_PULSE_BACKGROUND_LEASE_MODE = 'redis'

python regression\td03_redis_staging_canary.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python regression\td03_production_shared_mode_probe.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python regression\td03_http_dual_process_canary.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Roll back the process-local rollout flags before evaluating the gate. These
# environment changes are confined to this wrapper process and are not written
# to deployment configuration.
$env:MARKET_PULSE_RATE_LIMIT_MODE = 'local'
$env:MARKET_PULSE_CACHE_L2_MODE = 'local'
$env:MARKET_PULSE_SINGLE_FLIGHT_MODE = 'local'
$env:MARKET_PULSE_BACKGROUND_LEASE_MODE = 'local'
python regression\td03_h11_04_rollout_gate.py
exit $LASTEXITCODE
