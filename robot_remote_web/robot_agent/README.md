# 机器人端控制服务

这个目录用于部署到机器人本机。

现在它已经是一套 **机器人本机可视化系统**：

- 机器人本机启动常驻 HTTP 服务
- 机器人本机直接发布 `/joy_input`
- 机器人本机直接触发动作按键映射
- 机器人本机自己提供网页界面

建议部署位置：

```bash
/home/hightorque/robot_remote_web_agent/robot_agent
```

也可以在电脑上直接执行：

```bash
cd /Users/tree/Desktop/高擎小pi-啦啦操/robot_remote_web
bash deploy_robot_agent.sh
```

## 启动

```bash
cd /home/hightorque/robot_remote_web_agent/robot_agent
bash start_robot_agent.sh
```

## 浏览器访问

在 PC 或手机浏览器里打开：

```text
http://192.168.43.44:8766
```

这样你以后就不需要再在 PC 上额外跑一套 `server.py` 页面服务了。

## 键盘控制

打开页面后可直接使用键盘：

- `W / A / S / D`：前后左右
- `Q / E`：左转 / 右转
- `R`：切换原地踏步
- `Space`：急停
