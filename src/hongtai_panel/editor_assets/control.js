"use strict";

let token = "";
let panel = null;
let polling = null;
let brightnessDirty = false;

const $ = selector => document.querySelector(selector);

function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast show ${error ? "error" : ""}`;
  setTimeout(() => { toast.className = "toast"; }, 2800);
}

function stateText(state) {
  return {
    disconnected: ["Disconnected", "Waiting for panel detection", "Choose Detect panel to begin."],
    detected: ["Detected", "Panel ready", "Choose a layout, then start the display."],
    starting: ["Starting", "Starting display", "Opening the live image pipeline…"],
    streaming: ["Streaming", "Display is live", "Frames and keepalives are being sent."],
    stopped: ["Stopped", "Display stopped", "The serial connection is closed."],
    restarting: ["Restarting", "Waiting for panel restart", "USB is temporarily disconnected. When the panel returns, choose Detect panel manually."],
    error: ["Error", "Panel action failed", panel?.error || "See the error below."],
  }[state] || [state, "Working…", "Please wait."];
}

function render() {
  if (!panel) return;
  const [label, title, detail] = stateText(panel.state);
  const pill = $("#connection-pill");
  pill.textContent = label;
  pill.className = `connection-pill ${panel.state}`;
  $("#action-title").textContent = title;
  $("#action-detail").textContent = detail;
  $("#device-path").textContent = panel.path || "Not detected";
  $("#device-model").textContent = panel.model || "—";
  $("#device-firmware").textContent = panel.firmware || "—";
  $("#device-resolution").textContent = panel.width && panel.height ? `${panel.width} × ${panel.height}` : "—";
  if (Number.isInteger(panel.brightness) && !brightnessDirty) {
    $("#brightness").value = panel.brightness;
    $("#brightness-value").textContent = `${panel.brightness}%`;
  }
  const active = ["starting", "streaming"].includes(panel.state);
  const restarting = panel.state === "restarting";
  const known = Boolean(panel.path);
  $("#detect-panel").disabled = active;
  $("#start-display").disabled = active || restarting || !known;
  $("#stop-display").disabled = !active;
  $("#apply-brightness").disabled = !known || panel.state === "starting" || restarting;
  $("#restore-default").disabled = panel.can_restore_default !== true;
  $("#layout-choice").disabled = active || restarting;
  const errorBox = $("#error-box");
  errorBox.hidden = !panel.error;
  errorBox.textContent = panel.error || "";
}

async function request(path, body = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Control-Token": token},
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (result.panel) panel = result.panel;
  render();
  if (!response.ok) throw new Error(result.error || "Panel action failed");
  return result;
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/panel/status");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not read panel status");
    token = result.token;
    panel = result.panel;
    render();
  } catch (error) {
    $("#action-title").textContent = "Control app unavailable";
    $("#action-detail").textContent = error.message;
  }
}

function updatePreview() {
  const layout = $("#layout-choice").value;
  $("#panel-preview").src = `/api/panel/preview?layout=${encodeURIComponent(layout)}&t=${Date.now()}`;
}

$("#brightness").addEventListener("input", event => {
  brightnessDirty = true;
  $("#brightness-value").textContent = `${event.target.value}%`;
});

$("#layout-choice").addEventListener("change", updatePreview);

$("#detect-panel").addEventListener("click", async () => {
  try {
    $("#action-title").textContent = "Detecting panel…";
    await request("/api/panel/detect");
    showToast("Supported panel detected");
  } catch (error) { showToast(error.message, true); }
});

$("#start-display").addEventListener("click", async () => {
  try {
    await request("/api/panel/start", {
      layout: $("#layout-choice").value,
      brightness: Number($("#brightness").value),
    });
    brightnessDirty = false;
    render();
    showToast("Display starting");
  } catch (error) { showToast(error.message, true); }
});

$("#stop-display").addEventListener("click", async () => {
  try {
    await request("/api/panel/stop");
    showToast("Display stopped and serial connection closed");
  } catch (error) { showToast(error.message, true); }
});

$("#restore-default").addEventListener("click", async () => {
  const confirmed = window.confirm(
    "Restart the hardware panel now? The panel will briefly restart, USB will temporarily disconnect, and the factory/default animation should return."
  );
  if (!confirmed) return;
  try {
    $("#action-title").textContent = "Restarting panel…";
    await request("/api/panel/restore-default", {confirmed: true});
    showToast("Panel restart sent once; wait for USB, then choose Detect panel");
  } catch (error) { showToast(error.message, true); }
});

$("#apply-brightness").addEventListener("click", async () => {
  try {
    const value = Number($("#brightness").value);
    await request("/api/panel/brightness", {brightness: value});
    brightnessDirty = false;
    render();
    showToast(`Brightness set to ${value}%`);
  } catch (error) { showToast(error.message, true); }
});

$("#exit-app").addEventListener("click", async () => {
  try {
    await request("/api/app/exit");
    clearInterval(polling);
    document.querySelectorAll("button, input, select").forEach(element => { element.disabled = true; });
    $("#connection-pill").textContent = "Closed";
    $("#connection-pill").className = "connection-pill stopped";
    $("#action-title").textContent = "Panel Control closed";
    $("#action-detail").textContent = "The stream is stopped and the serial connection is closed. You may close this tab.";
  } catch (error) { showToast(error.message, true); }
});

updatePreview();
refreshStatus();
polling = setInterval(refreshStatus, 750);
