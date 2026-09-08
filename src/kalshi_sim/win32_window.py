"""Win32 window controller for floating desktop widget mode on Windows."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import List, Optional, Tuple

logger = logging.getLogger("Win32Window")

# Win32 Constants
GWL_EXSTYLE = -20
WS_EX_TOPMOST = 0x00000008
HWND_TOPMOST = wintypes.HWND(-1)
HWND_NOTOPMOST = wintypes.HWND(-2)

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_SHOWWINDOW = 0x0040
SWP_NOACTIVATE = 0x0010

WIDGET_WIDTH_MINIMIZED = 515
WIDGET_HEIGHT_MINIMIZED = 310
WIDGET_WIDTH_EXPANDED = 515
WIDGET_HEIGHT_EXPANDED = 780


def is_windows() -> bool:
    """Return True if running on Windows."""
    return sys.platform == "win32"


def _setup_user32():
    """Configure 64-bit argument and return types on ctypes user32."""
    if not is_windows():
        return None
    u32 = ctypes.windll.user32
    u32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    u32.SetWindowPos.restype = wintypes.BOOL

    u32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u32.GetWindowLongW.restype = ctypes.c_long

    return u32


def find_browser_executable() -> Optional[str]:
    """Locate Microsoft Edge or Google Chrome executable on the system."""
    if not is_windows():
        return None
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p
    return shutil.which("msedge") or shutil.which("chrome")


def find_cockpit_windows(title_sub: str = "pocket cockpit") -> List[Tuple[int, str]]:
    """Enumerate desktop windows matching Pocket Cockpit title on the interactive desktop."""
    if not is_windows():
        return []
    u32 = _setup_user32()
    if not u32:
        return []

    h_default = None
    try:
        # Attach process to interactive 'WinSta0' window station and 'Default' desktop
        h_winsta = u32.OpenWindowStationW("WinSta0", False, 0x037F)
        if h_winsta:
            u32.SetProcessWindowStation(h_winsta)
            h_default = u32.OpenDesktopW("Default", 0, False, 0x01FF)
            if h_default:
                u32.SetThreadDesktop(h_default)
    except Exception as e:
        logger.debug("Desktop attach note: %s", e)

    found: List[Tuple[int, str]] = []

    def _enum_cb(hwnd, _lparam):
        length = u32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            u32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            t_low = title.lower()
            if any(sub in t_low for sub in [title_sub.lower(), "pocket cockpit", "3-step dominion", "standalone engine"]):
                found.append((hwnd, title))
        return True

    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    if h_default:
        u32.EnumDesktopWindows(h_default, EnumWindowsProc(_enum_cb), 0)
    else:
        u32.EnumWindows(EnumWindowsProc(_enum_cb), 0)

    return found


def set_always_on_top(hwnd: int, topmost: bool = True) -> bool:
    """Toggle HWND_TOPMOST / Always on Top for a window."""
    if not is_windows():
        return False
    u32 = _setup_user32()
    if not u32:
        return False

    h_target = wintypes.HWND(hwnd)
    z_order = HWND_TOPMOST if topmost else HWND_NOTOPMOST
    ret = bool(u32.SetWindowPos(h_target, z_order, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW))
    logger.info("📌 SetWindowPos topmost=%s for hwnd=%d (ret=%s)", topmost, hwnd, ret)
    return ret


def is_always_on_top(hwnd: int) -> bool:
    """Check if window currently has WS_EX_TOPMOST style."""
    if not is_windows():
        return False
    u32 = _setup_user32()
    if not u32:
        return False
    ex_style = u32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    return bool(ex_style & WS_EX_TOPMOST)


def resize_window(hwnd: int, width: int, height: int, topmost: Optional[bool] = None) -> bool:
    """Resize window dimensions and optionally update topmost status."""
    if not is_windows():
        return False
    u32 = _setup_user32()
    if not u32:
        return False

    h_target = wintypes.HWND(hwnd)
    if topmost is None:
        flags = SWP_NOMOVE | SWP_SHOWWINDOW
        z_order = wintypes.HWND(0)
    else:
        flags = SWP_NOMOVE | SWP_SHOWWINDOW
        z_order = HWND_TOPMOST if topmost else HWND_NOTOPMOST

    ret = bool(u32.SetWindowPos(h_target, z_order, 0, 0, int(width), int(height), flags))
    logger.info("📐 Resized window hwnd=%d to %dx%d (topmost=%s, ret=%s)", hwnd, width, height, topmost, ret)
    return ret


def launch_widget_window(port: int = 8001, view: str = "minimized") -> bool:
    """Launch Microsoft Edge or Google Chrome in chromeless app mode and pin as floating desktop widget."""
    browser_exe = find_browser_executable()
    if not browser_exe:
        logger.warning("No compatible browser (Edge/Chrome) found for app widget mode.")
        return False

    url = f"http://localhost:{port}/?view={view}&widget=1"
    cmd = [
        browser_exe,
        f"--app={url}",
        f"--window-size={WIDGET_WIDTH_MINIMIZED},{WIDGET_HEIGHT_MINIMIZED}",
    ]

    try:
        logger.info("🚀 Spawning floating desktop widget: %s", " ".join(cmd))
        subprocess.Popen(cmd)

        # Background thread to locate and pin topmost once window renders
        def _pin_watchdog():
            for _ in range(12):  # Poll up to 6 seconds
                time.sleep(0.5)
                windows = find_cockpit_windows()
                if windows:
                    for h, t in windows:
                        set_always_on_top(h, True)
                        resize_window(h, WIDGET_WIDTH_MINIMIZED, WIDGET_HEIGHT_MINIMIZED, topmost=True)
                    logger.info("📌 [WIDGET PINNED] Pocket Cockpit is now floating on top of desktop.")
                    return
            logger.warning("Could not find Pocket Cockpit window to pin topmost.")

        threading.Thread(target=_pin_watchdog, daemon=True).start()
        return True
    except Exception as exc:
        logger.error("Failed to launch floating widget: %s", exc)
        return False
