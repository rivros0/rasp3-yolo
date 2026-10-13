import argparse
import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.camera import Camera, CameraSettings
from app.detector import YOLODetector, encode_jpeg
from app.schemas import DetectionResponse, HealthResponse, RuntimeConfig


class AppState:
    def __init__(self) -> None:
        self.config = RuntimeConfig()
        self.camera: Camera | None = None
        self.detector: YOLODetector | None = None
        self.model_path = "yolov8n.pt"


state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.camera.start()
    try:
        yield
    finally:
        state.camera.stop()


app = FastAPI(
    title="Raspberry Pi YOLO Lab",
    description="Webcam realtime e API didattiche per object detection con YOLO.",
    version="0.1.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (BASE_DIR / "templates" / "index.html").read_text(encoding="utf-8")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    camera = _camera()
    frame = camera.read()
    height, width = frame.shape[:2] if frame is not None else (0, 0)
    return HealthResponse(
        ok=camera.is_open() and frame is not None,
        camera_open=camera.is_open(),
        model=state.model_path,
        fps_estimate=camera.fps_estimate(),
        frame_width=width,
        frame_height=height,
        **camera.status(),
    )


@app.get("/api/classes")
def classes() -> dict[int, str]:
    return _detector().class_names()


@app.get("/api/config", response_model=RuntimeConfig)
def get_config() -> RuntimeConfig:
    return state.config


@app.post("/api/config", response_model=RuntimeConfig)
def update_config(config: RuntimeConfig) -> RuntimeConfig:
    state.config = _detector().update_config(config)
    return state.config


@app.get("/api/detections", response_model=DetectionResponse)
def detections() -> DetectionResponse:
    camera = _camera()
    frame, generation = camera.snapshot()
    if frame is None:
        return DetectionResponse(timestamp=time.time(), width=0, height=0, detections=[])
    return _detector().last_result(frame, generation)


@app.get("/api/frame.jpg")
def frame_jpg() -> Response:
    frame, generation = _camera().snapshot()
    if frame is None:
        raise HTTPException(status_code=503, detail="Webcam non collegata")
    annotated = _detector().process(frame, generation)
    current, current_generation = _camera().snapshot()
    if current is None or generation != current_generation:
        raise HTTPException(status_code=503, detail="Webcam scollegata durante l'elaborazione")
    return Response(content=encode_jpeg(annotated.image), media_type="image/jpeg")


@app.get("/stream.mjpg")
async def stream() -> StreamingResponse:
    offline_jpg = encode_jpeg(np.zeros((240, 320, 3), dtype=np.uint8))

    async def frames():
        while True:
            frame, generation = _camera().snapshot()
            if frame is not None:
                annotated = await asyncio.to_thread(_detector().process, frame, generation)
                current, current_generation = _camera().snapshot()
                jpg = encode_jpeg(annotated.image) if current is not None and generation == current_generation else offline_jpg
            else:
                jpg = offline_jpg
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpg
                + b"\r\n"
            )
            await asyncio.sleep(0.03)

    return StreamingResponse(
        frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


def _camera() -> Camera:
    if state.camera is None:
        raise HTTPException(status_code=503, detail="Camera non inizializzata")
    return state.camera


def _detector() -> YOLODetector:
    if state.detector is None:
        raise HTTPException(status_code=503, detail="Detector non inizializzato")
    return state.detector


def build_app(args: argparse.Namespace) -> FastAPI:
    state.model_path = args.model
    state.config = RuntimeConfig(
        confidence=args.confidence,
        inference_interval=args.inference_interval,
    )
    state.camera = Camera(
        CameraSettings(
            source=args.camera,
            width=args.width,
            height=args.height,
            fps=args.camera_fps,
        )
    )
    state.detector = YOLODetector(args.model, state.config)
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi YOLO Lab")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--camera", type=lambda value: int(value) if value.isdecimal() else value, default="auto", help="auto, indice o percorso webcam")
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=240)
    parser.add_argument("--camera-fps", type=int, default=15)
    parser.add_argument("--model", default="yolov8n.pt")
    parser.add_argument("--confidence", type=float, default=0.35)
    parser.add_argument("--inference-interval", type=float, default=0.25)
    return parser.parse_args()


def main() -> None:
    import uvicorn

    args = parse_args()
    build_app(args)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
