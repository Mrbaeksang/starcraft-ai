# Persistent foreground input for the pinned x64 Windows StarCraft client.
# JSON lines on stdin/stdout; no matchmaking or game policy is embedded here.
param([Parameter(Mandatory = $true)][string]$ManifestPath)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName System.Drawing

Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

public static class StarCraftInput {
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT { public int X, Y; }

    [StructLayout(LayoutKind.Sequential)]
    public struct MOUSEINPUT {
        public int dx, dy;
        public uint mouseData, dwFlags, time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct KEYBDINPUT {
        public ushort wVk, wScan;
        public uint dwFlags, time;
        public IntPtr dwExtraInfo;
    }

    [StructLayout(LayoutKind.Explicit, Size = 40)]
    public struct INPUT {
        [FieldOffset(0)] public uint type;
        [FieldOffset(8)] public MOUSEINPUT mouse;
        [FieldOffset(8)] public KEYBDINPUT keyboard;
    }

    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int command);
    [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
    [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint source, uint target, bool attach);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    public static uint ForegroundProcessId() {
        uint processId;
        GetWindowThreadProcessId(GetForegroundWindow(), out processId);
        return processId;
    }
    public static bool Focus(IntPtr window) {
        uint ignored;
        uint foregroundThread = GetWindowThreadProcessId(GetForegroundWindow(), out ignored);
        uint currentThread = GetCurrentThreadId();
        bool attached = foregroundThread != 0 && foregroundThread != currentThread
            && AttachThreadInput(currentThread, foregroundThread, true);
        try {
            ShowWindow(window, 9);
            BringWindowToTop(window);
            return SetForegroundWindow(window);
        } finally {
            if (attached) AttachThreadInput(currentThread, foregroundThread, false);
        }
    }
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hWnd, out RECT rect);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hWnd, ref POINT point);
    [DllImport("user32.dll", SetLastError = true)] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll", SetLastError = true)] public static extern uint SendInput(uint count, INPUT[] inputs, int size);

    public static void Verify(IntPtr window, uint processId, int width, int height) {
        if (GetForegroundWindow() != window) throw new InvalidOperationException("game_not_foreground");
        uint actualProcessId;
        GetWindowThreadProcessId(window, out actualProcessId);
        if (actualProcessId != processId) throw new InvalidOperationException("game_process_changed");
        RECT rect;
        if (!GetClientRect(window, out rect)) throw new InvalidOperationException("client_rect_unavailable");
        if (rect.Right - rect.Left != width || rect.Bottom - rect.Top != height)
            throw new InvalidOperationException("game_dimensions_changed");
    }

    public static double Click(IntPtr window, uint processId, int width, int height, int x, int y, string button) {
        Verify(window, processId, width, height);
        if (x < 0 || y < 0 || x >= width || y >= height)
            throw new ArgumentOutOfRangeException("client_coordinates");
        uint downFlag = button == "left" ? 0x0002u : button == "right" ? 0x0008u : 0;
        uint upFlag = button == "left" ? 0x0004u : button == "right" ? 0x0010u : 0;
        if (downFlag == 0) throw new ArgumentOutOfRangeException("button");
        POINT screen = new POINT { X = x, Y = y };
        if (!ClientToScreen(window, ref screen)) throw new InvalidOperationException("screen_transform_failed");
        Stopwatch timer = Stopwatch.StartNew();
        if (!SetCursorPos(screen.X, screen.Y)) throw new InvalidOperationException("cursor_move_failed");
        INPUT down = new INPUT { type = 0, mouse = new MOUSEINPUT { dwFlags = downFlag } };
        INPUT up = new INPUT { type = 0, mouse = new MOUSEINPUT { dwFlags = upFlag } };
        uint pressed = SendInput(1, new INPUT[] { down }, Marshal.SizeOf(typeof(INPUT)));
        Thread.Sleep(50);
        uint released = SendInput(1, new INPUT[] { up }, Marshal.SizeOf(typeof(INPUT)));
        if (pressed != 1 || released != 1)
            throw new InvalidOperationException("mouse_send_failed");
        timer.Stop();
        return timer.Elapsed.TotalMilliseconds;
    }

    public static double Keys(IntPtr window, uint processId, int width, int height, int[] virtualKeys) {
        Verify(window, processId, width, height);
        if (virtualKeys == null || virtualKeys.Length < 1 || virtualKeys.Length > 4)
            throw new ArgumentOutOfRangeException("virtualKeys");
        INPUT[] downs = new INPUT[virtualKeys.Length];
        INPUT[] ups = new INPUT[virtualKeys.Length];
        for (int i = 0; i < virtualKeys.Length; i++) {
            if (virtualKeys[i] < 1 || virtualKeys[i] > 254)
                throw new ArgumentOutOfRangeException("virtualKeys");
            downs[i] = new INPUT { type = 1, keyboard = new KEYBDINPUT { wVk = (ushort)virtualKeys[i] } };
            ups[virtualKeys.Length - 1 - i] = new INPUT {
                type = 1, keyboard = new KEYBDINPUT { wVk = (ushort)virtualKeys[i], dwFlags = 0x0002 }
            };
        }
        Stopwatch timer = Stopwatch.StartNew();
        uint pressed = SendInput((uint)downs.Length, downs, Marshal.SizeOf(typeof(INPUT)));
        Thread.Sleep(50);
        uint released = SendInput((uint)ups.Length, ups, Marshal.SizeOf(typeof(INPUT)));
        if (pressed != downs.Length || released != ups.Length)
            throw new InvalidOperationException("keyboard_send_failed");
        timer.Stop();
        return timer.Elapsed.TotalMilliseconds;
    }
}
'@

$games = @(Get-Process -Name StarCraft -ErrorAction Stop | Where-Object { $_.MainWindowTitle -eq 'Brood War' })
if ($games.Count -ne 1) { throw "Expected one Brood War window; found $($games.Count)" }
$game = $games[0]
$manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($manifest.schema -ne 'scai-remastered-client-v1' -or
    $manifest.product -ne 'starcraft-remastered' -or
    $manifest.architecture -ne 'x86_64' -or
    $manifest.executable_name -ne 'StarCraft.exe') {
    throw 'Unsupported client manifest'
}
$imagePath = $game.MainModule.FileName
$fileVersion = $game.MainModule.FileVersionInfo.FileVersion
$imageHash = (Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($fileVersion -ne $manifest.version -or $imageHash -ne $manifest.sha256.ToLowerInvariant()) {
    throw "Client build mismatch: version=$fileVersion sha256=$imageHash"
}
$window = $game.MainWindowHandle
$pidAtStart = [uint32]$game.Id
$rect = New-Object StarCraftInput+RECT
if (-not [StarCraftInput]::GetClientRect($window, [ref]$rect)) { throw 'Cannot read client rect' }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
$frameSequence = 0
[Console]::Out.WriteLine((@{ ok = $true; event = 'ready'; pid = $pidAtStart; hwnd = $window.ToInt64(); width = $width; height = $height; client_version = $fileVersion; client_sha256 = $imageHash } | ConvertTo-Json -Compress))

$running = $true
while ($running) {
    $line = [Console]::ReadLine()
    if ($null -eq $line) { break }
    try {
        $request = $line | ConvertFrom-Json
        switch ($request.op) {
            'focus' {
                $current = Get-Process -Id $pidAtStart -ErrorAction Stop
                if ($current.MainWindowHandle -ne $window) { throw 'game_window_changed' }
                $foregroundSet = [StarCraftInput]::Focus($window)
                $immediateWindow = [StarCraftInput]::GetForegroundWindow().ToInt64()
                Start-Sleep -Milliseconds 10
                if ([StarCraftInput]::GetForegroundWindow() -ne $window) {
                    throw "game_not_foreground:hwnd=$([StarCraftInput]::GetForegroundWindow().ToInt64()) pid=$([StarCraftInput]::ForegroundProcessId()) set=$foregroundSet immediate=$immediateWindow"
                }
                [StarCraftInput]::Verify($window, $pidAtStart, $width, $height)
                $response = @{ ok = $true; op = 'focus'; pid = $pidAtStart; hwnd = $window.ToInt64() }
            }
            'hello' {
                [StarCraftInput]::Verify($window, $pidAtStart, $width, $height)
                $response = @{ ok = $true; op = 'hello'; pid = $pidAtStart; hwnd = $window.ToInt64() }
            }
            'click' {
                if ($null -eq $request.x -or $null -eq $request.y) {
                    throw 'click requires x and y'
                }
                $button = if ($null -eq $request.button) { 'left' } else { [string]$request.button }
                $elapsed = [StarCraftInput]::Click($window, $pidAtStart, $width, $height, [int]$request.x, [int]$request.y, $button)
                $response = @{ ok = $true; op = 'click'; x = [int]$request.x; y = [int]$request.y; button = $button; input_ms = $elapsed }
            }
            'keys' {
                if ($null -eq $request.vks) { throw 'keys requires vks' }
                $elapsed = [StarCraftInput]::Keys($window, $pidAtStart, $width, $height, [int[]]@($request.vks))
                $response = @{ ok = $true; op = 'keys'; input_ms = $elapsed }
            }
            'capture' {
                [StarCraftInput]::Verify($window, $pidAtStart, $width, $height)
                $origin = New-Object StarCraftInput+POINT
                if (-not [StarCraftInput]::ClientToScreen($window, [ref]$origin)) {
                    throw 'screen_transform_failed'
                }
                $frameSequence += 1
                $path = Join-Path $env:TEMP ("scai-frame-$pidAtStart-$frameSequence.png")
                $bitmap = New-Object System.Drawing.Bitmap($width, $height)
                $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
                $timer = [System.Diagnostics.Stopwatch]::StartNew()
                try {
                    $graphics.CopyFromScreen($origin.X, $origin.Y, 0, 0, $bitmap.Size)
                    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
                } finally {
                    $timer.Stop()
                    $graphics.Dispose()
                    $bitmap.Dispose()
                }
                if ($frameSequence -gt 8) {
                    $expired = Join-Path $env:TEMP ("scai-frame-$pidAtStart-$($frameSequence - 8).png")
                    Remove-Item -LiteralPath $expired -ErrorAction SilentlyContinue
                }
                $response = @{ ok = $true; op = 'capture'; sequence = $frameSequence; path = $path; capture_ms = $timer.Elapsed.TotalMilliseconds; width = $width; height = $height }
            }
            'quit' {
                $response = @{ ok = $true; op = 'quit' }
                $running = $false
            }
            default { throw 'Unknown input operation' }
        }
    } catch {
        $response = @{ ok = $false; error = $_.Exception.Message }
    }
    [Console]::Out.WriteLine(($response | ConvertTo-Json -Compress))
}
