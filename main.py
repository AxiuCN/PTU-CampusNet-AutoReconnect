"""
PTU 校园网自动重连
后台监控网络连通性，断网时自动通过图片验证码重连。
"""

import os
import sys
import time
import logging
import logging.handlers
import threading

from config import Config
from network import check_connectivity
from auth import do_login

logger = logging.getLogger("PTU-Reconnect")


def setup_logging(config: Config, to_console: bool = True):
    """配置日志"""
    os.makedirs(config.log_dir, exist_ok=True)
    log_file = os.path.join(config.log_dir, "reconnect.log")

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "[%(levelname)s] %(asctime)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.handlers.TimedRotatingFileHandler(
        log_file, when="D", interval=1, backupCount=7, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    if to_console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)
        root.addHandler(ch)


class Monitor:
    """网络监控器"""

    def __init__(self, config: Config):
        self.config = config
        self._running = False
        self._thread: threading.Thread | None = None
        self._status_callback = None

    @property
    def is_running(self) -> bool:
        return self._running

    def set_status_callback(self, callback):
        self._status_callback = callback

    def _notify(self, status: str):
        if self._status_callback:
            try:
                self._status_callback(status)
            except Exception:
                pass

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="MonitorLoop")
        self._thread.start()
        logger.info("监控已启动")

    def stop(self):
        self._running = False
        logger.info("监控已停止")
        self._notify("已停止")

    def _loop(self):
        consecutive = 0
        first = True
        base_interval = self.config.check_interval

        while self._running:
            try:
                if check_connectivity(self.config):
                    if first or consecutive > 0:
                        self._notify("已连接")
                    consecutive = 0
                    first = False
                    time.sleep(base_interval)
                    continue

                # 断网
                consecutive += 1
                if consecutive <= 1:
                    self._notify("断网，正在重连...")
                elif consecutive % 10 == 0:
                    logger.warning("已连续断网 %d 次", consecutive)

                # 执行登录
                if do_login(self.config):
                    time.sleep(2)
                    if check_connectivity(self.config):
                        logger.info("重连成功")
                        self._notify("已连接")
                        consecutive = 0
                    else:
                        logger.warning("登录返回成功但网络仍不通")
                elif consecutive == 1:
                    self._notify("重连失败，将继续尝试...")

            except Exception as e:
                logger.error("监控异常: %s", e, exc_info=True)

            # 退避：连续失败超过阈值后延长等待
            delay = base_interval
            if consecutive > 10:
                delay = base_interval * 10  # 5 分钟
            elif consecutive > 5:
                delay = base_interval * 4   # 2 分钟
            time.sleep(delay)


def run_service():
    config = Config.load()
    setup_logging(config, to_console=False)
    logger.info("PTU 校园网自动重连服务启动")

    monitor = Monitor(config)
    monitor.start()

    try:
        while monitor.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        monitor.stop()


def run_console():
    config = Config.load()
    setup_logging(config, to_console=True)
    logger.info("PTU 校园网自动重连 - 按 Ctrl+C 停止")

    monitor = Monitor(config)
    monitor.start()

    try:
        while monitor.is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("正在停止...")
        monitor.stop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--service":
        run_service()
    else:
        run_console()
