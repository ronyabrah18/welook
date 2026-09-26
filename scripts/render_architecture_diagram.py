"""Render the submission architecture PNG from the current serving report.

Run from the repository root: uv run python scripts/render_architecture_diagram.py
The generator uses Pillow; the PNG is committed so reviewers need no renderer.
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "app" / "data" / "serving_report.json"
OUTPUT = ROOT / "docs" / "diagrams" / "architecture_diagram.png"
W, H = 3200, 1820

INK = "#172A43"
MUTED = "#53657A"
LINE = "#A9B8C8"
BACKGROUND = "#F7F9FC"
WHITE = "#FFFFFF"

FONT_DIR = Path("/System/Library/Fonts/Supplemental")
REGULAR = FONT_DIR / "Arial.ttf"
BOLD = FONT_DIR / "Arial Bold.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    target = BOLD if bold else REGULAR
    if target.exists():
        return ImageFont.truetype(str(target), size)
    return ImageFont.load_default(size=size)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str,
          size: int = 30, color: str = INK, bold: bool = False) -> None:
    draw.text(xy, value, font=font(size, bold), fill=color)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int],
          color: str = "#607894", width: int = 7) -> None:
    draw.line([start, end], fill=color, width=width, joint="curve")
    x, y = end
    if start[1] == end[1]:
        draw.polygon([(x, y), (x - 18, y - 12), (x - 18, y + 12)], fill=color)
    elif start[0] == end[0]:
        sign = 1 if end[1] > start[1] else -1
        draw.polygon([(x, y), (x - 12, y - 18 * sign),
                      (x + 12, y - 18 * sign)], fill=color)


def box(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int],
        fill: str, border: str = "#DAE3ED", radius: int = 24) -> None:
    x1, y1, x2, y2 = rect
    draw.rounded_rectangle((x1 + 4, y1 + 7, x2 + 4, y2 + 7), radius,
                           fill="#E6ECF3")
    draw.rounded_rectangle(rect, radius, fill=fill, outline=border, width=2)


def card(draw: ImageDraw.ImageDraw, x: int, stage: str, title: str,
         color: str, lines: list[tuple[str, bool]], location: str) -> None:
    y, width, height = 430, 420, 435
    box(draw, (x, y, x + width, y + height), color)
    draw.rounded_rectangle((x + 24, y + 26, x + 105, y + 72), 15,
                           fill="#FFFFFF")
    label(draw, (x + 43, y + 34), stage, 26, INK, True)
    label(draw, (x + 26, y + 98), title, 44, INK, True)
    draw.line((x + 26, y + 162, x + width - 26, y + 162),
              fill="#C2CFDD", width=2)
    for index, (value, emphasized) in enumerate(lines):
        label(draw, (x + 26, y + 188 + index * 53), value,
              31 if emphasized else 28, INK if emphasized else MUTED, emphasized)
    draw.line((x + 26, y + 382, x + width - 26, y + 382),
              fill="#C2CFDD", width=2)
    label(draw, (x + 26, y + 392), location, 22, MUTED)


def pill(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int],
         text: str, fill: str, color: str = INK) -> None:
    draw.rounded_rectangle(rect, radius=24, fill=fill)
    label(draw, (rect[0] + 22, rect[1] + 12), text, 27, color, True)


def panel(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int],
          title: str, eyebrow: str, fill: str) -> None:
    box(draw, rect, fill, radius=27)
    label(draw, (rect[0] + 34, rect[1] + 28), eyebrow, 25, MUTED, True)
    label(draw, (rect[0] + 34, rect[1] + 72), title, 42, INK, True)


def main() -> None:
    stats = json.loads(REPORT.read_text())
    assert stats["source_lines"] == stats["accepted_observations"]
    img = Image.new("RGB", (W, H), BACKGROUND)
    draw = ImageDraw.Draw(img)

    label(draw, (90, 69), "WeLook", 76, INK, True)
    label(draw, (401, 91), "From internet observations to a sales research queue", 48, INK)
    label(draw, (92, 177), "CURRENT IMPLEMENTATION  |  FULL SOURCE SNAPSHOT  |  26 SEP 2026",
          28, MUTED, True)

    box(draw, (90, 245, 3110, 330), WHITE, radius=20)
    label(draw, (122, 270), "RUNNER", 29, "#3B648D", True)
    label(draw, (280, 270), "scripts/run_pipeline.py  -  sequential local CLI, Python + uv",
          30, INK)
    label(draw, (2300, 270), "Runtime: laptop -> Git -> cloud", 27, MUTED)

    pill(draw, (90, 359, 2075, 414), "LOCAL LAPTOP  /  original + Parquet + DuckDB warehouse", "#E9EFF6")
    pill(draw, (2170, 359, 2600, 414), "GIT SNAPSHOT", "#FDE8DF")
    pill(draw, (2690, 359, 3110, 414), "CLOUD APP", "#EFE7FF")

    xs = [90, 610, 1130, 1650, 2170, 2690]
    source_rows = f"{stats['source_lines']:,} source rows"
    accepted_rows = f"{stats['accepted_observations']:,} accepted"
    cards = [
        ("01", "LANDING", "#FFF1C5", [
            ("Original JSONL.zst", True), ("12.44 GB compressed", True),
            (source_rows, False), ("Immutable local file", False)],
            "b2_download_file_by_id"),
        ("02", "BRONZE", "#E8EEF5", [
            ("Python stream + Arrow", True), ("656 Parquet parts", True),
            (source_rows, False), ("Raw line + file lineage", False)],
            "artifacts/runs/.../bronze/"),
        ("03", "SILVER", "#E0F3F4", [
            ("Python + PyArrow", True), ("Typed Parquet parts", True),
            (accepted_rows, False), ("0 rejected in full run", False)],
            "artifacts/runs/.../silver/"),
        ("04", "GOLD", "#DDEBFF", [
            ("DuckDB + dbt SQL", True), ("9,334,905 evidence links", False),
            (f"{stats['candidate_accounts']:,} domains", True),
            ("7 first  ·  5,411 review next", False)],
            "artifacts/warehouse/full.duckdb"),
        ("05", "SERVING", "#FFE7DD", [
            ("Read-only DuckDB", True), (f"{stats['hosted_accounts']:,} ranked domains", True),
            (f"{stats['hosted_evidence_rows']:,} evidence rows", False),
            (f"{stats['ai_assessed_accounts']} curated AI notes", False)],
            "app/data/welook_serving.duckdb"),
        ("06", "PRODUCT", "#ECE5FC", [
            ("Streamlit Cloud", True), ("Filter + inspect", False),
            ("Research handoff", False), ("Cited CSV export", False)],
            "welook.streamlit.app"),
    ]
    for x, (stage, title, color, lines, location) in zip(xs, cards):
        card(draw, x, stage, title, color, lines, location)
    for left, right, name in zip(xs, xs[1:],
                                 ["stream", "validate", "model", "export", "query"]):
        arrow(draw, (left + 430, 650), (right - 12, 650))
        label(draw, (left + 426, 580), name, 25, MUTED, True)

    # Silver validation has two outcomes. Rejected rows never enter the typed
    # silver Parquet or the gold models; they are written beside the run parts.
    arrow(draw, (1340, 868), (1340, 912), color="#C1772B", width=6)
    box(draw, (1080, 913, 1600, 988), "#FFF3E2", border="#E1A153", radius=15)
    label(draw, (1102, 922), "QUARANTINE  /  rejected rows", 27, "#854C17", True)
    label(draw, (1102, 955), "quarantine.jsonl  ·  0 in this full run", 24, MUTED)

    # Offline AI is a separate branch from rule-based gold, then joins serving.
    draw.line([(1860, 869), (1860, 987)], fill="#48A56C", width=7)
    draw.polygon([(1860, 999), (1848, 978), (1872, 978)], fill="#48A56C")
    draw.line([(2030, 1000), (2030, 930), (2380, 930), (2380, 876)],
              fill="#48A56C", width=7)
    draw.polygon([(2380, 864), (2368, 886), (2392, 886)], fill="#48A56C")

    panel(draw, (90, 1000, 1070, 1430), "Data quality + replay", "DATA ENGINEERING CONTROLS", "#FFFFFF")
    label(draw, (126, 1139), "1  File checksum skips a completed arrival", 32)
    label(draw, (126, 1200), "2  Bronze can replay silver without source", 32)
    label(draw, (126, 1261), "3  Bronze = silver + quarantine rows", 32)
    label(draw, (126, 1322), "4  Rejects stop release; dbt tests gate gold", 32)

    panel(draw, (1130, 1000, 2080, 1430), "Offline AI assessment", "SELECTED ACCOUNTS ONLY", "#E8F6EC")
    label(draw, (1166, 1137), "Up to 3 cited observations per domain", 32)
    label(draw, (1166, 1198), "GPT-4.1 mini + versioned prompt", 32)
    label(draw, (1166, 1259), "Publication gate -> gold AI table (46 notes)", 32)
    label(draw, (1166, 1320), "9 human-reviewed; local traces; $10 ceiling", 32)

    panel(draw, (2170, 1000, 3110, 1430), "Salesperson workflow", "HOSTED, READ-ONLY", "#F2ECFF")
    label(draw, (2206, 1137), "1  Filter evidence and product signals", 32)
    label(draw, (2206, 1198), "2  Review why a domain is in the queue", 32)
    label(draw, (2206, 1259), "3  Record identity source + status", 32)
    label(draw, (2206, 1320), "4  Export a cited handoff CSV", 32)

    box(draw, (90, 1515, 3110, 1715), "#EDF2F8", radius=22)
    label(draw, (126, 1542), "HOW INCREMENTAL INPUT WORKS", 28, "#3B648D", True)
    label(draw, (126, 1590), "New immutable file -> checksum -> append bronze/silver -> rebuild dbt gold -> refresh serving snapshot", 33)
    label(draw, (126, 1650), "AI notes invalidate when the source set changes. No LLM call occurs when a salesperson opens the app.", 31, MUTED)

    label(draw, (90, 1752), "Interpretation: domains are candidate evidence groups, not verified companies; scanner labels do not prove current exposure or buying intent.",
          27, MUTED)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT, optimize=True)
    print(f"Rendered {OUTPUT} ({W} x {H})")


if __name__ == "__main__":
    main()
