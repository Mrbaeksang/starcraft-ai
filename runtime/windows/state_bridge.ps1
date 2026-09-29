param(
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [Parameter(Mandatory = $true)][string]$CandidateRva,
    [int]$TargetPid = 0
)

# Read-only research bridge. The requested value is not an ObservationV1 frame.
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
if ($CandidateRva -cnotmatch '^0x[0-9a-fA-F]{1,8}$') { throw 'Invalid candidate RVA' }
$rva = [Convert]::ToInt64($CandidateRva.Substring(2), 16)
$image = [System.IO.File]::ReadAllBytes($imagePath)
$pe = [BitConverter]::ToInt32($image, 0x3c)
$sectionCount = [BitConverter]::ToUInt16($image, $pe + 6)
$sectionTable = $pe + 24 + [BitConverter]::ToUInt16($image, $pe + 20)
$inData = $false
for ($i = 0; $i -lt $sectionCount; $i++) {
    $entry = $sectionTable + 40 * $i
    $name = [System.Text.Encoding]::ASCII.GetString($image, $entry, 8).Trim([char]0)
    if ($name -ne '.data') { continue }
    $size = [BitConverter]::ToInt32($image, $entry + 8)
    $start = [BitConverter]::ToInt32($image, $entry + 12)
    $inData = $rva -ge $start -and $rva -le $start + $size - 4 -and $rva % 4 -eq 0
    break
}
if (-not $inData) { throw 'Candidate RVA is outside aligned .data section' }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ScaiStateRead {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, IntPtr length, out IntPtr bytesRead);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
    public static uint ReadU32(IntPtr process, long address) {
        byte[] bytes = new byte[4];
        IntPtr count;
        if (!ReadProcessMemory(process, new IntPtr(address), bytes, new IntPtr(4), out count)
            || count.ToInt64() != 4)
            throw new InvalidOperationException("ReadProcessMemory failed: " + Marshal.GetLastWin32Error());
        return BitConverter.ToUInt32(bytes, 0);
    }
}
'@
$handle = [ScaiStateRead]::OpenProcess(0x0410, $false, [uint32]$game.Id)
if ($handle -eq [IntPtr]::Zero) { throw 'OpenProcess failed' }
$address = $game.MainModule.BaseAddress.ToInt64() + $rva
[Console]::Out.WriteLine((@{
    ok = $true; event = 'ready'; pid = $game.Id; client_version = $fileVersion
    client_sha256 = $imageHash; candidate_rva = $CandidateRva; game_frame_proven = $false
} | ConvertTo-Json -Compress))
try {
    while ($true) {
        $line = [Console]::ReadLine()
        if ($null -eq $line) { break }
        try {
            $request = $line | ConvertFrom-Json
            if ($request.op -eq 'quit') {
                $response = @{ ok = $true; op = 'quit' }
                $running = $false
            } elseif ($request.op -eq 'snapshot') {
                $value = [ScaiStateRead]::ReadU32($handle, $address)
                $response = @{ ok = $true; op = 'snapshot'; candidate_value = $value;
                    observed_utc = [DateTime]::UtcNow.ToString('o'); game_frame_proven = $false }
                $running = $true
            } else { throw 'Unknown state operation' }
        } catch {
            $response = @{ ok = $false; error = $_.Exception.Message }
            $running = $false
        }
        [Console]::Out.WriteLine(($response | ConvertTo-Json -Compress))
        if (-not $running) { break }
    }
} finally {
    [ScaiStateRead]::CloseHandle($handle) | Out-Null
}
