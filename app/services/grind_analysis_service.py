"""Coffee grind particle size analysis service.

Analyzes photos of coffee grounds on a white/light background to detect
individual particles and compute size distribution statistics. Algorithm
inspired by coffeegrindsize (https://github.com/csatt/coffeegrindsize).
"""

import base64
import csv
import io
import math
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from PIL import Image


@dataclass
class AnalysisParams:
    threshold: float = 58.8  # percentage (0-100) — darkness threshold
    pixel_scale: float = 0.0  # mm per pixel (0 = report in pixels only)
    max_cluster_axis: int = 500  # max long axis in pixels before discarding
    min_surface: int = 4  # minimum cluster area in pixels
    min_roundness: float = 0.0  # 0-1, filter out elongated shapes
    max_dimension: int = 2000  # auto-downscale images larger than this


@dataclass
class Particle:
    surface: int
    long_axis: float
    short_axis: float
    roundness: float
    diameter_px: float
    diameter_mm: float | None
    centroid: tuple[float, float]


@dataclass
class AnalysisResult:
    particle_count: int
    avg_diameter_px: float
    std_diameter_px: float
    avg_diameter_mm: float | None
    std_diameter_mm: float | None
    particles: list[Particle] = field(default_factory=list)
    threshold_image_b64: str = ""
    cluster_image_b64: str = ""
    histogram_data: dict = field(default_factory=dict)
    csv_string: str = ""


def analyze_image(image_bytes: bytes, params: AnalysisParams | None = None) -> AnalysisResult:
    """Main entry point: analyze a coffee grind image and return results."""
    if params is None:
        params = AnalysisParams()

    img, blue = _load_and_extract_blue_channel(image_bytes, params.max_dimension)
    width, height = img.size
    img_array = np.array(img)

    mask = _compute_threshold_mask(blue, params.threshold)
    threshold_b64 = _generate_threshold_image(img_array, mask)

    clusters = _find_clusters(mask, width, height, params)
    particles = [_compute_particle_geometry(c, params.pixel_scale) for c in clusters]

    cluster_b64 = _generate_cluster_image(img_array, clusters)

    diameters_px = [p.diameter_px for p in particles]
    avg_px = float(np.mean(diameters_px)) if diameters_px else 0.0
    std_px = float(np.std(diameters_px)) if diameters_px else 0.0

    avg_mm = None
    std_mm = None
    if params.pixel_scale > 0 and diameters_px:
        diameters_mm = [p.diameter_mm for p in particles]
        avg_mm = float(np.mean(diameters_mm))
        std_mm = float(np.std(diameters_mm))

    histogram_data = _build_histogram_data(particles, params.pixel_scale)
    csv_string = _build_csv(particles)

    return AnalysisResult(
        particle_count=len(particles),
        avg_diameter_px=round(avg_px, 2),
        std_diameter_px=round(std_px, 2),
        avg_diameter_mm=round(avg_mm, 2) if avg_mm is not None else None,
        std_diameter_mm=round(std_mm, 2) if std_mm is not None else None,
        particles=particles,
        threshold_image_b64=threshold_b64,
        cluster_image_b64=cluster_b64,
        histogram_data=histogram_data,
        csv_string=csv_string,
    )


def _load_and_extract_blue_channel(
    image_bytes: bytes, max_dim: int
) -> tuple[Image.Image, np.ndarray]:
    """Load image, downscale if needed, return PIL image and blue channel array."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    rgb = np.array(img)
    blue = rgb[:, :, 2]  # blue channel used for thresholding
    return img, blue


def _compute_threshold_mask(blue: np.ndarray, threshold_pct: float) -> np.ndarray:
    """Create boolean mask of dark (coffee) pixels.

    Uses the median of the blue channel as the background reference.
    Pixels darker than (median * threshold_pct / 100) are considered coffee.
    """
    background = float(np.median(blue))
    cutoff = background * threshold_pct / 100.0
    return blue < cutoff


def _generate_threshold_image(img_array: np.ndarray, mask: np.ndarray) -> str:
    """Overlay red on masked pixels, return base64 JPEG."""
    overlay = img_array.copy()
    overlay[mask] = [220, 50, 50]
    return _array_to_b64_jpeg(overlay)


def _flood_fill_cluster(
    mask: np.ndarray, visited: np.ndarray, start_y: int, start_x: int
) -> list[tuple[int, int]]:
    """BFS flood fill with 8-connectivity, returns list of (y, x) pixel coords."""
    height, width = mask.shape
    queue = deque()
    queue.append((start_y, start_x))
    visited[start_y, start_x] = True
    pixels = []

    while queue:
        y, x = queue.popleft()
        pixels.append((y, x))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < height and 0 <= nx < width and not visited[ny, nx] and mask[ny, nx]:
                    visited[ny, nx] = True
                    queue.append((ny, nx))

    return pixels


def _find_clusters(
    mask: np.ndarray, width: int, height: int, params: AnalysisParams
) -> list[list[tuple[int, int]]]:
    """Find all connected clusters of masked pixels, filtering by params."""
    visited = np.zeros_like(mask, dtype=bool)
    clusters = []
    edge_margin = 2

    for y in range(height):
        for x in range(width):
            if mask[y, x] and not visited[y, x]:
                pixels = _flood_fill_cluster(mask, visited, y, x)

                # Filter by minimum surface
                if len(pixels) < params.min_surface:
                    continue

                # Filter edge-touching clusters
                ys = [p[0] for p in pixels]
                xs = [p[1] for p in pixels]
                if min(ys) <= edge_margin or max(ys) >= height - edge_margin - 1:
                    continue
                if min(xs) <= edge_margin or max(xs) >= width - edge_margin - 1:
                    continue

                # Filter by max cluster axis
                long_axis = max(max(ys) - min(ys), max(xs) - min(xs))
                if long_axis > params.max_cluster_axis:
                    continue

                # Filter by roundness
                if params.min_roundness > 0:
                    short_axis = min(max(ys) - min(ys), max(xs) - min(xs))
                    roundness = (short_axis / long_axis) if long_axis > 0 else 1.0
                    if roundness < params.min_roundness:
                        continue

                clusters.append(pixels)

    return clusters


def _compute_particle_geometry(
    pixels: list[tuple[int, int]], pixel_scale: float
) -> Particle:
    """Compute geometry for a single particle cluster."""
    ys = [p[0] for p in pixels]
    xs = [p[1] for p in pixels]

    surface = len(pixels)
    cy = sum(ys) / len(ys)
    cx = sum(xs) / len(xs)

    span_y = max(ys) - min(ys) + 1
    span_x = max(xs) - min(xs) + 1
    long_axis = float(max(span_y, span_x))
    short_axis = float(min(span_y, span_x))
    roundness = (short_axis / long_axis) if long_axis > 0 else 1.0

    # Equivalent diameter: diameter of circle with same area
    diameter_px = 2.0 * math.sqrt(surface / math.pi)
    diameter_mm = diameter_px * pixel_scale if pixel_scale > 0 else None

    return Particle(
        surface=surface,
        long_axis=round(long_axis, 2),
        short_axis=round(short_axis, 2),
        roundness=round(roundness, 3),
        diameter_px=round(diameter_px, 2),
        diameter_mm=round(diameter_mm, 3) if diameter_mm is not None else None,
        centroid=(round(cx, 1), round(cy, 1)),
    )


def _generate_cluster_image(
    img_array: np.ndarray, clusters: list[list[tuple[int, int]]]
) -> str:
    """Draw colored outlines for each cluster on the original image."""
    overlay = img_array.copy()
    height, width = overlay.shape[:2]

    # Generate distinct colors for clusters
    rng = np.random.RandomState(42)
    colors = []
    for _ in range(max(len(clusters), 1)):
        colors.append(rng.randint(60, 255, size=3).tolist())

    for i, pixels in enumerate(clusters):
        color = colors[i % len(colors)]
        pixel_set = set(pixels)
        for y, x in pixels:
            # Check if this pixel is on the border of the cluster
            is_border = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    ny, nx = y + dy, x + dx
                    if (ny, nx) not in pixel_set:
                        is_border = True
                        break
                if is_border:
                    break
            if is_border:
                overlay[y, x] = color

    return _array_to_b64_jpeg(overlay)


def _build_histogram_data(particles: list[Particle], pixel_scale: float) -> dict:
    """Build histogram data for Chart.js (log-scale bins)."""
    if not particles:
        return {"labels": [], "counts": [], "mass_weighted": []}

    diameters = [p.diameter_px for p in particles]
    use_mm = pixel_scale > 0
    if use_mm:
        diameters = [p.diameter_mm for p in particles]

    d_min = max(min(diameters), 0.1)
    d_max = max(diameters)

    # Log-scale bins
    num_bins = min(30, max(10, int(math.sqrt(len(diameters)))))
    bin_edges = np.logspace(np.log10(d_min * 0.9), np.log10(d_max * 1.1), num_bins + 1)

    counts = [0] * num_bins
    mass_weighted = [0.0] * num_bins
    labels = []

    for i in range(num_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        unit = "mm" if use_mm else "px"
        labels.append(f"{lo:.1f}-{hi:.1f} {unit}")
        for d in diameters:
            if lo <= d < hi or (i == num_bins - 1 and d == hi):
                counts[i] += 1
                # Mass proportional to d^3
                mass_weighted[i] += d ** 3

    # Normalize mass-weighted to percentage
    total_mass = sum(mass_weighted) if sum(mass_weighted) > 0 else 1
    mass_weighted = [round(m / total_mass * 100, 2) for m in mass_weighted]

    return {
        "labels": labels,
        "counts": counts,
        "mass_weighted": mass_weighted,
        "unit": "mm" if use_mm else "px",
    }


def _build_csv(particles: list[Particle]) -> str:
    """Build CSV string with per-particle data."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "particle_id", "surface_px", "long_axis", "short_axis",
        "roundness", "diameter_px", "diameter_mm", "centroid_x", "centroid_y",
    ])
    for i, p in enumerate(particles, 1):
        writer.writerow([
            i, p.surface, p.long_axis, p.short_axis,
            p.roundness, p.diameter_px, p.diameter_mm or "",
            p.centroid[0], p.centroid[1],
        ])
    return output.getvalue()


def _array_to_b64_jpeg(arr: np.ndarray) -> str:
    """Convert numpy array to base64-encoded JPEG string."""
    img = Image.fromarray(arr.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")
