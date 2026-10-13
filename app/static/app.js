const statusEl = document.querySelector("#status");
const detectionsEl = document.querySelector("#detections");
const confidenceEl = document.querySelector("#confidence");
const confidenceValueEl = document.querySelector("#confidenceValue");
const saveConfigEl = document.querySelector("#saveConfig");
const streamEl = document.querySelector("#stream");
const cameraMessageEl = document.querySelector("#cameraMessage");
let cameraGeneration = null;

function showCamera(connected, message = "Webcam non collegata") {
  streamEl.hidden = !connected;
  cameraMessageEl.hidden = connected;
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
  try {
    const [health, result] = await Promise.all([
      fetch("/api/health").then((response) => response.json()),
      fetch("/api/detections").then((response) => response.json()),
    ]);

    statusEl.textContent = health.ok
      ? `Online - ${health.fps_estimate} FPS`
      : "Webcam non collegata";
    statusEl.className = health.ok ? "status ok" : "status error";
    showCamera(health.ok);
    if (health.ok && cameraGeneration !== health.camera_generation) {
      cameraGeneration = health.camera_generation;
      streamEl.src = `/stream.mjpg?generation=${cameraGeneration}`;
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
  }
}

fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    confidenceEl.value = config.confidence;
    confidenceValueEl.textContent = Number(config.confidence).toFixed(2);
  });

setInterval(refresh, 1000);
refresh();
