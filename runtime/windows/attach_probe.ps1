param(
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [int]$TargetPid = 0
)

$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'scai-remastered-client-v1' -or
    $manifest.product -ne 'starcraft-remastered' -or
    $manifest.architecture -ne 'x86_64' -or
    $manifest.executable_name -ne 'StarCraft.exe') {
    throw 'Unsupported client manifest'
}

$games = @(Get-Process -Name StarCraft -ErrorAction Stop | Where-Object {
    $_.MainWindowTitle -eq 'Brood War' -and ($TargetPid -eq 0 -or $_.Id -eq $TargetPid)
})
if ($games.Count -ne 1) { throw "Expected one Brood War process; found $($games.Count)" }
$game = $games[0]
$imagePath = $game.MainModule.FileName
$fileVersion = $game.MainModule.FileVersionInfo.FileVersion
$imageHash = (Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($fileVersion -ne $manifest.version -or $imageHash -ne $manifest.sha256.ToLowerInvariant()) {
    throw "Client build mismatch: version=$fileVersion sha256=$imageHash"
}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ReadOnlyProcessProbe {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, IntPtr length, out IntPtr bytesRead);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
}
'@

$processHandle = [ReadOnlyProcessProbe]::OpenProcess(0x0410, $false, [uint32]$game.Id)
if ($processHandle -eq [IntPtr]::Zero) { throw 'OpenProcess failed' }
try {
    $header = New-Object byte[] 2
    $bytesRead = [IntPtr]::Zero
    $moduleBase = $game.MainModule.BaseAddress
    $readOk = [ReadOnlyProcessProbe]::ReadProcessMemory(
        $processHandle, $moduleBase, $header, [IntPtr]2, [ref]$bytesRead)
    if (-not $readOk -or $bytesRead.ToInt64() -ne 2 -or
        $header[0] -ne 0x4d -or $header[1] -ne 0x5a) {
        throw 'ReadProcessMemory did not return the expected PE header'
    }
} finally {
    [ReadOnlyProcessProbe]::CloseHandle($processHandle) | Out-Null
}

@{
    schema = 'scai-remastered-attach-v1'
    client_version = $fileVersion
    client_sha256 = $imageHash
    pid = $game.Id
    window_handle = $game.MainWindowHandle.ToInt64()
    process_image = $imagePath
    module_base = ('0x{0:x}' -f $moduleBase.ToInt64())
    version_locked_attach = $true
    process_image_header_read = $true
    read_game_state_proven = $false
    issue_commands_proven = $false
    multiplayer_sync_proven = $false
} | ConvertTo-Json -Compress
