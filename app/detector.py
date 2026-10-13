import time
import threading
from dataclasses import dataclass

import cv2
import numpy as np

from app.schemas import BoundingBox, Detection, DetectionResponse, RuntimeConfig


@dataclass
class AnnotatedFrame:
    image: np.ndarray
    result: DetectionResponse


class YOLODetector:
    def __init__(self, model_path: str, config: RuntimeConfig):
        from ultralytics import YOLO

        self.model_path = model_path
        self.config = config
        self.model = YOLO(model_path)
        self.names = self.model.names
        self._last_result: DetectionResponse | None = None
        self._generation: int | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._inference_ms = 0.0
        self._completed_at = 0.0
        self._inference_fps = 0.0
        self._error: str | None = None

    def start(self, camera) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(camera,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self, camera) -> None:
        while not self._stop.is_set():
            frame, generation = camera.snapshot()
            if frame is None:
                with self._lock:
                    self._last_result = None
                    self._inference_fps = 0.0
                    self._completed_at = 0.0
                self._stop.wait(0.1)
                continue
            started = time.monotonic()
            try:
                result = self._detect(frame)
                current, current_generation = camera.snapshot()
                if current is not None and current_generation == generation:
                    completed = time.monotonic()
                    with self._lock:
                        same_session = self._generation == generation
                        self._inference_fps = (1 / (completed - self._completed_at)
                                               if same_session and self._completed_at else 0.0)
                        self._generation = generation
                        self._last_result = result
                        self._inference_ms = (completed - started) * 1000
                        self._completed_at = completed
                        self._error = None
            except Exception as error:
                with self._lock:
                    self._last_result = None
                    self._error = str(error)
                    self._inference_fps = 0.0
                    self._completed_at = 0.0
                self._stop.wait(1.0)
            remaining = self.config.inference_interval - (time.monotonic() - started)
            self._stop.wait(max(0.01, remaining))

    def metrics(self, generation: int, connected: bool) -> dict:
        with self._lock:
            valid = connected and self._generation == generation
            return {
                "inference_fps": round(self._inference_fps, 2) if valid else 0.0,
                "inference_ms": round(self._inference_ms, 1) if valid else 0.0,
                "detection_age_ms": round((time.monotonic() - self._completed_at) * 1000, 1)
                if valid and self._completed_at else None,
                "inference_error": self._error,
            }

    def class_names(self) -> dict[int, str]:
        return {int(k): str(v) for k, v in self.names.items()}

    def update_config(self, config: RuntimeConfig) -> RuntimeConfig:
        self.config = config
        return self.config

    def process(self, frame: np.ndarray, generation: int = 0) -> AnnotatedFrame:
        annotated = frame.copy()
        result = self.last_result(frame, generation)
        self._draw(annotated, result.detections)
        return AnnotatedFrame(image=annotated, result=result)

    def last_result(self, frame: np.ndarray | None = None, generation: int = 0) -> DetectionResponse:
        with self._lock:
            result = self._last_result
            if result is not None and self._generation == generation:
                return result
        if frame is not None:
            return self._empty_result(frame)
        return DetectionResponse(timestamp=time.time(), width=0, height=0, detections=[])

    def _detect(self, frame: np.ndarray) -> DetectionResponse:
        height, width = frame.shape[:2]
        predictions = self.model.predict(frame, conf=self.config.confidence, imgsz=320, device="cpu", verbose=False)
        detections: list[Detection] = []

        if predictions:
            boxes = predictions[0].boxes
            for box in boxes:
                xyxy = box.xyxy[0].cpu().numpy().astype(int)
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())
                detections.append(
                    Detection(
                        class_id=class_id,
                        label=str(self.names.get(class_id, class_id)),
                        confidence=round(confidence, 4),
                        box=BoundingBox(
                            x1=max(0, int(xyxy[0])),
                            y1=max(0, int(xyxy[1])),
                            x2=min(width, int(xyxy[2])),
                            y2=min(height, int(xyxy[3])),
                        ),
                    )
                )

        return DetectionResponse(
            timestamp=time.time(),
            width=width,
            height=height,
            detections=detections,
        )

    def _empty_result(self, frame: np.ndarray) -> DetectionResponse:
        height, width = frame.shape[:2]
        return DetectionResponse(timestamp=time.time(), width=width, height=height, detections=[])

    def _draw(self, frame: np.ndarray, detections: list[Detection]) -> None:
        for detection in detections:
            box = detection.box
            label = f"{detection.label} {detection.confidence:.2f}"
            cv2.rectangle(frame, (box.x1, box.y1), (box.x2, box.y2), (0, 255, 80), 2)
            cv2.putText(
                frame,
                label,
                (box.x1, max(20, box.y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 80),
                2,
                cv2.LINE_AA,
            )


def encode_jpeg(frame: np.ndarray, quality: int = 80) -> bytes:
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("Impossibile codificare il frame JPEG")
    return encoded.tobytes()
