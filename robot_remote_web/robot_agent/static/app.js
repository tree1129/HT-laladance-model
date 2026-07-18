const state = {
  actions: null,
  pressedKeys: new Set(),
  moveLoop: null,
  marchLoop: null,
  pointerHoldLoop: null,
  wakeAttempted: false,
  lastMoveSignature: "",
  marchPhase: 1,
  moveRequestInFlight: false,
};

const moveMap = {
  forward: { vx: 0.08, vy: 0.0, wz: 0.0 },
  backward: { vx: -0.05, vy: 0.0, wz: 0.0 },
  left: { vx: 0.0, vy: 0.05, wz: 0.0 },
  right: { vx: 0.0, vy: -0.05, wz: 0.0 },
  "turn-left": { vx: 0.0, vy: 0.0, wz: 0.22 },
  "turn-right": { vx: 0.0, vy: 0.0, wz: -0.22 },
  stop: { vx: 0.0, vy: 0.0, wz: 0.0 },
};

const keyMoveMap = {
  KeyW: "forward",
  KeyS: "backward",
  KeyA: "left",
  KeyD: "right",
  KeyQ: "turn-left",
  KeyE: "turn-right",
};

function log(message, data) {
  const el = document.getElementById("log-output");
  const stamp = new Date().toLocaleTimeString();
  const line = [`[${stamp}] ${message}`];
  if (data) line.push(typeof data === "string" ? data : JSON.stringify(data, null, 2));
  el.textContent = `${line.join("\n")}\n\n${el.textContent}`.trim();
}

function setStatus(text) {
  document.getElementById("status-text").textContent = text;
}

function setBridgeStatus(text) {
  document.getElementById("bridge-status").textContent = text;
}

async function requestJson(path, payload = null, method = "POST") {
  const options = { method, headers: {} };
  if (payload !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(payload);
  }
  const res = await fetch(path, options);
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || "request failed");
  return data;
}

async function api(path, payload = {}) {
  return requestJson(path, payload, "POST");
}

function actionProfiles(itemName) {
  return (state.actions?.production_profiles || [])
    .filter(Boolean)
    .flatMap((profile) => {
      const groups = [
        ...(profile.multi_waypoint_config || []),
        ...(profile.series_waypoint_config || []),
        ...(profile.policy_change_config || []),
      ];
      return groups
        .filter((entry) => entry.name === itemName && entry.key)
        .map((entry) => ({ productionType: profile.production_type, key: entry.key }));
    });
}

function renderActionList(containerId, items, categoryLabel) {
  const box = document.getElementById(containerId);
  box.innerHTML = "";
  items.forEach((item) => {
    const profiles = actionProfiles(item.name);
    const keyTags = profiles.length
      ? `<div class="action-meta">${profiles.map((profile) => `<span class="action-key" title="${profile.productionType}">${profile.key}</span>`).join("")}</div>`
      : "";
    const btn = document.createElement("button");
    btn.className = "action-btn";
    btn.innerHTML = `
      <strong>${item.name}</strong>
      <span>${item.remark || categoryLabel}</span>
      ${keyTags}
    `;
    btn.addEventListener("click", () => runNamedAction(item.name, item.name));
    box.appendChild(btn);
  });
}

async function loadConfig() {
  const data = await requestJson("/api/config", null, "GET");
  state.actions = data.actions || {};
  document.getElementById("action-count").textContent = String(
    (state.actions.policy_change_config || []).length +
    (state.actions.multi_waypoint_config || []).length +
    (state.actions.series_waypoint_config || []).length
  );
  renderActionList("policy-list", state.actions.policy_change_config || [], "策略动作");
  renderActionList("waypoint-list", state.actions.multi_waypoint_config || [], "单段动作");
  renderActionList("series-list", state.actions.series_waypoint_config || [], "串联动作");
  setBridgeStatus("机器人本机 Joy");
  if (data.action_load_error || state.actions.load_error) {
    log("动作库未加载，走路/停止仍可测试", data.action_load_error || state.actions.load_error);
  } else {
    log("动作库已加载", state.actions.production_profiles || []);
  }
}

async function wakeRobot() {
  const result = await api("/api/wake");
  state.wakeAttempted = true;
  setStatus("已尝试进入运动模式");
  log("已发送运动模式唤醒", result);
  return result;
}

async function sendCmd(vector) {
  return (vector.vx === 0 && vector.vy === 0 && vector.wz === 0)
    ? api("/api/stop")
    : api("/api/move", { ...vector, repeat: 3 });
}

async function sendVector(vector, reason, options = {}) {
  const signature = JSON.stringify(vector);
  if (!options.force && signature === state.lastMoveSignature) return;
  if (!options.stop && state.moveRequestInFlight) return;

  state.lastMoveSignature = signature;
  state.moveRequestInFlight = true;
  try {
    const result = await sendCmd(vector);
    setStatus(reason);
    log(`运动控制: ${reason}`, { vector, result });
  } catch (err) {
    state.lastMoveSignature = "";
    setStatus("控制失败");
    log(`运动控制失败: ${reason}`, err.message);
  } finally {
    state.moveRequestInFlight = false;
  }
}

function stopMoveLoop() {
  if (state.moveLoop) clearInterval(state.moveLoop);
  state.moveLoop = null;
}

function stopMarchLoop() {
  if (state.marchLoop) clearInterval(state.marchLoop);
  state.marchLoop = null;
  document.getElementById("march-btn")?.classList.remove("active");
}

function stopPointerHoldLoop() {
  if (state.pointerHoldLoop) clearInterval(state.pointerHoldLoop);
  state.pointerHoldLoop = null;
}

function emergencyStop(reason = "急停") {
  state.pressedKeys.clear();
  stopMoveLoop();
  stopMarchLoop();
  stopPointerHoldLoop();
  state.lastMoveSignature = "";
  setStatus(`${reason}中`);
  sendVector(moveMap.stop, reason, { force: true, stop: true });
}

function getCurrentVector() {
  let vx = 0.0;
  let vy = 0.0;
  let wz = 0.0;
  if (state.pressedKeys.has("KeyW")) vx += moveMap.forward.vx;
  if (state.pressedKeys.has("KeyS")) vx += moveMap.backward.vx;
  if (state.pressedKeys.has("KeyA")) vy += moveMap.left.vy;
  if (state.pressedKeys.has("KeyD")) vy += moveMap.right.vy;
  if (state.pressedKeys.has("KeyQ")) wz += moveMap["turn-left"].wz;
  if (state.pressedKeys.has("KeyE")) wz += moveMap["turn-right"].wz;
  return {
    vx: Math.max(-0.08, Math.min(0.08, vx)),
    vy: Math.max(-0.05, Math.min(0.05, vy)),
    wz: Math.max(-0.22, Math.min(0.22, wz)),
  };
}

function refreshMoveLoop() {
  stopMoveLoop();
  const activeKeys = Object.keys(keyMoveMap).filter((code) => state.pressedKeys.has(code));
  if (!activeKeys.length) {
    emergencyStop("松开按键自动停止");
    return;
  }
  const tick = () => sendVector(getCurrentVector(), `键盘移动 ${activeKeys.map((code) => keyMoveMap[code]).join("+")}`, { force: true });
  tick();
  state.moveLoop = setInterval(tick, 240);
}

async function toggleMarchMode() {
  if (state.marchLoop) {
    emergencyStop("停止原地踏步");
    return;
  }
  stopMoveLoop();
  stopPointerHoldLoop();
  state.pressedKeys.clear();
  if (!state.wakeAttempted) await wakeRobot();
  state.marchPhase = 1;
  document.getElementById("march-btn")?.classList.add("active");
  const tick = () => {
    const vector = { vx: 0.02, vy: 0.0, wz: state.marchPhase > 0 ? 0.18 : -0.18 };
    state.marchPhase *= -1;
    sendVector(vector, "安全原地踏步", { force: true });
  };
  tick();
  state.marchLoop = setInterval(tick, 300);
  setStatus("安全原地踏步中");
}

async function startPointerHold(kind) {
  if (kind === "stop" || kind === "march-toggle") return;
  stopMarchLoop();
  stopPointerHoldLoop();
  if (!state.wakeAttempted) await wakeRobot();
  const vector = moveMap[kind];
  const tick = () => sendVector(vector, `按住控制 ${kind}`, { force: true });
  tick();
  state.pointerHoldLoop = setInterval(tick, 240);
}

async function runChoreography() {
  try {
    emergencyStop("编排开始前安全停止");
    setStatus("执行安全啦啦操编排中");
    const result = await api("/api/choreography");
    setStatus("编排执行完成");
    log("编排执行完成", result);
  } catch (err) {
    setStatus("编排执行失败");
    log("编排执行失败", err.message);
  }
}

async function runNamedAction(name, label = name) {
  try {
    setStatus(`执行 ${label}`);
    const result = await api("/api/action", { name });
    setStatus(`${label} 已发送`);
    log(`动作已发送: ${label}`, result);
  } catch (err) {
    setStatus(`${label} 发送失败`);
    log(`动作失败: ${label}`, err.message);
  }
}

function normalizeKeyCode(event) {
  if (event.code === "Space") return "Space";
  if (event.code === "KeyR") return "KeyR";
  if (event.code === "KeyC") return "KeyC";
  return keyMoveMap[event.code] ? event.code : "";
}

function bindKeyboard() {
  window.addEventListener("keydown", async (event) => {
    const code = normalizeKeyCode(event);
    if (!code) return;
    if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
    event.preventDefault();
    if (code === "Space") return emergencyStop("空格急停");
    if (code === "KeyR" && !event.repeat) return toggleMarchMode();
    if (code === "KeyC" && !event.repeat) return runNamedAction("cheer", "双手欢呼");
    if (event.repeat || state.pressedKeys.has(code)) return;
    if (!state.wakeAttempted) await wakeRobot();
    if (state.marchLoop) stopMarchLoop();
    state.pressedKeys.add(code);
    refreshMoveLoop();
  });

  window.addEventListener("keyup", (event) => {
    const code = normalizeKeyCode(event);
    if (!code || ["Space", "KeyR", "KeyC"].includes(code)) return;
    if (!state.pressedKeys.has(code)) return;
    state.pressedKeys.delete(code);
    refreshMoveLoop();
  });

  window.addEventListener("blur", () => emergencyStop("窗口失焦自动停止"));
}

function bindEvents() {
  document.querySelectorAll("[data-move]").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.dataset.move === "march-toggle") return toggleMarchMode();
      if (btn.dataset.move === "stop") return emergencyStop("停止按钮");
    });
    if (btn.dataset.move && !["stop", "march-toggle"].includes(btn.dataset.move)) {
      btn.addEventListener("mousedown", () => startPointerHold(btn.dataset.move));
      btn.addEventListener("mouseup", () => emergencyStop("松开按钮停止"));
      btn.addEventListener("mouseleave", () => emergencyStop("离开按钮停止"));
      btn.addEventListener("touchstart", (event) => {
        event.preventDefault();
        startPointerHold(btn.dataset.move);
      }, { passive: false });
      btn.addEventListener("touchend", () => emergencyStop("松开按钮停止"));
      btn.addEventListener("touchcancel", () => emergencyStop("触控取消停止"));
    }
  });
  document.getElementById("wake-btn").addEventListener("click", () => wakeRobot());
  document.getElementById("stop-btn").addEventListener("click", () => emergencyStop("急停按钮"));
  document.getElementById("choreo-btn").addEventListener("click", () => runChoreography());
  document.getElementById("cheer-btn").addEventListener("click", () => runNamedAction("cheer", "双手欢呼"));
}

bindEvents();
bindKeyboard();
setBridgeStatus("机器人本机 Joy");
loadConfig().catch((err) => {
  setStatus("初始化失败");
  log("初始化失败", err.message);
});
