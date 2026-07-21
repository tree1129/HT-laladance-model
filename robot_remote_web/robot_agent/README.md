# HT Pi Plus 机器人端控制服务

这个目录部署到机器人本机运行。推荐优先使用这一套服务，因为它直接在机器人上发布 `/joy_input`，路径和 SSH 交互问题更少。

## 部署位置

推荐位置：

```bash
/home/hightorque/robot_remote_web_agent/robot_agent
```

可以通过上级目录的部署脚本自动复制：

```bash
cd <你的项目目录>/robot_remote_web
bash deploy_robot_agent.sh 192.168.18.114 hightorque
```

## 启动

在机器人上运行：

```bash
cd /home/hightorque/robot_remote_web_agent/robot_agent
bash start_robot_agent.sh
```

启动后，在 PC 或手机浏览器里打开：

```text
http://192.168.18.114:8766
```

## 功能

- 提供网页遥控界面。
- 发布 `/joy_input`，模拟手柄控制。
- 读取机器人本机动作 YAML，生成动作按钮。
- 提供安全原地踏步、急停、低速移动、`cheer` 和 `laladance` 动作触发。
- 触发动作组合键时保留当前移动摇杆值，使 `W/A/S/D/Q/E` 可以继续响应。

## 键盘控制

- `W/A/S/D`：低速前后左右
- `Q/E`：低速转向
- `R`：安全原地踏步开关
- `C`：双手欢呼
- `F`：播放一次 `laladance.boost` 啦啦操动作
- `Space`：急停

## 配置 laladance.boost

Teach 模式生成的是包含下肢、手臂和头部的 `all/22` 全身轨迹，不能直接与行走叠加。先在电脑端转换为只包含 8 个手臂关节的 `arm_joint` 轨迹：

```powershell
python ..\..\robot_action_config\convert_all_to_arm_joint.py `
  ..\..\robot_action_config\laladance.boost `
  ..\..\robot_action_config\laladance_arm.boost
```

将转换结果放到机器人官方动作目录：

```text
/home/hightorque/sim2real_master/install/share/sim2real/action_config/laladance_arm.boost
```

然后编辑：

```text
/home/hightorque/sim2real_master/install/share/sim2real/action_config/config/pi_plus_22dof/base_waypoint.yaml
```

找到 `laladance` 动作项，将路径配置为 `action_config/laladance_arm.boost`。网页服务已在 `config.robot.json` 中把 `laladance` 固定映射为 `rt+x`。

配置完成后先重启机器人，并用真实手柄 `RT+X` 验证动作能够从开始完整播放到归位。确认手柄有效后，再用网页“啦啦操”按钮或键盘 `F` 测试。

`laladance` 的 `loop` 必须配置为 `false`，否则一次按键会让动作持续循环。网页模拟 Xbox 手柄时，LT/RT 扳机按下值为 `-1.0`；如果误发为 `+1.0`，控制器会把扳机当成松开，只识别到单独的 `X`，从而触发 `small_kick`。

`laladance_arm.boost` 只移除了下肢和头部通道，没有降低手臂动作幅度。若手臂动作本身大幅改变重心，即使下肢仍由行走策略控制，机器人也可能失衡。

Teach 模式生成的 `.boost` 是录制姿态轨迹，不应默认认为它只包含上肢。若录制时机器人处于蹲姿，DEFAULT 模式播放时可能把下肢也拉回该姿态。必须先站立单独验证动作；未确认关节范围前，不要和行走同时执行。

## 注意

如果动作 YAML 路径不对，网页仍能启动，但动作列表为空。此时先测试停止、唤醒和低速移动，再检查 `config.robot.json` 中的动作路径。
