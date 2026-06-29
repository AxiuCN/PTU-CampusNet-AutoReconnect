"""
认证模块 - 校园网图片验证码登录

真实流程 (来自 HAR 文件 + a42.js 逆向):
  1. GET /eportal/?c=main&a=getCode  → 验证码图片
  2. ddddocr 识别
  3. JSONP GET /eportal/?c=Portal&a=check_captcha  → 验证码校验
  4. JSONP GET /drcom/login  → 登录

关键参数 (来自浏览器 HAR 验证):
  - URL: http://192.168.116.8/drcom/login (port 80)
  - 0MKKey=123456 (固定值)
  - 无 R2 字段
  - callback=dr{timestamp} (JSONP 回调)
  - 验证码独立校验, 不随登录发送
"""

import logging
import re as _re
import json as _json
import time as _time
import httpx
import ddddocr

from config import Config

logger = logging.getLogger(__name__)


def _cb() -> str:
    return f"dr{int(_time.time() * 1000)}"


def _parse_jsonp(text: str):
    """解析 JSONP 响应"""
    if not text or not text.strip():
        return None
    text = text.strip()
    if text.startswith("{"):
        try:
            return _json.loads(text)
        except _json.JSONDecodeError:
            pass
    m = _re.search(r"\{.*\}", text, _re.DOTALL)
    if m:
        try:
            return _json.loads(m.group())
        except _json.JSONDecodeError:
            pass
    return None


def do_login(config: Config) -> bool:
    """
    完整登录流程，自动重试。服务器异常时退避。
    """
    base = f"http://{config.portal_host}"
    base_api = f"{base}:{config.portal_port}"
    ocr = ddddocr.DdddOcr(show_ad=False)

    for attempt in range(1, 4):
        if attempt > 1:
            logger.info("第 %d 次重试...", attempt)

        client = httpx.Client(timeout=config.connect_timeout + 10)
        client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
        })

        try:
            # ---- 1. 获取验证码 ----
            captcha_url = (
                f"{base_api}/eportal/"
                f"?c=main&a=getCode&v=3.0_{int(_time.time() * 1000)}"
            )
            resp = client.get(captcha_url, timeout=config.connect_timeout)
            resp.raise_for_status()
            captcha_bytes = resp.content

            # ---- 2. OCR 识别 ----
            captcha_text = ocr.classification(captcha_bytes)
            logger.info("验证码识别: %s", captcha_text)

            if len(captcha_text) < 3:
                logger.warning("验证码识别结果可疑: %s", captcha_text)

            # ---- 3. 验证码校验 ----
            resp = client.get(
                f"{base_api}/eportal/",
                params={
                    "c": "Portal", "a": "check_captcha",
                    "callback": _cb(), "captcha": captcha_text,
                    "_": int(_time.time() * 1000),
                },
                timeout=config.connect_timeout,
            )
            captcha_result = _parse_jsonp(resp.text)
            logger.debug("验证码校验: %s", resp.text[:150])

            if not captcha_result or str(captcha_result.get("result")) != "1":
                logger.warning("验证码校验失败, 重试...")
                continue

            logger.info("验证码校验通过")

            # ---- 4. 登录 ----
            suffix = config.get_carrier_suffix()
            username = config.username + suffix

            resp = client.get(
                f"{base}/drcom/login",
                params={
                    "callback": _cb(),
                    "DDDDD": username, "upass": config.password,
                    "0MKKey": "123456",
                    "R1": "0", "R3": "0", "R6": "0",
                    "para": "00", "v6ip": "",
                    "_": int(_time.time() * 1000),
                },
                timeout=config.connect_timeout,
            )

            logger.info("登录: 账号=%s", username)
            logger.debug("登录响应: %s", resp.text[:300])

            # ---- 5. 解析结果 ----
            result = _parse_jsonp(resp.text)

            if result:
                if str(result.get("result")) == "1":
                    logger.info("登录成功")
                    return True
                msg = result.get("msga", result.get("msg", ""))
                logger.warning("登录失败: result=%s, msg=%s",
                               result.get("result"), msg)
                if "waitsec" in str(msg):
                    _time.sleep(3)
            else:
                logger.warning("无法解析登录响应: %s", resp.text[:200])

        except httpx.HTTPStatusError as e:
            logger.warning("服务器返回 %d (暂不可用)", e.response.status_code)
        except httpx.RequestError:
            logger.warning("登录请求失败 (连接被拒或超时)")
        except Exception:
            logger.error("登录异常", exc_info=True)
        finally:
            client.close()

    logger.error("登录失败: 已达最大重试次数")
    return False
