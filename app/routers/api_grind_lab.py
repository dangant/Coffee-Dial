import asyncio

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services.grind_analysis_service import AnalysisParams, analyze_image

router = APIRouter(prefix="/api/v1/grind-lab", tags=["grind-lab"])

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/analyze")
async def analyze_grind(
    image: UploadFile = File(...),
    threshold: float = Form(58.8),
    pixel_scale: float = Form(0.0),
    max_cluster_axis: int = Form(500),
    min_surface: int = Form(4),
    min_roundness: float = Form(0.0),
    max_dimension: int = Form(2000),
):
    if image.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {image.content_type}")

    image_bytes = await image.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(400, "File too large (max 20 MB)")

    params = AnalysisParams(
        threshold=threshold,
        pixel_scale=pixel_scale,
        max_cluster_axis=max_cluster_axis,
        min_surface=min_surface,
        min_roundness=min_roundness,
        max_dimension=max_dimension,
    )

    result = await asyncio.to_thread(analyze_image, image_bytes, params)

    return {
        "particle_count": result.particle_count,
        "avg_diameter_px": result.avg_diameter_px,
        "std_diameter_px": result.std_diameter_px,
        "avg_diameter_mm": result.avg_diameter_mm,
        "std_diameter_mm": result.std_diameter_mm,
        "threshold_image": result.threshold_image_b64,
        "cluster_image": result.cluster_image_b64,
        "histogram": result.histogram_data,
        "csv": result.csv_string,
    }
