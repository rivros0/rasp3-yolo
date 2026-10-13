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
        self._last_annotated: np.ndarray | None = None
        self._last_inference_at = 0.0
        self._generation: int | None = None
        self._lock = threading.Lock()

    def class_names(self) -> dict[int, str]:
        return {int(k): str(v) for k, v in self.names.items()}

    def update_config(self, config: RuntimeConfig) -> RuntimeConfig:
        self.config = config
        return self.config

    def process(self, frame: np.ndarray, generation: int = 0) -> AnnotatedFrame:
        with self._lock:
            if self._generation != generation:
                self._last_result = None
                self._generation = generation
            return self._process(frame)

    def _process(self, frame: np.ndarray) -> AnnotatedFrame:
        now = time.time()
        should_infer = (
            self._last_result is None
            or now - self._last_inference_at >= self.config.inference_interval
        )

        if should_infer:
            self._last_result = self._detect(frame)
            self._last_inference_at = now

        annotated = frame.copy()
        result = self._last_result or self._empty_result(frame)
        self._draw(annotated, result.detections)
        self._last_annotated = annotated
        return AnnotatedFrame(image=annotated, result=result)

    def last_result(self, frame: np.ndarray | None = None, generation: int = 0) -> DetectionResponse:
        # Read the published result without waiting for a slow inference.
        result = self._last_result
        if result is not None and self._generation == generation:
            return result
        if frame is not None:
            return self._empty_result(frame)
        return DetectionResponse(timestamp=time.time(), width=0, height=0, detections=[])

    def _detect(self, frame: np.ndarray) -> DetectionResponse:
        height, width = frame.shape[:2]
        predictions = self.model.predict(frame, conf=self.config.confidence, verbose=False)
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
