param(
    [Parameter(Mandatory = $true)][string]$ManifestPath,
    [int]$TargetPid = 0,
    [string]$ExpectedSelfName = '',
    [switch]$ResearchAllSlots
)

# Diagnostic resource table read for client 1.23.10.13515 only.
# Full player slots require -ResearchAllSlots. The normal output contains
# only the uniquely matched candidate self slot and is still not policy-ready.
$ErrorActionPreference = 'Stop'
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'scai-remastered-client-v1' -or
    $manifest.product -ne 'starcraft-remastered' -or
    $manifest.architecture -ne 'x86_64' -or
    $manifest.executable_name -ne 'StarCraft.exe' -or
    $manifest.version -ne '1.23.10.13515' -or
    $manifest.sha256.ToLowerInvariant() -ne 'ce3ab05dc9a6aa35418947e5d95e19651ad6fbcd5e2c1856cd729c5b7c31281c') {
    throw 'Unsupported client manifest or resource binding build'
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
using System.Text;
public static class ScaiResourceRead {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, IntPtr length, out IntPtr bytesRead);
    [DllImport("kernel32.dll")]
    public static extern bool CloseHandle(IntPtr handle);
    public static uint[] ReadPair(IntPtr process, long address) {
        byte[] bytes = new byte[8];
        IntPtr count;
        if (!ReadProcessMemory(process, new IntPtr(address), bytes, new IntPtr(8), out count)
            || count.ToInt64() != 8)
            throw new InvalidOperationException("ReadProcessMemory failed: " + Marshal.GetLastWin32Error());
        return new uint[] { BitConverter.ToUInt32(bytes, 0), BitConverter.ToUInt32(bytes, 4) };
    }
    public static string ReadAsciiName(IntPtr process, long address) {
        byte[] bytes = new byte[32];
        IntPtr count;
        if (!ReadProcessMemory(process, new IntPtr(address), bytes, new IntPtr(32), out count)
            || count.ToInt64() != 32)
            throw new InvalidOperationException("ReadProcessMemory failed: " + Marshal.GetLastWin32Error());
        int length = Array.IndexOf(bytes, (byte)0);
        if (length < 0) length = 32;
        for (int i = 0; i < length; i++)
            if (bytes[i] < 32 || bytes[i] > 126) return "";
        return Encoding.ASCII.GetString(bytes, 0, length);
    }
}
'@
$handle = [ScaiResourceRead]::OpenProcess(0x0410, $false, [uint32]$game.Id)
if ($handle -eq [IntPtr]::Zero) { throw 'OpenProcess failed' }
$baseRva = 0xe801b4
$stride = 0x6e8
$nameBaseRva = 0x106a008
$nameStride = 0xe8
$slots = @()
try {
    for ($slot = 0; $slot -lt 8; $slot++) {
        $rva = $baseRva + $slot * $stride
        $values = [ScaiResourceRead]::ReadPair(
            $handle, $game.MainModule.BaseAddress.ToInt64() + $rva)
        $name = [ScaiResourceRead]::ReadAsciiName(
            $handle, $game.MainModule.BaseAddress.ToInt64() + $nameBaseRva + $slot * $nameStride)
        $slots += @{ slot = $slot; name = $name; minerals = $values[0]; gas = $values[1] }
    }
} finally {
    [ScaiResourceRead]::CloseHandle($handle) | Out-Null
}
$matchingSlots = @($slots | Where-Object { $ExpectedSelfName -ne '' -and $_.name -ceq $ExpectedSelfName })
$candidateSelfSlot = if ($matchingSlots.Count -eq 1) { $matchingSlots[0].slot } else { $null }
if (-not $ResearchAllSlots -and $matchingSlots.Count -ne 1) {
    throw 'Expected self name did not match exactly one player slot'
}
$selfResources = if ($matchingSlots.Count -eq 1) {
    @{ slot = $matchingSlots[0].slot; minerals = $matchingSlots[0].minerals;
        gas = $matchingSlots[0].gas }
} else { $null }
[object[]]$researchSlots = @()
if ($ResearchAllSlots) { $researchSlots = $slots }
@{
    schema = 'scai-remastered-resource-diagnostic-v1'
    client_version = $fileVersion
    client_sha256 = $imageHash
    pid = $game.Id
    table_base_rva = ('0x{0:x}' -f $baseRva)
    stride_bytes = $stride
    name_table_base_rva = ('0x{0:x}' -f $nameBaseRva)
    name_stride_bytes = $nameStride
    slots = $researchSlots
    candidate_self_slot = $candidateSelfSlot
    candidate_self_resources = $selfResources
    research_all_slots = [bool]$ResearchAllSlots
    active_match_validation_proven = $false
    local_player_id_proven = $false
    policy_observation_usable = $false
} | ConvertTo-Json -Depth 4 -Compress
