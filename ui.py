"""
PTU 校园网自动重连 - 系统托盘 UI
- 托盘图标 + 状态显示
- 设置窗口（账号、密码、运营商、检测间隔）
- 开机自启管理
- 手动启动/停止监控
"""

import os
import sys
import logging
import threading
import subprocess

# ---- 依赖自动安装（在第三方 import 前执行）----

_REQ_IMPORT_MAP = {
    "httpx": "httpx",
    "psutil": "psutil",
    "pystray": "pystray",
    "Pillow": "PIL",
    "ddddocr": "ddddocr",
}


def _importable(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _ensure_deps():
    """检查并自动安装依赖（入口处最先调用）"""
    req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
    if not os.path.exists(req_path):
        return

    missing = [req for req, imp in _REQ_IMPORT_MAP.items()
               if not _importable(imp)]

    if not missing:
        return

    subprocess.run(
        [sys.executable, "-m", "pip", "install", *missing, "-q"],
        capture_output=True,
    )


# ---- 以下 import 依赖已安装 ----

from PIL import Image, ImageDraw, ImageFont
import pystray

from config import Config
from main import Monitor, setup_logging

logger = logging.getLogger("PTU-Reconnect.UI")

# ---- 图标生成 ----


def _make_icon(color: str) -> Image.Image:
    """生成 64x64 纯色圆形图标"""
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 4
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=color,
        outline="white",
        width=2,
    )
    # 居中文字
    try:
        font = ImageFont.truetype("msyh.ttc", 20)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "网", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2, (size - th) / 2), "网", fill="white", font=font)
    return img


ICON_GREEN = _make_icon("#2ecc71")   # 已连接
ICON_RED = _make_icon("#e74c3c")     # 断网/重连中
ICON_GRAY = _make_icon("#95a5a6")    # 已停止


# ---- 开机自启管理 ----

def get_startup_dir() -> str:
    """获取 Windows 启动文件夹路径"""
    return os.path.join(
        os.environ.get("APPDATA", ""),
        "Microsoft", "Windows", "Start Menu", "Programs", "Startup",
    )


def get_startup_shortcut_path() -> str:
    return os.path.join(get_startup_dir(), "PTU校园网自动重连.lnk")


def is_startup_enabled() -> bool:
    return os.path.exists(get_startup_shortcut_path())


def enable_startup():
    """启用开机自启：在启动文件夹创建快捷方式"""
    startup_dir = get_startup_dir()
    os.makedirs(startup_dir, exist_ok=True)
    shortcut_path = get_startup_shortcut_path()

    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable

    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, "main.py")

    ps_cmd = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut_path}"); '
        f'$s.TargetPath = "{pythonw}"; '
        f'$s.Arguments = \'"{main_script}" --service\'; '
        f'$s.WorkingDirectory = "{script_dir}"; '
        f'$s.WindowStyle = 7; '
        f'$s.Save()'
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            capture_output=True, check=True,
        )
        logger.info(f"已创建开机启动快捷方式: {shortcut_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"创建开机启动失败: {e}")
        return False


def disable_startup():
    shortcut_path = get_startup_shortcut_path()
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        logger.info("已删除开机启动快捷方式")


# ---- 托盘应用 ----

class TrayApp:
    """系统托盘应用"""

    def __init__(self):
        self.config = Config.load()
        setup_logging(self.config, to_console=False)

        self.monitor = Monitor(self.config)
        self.monitor.set_status_callback(self._on_status_change)

        self.icon = pystray.Icon(
            "PTU-Reconnect",
            ICON_GRAY,
            "PTU 校园网自动重连",
        )

        self._status = "已停止"
        self._build_menu()

    def _build_menu(self):
        status_text = f"状态: {self._status}"
        self.icon.menu = pystray.Menu(
            pystray.MenuItem(status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("打开设置", self._open_settings),
            pystray.MenuItem(
                "启动监控" if not self.monitor.is_running else "停止监控",
                self._toggle_monitor,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                f"开机自启: {'[已启用]' if is_startup_enabled() else '[未启用]'}",
                self._toggle_startup,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("查看日志", self._open_log),
            pystray.MenuItem("退出", self._quit),
        )

    def _refresh_menu(self):
        self._build_menu()
        self.icon.update_menu()

    def _on_status_change(self, status: str):
        self._status = status
        if status == "已连接":
            self.icon.icon = ICON_GREEN
        elif status == "已停止":
            self.icon.icon = ICON_GRAY
        else:
            self.icon.icon = ICON_RED
        self._refresh_menu()

    def _toggle_monitor(self):
        if self.monitor.is_running:
            self.monitor.stop()
            self._status = "已停止"
            self.icon.icon = ICON_GRAY
        else:
            self.monitor.start()
            self._status = "启动中..."
            self.icon.icon = ICON_RED
        self._refresh_menu()

    def _toggle_startup(self):
        if is_startup_enabled():
            disable_startup()
        else:
            enable_startup()
        self._refresh_menu()

    def _open_settings(self):
        threading.Thread(target=self._settings_window, daemon=True).start()

    def _open_log(self):
        log_dir = self.config.log_dir
        os.makedirs(log_dir, exist_ok=True)
        os.startfile(log_dir)

    def _quit(self):
        if self.monitor.is_running:
            self.monitor.stop()
        self.icon.stop()

    def _settings_window(self):
        import tkinter as tk
        from tkinter import ttk, messagebox

        root = tk.Tk()
        root.title("PTU 校园网自动重连 - 设置")
        root.resizable(False, False)
        root.geometry("420x360")

        root.update_idletasks()
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = 420, 360
        root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="校园网账号设置", font=("", 11, "bold")).pack(anchor="w")

        row1 = ttk.Frame(frame)
        row1.pack(fill="x", pady=(8, 0))
        ttk.Label(row1, text="学号:", width=6).pack(side="left")
        username_var = tk.StringVar(value=self.config.username)
        ttk.Entry(row1, textvariable=username_var, width=30).pack(side="left", padx=(4, 0))

        row2 = ttk.Frame(frame)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="密码:", width=6).pack(side="left")
        password_var = tk.StringVar(value=self.config.password)
        ttk.Entry(row2, textvariable=password_var, width=30, show="*").pack(
            side="left", padx=(4, 0)
        )

        row3 = ttk.Frame(frame)
        row3.pack(fill="x", pady=(6, 0))
        ttk.Label(row3, text="运营商:", width=6).pack(side="left")
        carrier_var = tk.StringVar(value=self.config.carrier)
        carrier_cb = ttk.Combobox(
            row3, textvariable=carrier_var, width=12, state="readonly",
            values=["中国移动", "中国电信", "中国联通", "校园其他"],
        )
        carrier_cb.pack(side="left", padx=(4, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=12)

        ttk.Label(frame, text="网络设置", font=("", 11, "bold")).pack(anchor="w")

        row4 = ttk.Frame(frame)
        row4.pack(fill="x", pady=(8, 0))
        ttk.Label(row4, text="检测间隔:", width=10).pack(side="left")
        interval_var = tk.IntVar(value=self.config.check_interval)
        ttk.Spinbox(
            row4, from_=10, to=300, textvariable=interval_var, width=8,
        ).pack(side="left", padx=(4, 0))
        ttk.Label(row4, text="秒").pack(side="left", padx=(4, 0))

        row5 = ttk.Frame(frame)
        row5.pack(fill="x", pady=(6, 0))
        ttk.Label(row5, text="Portal地址:", width=10).pack(side="left")
        portal_var = tk.StringVar(value=self.config.portal_host)
        ttk.Entry(row5, textvariable=portal_var, width=20).pack(side="left", padx=(4, 0))

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=12)

        tip = (
            "自动检测断网并重连（图片验证码识别）。\n"
            "请确保账号、密码、运营商选择正确。"
        )
        ttk.Label(frame, text=tip, foreground="gray", wraplength=380).pack(anchor="w")

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=(12, 0))

        def save_settings():
            self.config.username = username_var.get().strip()
            self.config.password = password_var.get().strip()
            self.config.carrier = carrier_var.get()
            self.config.check_interval = interval_var.get()
            self.config.portal_host = portal_var.get().strip()
            self.config.save()
            messagebox.showinfo("提示", "设置已保存")
            root.destroy()

        ttk.Button(btn_frame, text="保存", command=save_settings).pack(side="right")
        ttk.Button(btn_frame, text="取消", command=root.destroy).pack(
            side="right", padx=(0, 8)
        )

        root.mainloop()

    def run(self):
        """启动托盘应用"""
        logger.info("托盘应用启动")
        self.monitor.start()
        self._status = "启动中..."
        self.icon.icon = ICON_RED
        self._refresh_menu()
        self.icon.run()


def main():
    """UI 入口"""
    _ensure_deps()
    app = TrayApp()
    app.run()


if __name__ == "__main__":
    main()
