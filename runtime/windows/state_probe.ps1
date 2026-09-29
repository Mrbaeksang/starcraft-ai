param(
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [int]$TargetPid = 0,
    [ValidateRange(100, 5000)][int]$IntervalMs = 1000
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

$image = [System.IO.File]::ReadAllBytes($imagePath)
$pe = [BitConverter]::ToInt32($image, 0x3c)
$sectionCount = [BitConverter]::ToUInt16($image, $pe + 6)
$sectionTable = $pe + 24 + [BitConverter]::ToUInt16($image, $pe + 20)
$dataRva = -1
$dataSize = 0
for ($i = 0; $i -lt $sectionCount; $i++) {
    $entry = $sectionTable + 40 * $i
    $name = [System.Text.Encoding]::ASCII.GetString($image, $entry, 8).Trim([char]0)
    if ($name -eq '.data') {
        $dataSize = [BitConverter]::ToInt32($image, $entry + 8)
        $dataRva = [BitConverter]::ToInt32($image, $entry + 12)
        break
    }
}
if ($dataRva -lt 0 -or $dataSize -lt 4 -or $dataSize -gt 67108864) {
    throw 'Missing or oversized writable data section'
}

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;

public static class ScaiStateProbe {
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, IntPtr length, out IntPtr bytesRead);
    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);

    public struct Candidate {
        public int Offset;
        public uint First, Second, Third, Delta1, Delta2;
    }

    static byte[] Read(IntPtr process, long address, int size) {
        byte[] bytes = new byte[size];
        IntPtr count;
        if (!ReadProcessMemory(process, new IntPtr(address), bytes, new IntPtr(size), out count)
            || count.ToInt64() != size)
            throw new InvalidOperationException("ReadProcessMemory failed: " + Marshal.GetLastWin32Error());
        return bytes;
    }

    public static Candidate[] FindCounters(uint pid, long address, int size, int intervalMs) {
        IntPtr process = OpenProcess(0x0410, false, pid);
        if (process == IntPtr.Zero) throw new InvalidOperationException("OpenProcess failed");
        try {
            byte[] first = Read(process, address, size);
            Thread.Sleep(intervalMs);
            byte[] second = Read(process, address, size);
            Thread.Sleep(intervalMs);
            byte[] third = Read(process, address, size);
            List<Candidate> matches = new List<Candidate>();
            for (int offset = 0; offset <= size - 4; offset += 4) {
                uint a = BitConverter.ToUInt32(first, offset);
                uint b = BitConverter.ToUInt32(second, offset);
                uint c = BitConverter.ToUInt32(third, offset);
                if (b <= a || c <= b) continue;
                uint d1 = b - a, d2 = c - b;
                if (d1 < 10 || d1 > 500 || d2 < 10 || d2 > 500) continue;
                if (Math.Abs((long)d1 - d2) > Math.Max(5, d1 / 4)) continue;
                matches.Add(new Candidate { Offset=offset, First=a, Second=b, Third=c,
                    Delta1=d1, Delta2=d2 });
            }
            return matches.ToArray();
        } finally {
            CloseHandle(process);
        }
    }
}
'@

$address = $game.MainModule.BaseAddress.ToInt64() + $dataRva
$candidates = [ScaiStateProbe]::FindCounters([uint32]$game.Id, $address, $dataSize, $IntervalMs)
$top = @($candidates | Sort-Object @{ Expression = { [Math]::Abs($_.Delta1 - 24) + [Math]::Abs($_.Delta2 - 24) } } |
    Select-Object -First 30 | ForEach-Object {
        @{ rva = ('0x{0:x}' -f ($dataRva + $_.Offset)); first = $_.First;
            second = $_.Second; third = $_.Third; delta1 = $_.Delta1; delta2 = $_.Delta2 }
    })
@{
    schema = 'scai-remastered-counter-candidates-v1'
    client_version = $fileVersion
    client_sha256 = $imageHash
    pid = $game.Id
    section_rva = ('0x{0:x}' -f $dataRva)
    section_size = $dataSize
    sample_interval_ms = $IntervalMs
    candidate_count = $candidates.Length
    candidates = $top
    active_match_proven = $false
    game_frame_proven = $false
    read_units_proven = $false
} | ConvertTo-Json -Depth 4 -Compress
