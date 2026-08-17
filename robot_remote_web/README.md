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
bash deploy_robot_agent.sh 192.168.18.114 hightorque
```

如果你使用的是 Windows PowerShell / PyCharm 默认终端，请运行：

```powershell
cd <你的项目目录>\robot_remote_web
.\deploy_robot_agent.ps1 192.168.18.114 hightorque
```

部署后在机器人上启动：

```bash
ssh hightorque@192.168.18.114
cd /home/hightorque/robot_remote_web_agent/robot_agent
bash start_robot_agent.sh
```

浏览器打开：

```text
http://192.168.18.114:8766
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

如需让 PC 端代理通过密码登录，请在启动前设置环境变量
`HT_ROBOT_PASSWORD`。不要把机器人密码写入 `config.json` 或提交到 Git。

## 配置文件

主要配置在 `config.json`：

- `robot.host`：机器人 IP，默认 `192.168.18.114`
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
- `F`：播放一次自定义啦啦操上肢动作
- `Space`：急停

网页按钮：

- “唤醒运动模式”：尝试让机器人进入可运动状态。
- “急停”：立即清除移动循环并发送停止。
- “安全原地踏步”：用于第一版啦啦操 Demo 的保守下肢动作。
- “安全啦啦操编排”：短序列，先踏步，再触发 `cheer`，再慢速前进，再停止。

## 重新示教和更换上肢动作

如果不熟悉 TEACH 模式的进入、录制、保存和复现操作，请先查阅高擎动力官网的 Mini Pi Plus 示教模式教程。本节只说明示教完成后，如何把全身轨迹转换成可与行走配合的上肢轨迹。

### 1. 保存示教文件

TEACH 模式默认将最新动作保存为：

```text
/home/hightorque/sim2real_master/install/share/sim2real/action_config/test.boost
```

进入动作目录并确认文件：

```bash
ACTION=/home/hightorque/sim2real_master/install/share/sim2real/action_config
cd "$ACTION"
ls -lh --full-time test.boost
```

不要直接把原始文件命名为 `laladance_arm.boost`。TEACH 生成的文件通常是包含腿、手臂和头部的 `all/22` 全身轨迹，还没有去除下肢。先将其保留为：

```bash
mv test.boost laladance_all.boost
```

录制关键帧时，每个关键姿势只按一次记录键，不要长按，也不要录入大量重复姿势。关键帧过多会增大 `.boost` 文件、延长加载和播放时间，并让动作难以调试。第一版建议只保留完成动作所必需的关键姿势。

### 2. 下载原始动作和官方参考动作

在电脑 PowerShell 中运行：

```powershell
cd <你的项目目录>

scp hightorque@<机器人IP>:/home/hightorque/sim2real_master/install/share/sim2real/action_config/cheer.boost `
  .\robot_action_config\cheer.boost

scp hightorque@<机器人IP>:/home/hightorque/sim2real_master/install/share/sim2real/action_config/laladance_all.boost `
  .\robot_action_config\laladance_all.boost
```

`cheer.boost` 是官方上肢动作参考文件。当前机器人上的官方文件为 `arm_joint/8`，只包含 8 个手臂关节；TEACH 文件为 `all/22`，包含 12 个腿部关节、8 个手臂关节和 2 个头部关节。

### 3. 使用 AI 工具转换为上肢动作

本项目已经提供转换脚本：

```powershell
python .\robot_action_config\convert_all_to_arm_joint.py `
  .\robot_action_config\laladance_all.boost `
  .\robot_action_config\laladance_arm.boost
```

如果需要让 Codex 或其他能够读取本地文件的 AI 工具重新分析，可以将 `cheer.boost` 和 `laladance_all.boost` 一并提供，并使用下面的提示词：

```text
请比较 cheer.boost 和 laladance_all.boost 的 Boost 文本归档结构。
cheer.boost 是机器人官方上肢动作参考，laladance_all.boost 是 Mini Pi Plus
22DOF 示教生成的全身动作。请先确认文件类型、帧数和每帧维度，再判断 22 个
关节的排列。目标是保留 laladance_all.boost 中的手臂动作，删除所有下肢和头部
通道，生成与 cheer.boost 相同的 arm_joint/8 格式。

要求：
1. 不覆盖或修改两个输入文件；
2. 对每个 all/22 轨迹点提取第 12-19 列共 8 个手臂关节值；
3. 不插值、不缩放、不改变原始手臂数值和帧顺序；
4. 输出文件命名为 laladance_arm.boost；
5. 验证输出帧数与输入一致、每帧恰好 8 个值，并报告验证结果；
6. 如果文件结构与上述假设不一致，停止转换并说明差异，不要猜测修改。
```

### 4. 确认机器人 IP

背板显示的 `lo: 127.0.0.1` 是机器人访问自己的回环地址，不能供电脑连接。需要使用机器人 Wi-Fi 网卡在当前局域网中的地址。

在机器人终端运行：

```bash
hostname -I
ip -4 addr show
```

通常应选择 `wlan0` 或其他无线网卡下的地址，例如 `192.168.18.114`。电脑和机器人应连接同一个局域网，并在电脑 PowerShell 中确认：

```powershell
ping <机器人IP>
```

IP 变化后，部署命令、浏览器地址和项目配置中的旧 IP 都要相应更新。机器人端网页地址是：

```text
http://<机器人IP>:8766
```

### 5. 上传转换后的动作

先在机器人终端备份当前动作配置：

```bash
ACTION=/home/hightorque/sim2real_master/install/share/sim2real/action_config
CFG=$ACTION/config/pi_plus_22dof
cp -a "$CFG/base_waypoint.yaml" \
  "$CFG/base_waypoint.yaml.bak-$(date +%Y%m%d-%H%M%S)"
```

然后在电脑 PowerShell 上传转换后的动作和配置：

```powershell
scp .\robot_action_config\laladance_arm.boost `
  hightorque@<机器人IP>:/home/hightorque/sim2real_master/install/share/sim2real/action_config/laladance_arm.boost

scp .\robot_action_config\base_waypoint.yaml `
  hightorque@<机器人IP>:/home/hightorque/sim2real_master/install/share/sim2real/action_config/config/pi_plus_22dof/base_waypoint.yaml
```

`base_waypoint.yaml` 中应包含：

```yaml
- name: "laladance"
  path: "action_config/laladance_arm.boost"
  loop: false
```

`loop: false` 表示按一次只播放一遍；改成 `true` 会循环播放。修改动作文件或 YAML 后应完整重启机器人，让官方控制程序重新加载配置。

### 6. 真机验证和停止动作

进入 DEFAULT/RUNNING 状态后，先由一人扶住机器人，再使用真实手柄按 `RT+X`。这可以直接验证新的啦啦操上肢动作是否已经被正确加载。确认只有手臂运动、腿部没有回到示教蹲姿后，再测试网页 `F`，最后才测试低速行走时触发动作。

当前 `loop: false`，动作正常情况下会自行播放到结束。如果上肢动作没有结束或需要退出：

1. 先松开所有按键，扶稳机器人。
2. 同时按 `LT+RT+START`，尝试切回运行状态。
3. 也可以同时按 `LT+RT+LB`。该操作可能让手臂较快归位。
4. 如果没有响应，先完全松开按键，稍等后再同时按一次，不要连续快速乱按。
5. 仍无法退出时，同时按 `LT+RT+B` 让机器人蹲下并重新开始控制流程。执行前必须扶住机器人，避免腿部卸力或姿态切换时摔倒。

这些组合键会切换机器人整体控制状态，不是只停止手臂的独立急停。网页 `Space` 主要停止移动输入，不能保证终止正在执行的上肢轨迹。

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
