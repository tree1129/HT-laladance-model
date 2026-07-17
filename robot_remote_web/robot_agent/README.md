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
bash deploy_robot_agent.sh 192.168.43.44 hightorque
```

## 启动

在机器人上运行：

```bash
cd /home/hightorque/robot_remote_web_agent/robot_agent
bash start_robot_agent.sh
```

启动后，在 PC 或手机浏览器里打开：

```text
http://192.168.43.44:8766
```

## 功能

- 提供网页遥控界面。
- 发布 `/joy_input`，模拟手柄控制。
- 读取机器人本机动作 YAML，生成动作按钮。
- 提供安全原地踏步、急停、低速移动和 `cheer` 动作触发。

## 键盘控制

- `W/A/S/D`：低速前后左右
- `Q/E`：低速转向
- `R`：安全原地踏步开关
- `C`：双手欢呼
- `Space`：急停

## 注意

如果动作 YAML 路径不对，网页仍能启动，但动作列表为空。此时先测试停止、唤醒和低速移动，再检查 `config.robot.json` 中的动作路径。
