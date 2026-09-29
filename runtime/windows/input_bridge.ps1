# Persistent foreground input for the current x64 Windows StarCraft client.
# JSON lines on stdin/stdout; no matchmaking or game policy is embedded here.
$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

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
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
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

    public static double Click(IntPtr window, uint processId, int width, int height, int x, int y) {
        Verify(window, processId, width, height);
        if (x < 0 || y < 0 || x >= width || y >= height)
            throw new ArgumentOutOfRangeException("client_coordinates");
        POINT screen = new POINT { X = x, Y = y };
        if (!ClientToScreen(window, ref screen)) throw new InvalidOperationException("screen_transform_failed");
        Stopwatch timer = Stopwatch.StartNew();
        if (!SetCursorPos(screen.X, screen.Y)) throw new InvalidOperationException("cursor_move_failed");
        INPUT down = new INPUT { type = 0, mouse = new MOUSEINPUT { dwFlags = 0x0002 } };
        INPUT up = new INPUT { type = 0, mouse = new MOUSEINPUT { dwFlags = 0x0004 } };
        if (SendInput(2, new INPUT[] { down, up }, Marshal.SizeOf(typeof(INPUT))) != 2)
            throw new InvalidOperationException("mouse_send_failed");
        timer.Stop();
        return timer.Elapsed.TotalMilliseconds;
    }

    public static double Keys(IntPtr window, uint processId, int width, int height, int[] virtualKeys) {
        Verify(window, processId, width, height);
        if (virtualKeys == null || virtualKeys.Length < 1 || virtualKeys.Length > 4)
            throw new ArgumentOutOfRangeException("virtualKeys");
        INPUT[] inputs = new INPUT[virtualKeys.Length * 2];
        for (int i = 0; i < virtualKeys.Length; i++) {
            if (virtualKeys[i] < 1 || virtualKeys[i] > 254)
                throw new ArgumentOutOfRangeException("virtualKeys");
            inputs[i] = new INPUT { type = 1, keyboard = new KEYBDINPUT { wVk = (ushort)virtualKeys[i] } };
            inputs[inputs.Length - 1 - i] = new INPUT {
                type = 1, keyboard = new KEYBDINPUT { wVk = (ushort)virtualKeys[i], dwFlags = 0x0002 }
            };
        }
        Stopwatch timer = Stopwatch.StartNew();
        if (SendInput((uint)inputs.Length, inputs, Marshal.SizeOf(typeof(INPUT))) != inputs.Length)
            throw new InvalidOperationException("keyboard_send_failed");
        timer.Stop();
        return timer.Elapsed.TotalMilliseconds;
    }
}
'@

$games = @(Get-Process -Name StarCraft -ErrorAction Stop | Where-Object { $_.MainWindowTitle -eq 'Brood War' })
if ($games.Count -ne 1) { throw "Expected one Brood War window; found $($games.Count)" }
$game = $games[0]
$window = $game.MainWindowHandle
$pidAtStart = [uint32]$game.Id
$rect = New-Object StarCraftInput+RECT
if (-not [StarCraftInput]::GetClientRect($window, [ref]$rect)) { throw 'Cannot read client rect' }
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
[Console]::Out.WriteLine((@{ ok = $true; event = 'ready'; pid = $pidAtStart; hwnd = $window.ToInt64(); width = $width; height = $height } | ConvertTo-Json -Compress))

$running = $true
while ($running) {
    $line = [Console]::ReadLine()
    if ($null -eq $line) { break }
    try {
        $request = $line | ConvertFrom-Json
        switch ($request.op) {
            'hello' {
                [StarCraftInput]::Verify($window, $pidAtStart, $width, $height)
                $response = @{ ok = $true; op = 'hello'; pid = $pidAtStart; hwnd = $window.ToInt64() }
            }
            'click' {
                if ($null -eq $request.x -or $null -eq $request.y) {
                    throw 'click requires x and y'
                }
                $elapsed = [StarCraftInput]::Click($window, $pidAtStart, $width, $height, [int]$request.x, [int]$request.y)
                $response = @{ ok = $true; op = 'click'; x = [int]$request.x; y = [int]$request.y; input_ms = $elapsed }
            }
            'keys' {
                if ($null -eq $request.vks) { throw 'keys requires vks' }
                $elapsed = [StarCraftInput]::Keys($window, $pidAtStart, $width, $height, [int[]]@($request.vks))
                $response = @{ ok = $true; op = 'keys'; input_ms = $elapsed }
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
