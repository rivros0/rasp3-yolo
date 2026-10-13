import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class CameraSettings:
    source: int | str = 0
    width: int = 320
    height: int = 240
    fps: int = 15


class Camera:
    def __init__(self, settings: CameraSettings):
        self.settings = settings
        self._capture: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._frames_seen = 0
        self._started_at = time.time()

    def start(self) -> None:
        if self._running.is_set():
            return

        self._capture = cv2.VideoCapture(self.settings.source)
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
        self._capture.set(cv2.CAP_PROP_FPS, self.settings.fps)

        self._running.set()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        if self._thread:
            self._thread.join(timeout=2)
        if self._capture:
            self._capture.release()

    def is_open(self) -> bool:
        return bool(self._capture and self._capture.isOpened())

    def read(self) -> np.ndarray | None:
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def fps_estimate(self) -> float:
        elapsed = max(time.time() - self._started_at, 0.001)
        return round(self._frames_seen / elapsed, 2)

    def _read_loop(self) -> None:
        while self._running.is_set():
            if not self._capture:
                time.sleep(0.1)
                continue

            ok, frame = self._capture.read()
            if not ok:
                time.sleep(0.1)
                continue

            with self._lock:
                self._frame = frame
                self._frames_seen += 1

