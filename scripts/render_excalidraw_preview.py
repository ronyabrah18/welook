"""Render a portable sketch-style PNG preview of the native Excalidraw diagram.

The `.excalidraw` JSON is the editable source of truth. Open it in Excalidraw for
native rendering and further edits; this Pillow renderer makes a GitHub preview.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "diagrams" / "welook-architecture.excalidraw"
OUTPUT = ROOT / "docs" / "diagrams" / "architecture_diagram_sketch.png"
SCALE = 2
PAD = 60
HAND_FONT = Path("/System/Library/Fonts/MarkerFelt.ttc")
FALLBACK_FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")


def font(size: int) -> ImageFont.FreeTypeFont:
    path = HAND_FONT if HAND_FONT.exists() else FALLBACK_FONT
    return ImageFont.truetype(str(path), max(12, round(size * SCALE)))


def jagged_edge(draw: ImageDraw.ImageDraw, start: tuple[float, float],
                end: tuple[float, float], color: str, width: int,
                rng: random.Random, dashed: bool = False) -> None:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return
    segments = max(2, math.ceil(length / 25))
    points = []
    for i in range(segments + 1):
        t = i / segments
        offset = 0 if i in (0, segments) else rng.uniform(-1.6, 1.6)
        points.append((start[0] + dx * t - dy / length * offset,
                       start[1] + dy * t + dx / length * offset))
    if dashed:
        for i in range(0, len(points) - 1, 2):
            draw.line([points[i], points[i + 1]], fill=color, width=width)
    else:
        draw.line(points, fill=color, width=width, joint="curve")


def rectangle(draw: ImageDraw.ImageDraw, e: dict, ox: float, oy: float) -> None:
    x1, y1 = (e["x"] - ox) * SCALE, (e["y"] - oy) * SCALE
    x2, y2 = x1 + e["width"] * SCALE, y1 + e["height"] * SCALE
    fill = e.get("backgroundColor", "transparent")
    if fill != "transparent":
        draw.rounded_rectangle((x1, y1, x2, y2), radius=12,
                               fill=fill)
    border = e.get("strokeColor", "#334155")
    rng = random.Random(int(hashlib.sha256(e["id"].encode()).hexdigest()[:8], 16))
    edges = [((x1, y1), (x2, y1)), ((x2, y1), (x2, y2)),
             ((x2, y2), (x1, y2)), ((x1, y2), (x1, y1))]
    for start, end in edges:
        jagged_edge(draw, start, end, border, max(2, e.get("strokeWidth", 2) * SCALE),
                    rng, e.get("strokeStyle") == "dashed")


def arrow(draw: ImageDraw.ImageDraw, e: dict, ox: float, oy: float) -> None:
    pts = [((e["x"] + p[0] - ox) * SCALE, (e["y"] + p[1] - oy) * SCALE)
           for p in e.get("points", [])]
    if len(pts) < 2:
        return
    color = e.get("strokeColor", "#475569")
    rng = random.Random(int(hashlib.sha256(e["id"].encode()).hexdigest()[:8], 16))
    for start, end in zip(pts, pts[1:]):
        jagged_edge(draw, start, end, color, max(2, e.get("strokeWidth", 2) * SCALE),
                    rng, e.get("strokeStyle") == "dashed")
    x1, y1 = pts[-2]
    x2, y2 = pts[-1]
    angle = math.atan2(y2 - y1, x2 - x1)
    arm = 11 * SCALE
    for turn in (-0.55, 0.55):
        endpoint = (x2 - arm * math.cos(angle + turn),
                    y2 - arm * math.sin(angle + turn))
        jagged_edge(draw, (x2, y2), endpoint, color, 3, rng)


def text(draw: ImageDraw.ImageDraw, e: dict, ox: float, oy: float) -> None:
    lines = e.get("text", "").split("\n")
    text_font = font(e.get("fontSize", 18))
    row_height = e.get("fontSize", 18) * e.get("lineHeight", 1.25) * SCALE
    total_height = len(lines) * row_height
    y = (e["y"] - oy) * SCALE
    if e.get("verticalAlign") == "middle":
        y += max(0, (e["height"] * SCALE - total_height) / 2)
    for line in lines:
        x = (e["x"] - ox) * SCALE
        if e.get("textAlign") == "center":
            line_width = draw.textlength(line, font=text_font)
            x += (e["width"] * SCALE - line_width) / 2
        draw.text((x, y), line, font=text_font,
                  fill=e.get("strokeColor", "#1e293b"), stroke_width=0)
        y += row_height


def main() -> None:
    elements = json.loads(SOURCE.read_text())["elements"]
    min_x = min(e["x"] for e in elements) - PAD
    min_y = min(e["y"] for e in elements) - PAD
    max_x = max(e["x"] + e["width"] for e in elements) + PAD
    max_y = max(e["y"] + e["height"] for e in elements) + PAD
    image = Image.new("RGB", (math.ceil((max_x - min_x) * SCALE),
                              math.ceil((max_y - min_y) * SCALE)), "#ffffff")
    draw = ImageDraw.Draw(image)
    for e in elements:
        if e["type"] == "rectangle":
            rectangle(draw, e, min_x, min_y)
    for e in elements:
        if e["type"] == "arrow":
            arrow(draw, e, min_x, min_y)
    for e in elements:
        if e["type"] == "text":
            text(draw, e, min_x, min_y)
    image.save(OUTPUT, optimize=True)
    print(f"Rendered {OUTPUT} ({image.width} x {image.height})")


if __name__ == "__main__":
    main()
