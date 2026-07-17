#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import time

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
STATIC_DIR = ROOT / "static"
CONFIG_PATH = ROOT / "config.json"
APP_CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

HOST = APP_CONFIG["server"]["host"]
PORT = APP_CONFIG["server"]["port"]
ROBOT_CONFIG = APP_CONFIG["robot"]

ACTION_BASE = WORKSPACE / APP_CONFIG["paths"]["action_config_root"]
BASE_POLICY = WORKSPACE / APP_CONFIG["paths"]["base_policy"]
BASE_WAYPOINT = WORKSPACE / APP_CONFIG["paths"]["base_waypoint"]
CUSTOM_ACTION = WORKSPACE / APP_CONFIG["paths"]["custom_action"]


def load_yaml(path: Path):
    if yaml is None:
        raise RuntimeError("缺少 PyYAML，动作库暂不可读；走路、停止、唤醒接口仍可测试")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def empty_action_catalog(load_error: str = ""):
    return {
        "policy_change_config": [],
        "multi_waypoint_config": [],
        "series_waypoint_config": [],
        "production_profiles": [],
        "load_error": load_error,
    }


def build_action_catalog():
    catalog = empty_action_catalog()

    try:
        base_policy = load_yaml(BASE_POLICY)
        base_waypoint = load_yaml(BASE_WAYPOINT)
        custom_action = load_yaml(CUSTOM_ACTION)
    except Exception as exc:
        return empty_action_catalog(str(exc))

    catalog["policy_change_config"] = base_policy.get("policy_change_config", [])
    catalog["multi_waypoint_config"] = base_waypoint.get("multi_waypoint_config", [])
    catalog["series_waypoint_config"] = base_waypoint.get("series_waypoint_config", [])
    catalog["production_profiles"] = custom_action if isinstance(custom_action, list) else []
    return catalog


ACTION_CATALOG = build_action_catalog()
ACTION_LOCK = threading.Lock()

KEY_TO_JOY = {
    "a": {"buttons": {0: 1}},
    "b": {"buttons": {1: 1}},
    "x": {"buttons": {2: 1}},
    "y": {"buttons": {3: 1}},
    "lb": {"buttons": {4: 1}},
    "rb": {"buttons": {5: 1}},
    "back": {"buttons": {6: 1}},
    "start": {"buttons": {7: 1}},
    "l": {"buttons": {9: 1}},
    "r": {"buttons": {10: 1}},
    "lt": {"axes": {2: 1.0}},
    "rt": {"axes": {5: 1.0}},
    "dpl": {"axes": {6: -1.0}},
    "dpr": {"axes": {6: 1.0}},
    "dpu": {"axes": {7: 1.0}},
    "dpd": {"axes": {7: -1.0}},
}


def tcl_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace('"', '\\"')
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("$", "\\$")
    )


def run_ssh_command(remote_command: str):
    expect_script = f'''
set timeout 20
spawn ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {ROBOT_CONFIG["user"]}@{ROBOT_CONFIG["host"]} "{tcl_escape(remote_command)}"
expect {{
    "*yes/no*" {{ send "yes\\r"; exp_continue }}
    "*assword:*" {{ send "{tcl_escape(ROBOT_CONFIG["password"])}\\r" }}
}}
expect eof
'''
    result = subprocess.run(
        ["/usr/bin/expect", "-c", expect_script],
        capture_output=True,
        text=True,
        cwd=str(WORKSPACE),
    )
    return {
        "ok": result.returncode == 0,
        "code": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "remote_command": remote_command,
    }


def ros_remote_command(inner: str) -> str:
    return (
        "bash -lc "
        + shlex.quote(
            "source /opt/ros/noetic/setup.bash >/dev/null 2>&1; "
            "if [ -f ~/catkin_ws/devel/setup.bash ]; then source ~/catkin_ws/devel/setup.bash >/dev/null 2>&1; fi; "
            "if [ -f ~/catkin_ws/install/setup.bash ]; then source ~/catkin_ws/install/setup.bash >/dev/null 2>&1; fi; "
            + inner
        )
    )


def publish_cmd_vel(vx: float, vy: float, wz: float):
    cmd = (
        "rostopic pub -1 /cmd_vel geometry_msgs/Twist "
        f"'{{linear: {{x: {vx}, y: {vy}, z: 0.0}}, angular: {{x: 0.0, y: 0.0, z: {wz}}}}}'"
    )
    return run_ssh_command(ros_remote_command(cmd))


def repeat_cmd_vel(vx: float, vy: float, wz: float, repeat: int, sleep_s: float):
    cmd_vel = (
        "rostopic pub -1 /cmd_vel geometry_msgs/Twist "
        f"'{{linear: {{x: {vx}, y: {vy}, z: 0.0}}, angular: {{x: 0.0, y: 0.0, z: {wz}}}}}'"
    )
    remote = (
        "bash -lc "
        + shlex.quote(
            f"for i in $(seq 1 {repeat}); do "
            f"{cmd_vel} >/dev/null 2>&1; "
            f"sleep {sleep_s}; "
            "done"
        )
    )
    return run_ssh_command(ros_remote_command(remote))


def publish_joy_input(axes=None, buttons=None):
    axes = axes or [0.0] * 8
    buttons = buttons or [0] * 11
    axes_text = ", ".join(str(v) for v in axes)
    buttons_text = ", ".join(str(v) for v in buttons)
    cmd = (
        "rostopic pub -1 /joy_input sensor_msgs/Joy "
        + shlex.quote(
            "{header: {stamp: now, frame_id: ''}, axes: ["
            + axes_text
            + "], buttons: ["
            + buttons_text
            + "]}"
        )
    )
    return run_ssh_command(ros_remote_command(cmd))


def publish_joy_input_stream(axes=None, buttons=None, duration=0.3, interval=0.06):
    axes = axes or [0.0] * 8
    buttons = buttons or [0] * 11
    loops = max(1, int(duration / interval))
    axes_text = ", ".join(str(v) for v in axes)
    buttons_text = ", ".join(str(v) for v in buttons)
    cmd = (
        f"for i in $(seq 1 {loops}); do "
        + "rostopic pub -1 /joy_input sensor_msgs/Joy "
        + shlex.quote(
            "{header: {stamp: now, frame_id: ''}, axes: ["
            + axes_text
            + "], buttons: ["
            + buttons_text
            + "]}"
        )
        + f" >/dev/null 2>&1; sleep {interval}; done"
    )
    return run_ssh_command(ros_remote_command(cmd))


def wake_running_mode():
    # 对照 joy_footstep.yaml:
    # button 4 -> running_standby_switch
    # button 9 -> standby
    buttons = [0] * 11
    buttons[4] = 1
    return publish_joy_input_stream(buttons=buttons, duration=0.25, interval=0.08)


def standby_mode():
    buttons = [0] * 11
    buttons[9] = 1
    return publish_joy_input_stream(buttons=buttons, duration=0.25, interval=0.08)


def build_joy_from_keys(keys):
    axes = [0.0] * 8
    buttons = [0] * 11
    for key in keys:
        mapping = KEY_TO_JOY.get(key.lower())
        if not mapping:
            continue
        for idx, value in mapping.get("axes", {}).items():
            axes[idx] = value
        for idx, value in mapping.get("buttons", {}).items():
            buttons[idx] = value
    return axes, buttons


def trigger_action_keys(keys):
    axes, buttons = build_joy_from_keys(keys)
    return publish_joy_input_stream(axes=axes, buttons=buttons, duration=0.35, interval=0.08)


def joy_move(vx: float, vy: float, wz: float, duration: float = 0.25, interval: float = 0.06):
    axes = [0.0] * 8
    buttons = [0] * 11
    axes[0] = float(vy)
    axes[1] = float(vx)
    axes[2] = float(wz)
    return publish_joy_input_stream(axes=axes, buttons=buttons, duration=duration, interval=interval)


def resolve_action(name: str):
    for section in ("policy_change_config", "multi_waypoint_config", "series_waypoint_config"):
        for item in ACTION_CATALOG.get(section, []):
            if item.get("name") == name:
                return section, item
    return None, None


def action_key_profiles(name: str):
    matches = []
    for profile in ACTION_CATALOG.get("production_profiles", []):
        if not profile:
            continue
        for section in ("policy_change_config", "multi_waypoint_config", "series_waypoint_config"):
            items = profile.get(section) or []
            for item in items:
                if item.get("name") == name:
                    matches.append(
                        {
                            "production_type": profile.get("production_type", ""),
                            "section": section,
                            "key": item.get("key", ""),
                            "remark": item.get("remark", ""),
                        }
                    )
    return matches


def run_named_action(name: str):
    section, item = resolve_action(name)
    if not item:
        return {
            "ok": False,
            "error": f"未找到动作: {name}",
        }

    profiles = action_key_profiles(name)
    detail = {
        "name": item.get("name"),
        "remark": item.get("remark", ""),
        "section": section,
        "profiles": profiles,
    }

    selected_profile = None
    for profile in profiles:
        if profile.get("key"):
            selected_profile = profile
            break

    if selected_profile and selected_profile.get("key"):
        key_tokens = [token.strip().lower() for token in selected_profile["key"].split("+") if token.strip()]
        ssh_result = trigger_action_keys(key_tokens)
        transport = "joy_input:key_combo"
    else:
        cmd = (
            "rostopic pub -1 /web_remote_action std_msgs/String "
            + shlex.quote(f"data: '{json.dumps(detail, ensure_ascii=False)}'")
        )
        ssh_result = run_ssh_command(ros_remote_command(cmd))
        transport = "ros_topic:/web_remote_action"

    return {
        "ok": ssh_result["ok"],
        "detail": detail,
        "transport": transport,
        "ssh": ssh_result,
        "hint": selected_profile["key"] if selected_profile else "未找到对应按键映射，已退回字符串动作指令。",
    }


def run_choreography():
    steps = []

    def record(step_name, result):
        steps.append({
            "step": step_name,
            "ok": result.get("ok", False),
            "result": result,
        })
        return result.get("ok", False)

    record("wake_running_mode", wake_running_mode())

    for index in range(4):
        direction = 0.28 if index % 2 == 0 else -0.28
        record(
            f"safe_march_{index + 1:02d}",
            repeat_cmd_vel(0.03, 0.0, direction, repeat=2, sleep_s=0.22),
        )

    record("double_hand_cheer", run_named_action("cheer"))
    record("slow_forward", repeat_cmd_vel(0.10, 0.0, 0.0, repeat=4, sleep_s=0.22))
    record("double_hand_cheer_repeat", run_named_action("cheer"))
    record("stop", publish_cmd_vel(0.0, 0.0, 0.0))
    record("standby_mode", standby_mode())

    return {
        "ok": all(step["ok"] for step in steps),
        "sequence": "wake -> safe march -> cheer -> slow forward -> cheer -> stop -> standby",
        "policy": "safe_demo_v1",
        "steps": steps,
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path: Path, content_type: str):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if parsed.path == "/app.js":
            return self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if parsed.path == "/styles.css":
            return self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        if parsed.path == "/api/config":
            return self._send_json(
                {
                    "ok": True,
                    "robot": {
                        "host_alias": ROBOT_CONFIG.get("host_alias", ""),
                        "host": ROBOT_CONFIG.get("host", ""),
                        "user": ROBOT_CONFIG.get("user", ""),
                    },
                    "actions": ACTION_CATALOG,
                    "action_load_error": ACTION_CATALOG.get("load_error", ""),
                }
            )
        return self._send_json({"ok": False, "error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}

        if parsed.path == "/api/move":
            vx = float(payload.get("vx", 0.0))
            vy = float(payload.get("vy", 0.0))
            wz = float(payload.get("wz", 0.0))
            duration = float(payload.get("duration", 0.25))
            interval = float(payload.get("interval", 0.06))
            result = joy_move(vx, vy, wz, duration=duration, interval=interval)
            return self._send_json({"ok": result["ok"], "result": result})

        if parsed.path == "/api/stop":
            result = joy_move(0.0, 0.0, 0.0, duration=0.12, interval=0.06)
            return self._send_json({"ok": result["ok"], "result": result})

        if parsed.path == "/api/wake":
            result = wake_running_mode()
            return self._send_json({"ok": result["ok"], "result": result})

        if parsed.path == "/api/action":
            name = str(payload.get("name", "")).strip()
            if not name:
                return self._send_json({"ok": False, "error": "缺少动作名"}, status=400)
            with ACTION_LOCK:
                result = run_named_action(name)
            return self._send_json(result, status=200 if result.get("ok") else 500)

        if parsed.path == "/api/choreography":
            with ACTION_LOCK:
                result = run_choreography()
            return self._send_json(result, status=200 if result.get("ok") else 500)

        return self._send_json({"ok": False, "error": "Not found"}, status=404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Virtual remote started: http://{HOST}:{PORT}")
    print(f"Robot target: {ROBOT_CONFIG['user']}@{ROBOT_CONFIG['host']}")
    server.serve_forever()


if __name__ == "__main__":
    main()
