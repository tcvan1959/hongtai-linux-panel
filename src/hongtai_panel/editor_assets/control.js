"use strict";

let token = "";
let panel = null;
let polling = null;
let brightnessDirty = false;
let mediaFiles = [];

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
  const imageSelected = Boolean(panel.selected_image);
  const imageMode = $("#layout-choice").value === "image";
  $("#detect-panel").disabled = active;
  $("#start-display").disabled = active || restarting || !known || (imageMode && !imageSelected);
  $("#start-display").textContent = imageMode ? "Display image" : "Start display";
  $("#stop-display").disabled = !active;
  $("#apply-brightness").disabled = !known || panel.state === "starting" || restarting;
  $("#restore-default").disabled = panel.can_restore_default !== true;
  $("#layout-choice").disabled = active || restarting;
  $("#layout-choice").querySelector('option[value="image"]').disabled = !imageSelected;
  $("#refresh-media").disabled = active || restarting;
  $("#browse-image").disabled = active || restarting;
  $("#library-image").disabled = active || restarting || mediaFiles.length === 0;
  $("#select-library-image").disabled = active || restarting || !$("#library-image").value;
  $("#selected-image").textContent = imageSelected
    ? `${panel.selected_image} (${panel.selected_image_source})`
    : "None selected";
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

async function refreshMedia() {
  const response = await fetch("/api/media");
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not read private media folder");
  if (result.token) token = result.token;
  mediaFiles = result.media.files || [];
  const select = $("#library-image");
  const prior = select.value;
  select.replaceChildren();
  if (mediaFiles.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No local images found";
    select.append(option);
  } else {
    for (const name of mediaFiles) {
      const option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      select.append(option);
    }
    if (mediaFiles.includes(prior)) select.value = prior;
  }
  render();
}

function updatePreview() {
  const layout = $("#layout-choice").value;
  if (layout === "image" && !panel?.selected_image) return;
  $("#panel-preview").src = `/api/panel/preview?layout=${encodeURIComponent(layout)}&t=${Date.now()}`;
}

$("#brightness").addEventListener("input", event => {
  brightnessDirty = true;
  $("#brightness-value").textContent = `${event.target.value}%`;
});

$("#layout-choice").addEventListener("change", () => {
  render();
  updatePreview();
});

$("#library-image").addEventListener("change", render);

$("#refresh-media").addEventListener("click", async () => {
  try {
    await refreshMedia();
    showToast("Private media folder refreshed");
  } catch (error) { showToast(error.message, true); }
});

$("#select-library-image").addEventListener("click", async () => {
  try {
    const name = $("#library-image").value;
    if (!name) throw new Error("Choose an image from the private folder");
    await request("/api/media/select", {name});
    $("#layout-choice").value = "image";
    render();
    updatePreview();
    showToast("Private image selected; choose Display image when ready");
  } catch (error) { showToast(error.message, true); }
});

$("#browse-image").addEventListener("click", () => $("#image-file").click());

$("#image-file").addEventListener("change", async event => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    const response = await fetch("/api/media/upload", {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-Control-Token": token,
        "X-Media-Name": encodeURIComponent(file.name),
      },
      body: file,
    });
    const result = await response.json();
    if (result.panel) panel = result.panel;
    if (!response.ok) throw new Error(result.error || "Could not select image");
    $("#layout-choice").value = "image";
    render();
    updatePreview();
    showToast("Image selected in memory; choose Display image when ready");
  } catch (error) { showToast(error.message, true); }
  finally { event.target.value = ""; }
});

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
refreshStatus().then(refreshMedia).catch(error => showToast(error.message, true));
polling = setInterval(refreshStatus, 750);
