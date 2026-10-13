import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class CameraSettings:
    source: int | str = "auto"
    width: int = 320
    height: int = 240
    fps: int = 15
    retry_interval: float = 2.0
    stale_timeout: float = 2.0


class Camera:
    def __init__(self, settings: CameraSettings):
        self.settings = settings
        self._capture: cv2.VideoCapture | None = None
        self._frame: np.ndarray | None = None
        self._lock = threading.Lock()
        self._running = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._frames_seen = 0
        self._started_at = time.monotonic()
        self._last_frame_at = 0.0
        self._source: int | str | None = None
        self._generation = 0

    def start(self) -> None:
        if self._running.is_set():
            return

        if self._thread and self._thread.is_alive():
            raise RuntimeError("Acquisizione precedente ancora in arresto")
        self._stop.clear()
        self._running.set()
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running.clear()
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._clear_frame()

    def is_open(self) -> bool:
        with self._lock:
            return self._fresh()

    def _fresh(self) -> bool:
        return self._frame is not None and time.monotonic() - self._last_frame_at < self.settings.stale_timeout

    def snapshot(self) -> tuple[np.ndarray | None, int]:
        with self._lock:
            return (self._frame.copy() if self._fresh() else None, self._generation)

    def status(self) -> dict:
        with self._lock:
            fresh = self._fresh()
            return {
                "camera_state": "connected" if fresh else "waiting",
                "camera_source": str(self._source) if fresh else None,
                "camera_generation": self._generation,
            }

    def read(self) -> np.ndarray | None:
        return self.snapshot()[0]

    def fps_estimate(self) -> float:
        with self._lock:
            if not self._fresh():
                return 0.0
            elapsed = max(time.monotonic() - self._started_at, 0.001)
            return round(self._frames_seen / elapsed, 2)

    def _clear_frame(self) -> None:
        with self._lock:
            self._frame = None
            self._source = None
            self._frames_seen = 0

    def _candidates(self) -> list[int | str]:
        if self.settings.source != "auto":
            return [self.settings.source]
        # Probe real Linux devices, including capture nodes after video0.
        return [str(path) for path in sorted(Path("/dev").glob("video[0-9]*"), key=lambda path: int(path.name[5:]))]

    def _connect(self) -> bool:
        for source in self._candidates():
            if self._stop.is_set():
                break
            capture = None
            try:
                capture = cv2.VideoCapture(source)
                if not capture.isOpened():
                    continue
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.settings.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.settings.height)
                capture.set(cv2.CAP_PROP_FPS, self.settings.fps)
                ok, frame = capture.read()
                if not ok or frame is None or frame.size == 0 or self._stop.is_set():
                    continue
                self._capture = capture
                with self._lock:
                    self._generation += 1
                    self._source = source
                    self._frame = frame
                    self._started_at = self._last_frame_at = time.monotonic()
                    self._frames_seen = 1
                return True
            except cv2.error:
                pass
            finally:
                if capture is not None and capture is not self._capture:
                    capture.release()
        return False

    def _read_loop(self) -> None:
        try:
            while not self._stop.is_set():
                if self._capture is None:
                    if not self._connect():
                        self._stop.wait(self.settings.retry_interval)
                    continue
                try:
                    ok, frame = self._capture.read()
                except cv2.error:
                    ok, frame = False, None
                if not ok or frame is None or frame.size == 0:
                    self._clear_frame()
                    self._capture.release()
                    self._capture = None
                    self._stop.wait(self.settings.retry_interval)
                    continue
                with self._lock:
                    self._frame = frame
                    self._last_frame_at = time.monotonic()
                    self._frames_seen += 1
        finally:
            if self._capture is not None:
                self._capture.release()
                self._capture = None
            self._clear_frame()
            self._running.clear()
