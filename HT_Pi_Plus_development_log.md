# HT Pi Plus 开发学习记录

这个文件用于记录三天内完成 HT Pi Plus / Mini Pi Plus 啦啦操演示任务的开发过程。

目标不是写成正式论文，而是把每次尝试、每个命令、每个错误和每次修改都留下来。这样即使机器人还给甲方之后，也能回头看清楚当时是怎么把系统跑通的。

## 2026-07-16 初始代码摸底

### 本次目标

先了解现有 `robot_remote_web` 文件夹到底实现了什么功能，以及后续应该怎么基于它继续开发。

### 当前代码结构

- `robot_remote_web/server.py`：电脑端本地网页服务。它负责打开控制网页，也可以通过 SSH 登录机器人，在机器人上发布 ROS 消息。
- `robot_remote_web/robot_agent/server_robot.py`：机器人端网页服务。设计目标是直接部署到机器人上运行，然后在机器人本机用 `rospy` 发布 `/joy_input`。
- `robot_remote_web/static/app.js`：电脑端网页的交互逻辑，比如键盘按键、按钮点击、调用接口。
- `robot_remote_web/robot_agent/static/app.js`：机器人端网页的交互逻辑。
- `robot_remote_web/config.json`：电脑端配置，里面有机器人 IP、用户名、密码、动作配置文件路径等。
- `robot_remote_web/robot_agent/config.robot.json`：机器人端配置，里面有机器人端服务端口和动作配置文件路径。
- `参考手册/`：本地已有的参考 PDF，目前看到有示教模式和风格化动作配置相关手册。

### 现有功能理解

这个项目现在像一个“网页遥控器”。

它的基本控制链路是：

```text
键盘/网页按钮
  -> 浏览器里的 JavaScript
  -> HTTP 接口
  -> 发布 ROS 的 /joy_input 消息
  -> 机器人原有行走控制器
  -> 机器人电机执行动作
```

换成人话就是：

我们不是直接控制 20 多个电机，而是假装自己是一个手柄。机器人原本就能接收手柄消息，所以网页只需要把键盘输入翻译成“手柄摇杆/按键”消息。

### 当前键盘映射

网页里目前已经有基础移动按键：

- `W`：前进
- `S`：后退
- `A`：左移
- `D`：右移
- `Q`：左转
- `E`：右转
- 停止按钮或急停按钮：发送停止速度

移动命令内部用三个量表示：

- `vx`：前后方向速度，正数是前进，负数是后退。
- `vy`：左右方向速度。
- `wz`：转向速度。

### ROS 概念记录

- ROS topic：可以理解成一个“消息频道”。一个程序往频道里发消息，另一个程序从频道里收消息。
- `/joy_input`：机器人接收手柄输入的频道。当前网页遥控器主要就是往这个频道发消息。
- `sensor_msgs/Joy`：ROS 里表示手柄数据的消息格式，里面有两类数据：
  - `axes`：摇杆、扳机这类连续值。
  - `buttons`：按钮这类 0/1 值。
- 动作 YAML：机器人动作配置文件，里面记录了有哪些动作、动作名字是什么、可能对应哪个按键组合。

### 已执行检查

```bash
python -m py_compile robot_remote_web/server.py robot_remote_web/robot_agent/server_robot.py
```

结果：语法检查通过。

这只能说明 Python 文件没有明显语法错误，不代表真机上一定能跑通。

### 已发现风险

- 当前本地目录没有看到 `sim2real_master` 动作配置目录，所以动作列表可能需要从机器人真实文件系统读取，或者后续把 YAML 文件复制到本地再分析。
- 旧 README 和网页里有一些中文乱码，说明它们可能经历过错误编码转换。后续新写的文档应该直接用 UTF-8 保存。
- `robot_agent/server_robot.py` 里 `/api/choreography` 路由疑似有运行时问题：代码看起来调用了 `self.run_choreography()`，但实际编排函数属于 `BRIDGE` 对象。这个问题语法检查发现不了，需要后续修复或真机接口测试确认。

### 下一步建议

先不要急着做复杂啦啦操。下一步应该按最小风险顺序跑通：

1. 确认机器人 IP 和 SSH 能连通。
2. 确认机器人 ROS 环境正常。
3. 测试 `/api/stop`，确保停止指令可用。
4. 测试 `/api/wake`，确认机器人能进入可运动状态。
5. 用很小速度测试 `/api/move`。
6. 再测试一个上肢动作。
7. 最后再组合“慢速走动 + 上肢动作”。

### 安全提醒

真机测试时先小速度、短时间、旁边有人扶或保护，急停必须提前确认可用。不要一开始就跑完整编排。

## 2026-07-16 网页遥控器安全实现

### 本次目标

把三天计划里的代码层修改先落地：修复机器人端编排接口，降低默认移动速度，增强急停逻辑，并让服务在动作 YAML 或 PyYAML 缺失时仍能启动。

### 修改内容

- 修复 `robot_remote_web/robot_agent/server_robot.py` 的 `/api/choreography` 路由，现在调用 `BRIDGE.run_choreography()`。
- 机器人端和电脑端服务都增加了 CORS 响应头，电脑网页可以优先请求机器人端服务。
- 电脑端 `/api/config` 不再把密码返回给浏览器，只返回 `host_alias`、`host`、`user`。
- 动作库读取增加容错：如果缺少 PyYAML 或动作 YAML，服务仍可启动，页面日志会提示“动作库暂不可读”，但停止、唤醒、低速移动仍可测试。
- 两套网页脚本都改成保守速度：
  - 前进 `vx = 0.12`
  - 后退 `vx = -0.08`
  - 左右移动 `vy = ±0.08`
  - 转向 `wz = ±0.35`
  - 原地踏步使用 `vx = 0.03` 和小幅左右转向。
- 空格、急停按钮、松开移动按钮、窗口失焦都会清掉移动循环并发送停止。
- 两个网页页面的乱码中文已改成可读中文。
- 新增 `HT_Pi_Plus_demo_runbook.md`，用于现场真机操作。

### 已执行检查

```bash
python -m py_compile robot_remote_web/server.py robot_remote_web/robot_agent/server_robot.py
node --check robot_remote_web/static/app.js
node --check robot_remote_web/robot_agent/static/app.js
```

结果：通过。

还短暂启动了电脑端服务并请求：

```text
http://127.0.0.1:8765/api/config
```

结果：返回 `200`，并能在缺少 PyYAML 时返回动作库错误提示；跨域预检 `OPTIONS` 返回 `204` 和 `Access-Control-Allow-Origin: *`。

### 仍需真机验证

- 电脑能否 ping 通 `192.168.43.44`。
- 电脑能否 SSH 登录机器人。
- 机器人端是否已经启动官方 ROS 控制程序。
- `/joy_input` 是否确实是当前机器人控制链路使用的话题。
- `cheer` 动作名是否存在于机器人动作 YAML 中。

## 2026-07-17 路径无关修复

### 本次目标

解决源代码和 README 中残留的师兄电脑绝对路径问题，让项目放在不同目录也能启动。

### 已保存版本

路径修复前已经做了一次 Git 基线提交：

```text
c4d20da baseline before path fixes
```

如果路径修复后想退回，可以使用 Git 回到这次提交。

### 修改内容

- `robot_remote_web/start_remote.sh` 不再 `cd` 到旧 Mac 目录，而是自动进入脚本所在目录。
- 新增 `robot_remote_web/start_remote.ps1`，用于 Windows PowerShell 从任意项目路径启动。
- `robot_remote_web/restart_remote.sh` 改为基于脚本所在目录重启。
- `robot_remote_web/deploy_robot_agent.sh` 改为无旧路径、无乱码提示，并允许传入机器人 IP、用户名和远端目录。
- `robot_remote_web/server.py` 重写为干净版本：
  - 动作 YAML 路径按环境变量和当前项目位置搜索。
  - 支持 `HT_PI_PLUS_WORKSPACE`、`HT_PI_PLUS_PROJECT_ROOT`、`SIM2REAL_ROOT`。
  - 不再写死 `/usr/bin/expect`，会自动查找 `expect`；没有 `expect` 时尝试系统 `ssh`。
  - 继续保持原来的 HTTP API。
- `robot_remote_web/README.md` 和 `robot_remote_web/robot_agent/README.md` 改成中文可读版本，不再引用旧电脑路径。
- `HT_Pi_Plus_demo_runbook.md` 改成 `<你的项目目录>` 形式，避免路径过期。

### 已执行检查

```bash
python -m py_compile robot_remote_web/server.py robot_remote_web/robot_agent/server_robot.py
node --check robot_remote_web/static/app.js
node --check robot_remote_web/robot_agent/static/app.js
```

结果：通过。

还验证了：

- `start_remote.ps1` PowerShell 语法解析通过。
- 旧路径关键字搜索无结果。
- 从 `robot_remote_web` 目录直接启动 `server.py` 后，`/api/config` 返回 `200`。
- `/api/config` 返回给浏览器的机器人字段不包含 `password`。
