import json
import struct
import zlib
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from starcraft_ai.remastered_runtime import GameWindow, WinAppWindow


def _tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", zlib.crc32(payload))

    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


def test_capture_requires_same_background_window_before_and_after(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    output = tmp_path / "frame.png"
    client = WinAppWindow(exe)
    calls: list[tuple[str, ...]] = []
    window = {
        "hwnd": 42,
        "processId": 10,
        "processName": "StarCraft",
        "title": "Brood War",
        "width": 1920,
        "height": 1080,
        "isForeground": False,
    }

    def fake_run(*args: str) -> object:
        calls.append(args)
        if args[0] == "list-windows":
            return [window]
        Path(args[args.index("--output") + 1]).write_bytes(_tiny_png())
        return {"hwnd": 42, "processId": 10, "width": 1, "height": 1}

    monkeypatch.setattr(client, "_run", fake_run)
    monkeypatch.setattr("starcraft_ai.remastered_runtime._windows_path", lambda path: str(path))

    result = client.capture(client.find_game_window(), output)

    assert result.background_window_png_captured is True
    assert result.content_visually_verified is False
    assert result.gameplay_verified is False
    assert result.mouse_input_verified is False
    assert any(call[:3] == ("screenshot", "--window", "42") for call in calls)
    assert output.read_bytes() == _tiny_png()
    assert all("--focus" not in call and "--capture-screen" not in call for call in calls)


def test_rejects_window_change_during_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    output = tmp_path / "frame.png"
    client = WinAppWindow(exe)
    before = GameWindow(42, 10, "Brood War", 1920, 1080, False)
    monkeypatch.setattr("starcraft_ai.remastered_runtime._windows_path", lambda path: str(path))

    def fake_run(*args: str) -> object:
        Path(args[args.index("--output") + 1]).write_bytes(_tiny_png())
        return {"hwnd": 43, "processId": 11, "width": 1, "height": 1}

    monkeypatch.setattr(client, "_run", fake_run)

    with pytest.raises(RuntimeError, match="Capture target changed"):
        client.capture(before, output)


def test_rejects_invalid_new_capture_without_replacing_previous_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    output = tmp_path / "frame.png"
    output.write_bytes(b"previous capture")
    client = WinAppWindow(exe)
    window = GameWindow(42, 10, "Brood War", 1920, 1080, False)
    monkeypatch.setattr("starcraft_ai.remastered_runtime._windows_path", lambda path: str(path))

    def fake_run(*args: str) -> object:
        Path(args[args.index("--output") + 1]).write_bytes(b"not a PNG")
        return {"hwnd": 42, "processId": 10, "width": 1, "height": 1}

    monkeypatch.setattr(client, "_run", fake_run)

    with pytest.raises(RuntimeError, match="not a PNG"):
        client.capture(window, output)
    assert output.read_bytes() == b"previous capture"


def test_keyboard_uses_targeted_post_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    client = WinAppWindow(exe)
    window = GameWindow(42, 10, "Brood War", 1920, 1080, False)
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str) -> object:
        calls.append(args)
        if args[0] == "list-windows":
            return [
                {
                    "hwnd": 42,
                    "processId": 10,
                    "processName": "StarCraft",
                    "title": "Brood War",
                    "width": 1920,
                    "height": 1080,
                    "isForeground": False,
                }
            ]
        return {"hwnd": 42, "actionCount": 1}

    monkeypatch.setattr(client, "_run", fake_run)
    client.send_background_keys(window, "backspace")

    assert ("send-keys", "backspace", "--window", "42", "--via", "post-message") in calls


def test_keyboard_rejects_stale_window_before_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    client = WinAppWindow(exe)
    window = GameWindow(42, 10, "Brood War", 1920, 1080, False)
    calls: list[tuple[str, ...]] = []

    def fake_run(*args: str) -> object:
        calls.append(args)
        return [
            {
                "hwnd": 42,
                "processId": 11,
                "processName": "StarCraft",
                "title": "Brood War",
                "width": 1920,
                "height": 1080,
                "isForeground": False,
            }
        ]

    monkeypatch.setattr(client, "_run", fake_run)

    with pytest.raises(RuntimeError, match="changed before keyboard input"):
        client.send_background_keys(window, "backspace")
    assert not any(call[0] == "send-keys" for call in calls)


def test_cli_reports_bad_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    client = WinAppWindow(exe)
    monkeypatch.setattr(
        "starcraft_ai.remastered_runtime.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args, 0, "not json", ""),
    )

    with pytest.raises(RuntimeError, match="one JSON result"):
        client.find_game_window()


def test_finds_exact_game_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    exe = tmp_path / "winapp.exe"
    exe.touch()
    client = WinAppWindow(exe)
    windows = [
        {"processName": "Other", "title": "Brood War"},
        {
            "hwnd": 42,
            "processId": 10,
            "processName": "StarCraft",
            "title": "Brood War",
            "width": 1920,
            "height": 1080,
            "isForeground": False,
        },
    ]
    monkeypatch.setattr(client, "_run", lambda *args: json.loads(json.dumps(windows)))

    assert client.find_game_window().hwnd == 42
