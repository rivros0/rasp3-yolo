import importlib.util
import sys
import threading
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, patch


cv2 = ModuleType("cv2")
numpy = ModuleType("numpy")
numpy.ndarray = object
schemas = ModuleType("app.schemas")
for name in ("BoundingBox", "Detection", "DetectionResponse", "RuntimeConfig"):
    setattr(schemas, name, SimpleNamespace)
spec = importlib.util.spec_from_file_location("detector_under_test", Path(__file__).parents[1] / "app/detector.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
with patch.dict(sys.modules, {"cv2": cv2, "numpy": numpy, "app.schemas": schemas}):
    spec.loader.exec_module(module)


class DetectorTests(unittest.TestCase):
    def setUp(self):
        ultralytics = ModuleType("ultralytics")
        ultralytics.YOLO = MagicMock()
        with patch.dict(sys.modules, {"ultralytics": ultralytics}):
            self.detector = module.YOLODetector("fake.pt", SimpleNamespace(confidence=0.35, inference_interval=0.01))
        self.frame = MagicMock(shape=(240, 320, 3))
        self.detector._draw = MagicMock()
        self.camera = MagicMock()
        self.camera.snapshot.return_value = (self.frame, 1)

    def test_slow_inference_does_not_block_annotation(self):
        started, finish = threading.Event(), threading.Event()
        def detect(frame):
            started.set()
            finish.wait(2)
            return SimpleNamespace(detections=[])
        self.detector._detect = detect
        self.detector.start(self.camera)
        try:
            self.assertTrue(started.wait(1))
            annotated = self.detector.process(self.frame, 1)
            self.assertEqual(annotated.result.detections, [])
            self.assertFalse(finish.is_set())
        finally:
            self.detector._stop.set()
            finish.set()
            self.detector.stop()

    def test_result_from_replaced_camera_is_discarded(self):
        def detect(frame):
            self.camera.snapshot.return_value = (self.frame, 2)
            self.detector._stop.set()
            return SimpleNamespace(detections=["old-camera"])
        self.detector._detect = detect
        self.detector._run(self.camera)
        self.assertIsNone(self.detector._last_result)
        self.assertEqual(self.detector.last_result(self.frame, 2).detections, [])

    def test_worker_reads_latest_frame_after_previous_inference(self):
        newest = MagicMock(shape=(240, 320, 3))
        received = []
        def detect(frame):
            received.append(frame)
            self.camera.snapshot.return_value = (newest, 1)
            if len(received) == 2:
                self.detector._stop.set()
            return SimpleNamespace(detections=[])
        self.detector._detect = detect
        self.detector._run(self.camera)
        self.assertEqual(received, [self.frame, newest])
        self.assertGreater(self.detector.metrics(1, True)["inference_fps"], 0)

    def test_model_receives_small_cpu_input(self):
        self.detector.model.predict.return_value = []
        self.detector._detect(self.frame)
        self.detector.model.predict.assert_called_once_with(self.frame, conf=0.35, imgsz=320, device="cpu", verbose=False)


if __name__ == "__main__":
    unittest.main()
