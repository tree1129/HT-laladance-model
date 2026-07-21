#!/usr/bin/env python3
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import rospy
from sensor_msgs.msg import Joy

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


CHOREOGRAPHY_SEQUENCE = [
    {"move": {"vx": 0.03, "vy": 0.0, "wz": 0.28}, "label": "安全原地踏步左摆", "repeat": 4, "pause": 0.3},
    {"move": {"vx": 0.03, "vy": 0.0, "wz": -0.28}, "label": "安全原地踏步右摆", "repeat": 4, "pause": 0.3},
    {"action": "cheer", "label": "双手欢呼", "pause": 0.8},
    {"move": {"vx": 0.10, "vy": 0.0, "wz": 0.0}, "label": "慢速前进", "repeat": 6, "pause": 0.5},
    {"action": "cheer", "label": "双手欢呼", "pause": 0.8},
    {"move": {"vx": 0.0, "vy": 0.0, "wz": 0.0}, "label": "停止", "repeat": 3, "pause": 0.0},
]


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CONFIG = json.loads((ROOT / "config.robot.json").read_text(encoding="utf-8"))
HOST = CONFIG["server"]["host"]
PORT = CONFIG["server"]["port"]
ROBOT_INFO = CONFIG.get("robot", {})
PATHS_CONFIG = CONFIG.get("paths", {})
ACTION_KEY_OVERRIDES = CONFIG.get("action_keys", {})

KEY_TO_JOY = {
    "a": {"buttons": {0: 1}},
    "b": {"buttons": {1: 1}},
    "x": {"buttons": {2: 1}},
    "y": {"buttons": {3: 1}},
    "lb": {"buttons": {4: 1}},
    "rb": {"buttons": {5: 1}},
    "back": {"buttons": {6: 1}},
    "start": {"buttons": {7: 1}},
    "center": {"buttons": {8: 1}},
    "l": {"buttons": {9: 1}},
    "r": {"buttons": {10: 1}},
    # Xbox-style ROS Joy reports triggers as +1 when released and -1 when pressed.
    "lt": {"axes": {2: -1.0}},
    "rt": {"axes": {5: -1.0}},
    "dpl": {"axes": {6: -1.0}},
    "dpr": {"axes": {6: 1.0}},
    "dpu": {"axes": {7: 1.0}},
    "dpd": {"axes": {7: -1.0}},
}


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


def first_existing_path(candidates):
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.exists():
            return path
    raise FileNotFoundError("未找到可用动作配置文件: " + " | ".join(str(Path(c)) for c in candidates))


def resolve_action_paths():
    configured_policy = PATHS_CONFIG.get("base_policy")
    configured_waypoint = PATHS_CONFIG.get("base_waypoint")
    configured_custom = PATHS_CONFIG.get("custom_action")

    candidate_roots = [
        Path("/home/hightorque/catkin_ws/src/sim2real_master/src/sim2real/action_config/config/pi_plus_22dof"),
        Path("/home/hightorque/catkin_ws/src/sim2real/action_config/config/pi_plus_22dof"),
        Path("/home/hightorque/Sim2Real/sim2real_master/src/sim2real/action_config/config/pi_plus_22dof"),
    ]

    base_policy = first_existing_path(
        ([configured_policy] if configured_policy else [])
        + [root / "base_policy.yaml" for root in candidate_roots]
    )
    base_waypoint = first_existing_path(
        ([configured_waypoint] if configured_waypoint else [])
        + [root / "base_waypoint.yaml" for root in candidate_roots]
    )
    custom_action = first_existing_path(
        ([configured_custom] if configured_custom else [])
        + [root / "custom_action.yaml" for root in candidate_roots]
    )
    return base_policy, base_waypoint, custom_action


def build_action_catalog():
    catalog = empty_action_catalog()
    try:
        base_policy_path, base_waypoint_path, custom_action_path = resolve_action_paths()
        base_policy = load_yaml(base_policy_path)
        base_waypoint = load_yaml(base_waypoint_path)
        custom_action = load_yaml(custom_action_path)
    except Exception as exc:
        return empty_action_catalog(str(exc))

    catalog["policy_change_config"] = base_policy.get("policy_change_config", [])
    catalog["multi_waypoint_config"] = base_waypoint.get("multi_waypoint_config", [])
    catalog["series_waypoint_config"] = base_waypoint.get("series_waypoint_config", [])
    catalog["production_profiles"] = custom_action if isinstance(custom_action, list) else []
    return catalog


ACTION_CATALOG = build_action_catalog()
ACTION_LOCK = threading.Lock()


class RobotControlBridge:
    def __init__(self):
        rospy.init_node("pc_robot_remote_bridge", anonymous=True)
        self.joy_pub = rospy.Publisher("/joy_input", Joy, queue_size=1)
        self._motion_lock = threading.Lock()
        self._motion_axes = [0.0] * 8
        self._motion_active = False
        self._motion_deadline = 0.0
        self._motion_stop_frames = 0
        self._action_axes = {}
        self._action_buttons = {}
        self._action_frames_remaining = 0
        self._action_release_pending = False
        self._motion_thread = threading.Thread(target=self._publish_motion_loop, daemon=True)
        self._motion_thread.start()

    def _publish_motion_loop(self):
        rate = rospy.Rate(16)
        while not rospy.is_shutdown():
            should_publish, axes, buttons = self._compose_next_joy()
            if should_publish:
                msg = Joy()
                msg.header.stamp = rospy.Time.now()
                msg.axes = axes
                msg.buttons = buttons
                self.joy_pub.publish(msg)
            rate.sleep()

    def _compose_next_joy(self):
        expired = False
        with self._motion_lock:
            if self._motion_active and time.monotonic() >= self._motion_deadline:
                self._motion_active = False
                self._motion_axes = [0.0] * 8
                self._motion_stop_frames = max(self._motion_stop_frames, 1)
                expired = True

            motion_active = self._motion_active
            axes = list(self._motion_axes)
            buttons = [0] * 11

            action_active = self._action_frames_remaining > 0
            if action_active:
                for idx, value in self._action_axes.items():
                    axes[idx] = value
                for idx, value in self._action_buttons.items():
                    buttons[idx] = value
                self._action_frames_remaining -= 1
                if self._action_frames_remaining == 0:
                    self._action_release_pending = True

            release_action = not action_active and self._action_release_pending
            if release_action:
                self._action_release_pending = False

            stop_active = self._motion_stop_frames > 0
            if stop_active:
                self._motion_stop_frames -= 1

        should_publish = motion_active or expired or stop_active or action_active or release_action
        return should_publish, axes, buttons

    @staticmethod
    def movement_axes(vx, vy, wz):
        axes = [0.0] * 8
        axes[0] = max(-1.0, min(1.0, float(vy)))
        axes[1] = max(-1.0, min(1.0, float(vx)))
        axes[3] = max(-1.0, min(1.0, float(wz)))
        return axes

    def set_motion_target(self, vx, vy, wz, timeout=0.7):
        axes = self.movement_axes(vx, vy, wz)
        with self._motion_lock:
            self._motion_axes = axes
            self._motion_active = True
            self._motion_deadline = time.monotonic() + max(0.2, float(timeout))
            self._motion_stop_frames = 0
        return {"ok": True, "axes": axes, "timeout": timeout}

    def stop_motion(self):
        with self._motion_lock:
            self._motion_active = False
            self._motion_axes = [0.0] * 8
            self._motion_deadline = 0.0
            self._motion_stop_frames = 2
        return {"ok": True, "axes": [0.0] * 8, "buttons": [0] * 11, "repeat": 2}

    def publish_joy(self, axes=None, buttons=None, repeat=1):
        axes = axes or [0.0] * 8
        buttons = buttons or [0] * 11
        msg = Joy()
        msg.axes = axes
        msg.buttons = buttons
        rate = rospy.Rate(16)
        for _ in range(max(1, repeat)):
            msg.header.stamp = rospy.Time.now()
            self.joy_pub.publish(msg)
            rate.sleep()
        return {"ok": True, "axes": axes, "buttons": buttons, "repeat": repeat}

    def joy_move(self, vx, vy, wz, repeat=4):
        return self.publish_joy(axes=self.movement_axes(vx, vy, wz), repeat=repeat)

    def wake_running_mode(self):
        buttons = [0] * 11
        buttons[4] = 1
        return self.publish_joy(buttons=buttons, repeat=3)

    def standby_mode(self):
        buttons = [0] * 11
        buttons[9] = 1
        return self.publish_joy(buttons=buttons, repeat=3)

    def trigger_action_keys(self, keys):
        action_axes = {}
        action_buttons = {}
        recognized_keys = []
        for key in keys:
            mapping = KEY_TO_JOY.get(key.lower())
            if not mapping:
                continue
            recognized_keys.append(key.lower())
            for idx, value in mapping.get("axes", {}).items():
                action_axes[idx] = value
            for idx, value in mapping.get("buttons", {}).items():
                action_buttons[idx] = value

        if not recognized_keys:
            return {"ok": False, "error": "No valid virtual controller keys"}

        with self._motion_lock:
            self._action_axes = action_axes
            self._action_buttons = action_buttons
            self._action_frames_remaining = 5
            self._action_release_pending = False

        return {"ok": True, "keys": recognized_keys, "frames": 5}

    def action_key_profiles(self, name):
        matches = []
        for profile in ACTION_CATALOG.get("production_profiles", []):
            if not profile:
                continue
            for section in ("policy_change_config", "multi_waypoint_config", "series_waypoint_config"):
                for item in profile.get(section) or []:
                    if item.get("name") == name:
                        matches.append(item.get("key"))
        return [match for match in matches if match]

    def run_named_action(self, name):
        keys = self.action_key_profiles(name)
        selected_key = ACTION_KEY_OVERRIDES.get(name) or (keys[0] if keys else "")
        if not selected_key:
            return {"ok": False, "error": f"未找到动作按键映射: {name}"}
        tokens = [token.strip().lower() for token in selected_key.split("+") if token.strip()]
        result = self.trigger_action_keys(tokens)
        result["name"] = name
        result["key"] = selected_key
        return result

    def run_choreography(self):
        try:
            rospy.loginfo("开始执行安全啦啦操编排")
            for index, step in enumerate(CHOREOGRAPHY_SEQUENCE, start=1):
                if "action" in step:
                    rospy.loginfo(f"编排步骤 {index}: {step['label']}")
                    result = self.run_named_action(step["action"])
                    if not result.get("ok"):
                        return {"ok": False, "error": f"编排步骤 {index} 失败: {result.get('error')}"}
                elif "move" in step:
                    rospy.loginfo(f"编排步骤 {index}: {step['label']}")
                    move = step["move"]
                    result = self.joy_move(
                        float(move.get("vx", 0.0)),
                        float(move.get("vy", 0.0)),
                        float(move.get("wz", 0.0)),
                        repeat=int(step.get("repeat", 4)),
                    )
                    if not result.get("ok"):
                        return {"ok": False, "error": f"编排步骤 {index} 失败: {result.get('error')}"}
                else:
                    return {"ok": False, "error": f"编排步骤 {index} 配置错误"}

                pause = float(step.get("pause", 0.0))
                if pause > 0:
                    rospy.loginfo(f"编排步骤 {index} 完成后等待 {pause} 秒")
                    rospy.sleep(pause)

            rospy.loginfo("编排序列执行完成")
            return {"ok": True, "message": "编排执行完成", "steps": len(CHOREOGRAPHY_SEQUENCE)}
        except Exception as exc:
            rospy.logerr(f"编排执行异常: {exc}")
            return {"ok": False, "error": str(exc)}


BRIDGE = RobotControlBridge()


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
        path = urlparse(self.path).path
        if path == "/":
            return self._send_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._send_file(STATIC_DIR / "app.js", "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self._send_file(STATIC_DIR / "styles.css", "text/css; charset=utf-8")
        if path == "/api/config":
            return self._send_json({
                "ok": True,
                "actions": ACTION_CATALOG,
                "action_load_error": ACTION_CATALOG.get("load_error", ""),
                "mode": "robot-local",
                "robot": {
                    "host": ROBOT_INFO.get("host", "localhost"),
                    "user": ROBOT_INFO.get("user", "hightorque"),
                },
            })
        return self._send_json({"ok": False, "error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            payload = json.loads(raw or "{}")
        except json.JSONDecodeError:
            payload = {}

        with ACTION_LOCK:
            if parsed.path == "/api/move":
                result = BRIDGE.set_motion_target(
                    float(payload.get("vx", 0.0)),
                    float(payload.get("vy", 0.0)),
                    float(payload.get("wz", 0.0)),
                    float(payload.get("timeout", 0.7)),
                )
                return self._send_json({"ok": result["ok"], "result": result})

            if parsed.path == "/api/stop":
                result = BRIDGE.stop_motion()
                return self._send_json({"ok": result["ok"], "result": result})

            if parsed.path == "/api/wake":
                result = BRIDGE.wake_running_mode()
                return self._send_json({"ok": result["ok"], "result": result})

            if parsed.path == "/api/standby":
                result = BRIDGE.standby_mode()
                return self._send_json({"ok": result["ok"], "result": result})

            if parsed.path == "/api/action":
                name = str(payload.get("name", "")).strip()
                if not name:
                    return self._send_json({"ok": False, "error": "缺少动作名"}, 400)
                result = BRIDGE.run_named_action(name)
                return self._send_json(result, 200 if result.get("ok") else 500)

            if parsed.path == "/api/choreography":
                result = BRIDGE.run_choreography()
                return self._send_json(result, 200 if result.get("ok") else 500)

        return self._send_json({"ok": False, "error": "Not found"}, 404)


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Robot remote bridge started on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
