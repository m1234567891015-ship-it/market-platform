param(
    [int]$SourcePort = 6391,
    [int]$RestorePort = 6393
)

$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path (Join-Path $PSScriptRoot '..\.td03_runtime')).Path
$cli = Join-Path $runtime 'redis-win\redis-cli.exe'
$server = Join-Path $runtime 'redis-win\redis-server.exe'
$restoreDir = Join-Path $runtime 'restore'
$sourceRdb = Join-Path $runtime 'redis-staging.rdb'
$restoreRdb = Join-Path $restoreDir 'redis-staging.rdb'
$sentinel = 'market-pulse:staging:td03-backup-restore:sentinel'
$value = 'td03-backup-restore-' + [Guid]::NewGuid().ToString('N')
$restoreProcess = $null

if (-not (Test-Path -LiteralPath $cli) -or -not (Test-Path -LiteralPath $server)) {
    throw 'Portable Redis runtime is not available.'
}

try {
    if ((& $cli -h 127.0.0.1 -p $SourcePort set $sentinel $value) -ne 'OK') {
        throw 'Source Redis sentinel write failed.'
    }
    & $cli -h 127.0.0.1 -p $SourcePort bgsave | Out-Null

    $deadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 250
        $persistence = & $cli -h 127.0.0.1 -p $SourcePort info persistence
        $inProgress = ($persistence | Select-String '^rdb_bgsave_in_progress:').ToString().Split(':')[1].Trim()
    } while ($inProgress -ne '0' -and (Get-Date) -lt $deadline)
    if ($inProgress -ne '0' -or -not (Test-Path -LiteralPath $sourceRdb)) {
        throw 'Source Redis RDB checkpoint did not complete.'
    }

    New-Item -ItemType Directory -Force -Path $restoreDir | Out-Null
    Copy-Item -LiteralPath $sourceRdb -Destination $restoreRdb -Force
    $restoreLog = Join-Path $restoreDir 'redis-restore.log'
    $argsLine = "--bind 127.0.0.1 --protected-mode yes --port $RestorePort --save `"`" --appendonly no --dir `"$restoreDir`" --dbfilename redis-staging.rdb --logfile `"$restoreLog`""
    $restoreProcess = Start-Process -FilePath $server -ArgumentList $argsLine -WorkingDirectory $runtime -WindowStyle Hidden -PassThru

    $healthy = $false
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        if ((& $cli -h 127.0.0.1 -p $RestorePort ping 2>$null) -eq 'PONG') {
            $healthy = $true
            break
        }
    }
    if (-not $healthy) {
        throw 'Restore Redis service did not become healthy.'
    }
    $readBack = & $cli -h 127.0.0.1 -p $RestorePort get $sentinel
    if ($readBack -ne $value) {
        throw 'Restored Redis sentinel read-back failed.'
    }

    & $cli -h 127.0.0.1 -p $SourcePort del $sentinel | Out-Null
    & $cli -h 127.0.0.1 -p $RestorePort del $sentinel | Out-Null
    [PSCustomObject]@{
        status = 'pass'
        source_port = $SourcePort
        restore_port = $RestorePort
        checkpoint = 'RDB bgsave pass'
        restore_readback = 'pass'
        scope = 'local substitute; not provider-native backup/restore'
    } | ConvertTo-Json -Compress
    'TD03_LOCAL_BACKUP_RESTORE_OK'
}
finally {
    if ($null -ne $restoreProcess -and $restoreProcess.HasExited -eq $false) {
        Stop-Process -Id $restoreProcess.Id -Force
    }
}
