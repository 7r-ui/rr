"""OpenCV-based chart image normalization and pixel<->price/time mapping.

Detects candidate horizontal support/resistance lines from the raw pixels
(cheap, deterministic, works with no API key) and provides the coordinate
mapping used to translate ANY pixel-space detection - from here or from the
vision model in `model_client.py` - back into real price/time axes, given
the two-point axis hints the caller supplies.
"""
from __future__ import annotations

import cv2
import numpy as np

from app.models.schemas import ChartAnalysisRequest, DetectedLevel


def decode_image(image_bytes: bytes) -> np.ndarray:
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Could not decode image; expected PNG/JPEG chart screenshot bytes.")
    return img


def detect_horizontal_levels(
    image: np.ndarray, *, min_line_len_ratio: float = 0.25, cluster_px: int = 6
) -> list[DetectedLevel]:
    """Canny edges -> probabilistic Hough transform -> keep near-horizontal
    segments -> cluster by y-coordinate so one drawn line isn't reported N times."""
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    min_len = int(width * min_line_len_ratio)
    lines = cv2.HoughLinesP(
        edges, 1, np.pi / 180, threshold=80, minLineLength=min_len, maxLineGap=10
    )
    if lines is None:
        return []

    horizontals: list[tuple[int, int, int, int]] = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(y2 - y1) <= 2:  # near-horizontal only
            horizontals.append((int(x1), int(y1), int(x2), int(y2)))

    horizontals.sort(key=lambda seg: seg[1])
    clusters: list[list[tuple[int, int, int, int]]] = []
    for seg in horizontals:
        if clusters and abs(seg[1] - clusters[-1][-1][1]) <= cluster_px:
            clusters[-1].append(seg)
        else:
            clusters.append([seg])

    levels: list[DetectedLevel] = []
    for cluster in clusters:
        x_min = min(s[0] for s in cluster)
        x_max = max(s[2] for s in cluster)
        y_avg = int(sum(s[1] for s in cluster) / len(cluster))
        confidence = min(1.0, 0.4 + 0.1 * len(cluster))
        levels.append(
            DetectedLevel(
                label="support" if y_avg > height / 2 else "resistance",
                pixel_bbox=(x_min, y_avg, x_max, y_avg),
                confidence=confidence,
            )
        )
    return levels


def map_pixel_y_to_price(
    pixel_y: int, image_height: int, price_axis_hint: tuple[float, float] | None
) -> float | None:
    """`price_axis_hint` is (price_at_top_of_image, price_at_bottom_of_image)."""
    if price_axis_hint is None:
        return None
    price_top, price_bottom = price_axis_hint
    ratio = pixel_y / max(image_height, 1)
    return price_top + ratio * (price_bottom - price_top)


def apply_price_mapping(
    levels: list[DetectedLevel], image: np.ndarray, request: ChartAnalysisRequest
) -> list[DetectedLevel]:
    height = image.shape[0]
    for level in levels:
        y = level.pixel_bbox[1]
        price = map_pixel_y_to_price(y, height, request.price_axis_hint)
        if price is not None:
            level.price = round(price, 6)
    return levels
