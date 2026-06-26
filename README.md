# PTU 校园网自动重连

莆田学院校园网 Dr.COM 断网自动重连工具。后台检测连通性，断网时自动获取验证码、识别并登录。

## 原理

校园网每隔约 24 小时强制断网，重连需要输入图片验证码。本工具自动完成：

- **检测**：请求 `http://connect.rom.miui.com/generate_204`，收到 204 表示已连接
- **验证码**：GET `http://192.168.116.8:801/eportal/?c=main&a=getCode` 获取图片
- **识别**：ddddocr 识别 4 位字符验证码
- **校验**：JSONP GET `http://192.168.116.8:801/eportal/?c=Portal&a=check_captcha` 验证
- **登录**：JSONP GET `http://192.168.116.8/drcom/login` 提交账号密码

## 获取安装

在安装目录执行：
> Github
```bash
git clone --depth=1 https://github.com/AxiuCN/PTU-CampusNet-AutoReconnect.git
```

或下载压缩包：
[GitHub Releases](https://github.com/AxiuCN/PTU-CampusNet-AutoReconnect/releases) 下载最新版 ZIP，解压即可

## 快速开始

### 1. 安装 Python

需要 Python 3.10+，安装时勾选"Add Python to PATH"。

### 2. 启动

双击 `PTU-CampusNet-AutoReconnect.vbs`，程序自动安装依赖并启动到系统托盘。

命令行调试：
```bash
python ui.py
```

### 3. 配置账号

右键托盘图标 -> 打开设置 -> 填写学号和密码、选择运营商(正常选校园其他) -> 保存。

### 4. 设置开机自启

右键托盘图标 -> 点击「开机自启」切换为已启用。

## 托盘图标

| 图标 | 含义 |
|------|------|
| 绿色 | 已连接 |
| 红色 | 断网/重连中 |
| 灰色 | 已停止 |

## 风险说明

- **密码明文存储**：账号密码保存在 `config.json`，明文存储。请勿将 `config.json` 分享给他人，确保电脑不被他人物理接触
- **环境依赖**：需要 Python 3.10+ 环境，自动安装的依赖包仅在本机有效
- **验证码识别**：ddddocr 识别非 100% 准确，极端天气或图片变形时可能连续失败，此时需手动在浏览器登录
- **接口变化**：依赖 Dr.COM 校园网认证系统特定接口，学校升级认证系统后可能失效
- **账号互斥**：同一账号同时在线可能会被另一方踢下线

## 免责声明

本工具为个人开源项目，基于 GPL 3.0 协议，仅供学习研究，使用者**风险自担**。

- 账号密码在本地明文存储，请自行保管好 `config.json`
- 请遵守莆田学院校园网使用规定
- 校园网认证系统升级可能导致工具失效，开发者不保证长期可用

## 项目结构

```
├── ui.py              # 托盘 UI 入口
├── main.py            # 监控循环
├── auth.py            # 验证码获取 + ddddocr 识别 + 登录
├── network.py         # 连通性检测
├── config.py          # 配置管理
├── config.json         # 账号密码（不提交 git）
├── run_ui.vbs         # 双击无黑窗启动
├── requirements.txt
└── logs/
```
