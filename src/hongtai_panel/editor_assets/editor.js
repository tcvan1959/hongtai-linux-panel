"use strict";

const SCALE = 1.25;
const METRICS = ["cpu_percent", "cpu_temp_c", "memory_percent", "memory_used_gib", "memory_total_gib", "gpu_name", "gpu_percent", "gpu_temp_c", "gpu_memory_used_gib", "gpu_memory_total_gib"];
const SAMPLE = {cpu_percent: "42%", cpu_temp_c: "51°C", memory_percent: "37%", memory_used_gib: "11.8 GiB", memory_total_gib: "31.2 GiB", gpu_name: "AMD Radeon", gpu_percent: "18%", gpu_temp_c: "44°C", gpu_memory_used_gib: "0.4 GiB", gpu_memory_total_gib: "0.5 GiB"};
const canvas = document.querySelector("#canvas");
const form = document.querySelector("#properties");
const status = document.querySelector("#status");
const saveButton = document.querySelector("#save");
let layout = null;
let token = "";
let selected = -1;
let dirty = false;
let gesture = null;

const esc = value => String(value ?? "").replace(/[&<>"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[ch]));
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

function setDirty(value = true) {
  dirty = value;
  saveButton.disabled = !value;
  status.textContent = value ? "Unsaved changes" : "All changes saved";
  status.className = `status ${value ? "dirty" : "saved"}`;
}

function previewText(widget) {
  if (widget.kind === "label") return widget.text || "Text";
  if (widget.kind === "clock") return "12:47:09";
  if (widget.kind === "value") return SAMPLE[widget.source] || widget.missing || "--";
  return "";
}

function draw() {
  if (!layout) return;
  canvas.style.width = `${layout.width * SCALE}px`;
  canvas.style.height = `${layout.height * SCALE}px`;
  canvas.style.background = layout.background;
  canvas.replaceChildren();
  layout.widgets.forEach((widget, index) => {
    const element = document.createElement("div");
    element.className = `widget ${widget.kind} ${["label","clock","value"].includes(widget.kind) ? "textual" : ""} ${index === selected ? "selected" : ""}`;
    element.dataset.index = index;
    element.style.cssText = `left:${widget.x*SCALE}px;top:${widget.y*SCALE}px;width:${widget.width*SCALE}px;height:${widget.height*SCALE}px;z-index:${index+1}`;
    const content = document.createElement("div");
    content.className = "content";
    if (widget.kind === "panel") {
      content.style.background = widget.fill || "transparent";
      content.style.borderColor = widget.outline || "transparent";
      content.style.borderWidth = `${(widget.stroke_width || 0)*SCALE}px`;
      content.style.borderRadius = `${(widget.radius || 0)*SCALE}px`;
    } else if (["label","clock","value"].includes(widget.kind)) {
      content.textContent = previewText(widget);
      content.style.color = widget.color || "#f8fafc";
      content.style.fontSize = `${(widget.font_size || 16)*SCALE}px`;
      content.style.fontWeight = widget.bold ? "700" : "400";
      content.style.justifyContent = {left:"flex-start",center:"center",right:"flex-end"}[widget.align || "left"];
    } else if (widget.kind === "progress") {
      content.style.background = widget.fill || "#263449";
      content.style.borderRadius = `${(widget.radius || 0)*SCALE}px`;
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.style.background = widget.color || "#22d3ee";
      bar.style.borderRadius = "inherit";
      content.append(bar);
    } else if (widget.kind === "image") {
      content.textContent = widget.path ? `IMAGE · ${widget.path.split("/").pop()}` : "IMAGE";
    }
    element.append(content);
    if (index === selected) {
      const handle = document.createElement("div");
      handle.className = "resize";
      element.append(handle);
    }
    canvas.append(element);
  });
  document.querySelector("#widget-count").textContent = `${layout.widgets.length} widget${layout.widgets.length === 1 ? "" : "s"}`;
}

function field(name, label, type = "text", options = null, wide = false) {
  const widget = layout.widgets[selected];
  let input;
  if (options) {
    input = `<select data-field="${name}">${options.map(value => `<option value="${esc(value)}" ${widget[name] === value ? "selected" : ""}>${esc(value)}</option>`).join("")}</select>`;
  } else if (type === "checkbox") {
    return `<label class="check ${wide ? "wide" : ""}"><input data-field="${name}" type="checkbox" ${widget[name] ? "checked" : ""}> ${label}</label>`;
  } else {
    input = `<input data-field="${name}" type="${type}" value="${esc(widget[name] ?? "")}">`;
  }
  return `<label class="${wide ? "wide" : ""}">${label}${input}</label>`;
}

function inspect() {
  const has = selected >= 0 && selected < (layout?.widgets.length || 0);
  document.querySelector("#empty-inspector").hidden = has;
  form.hidden = !has;
  document.querySelector("#delete").disabled = !has;
  document.querySelector("#duplicate").disabled = !has;
  if (!has) {
    document.querySelector("#selection-title").textContent = "Nothing selected";
    return;
  }
  const widget = layout.widgets[selected];
  document.querySelector("#selection-title").textContent = widget.kind[0].toUpperCase() + widget.kind.slice(1);
  let html = `<div class="section">POSITION & SIZE</div>${field("x","X","number")}${field("y","Y","number")}${field("width","Width","number")}${field("height","Height","number")}`;
  html += `<div class="section">ALIGN TO DISPLAY</div><div class="action-grid align"><button type="button" data-action="align-left">Left</button><button type="button" data-action="align-center-x">Center</button><button type="button" data-action="align-right">Right</button><button type="button" data-action="align-top">Top</button><button type="button" data-action="align-center-y">Middle</button><button type="button" data-action="align-bottom">Bottom</button></div>`;
  html += `<div class="section">LAYER ORDER</div><div class="action-grid"><button type="button" data-action="send-back" ${selected === 0 ? "disabled" : ""}>Send to back</button><button type="button" data-action="bring-front" ${selected === layout.widgets.length - 1 ? "disabled" : ""}>Bring to front</button><button type="button" data-action="move-back" ${selected === 0 ? "disabled" : ""}>One step back</button><button type="button" data-action="move-forward" ${selected === layout.widgets.length - 1 ? "disabled" : ""}>One step forward</button></div>`;
  if (widget.kind === "label") html += `<div class="section">CONTENT</div>${field("text","Text","text",null,true)}`;
  if (widget.kind === "clock") html += `<div class="section">CONTENT</div>${field("format","Time format","text",null,true)}`;
  if (["value","progress"].includes(widget.kind)) html += `<div class="section">SENSOR</div>${field("source","Metric","text",METRICS,true)}`;
  if (widget.kind === "value") html += `${field("format","Number format","text",null,true)}${field("missing","When unavailable","text",null,true)}`;
  if (widget.kind === "image") html += `<div class="section">IMAGE</div>${field("path","File path","text",null,true)}${field("fit","Fitting","text",["contain","cover","stretch"],true)}`;
  if (["label","clock","value"].includes(widget.kind)) html += `<div class="section">TEXT STYLE</div>${field("font_size","Size","number")}${field("color","Color","color")}${field("align","Alignment","text",["left","center","right"],true)}${field("bold","Bold text","checkbox",null,true)}`;
  if (["panel","progress"].includes(widget.kind)) html += `<div class="section">APPEARANCE</div>${field("fill","Background","color")}${field("radius","Corner radius","number")}`;
  if (widget.kind === "panel") html += `${field("outline","Outline","color")}${field("stroke_width","Outline width","number")}`;
  if (widget.kind === "progress") html += `${field("color","Bar color","color")}${field("minimum","Minimum","number")}${field("maximum","Maximum","number")}`;
  form.innerHTML = html;
}

function select(index) {
  selected = index;
  draw();
  inspect();
}

function normalizeGeometry(widget) {
  widget.width = Math.max(1, Math.min(layout.width, Math.round(number(widget.width, 1))));
  widget.height = Math.max(1, Math.min(layout.height, Math.round(number(widget.height, 1))));
  widget.x = Math.max(0, Math.min(layout.width - widget.width, Math.round(number(widget.x))));
  widget.y = Math.max(0, Math.min(layout.height - widget.height, Math.round(number(widget.y))));
}

function addWidget(kind) {
  const base = {kind, x: 24, y: 24, width: 160, height: 40};
  const specialized = {
    panel: {width: 200, height: 100, fill: "#111827", outline: "#263449", radius: 10, stroke_width: 1},
    label: {text: "New text", font_size: 18, bold: false, color: "#f8fafc", align: "left"},
    clock: {format: "%H:%M:%S", font_size: 24, bold: true, color: "#67e8f9", align: "left"},
    value: {source: "cpu_percent", format: "{value:.0f}%", missing: "--", font_size: 24, bold: true, color: "#f8fafc", align: "left"},
    progress: {width: 200, height: 18, source: "cpu_percent", fill: "#263449", color: "#22d3ee", radius: 7, minimum: 0, maximum: 100},
    image: {width: 200, height: 120, path: "image.png", fit: "contain"}
  };
  layout.widgets.push({...base, ...specialized[kind]});
  select(layout.widgets.length - 1);
  setDirty();
}

canvas.addEventListener("pointerdown", event => {
  const element = event.target.closest(".widget");
  if (!element) { select(-1); return; }
  const index = Number(element.dataset.index);
  if (index !== selected) select(index);
  const widget = layout.widgets[index];
  gesture = {index, resize: event.target.classList.contains("resize"), startX: event.clientX, startY: event.clientY, x: widget.x, y: widget.y, width: widget.width, height: widget.height};
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointermove", event => {
  if (!gesture) return;
  const widget = layout.widgets[gesture.index];
  const dx = (event.clientX - gesture.startX) / SCALE;
  const dy = (event.clientY - gesture.startY) / SCALE;
  if (gesture.resize) { widget.width = gesture.width + dx; widget.height = gesture.height + dy; }
  else { widget.x = gesture.x + dx; widget.y = gesture.y + dy; }
  normalizeGeometry(widget);
  draw();
  inspect();
  setDirty();
});

canvas.addEventListener("pointerup", () => { gesture = null; });
canvas.addEventListener("pointercancel", () => { gesture = null; });

form.addEventListener("input", event => {
  const input = event.target.closest("[data-field]");
  if (!input || selected < 0) return;
  const fieldName = input.dataset.field;
  const numeric = ["x","y","width","height","font_size","radius","stroke_width","minimum","maximum"].includes(fieldName);
  layout.widgets[selected][fieldName] = input.type === "checkbox" ? input.checked : numeric ? number(input.value) : input.value;
  normalizeGeometry(layout.widgets[selected]);
  draw();
  setDirty();
});

form.addEventListener("click", event => {
  const button = event.target.closest("button[data-action]");
  if (!button || selected < 0) return;
  const action = button.dataset.action;
  const widget = layout.widgets[selected];
  if (action === "align-left") widget.x = 0;
  if (action === "align-center-x") widget.x = Math.round((layout.width - widget.width) / 2);
  if (action === "align-right") widget.x = layout.width - widget.width;
  if (action === "align-top") widget.y = 0;
  if (action === "align-center-y") widget.y = Math.round((layout.height - widget.height) / 2);
  if (action === "align-bottom") widget.y = layout.height - widget.height;
  if (["send-back", "bring-front", "move-back", "move-forward"].includes(action)) {
    const target = action === "send-back" ? 0 : action === "bring-front" ? layout.widgets.length - 1 : action === "move-back" ? selected - 1 : selected + 1;
    const [moved] = layout.widgets.splice(selected, 1);
    layout.widgets.splice(target, 0, moved);
    selected = target;
  }
  normalizeGeometry(layout.widgets[selected]);
  draw(); inspect(); setDirty();
});

document.querySelector("#palette").addEventListener("click", event => {
  const button = event.target.closest("button[data-kind]");
  if (button) addWidget(button.dataset.kind);
});

document.querySelector("#delete").addEventListener("click", () => {
  if (selected < 0) return;
  layout.widgets.splice(selected, 1);
  select(-1);
  setDirty();
});

document.querySelector("#duplicate").addEventListener("click", () => {
  if (selected < 0) return;
  const copy = structuredClone(layout.widgets[selected]);
  copy.x += 8; copy.y += 8; normalizeGeometry(copy);
  layout.widgets.push(copy);
  select(layout.widgets.length - 1);
  setDirty();
});

document.querySelector("#layout-name").addEventListener("input", event => { layout.name = event.target.value; setDirty(); });
document.querySelector("#layout-background").addEventListener("input", event => { layout.background = event.target.value; draw(); setDirty(); });

window.addEventListener("keydown", event => {
  if (selected < 0 || !["ArrowLeft","ArrowRight","ArrowUp","ArrowDown"].includes(event.key) || ["INPUT","SELECT"].includes(document.activeElement.tagName)) return;
  event.preventDefault();
  const step = event.shiftKey ? 10 : 1;
  const widget = layout.widgets[selected];
  if (event.key === "ArrowLeft") widget.x -= step;
  if (event.key === "ArrowRight") widget.x += step;
  if (event.key === "ArrowUp") widget.y -= step;
  if (event.key === "ArrowDown") widget.y += step;
  normalizeGeometry(widget); draw(); inspect(); setDirty();
});

function showToast(message, error = false) {
  const toast = document.querySelector("#toast");
  toast.textContent = message;
  toast.className = `toast show ${error ? "error" : ""}`;
  setTimeout(() => { toast.className = "toast"; }, 2600);
}

saveButton.addEventListener("click", async () => {
  saveButton.disabled = true;
  status.textContent = "Validating and saving…";
  try {
    const response = await fetch("/api/layout", {method: "PUT", headers: {"Content-Type":"application/json", "X-Editor-Token":token}, body: JSON.stringify(layout)});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Save failed");
    layout = result.layout;
    setDirty(false);
    showToast("Layout saved safely");
  } catch (error) {
    status.textContent = "Could not save";
    status.className = "status dirty";
    saveButton.disabled = false;
    showToast(error.message, true);
  }
});

async function start() {
  try {
    const response = await fetch("/api/layout");
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Could not load layout");
    layout = result.layout;
    token = result.token;
    document.querySelector("#layout-name").value = layout.name;
    document.querySelector("#layout-background").value = layout.background;
    document.querySelector("#dimensions").textContent = `${layout.width} × ${layout.height}`;
    draw(); inspect(); setDirty(false);
  } catch (error) {
    status.textContent = error.message;
    status.className = "status dirty";
    showToast(error.message, true);
  }
}

start();
