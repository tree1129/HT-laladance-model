# HT Pi Plus 虚拟遥控器

这是用于 HT Pi Plus / Mini Pi Plus 啦啦操 Demo 的网页遥控器。

核心思路：

```text
键盘/网页按钮 -> HTTP 接口 -> /joy_input -> 机器人官方控制器 -> 机器人运动
```

也就是说，它不是直接控制每个电机，而是模拟手柄输入。这样更适合三天内做稳定 Demo。

## 目录结构

```text
robot_remote_web/
├── config.json                 # PC 端配置
├── server.py                   # PC 端本地服务，可作为 SSH 代理
├── start_remote.ps1            # Windows PowerShell 启动脚本
├── start_remote.sh             # Bash 启动脚本
├── deploy_robot_agent.sh       # 部署机器人端服务
├── static/                     # PC 端网页
└── robot_agent/                # 机器人端服务，推荐优先使用
```

## 推荐运行方式

优先使用机器人端服务。

原因：机器人端服务直接在机器人本机发布 `/joy_input`，不依赖 PC 端 SSH 密码交互，也不受 PC 路径影响。

### 1. 部署机器人端服务

在能执行 `ssh` 和 `rsync` 的终端里运行：

```bash
cd <你的项目目录>/robot_remote_web
bash deploy_robot_agent.sh 192.168.43.44 hightorque
```

如果你使用的是 Windows PowerShell / PyCharm 默认终端，请运行：

```powershell
cd <你的项目目录>\robot_remote_web
.\deploy_robot_agent.ps1 192.168.43.44 hightorque
```

部署后在机器人上启动：

```bash
ssh hightorque@192.168.43.44
cd /home/hightorque/robot_remote_web_agent/robot_agent
bash start_robot_agent.sh
```

浏览器打开：

```text
http://192.168.43.44:8766
```

### 2. PC 端备用方式

如果暂时不能部署机器人端服务，可以在 PC 上启动本地服务：

Windows PowerShell：

```powershell
cd <你的项目目录>\robot_remote_web
.\start_remote.ps1
```

Bash / Git Bash / WSL：

```bash
cd /path/to/HT_Pi_plus_laladance/robot_remote_web
bash start_remote.sh
```

浏览器打开：

```text
http://127.0.0.1:8765
```

注意：PC 端 SSH 代理如果没有 `expect`，会尝试免密 SSH。没有配置 SSH key 时，建议改用机器人端服务。

## 配置文件

主要配置在 `config.json`：

- `robot.host`：机器人 IP，默认 `192.168.43.44`
- `robot.user`：机器人用户名，默认 `hightorque`
- `robot_agent.base_url`：机器人端服务地址
- `paths`：动作 YAML 的相对路径

动作配置路径不再依赖固定电脑目录。程序会按下面顺序搜索：

1. 环境变量 `HT_PI_PLUS_WORKSPACE`
2. 环境变量 `HT_PI_PLUS_PROJECT_ROOT`
3. 环境变量 `SIM2REAL_ROOT`
4. 当前项目目录
5. `robot_remote_web` 目录
6. 当前运行目录

如果本地没有动作 YAML，网页仍能启动，走路、停止、唤醒仍可测试；动作库会显示为空并在日志里提示原因。

## 网页按键

- `W/A/S/D`：低速前后左右
- `Q/E`：低速转向
- `R`：安全原地踏步开关
- `C`：双手欢呼动作
- `Space`：急停

网页按钮：

- “唤醒运动模式”：尝试让机器人进入可运动状态。
- “急停”：立即清除移动循环并发送停止。
- “安全原地踏步”：用于第一版啦啦操 Demo 的保守下肢动作。
- “安全啦啦操编排”：短序列，先踏步，再触发 `cheer`，再慢速前进，再停止。

## 推荐测试顺序

不要跳步：

1. 打开网页。
2. 点击“急停”。
3. 点击“唤醒运动模式”。
4. 短按“低速前进”，马上松开。
5. 按 `Space` 急停。
6. 按 `R` 测试安全原地踏步，再按 `Space` 停止。
7. 点击“双手欢呼”。
8. 前面都稳定后，再点击“安全啦啦操编排”。

## 回退

本项目已经建立 Git 仓库。路径修复前的基线提交是：

```text
c4d20da baseline before path fixes
```

如需回退到这版，先确认没有需要保留的新改动，再执行：

```bash
git checkout c4d20da -- .
```
