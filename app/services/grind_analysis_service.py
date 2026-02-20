"""Coffee grind particle size analysis service.

Analyzes photos of coffee grounds on a white/light background to detect
individual particles and compute size distribution statistics.

Algorithm faithfully reimplemented from coffeegrindsize.py by Jonathan Gagne
(https://github.com/csatt/coffeegrindsize). Key formulas preserved:
- Blue channel thresholding against background median
- 4-connectivity flood fill (quick_cluster)
- Axis = max distance from centroid; short_axis = surface / (pi * axis)
- Roundness = surface / (pi * axis^2)
- Diameter = 2 * sqrt(long_axis * short_axis) (geometric mean of axes)
- Surface brightness multiplier for sub-pixel grounds
- Volume = pi * short_axis^2 * axis (prolate ellipsoid)
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
    pixel_scale: float = 0.0  # pixels per mm (0 = report in pixels only)
    max_cluster_axis: int = 100  # max semi-major axis in pixels
    min_surface: int = 5  # minimum cluster area in pixels
    min_roundness: float = 0.0  # 0-1, filter out elongated shapes
    max_dimension: int = 2000  # auto-downscale images larger than this


@dataclass
class Particle:
    surface: float  # brightness-adjusted surface area
    long_axis: float  # semi-major axis (max dist from centroid)
    short_axis: float  # derived: surface / (pi * long_axis)
    roundness: float  # surface / (pi * long_axis^2)
    diameter_px: float  # 2 * sqrt(long_axis * short_axis)
    diameter_mm: float | None
    volume: float  # pi * short_axis^2 * long_axis
    centroid: tuple[float, float]
    _pixels: list[tuple[int, int]] = field(default_factory=list, repr=False)


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

    background_median = float(np.median(blue))
    mask = _compute_threshold_mask(blue, params.threshold, background_median)
    threshold_b64 = _generate_threshold_image(img_array, mask)

    particles = _find_and_measure_clusters(
        mask, blue, width, height, background_median, params
    )

    cluster_b64 = _generate_cluster_image(img_array, particles)

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


def _compute_threshold_mask(
    blue: np.ndarray, threshold_pct: float, background_median: float
) -> np.ndarray:
    """Create boolean mask of dark (coffee) pixels.

    Matches original: mask = where(blue < background_median * threshold / 100)
    """
    cutoff = background_median * threshold_pct / 100.0
    return blue < cutoff


def _generate_threshold_image(img_array: np.ndarray, mask: np.ndarray) -> str:
    """Overlay red on masked pixels, return base64 JPEG.

    Matches original: RGB = (255, 0, 0) for thresholded pixels.
    """
    overlay = img_array.copy()
    overlay[mask, 0] = 255
    overlay[mask, 1] = 0
    overlay[mask, 2] = 0
    return _array_to_b64_jpeg(overlay)


def _quick_cluster(
    mask: np.ndarray, visited: np.ndarray, start_y: int, start_x: int
) -> list[tuple[int, int]]:
    """4-connectivity flood fill matching original quick_cluster.

    Uses Manhattan distance <= 1 (up/down/left/right only, no diagonals).
    """
    height, width = mask.shape
    queue = deque()
    queue.append((start_y, start_x))
    visited[start_y, start_x] = True
    pixels = []

    while queue:
        y, x = queue.popleft()
        pixels.append((y, x))
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < height and 0 <= nx < width and not visited[ny, nx] and mask[ny, nx]:
                visited[ny, nx] = True
                queue.append((ny, nx))

    return pixels


def _find_and_measure_clusters(
    mask: np.ndarray,
    blue: np.ndarray,
    width: int,
    height: int,
    background_median: float,
    params: AnalysisParams,
) -> list[Particle]:
    """Find all connected clusters and compute particle geometry.

    Matches the original launch_psd flow:
    1. Flood fill to find clusters (4-connectivity)
    2. Filter by surface, edge, axis, roundness
    3. Compute geometry matching original formulas
    """
    visited = np.zeros_like(mask, dtype=bool)
    particles = []

    for y in range(height):
        for x in range(width):
            if mask[y, x] and not visited[y, x]:
                pixels = _quick_cluster(mask, visited, y, x)

                # Filter by minimum surface (raw pixel count, before brightness adjustment)
                if len(pixels) < params.min_surface:
                    continue

                ys = np.array([p[0] for p in pixels], dtype=float)
                xs = np.array([p[1] for p in pixels], dtype=float)

                # Avoid image edges (matches original: min <= 0 or max >= size-1)
                if ys.min() <= 0 or ys.max() >= height - 1:
                    continue
                if xs.min() <= 0 or xs.max() >= width - 1:
                    continue

                # Centroid
                xmean = float(np.mean(ys))
                ymean = float(np.mean(xs))

                # Semi-major axis = max distance from centroid
                # (matches original: dlist = sqrt((x-xmean)^2 + (y-ymean)^2), axis = max(dlist))
                dists = np.sqrt((ys - xmean) ** 2 + (xs - ymean) ** 2)
                dists = np.maximum(dists, 1e-4)
                long_axis = float(np.max(dists))

                # Filter by max cluster axis
                if long_axis > params.max_cluster_axis:
                    continue

                # Brightness-adjusted surface multiplier
                # (matches original: surface_multiplier = (median - min_blue) / median, clamped >= 1)
                pixel_blues = blue[ys.astype(int), xs.astype(int)].astype(float)
                surface_multiplier = (background_median - pixel_blues.min()) / background_median
                surface_multiplier = max(surface_multiplier, 1.0)
                surface = float(len(pixels)) * surface_multiplier

                # Roundness = surface / (pi * axis^2)
                # (matches original formula)
                if surface == 1:
                    roundness = 1.0
                else:
                    roundness = surface / (math.pi * long_axis ** 2)

                # Filter by roundness
                if roundness < params.min_roundness:
                    continue

                # Short axis = surface / (pi * axis)
                short_axis = surface / (math.pi * long_axis)

                # Volume = pi * short_axis^2 * axis (prolate ellipsoid)
                volume = math.pi * short_axis ** 2 * long_axis

                # Diameter = 2 * sqrt(long_axis * short_axis) (geometric mean)
                diameter_px = 2.0 * math.sqrt(long_axis * short_axis)
                diameter_mm = (diameter_px / params.pixel_scale) if params.pixel_scale > 0 else None

                particles.append(Particle(
                    surface=round(surface, 2),
                    long_axis=round(long_axis, 2),
                    short_axis=round(short_axis, 2),
                    roundness=round(roundness, 3),
                    diameter_px=round(diameter_px, 2),
                    diameter_mm=round(diameter_mm, 3) if diameter_mm is not None else None,
                    volume=round(volume, 2),
                    centroid=(round(ymean, 1), round(xmean, 1)),
                    _pixels=pixels,
                ))

    return particles


def _generate_cluster_image(
    img_array: np.ndarray, particles: list[Particle]
) -> str:
    """Draw cluster outlines in red with blue centroids.

    Matches original refresh_cluster_data: edge pixels in red (255,0,0),
    centroid pixel in blue (80,80,255). A pixel is an edge pixel if it
    has fewer than 9 neighbors (including itself) in the cluster.
    """
    overlay = img_array.copy()

    for p in particles:
        pixel_set = set(p._pixels)
        ys = np.array([pt[0] for pt in p._pixels])
        xs = np.array([pt[1] for pt in p._pixels])

        for idx in range(len(p._pixels)):
            y, x = ys[idx], xs[idx]
            # Count neighbors (including self) within abs distance <= 1
            # Matches original: np.where((abs(x-x[l])<=1) & (abs(y-y[l])<=1))
            neighbor_count = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if (y + dy, x + dx) in pixel_set:
                        neighbor_count += 1
            # Skip if fully surrounded (9 neighbors = interior pixel)
            if neighbor_count == 9:
                continue
            # Mark edge pixel in red
            overlay[y, x] = [255, 0, 0]

        # Mark centroid in blue
        cy = int(round(p.centroid[1]))
        cx = int(round(p.centroid[0]))
        if 0 <= cy < overlay.shape[0] and 0 <= cx < overlay.shape[1]:
            overlay[cy, cx] = [80, 80, 255]

    return _array_to_b64_jpeg(overlay)


def _build_histogram_data(particles: list[Particle], pixel_scale: float) -> dict:
    """Build histogram data for Chart.js (log-scale bins).

    Uses volume-weighted (mass) histogram matching original "Mass vs Diameter".
    """
    if not particles:
        return {"labels": [], "counts": [], "mass_weighted": [], "unit": "px"}

    use_mm = pixel_scale > 0
    if use_mm:
        diameters = [p.diameter_mm for p in particles]
    else:
        diameters = [p.diameter_px for p in particles]

    volumes = [p.volume for p in particles]

    d_min = max(min(diameters), 0.1)
    d_max = max(diameters)

    # Log-scale bins (matches original logspace approach)
    num_bins = min(30, max(10, int(math.sqrt(len(diameters)))))
    bin_edges = np.logspace(np.log10(d_min * 0.9), np.log10(d_max * 1.1), num_bins + 1)

    counts = [0] * num_bins
    mass_weighted = [0.0] * num_bins
    labels = []

    for i in range(num_bins):
        lo, hi = float(bin_edges[i]), float(bin_edges[i + 1])
        unit = "mm" if use_mm else "px"
        labels.append(f"{lo:.1f}-{hi:.1f} {unit}")
        for j, d in enumerate(diameters):
            if lo <= d < hi or (i == num_bins - 1 and d == hi):
                counts[i] += 1
                mass_weighted[i] += volumes[j]

    # Normalize mass-weighted to fraction (matches original: weights/sum(weights))
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
        "particle_id", "surface", "long_axis", "short_axis",
        "roundness", "diameter_px", "diameter_mm", "volume",
        "centroid_x", "centroid_y",
    ])
    for i, p in enumerate(particles, 1):
        writer.writerow([
            i, p.surface, p.long_axis, p.short_axis,
            p.roundness, p.diameter_px, p.diameter_mm or "",
            p.volume, p.centroid[0], p.centroid[1],
        ])
    return output.getvalue()


def _array_to_b64_jpeg(arr: np.ndarray) -> str:
    """Convert numpy array to base64-encoded JPEG string."""
    img = Image.fromarray(arr.astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")
