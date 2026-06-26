"""
网络检测模块
- 连通性检测（HTTP 204 方法）
- 本机网卡 IP / MAC 获取
"""

import logging
import httpx
import psutil

from config import Config

logger = logging.getLogger(__name__)

# 虚拟网卡过滤
VIRTUAL_NIC_KEYWORDS = [
    "virtual", "vmware", "hyper-v", "virtualbox", "bluetooth",
    "loopback", "tunnel", "vethernet", "docker", "vpn",
]

WIRELESS_NIC_KEYWORDS = ["wi-fi", "wlan", "无线", "wireless"]


def _is_wireless_nic(name: str) -> bool:
    lower = name.lower()
    for kw in WIRELESS_NIC_KEYWORDS:
        if kw in lower:
            return True
    return False


def _is_active_nic(name: str) -> bool:
    lower = name.lower()
    if "loopback" in lower:
        return False
    for kw in VIRTUAL_NIC_KEYWORDS:
        if kw in lower:
            return False
    return True


def _is_campus_ip(ip: str) -> bool:
    """校园网私有地址段 172.16.0.0/12"""
    if ip.startswith("172."):
        second = int(ip.split(".")[1])
        return 16 <= second <= 31
    return False


def _is_apipa(ip: str) -> bool:
    return ip.startswith("169.254.")


def _collect_interfaces() -> list[dict]:
    """收集所有活跃网卡，按优先级排序：校园网IP > 无线 > 非APIPA > APIPA"""
    interfaces = []
    for name, addrs in psutil.net_if_addrs().items():
        if not _is_active_nic(name):
            continue
        ips, macs = [], []
        for addr in addrs:
            if addr.family == 2 and addr.address != "127.0.0.1":
                ips.append(addr.address)
            if addr.family == -1:
                m = addr.address.replace("-", "").replace(":", "").lower()
                if m and m != "000000000000":
                    macs.append(m)

        for ip in ips:
            interfaces.append({
                "name": name,
                "ip": ip,
                "mac": macs[0] if macs else "",
                "is_wireless": _is_wireless_nic(name),
                "is_campus": _is_campus_ip(ip),
                "is_apipa": _is_apipa(ip),
            })

    interfaces.sort(key=lambda x: (
        not x["is_campus"],
        not x["is_wireless"],
        x["is_apipa"],
    ))
    return interfaces


def get_mac() -> str:
    """获取本机 MAC 地址，小写无分隔符"""
    for iface in _collect_interfaces():
        if iface["mac"]:
            return iface["mac"]
    return ""


def check_connectivity(config: Config) -> bool:
    """
    检测外网连通性。
    请求 generate_204，收到 204 表示已联网。
    """
    try:
        resp = httpx.get(
            config.captive_check_url,
            follow_redirects=False,
            timeout=config.connect_timeout,
        )
        return resp.status_code == 204
    except Exception:
        return False
