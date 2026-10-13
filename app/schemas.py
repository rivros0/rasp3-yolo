from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int


class Detection(BaseModel):
    class_id: int
    label: str
    confidence: float
    box: BoundingBox


class DetectionResponse(BaseModel):
    timestamp: float
    width: int
    height: int
    detections: list[Detection]


class RuntimeConfig(BaseModel):
    confidence: float = Field(default=0.35, ge=0.05, le=0.95)
    inference_interval: float = Field(default=0.25, ge=0.05, le=5.0)


class HealthResponse(BaseModel):
    ok: bool
    camera_open: bool
    model: str
    fps_estimate: float
    frame_width: int
    frame_height: int

