import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch


# Load the acquisition module with fake hardware and without OpenCV installed.
cv2 = ModuleType("cv2")
cv2.error = RuntimeError
cv2.CAP_PROP_FRAME_WIDTH = 3
cv2.CAP_PROP_FRAME_HEIGHT = 4
cv2.CAP_PROP_FPS = 5
cv2.VideoCapture = MagicMock()
numpy = ModuleType("numpy")
numpy.ndarray = object
spec = importlib.util.spec_from_file_location("camera_under_test", Path(__file__).parents[1] / "app/camera.py")
camera_module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = camera_module
with patch.dict(sys.modules, {"cv2": cv2, "numpy": numpy}):
    spec.loader.exec_module(camera_module)
Camera = camera_module.Camera
CameraSettings = camera_module.CameraSettings


class CameraTests(unittest.TestCase):
    def setUp(self):
        cv2.VideoCapture.reset_mock(side_effect=True)
        self.camera = Camera(CameraSettings())
        self.frame = MagicMock(size=100)
        self.frame.copy.return_value = self.frame

    def capture(self, working=True):
        capture = MagicMock()
        capture.isOpened.return_value = True
        capture.read.return_value = (working, self.frame if working else None)
        return capture

    def test_skips_devices_that_open_but_have_no_frames(self):
        bad, good = self.capture(False), self.capture()
        cv2.VideoCapture.side_effect = [bad, good]
        with patch.object(self.camera, "_candidates", return_value=["/dev/video0", "/dev/video2"]):
            self.assertTrue(self.camera._connect())
        bad.release.assert_called_once()
        self.assertEqual(self.camera.status()["camera_source"], "/dev/video2")
        self.assertIs(self.camera.read(), self.frame)

    def test_retries_when_no_camera_exists(self):
        def wait(_):
            self.camera._stop.set()
        with patch.object(self.camera, "_candidates", return_value=[]), patch.object(self.camera._stop, "wait", side_effect=wait) as retry:
            self.camera._read_loop()
        retry.assert_called_once_with(2.0)
        self.assertFalse(self.camera.is_open())
        self.assertIsNone(self.camera.read())

    def test_disconnect_clears_frame_and_releases_capture(self):
        capture = self.capture()
        cv2.VideoCapture.return_value = capture
        with patch.object(self.camera, "_candidates", return_value=[0]):
            self.camera._connect()
        capture.read.return_value = (False, None)
        def wait(_):
            self.assertIsNone(self.camera.read())
            self.camera._stop.set()
        with patch.object(self.camera._stop, "wait", side_effect=wait):
            self.camera._read_loop()
        capture.release.assert_called_once()
        self.assertEqual(self.camera.status()["camera_state"], "waiting")

    def test_replacement_changes_generation_and_source(self):
        cv2.VideoCapture.side_effect = [self.capture(), self.capture()]
        with patch.object(self.camera, "_candidates", return_value=["/dev/video0"]):
            self.camera._connect()
        generation = self.camera.snapshot()[1]
        self.camera._capture.release()
        self.camera._capture = None
        self.camera._clear_frame()
        with patch.object(self.camera, "_candidates", return_value=["/dev/video4"]):
            self.camera._connect()
        self.assertEqual(self.camera.snapshot()[1], generation + 1)
        self.assertEqual(self.camera.status()["camera_source"], "/dev/video4")

    def test_stale_frame_is_not_reported_as_online(self):
        self.camera._frame = self.frame
        self.camera._last_frame_at = 10.0
        with patch.object(camera_module.time, "monotonic", return_value=13.0):
            self.assertIsNone(self.camera.read())
            self.assertFalse(self.camera.is_open())
            self.assertEqual(self.camera.fps_estimate(), 0)

    def test_explicit_source_is_preserved(self):
        self.camera.settings.source = "/dev/v4l/by-id/lab-camera"
        self.assertEqual(self.camera._candidates(), ["/dev/v4l/by-id/lab-camera"])


if __name__ == "__main__":
    unittest.main()
