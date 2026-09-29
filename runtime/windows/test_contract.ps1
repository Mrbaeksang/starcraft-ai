$ErrorActionPreference = 'Stop'

foreach ($name in @('attach_probe.ps1', 'input_bridge.ps1', 'state_probe.ps1', 'state_bridge.ps1', 'resource_probe.ps1')) {
    $path = Join-Path $PSScriptRoot $name
    $tokens = $null
    $parseErrors = $null
    [System.Management.Automation.Language.Parser]::ParseFile(
        $path, [ref]$tokens, [ref]$parseErrors) | Out-Null
    if ($parseErrors.Count -gt 0) { throw "$name syntax: $($parseErrors[0].Message)" }

    $source = Get-Content -LiteralPath $path -Raw
    $match = [regex]::Match($source, "(?s)Add-Type -TypeDefinition @'\r?\n(.*?)\r?\n'@")
    if (-not $match.Success) { throw "$name C# source was not found" }
    Add-Type -TypeDefinition $match.Groups[1].Value -ErrorAction Stop
    Write-Output "$name C# compiled"
}

$invalidManifest = Join-Path $env:TEMP ('scai-invalid-manifest-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    Set-Content -LiteralPath $invalidManifest -Value '{"schema":"invalid"}' -Encoding UTF8
    foreach ($name in @('attach_probe.ps1', 'state_bridge.ps1', 'resource_probe.ps1')) {
        $output = ''
        try {
            if ($name -eq 'state_bridge.ps1') {
                & (Join-Path $PSScriptRoot $name) -ManifestPath $invalidManifest -CandidateRva 0x1090870 | Out-Null
            } else {
                & (Join-Path $PSScriptRoot $name) -ManifestPath $invalidManifest | Out-Null
            }
        } catch {
            $output = $_.Exception.Message
        }
        if ($output -notmatch 'Unsupported client manifest') {
            throw "$name did not reject malformed manifest: $output"
        }
    }
    Write-Output 'Malformed manifest rejected'
} finally {
    Remove-Item -LiteralPath $invalidManifest -ErrorAction SilentlyContinue
}
