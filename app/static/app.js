const statusEl = document.querySelector("#status");
const detectionsEl = document.querySelector("#detections");
const confidenceEl = document.querySelector("#confidence");
const confidenceValueEl = document.querySelector("#confidenceValue");
const saveConfigEl = document.querySelector("#saveConfig");
const streamEl = document.querySelector("#stream");
const cameraMessageEl = document.querySelector("#cameraMessage");
let cameraGeneration = null;
const overlayEl = document.querySelector("#boxOverlay");
const svgNS = "http://www.w3.org/2000/svg";
let refreshing = false;

// Le coordinate delle API restano espresse nella risoluzione originale 320x240.
// SVG le ridisegna come grafica vettoriale a qualunque dimensione del browser.
function drawBoxes(result) {
  overlayEl.replaceChildren();
  if (!result.width || !result.height) {
    return;
  }
  overlayEl.setAttribute("viewBox", "0 0 " + result.width + " " + result.height);
  overlayEl.setAttribute("preserveAspectRatio", "none");
  for (const detection of result.detections) {
    const box = detection.box;
    const x = Math.max(0, box.x1);
    const y = Math.max(0, box.y1);
    const w = Math.max(0, box.x2 - box.x1);
    const h = Math.max(0, box.y2 - box.y1);
    if (w === 0 || h === 0) {
      continue;
    }
    const rectangle = document.createElementNS(svgNS, "rect");
    rectangle.setAttribute("x", x);
    rectangle.setAttribute("y", y);
    rectangle.setAttribute("width", w);
    rectangle.setAttribute("height", h);
    rectangle.setAttribute("stroke", "#42f5a7");
    rectangle.setAttribute("stroke-width", "2");
    rectangle.setAttribute("vector-effect", "non-scaling-stroke");
    rectangle.setAttribute("fill", "none");
    overlayEl.appendChild(rectangle);

    const label = detection.label + " " + Math.round(detection.confidence * 100) + "%";
    const labelWidth = Math.min(result.width, Math.max(36, label.length * 6.5 + 10));
    const labelHeight = 20;
    const labelX = Math.min(x, result.width - labelWidth);
    let labelY = y - labelHeight;
    if (labelY < 0) {
      labelY = Math.min(y + 2, result.height - labelHeight);
    }
    const background = document.createElementNS(svgNS, "rect");
    background.setAttribute("x", labelX);
    background.setAttribute("y", labelY);
    background.setAttribute("width", labelWidth);
    background.setAttribute("height", labelHeight);
    background.setAttribute("fill", "#42f5a7");
    overlayEl.appendChild(background);
    const text = document.createElementNS(svgNS, "text");
    text.setAttribute("x", labelX + 5);
    text.setAttribute("y", labelY + 14);
    text.setAttribute("font-size", "12");
    text.setAttribute("font-weight", "bold");
    text.setAttribute("font-family", "sans-serif");
    text.setAttribute("fill", "#10231b");
    text.textContent = label;
    overlayEl.appendChild(text);
  }
}

function showCamera(connected, message = "Webcam non collegata") {
  streamEl.hidden = !connected;
  cameraMessageEl.hidden = connected;
  overlayEl.hidden = !connected;
  if (!connected) {
    overlayEl.replaceChildren();
  }
  cameraMessageEl.textContent = message;
}

confidenceEl.addEventListener("input", () => {
  confidenceValueEl.textContent = Number(confidenceEl.value).toFixed(2);
});

saveConfigEl.addEventListener("click", async () => {
  const current = await fetch("/api/config").then((response) => response.json());
  current.confidence = Number(confidenceEl.value);

  await fetch("/api/config", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(current),
  });
});

async function refresh() {
  if (refreshing) {
    return;
  }
  refreshing = true;
  try {
    const [health, result] = await Promise.all([
      fetch("/api/health").then((response) => response.json()),
      fetch("/api/detections").then((response) => response.json()),
    ]);

    statusEl.textContent = health.ok
      ? `Video ${health.video_fps} FPS | YOLO ${health.inference_fps} FPS | ${health.inference_ms} ms`
      : "Webcam non collegata";
    statusEl.className = health.ok ? "status ok" : "status error";
    showCamera(health.ok);
    if (health.ok && cameraGeneration !== health.camera_generation) {
      cameraGeneration = health.camera_generation;
      streamEl.src = `/stream.mjpg?raw=true&generation=${cameraGeneration}`;
    }

    if (health.ok) {
      drawBoxes(result);
    }
    detectionsEl.innerHTML = "";
    if (result.detections.length === 0) {
      const item = document.createElement("li");
      item.textContent = "Nessun oggetto rilevato";
      detectionsEl.appendChild(item);
      return;
    }

    for (const detection of result.detections) {
      const item = document.createElement("li");
      const label = document.createElement("span");
      const score = document.createElement("strong");
      label.textContent = detection.label;
      score.textContent = detection.confidence.toFixed(2);
      item.append(label, score);
      detectionsEl.appendChild(item);
    }
  } catch (error) {
    statusEl.textContent = "Errore API";
    statusEl.className = "status error";
    showCamera(false, "Connessione al server non disponibile");
    detectionsEl.replaceChildren();
  } finally {
    refreshing = false;
  }
}

fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    confidenceEl.value = config.confidence;
    confidenceValueEl.textContent = Number(config.confidence).toFixed(2);
  });

setInterval(refresh, 250);
refresh();
