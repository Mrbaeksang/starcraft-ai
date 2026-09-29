$ErrorActionPreference = 'Stop'

foreach ($name in @('attach_probe.ps1', 'input_bridge.ps1')) {
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
    $output = ''
    try {
        & (Join-Path $PSScriptRoot 'attach_probe.ps1') -ManifestPath $invalidManifest | Out-Null
    } catch {
        $output = $_.Exception.Message
    }
    if ($output -notmatch 'Unsupported client manifest') {
        throw "Malformed manifest was not rejected as expected: $output"
    }
    Write-Output 'Malformed manifest rejected'
} finally {
    Remove-Item -LiteralPath $invalidManifest -ErrorAction SilentlyContinue
}
