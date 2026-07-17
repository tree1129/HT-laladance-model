# 虚拟遥控器

这是一个运行在 **PC 端** 的 `HT Pi Plus / Mini Pi Plus` 虚拟遥控器。

## 代码目录

```text
robot_remote_web/
├── config.json
├── server.py
├── start_remote.sh
├── README.md
└── static/
    ├── index.html
    ├── styles.css
    └── app.js
```

## 哪些文件在你的 PC 上

这些都是我给你做的、跑在电脑上的代码：

- [config.json](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/config.json:1)
- [server.py](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/server.py:1)
- [start_remote.sh](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/start_remote.sh:1)
- [static/index.html](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/static/index.html:1)
- [static/styles.css](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/static/styles.css:1)
- [static/app.js](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/static/app.js:1)

## 机器人上有没有新放文件

默认情况下没有自动部署。

但我已经给你准备好了机器人端服务目录：

- [robot_agent](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/robot_agent/README.md:1)

建议你把它部署到机器人：

```bash
/home/hightorque/robot_remote_web_agent
```

这样后面就是：

- 机器人本机运行 `server_robot.py`
- PC 页面直接请求机器人 `http://192.168.43.44:8766`
- 只有机器人端服务不可用时，PC 才回退到本地 SSH 代理模式

## 机器人端实际复用的现有代码

关键是这些：

- [humanoid_controller.py](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/robot_driver/src/controllers/humanoid_controller.py:1)
  作用：机器人真实控制链路，订阅 `/joy_input`

- [params.yaml](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/robot_driver/config/params.yaml:1)
  作用：`humanoid_driver` 参数

- [joy.yaml](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/sim2real_master/joy.yaml:1)
  作用：真实遥控器按键/轴映射

- [joy_footstep.yaml](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/sim2real_master/joy_footstep.yaml:1)
  作用：步态、模式切换映射

- [base_policy.yaml](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/sim2real/action_config/config/pi_plus_22dof/base_policy.yaml:1)
  作用：策略动作库

- [base_waypoint.yaml](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/sim2real/action_config/config/pi_plus_22dof/base_waypoint.yaml:1)
  作用：单段动作库

- [custom_action.yaml](/Users/tree/Desktop/高擎小pi-啦啦操/sim2real_master/src/sim2real/action_config/config/pi_plus_22dof/custom_action.yaml:1)
  作用：动作和真实遥控器按键组合映射

## 当前控制链路

### PC 端

- 页面：`static/index.html`
- 交互逻辑：`static/app.js`
- 本地服务：`server.py`

### 机器人端

- `server.py` 通过 SSH 登录机器人
- 在机器人上发布 ROS 命令
- 运动控制现在优先模拟 **真实遥控器 `sensor_msgs/Joy`**
- 也就是走：
  `PC页面 -> server.py -> SSH -> /joy_input -> humanoid_driver -> 机器人`

## 配置文件怎么改

如果后面你要换机器人 IP、账号、动作配置路径，优先改这里：

- [config.json](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/config.json:1)

## 启动

```bash
cd /Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web
python3 server.py
```

或者：

```bash
cd /Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web
./start_remote.sh
```

打开：

[`http://127.0.0.1:8765`](http://127.0.0.1:8765)

## 停止

```bash
pkill -f 'robot_remote_web/server.py'
```

## 维护建议

你后面维护时，可以按这个分工找文件：

- 改机器人地址和账号：
  - [config.json](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/config.json:1)

- 改页面长相：
  - [static/index.html](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/static/index.html:1)
  - [static/styles.css](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/static/styles.css:1)

- 改按钮、键盘、动作编排：
  - [static/app.js](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/static/app.js:1)

- 改 SSH、ROS 发布、动作触发逻辑：
  - [server.py](/Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web/server.py:1)
