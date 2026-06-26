"""
配置管理模块
- 持久化存储到 config.json
- 验证码登录所需配置
"""

import json
import os
from dataclasses import dataclass, field, asdict

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 运营商后缀映射
# Portal a41.js: 校园用户/@xyw 即中国移动
CARRIER_SUFFIX = {
    "中国移动": "@xyw",
    "中国电信": "@dx",
    "中国联通": "@lt",
    "校园其他": "",
}


@dataclass
class Config:
    # ---- 网络参数 ----
    portal_host: str = "192.168.116.8"
    portal_port: int = 801
    check_interval: int = 30         # 连通性检测间隔（秒）
    captive_check_url: str = "http://connect.rom.miui.com/generate_204"
    connect_timeout: int = 5         # HTTP 请求超时（秒）

    # ---- 登录凭证（必填）----
    username: str = ""               # 学号
    password: str = ""               # 校园网密码
    carrier: str = "中国移动"          # 运营商选择

    # ---- 日志 ----
    log_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "logs"))

    @classmethod
    def load(cls) -> "Config":
        """从 config.json 加载，不存在或损坏则创建默认配置"""
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, IOError, OSError):
                pass
        config = cls()
        config.save()
        return config

    def save(self):
        """保存到 config.json"""
        data = asdict(self)
        # 不保存 log_dir 到配置文件（每次启动动态生成）
        data.pop("log_dir", None)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_carrier_suffix(self) -> str:
        """获取运营商后缀，未知运营商返回空字符串"""
        return CARRIER_SUFFIX.get(self.carrier, "")
