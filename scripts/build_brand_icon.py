#!/usr/bin/env python3
"""Generate the integration's brand icon.

Since Home Assistant 2026.3 a custom integration ships its own brand images in
a ``brand/`` directory beside its manifest, rather than submitting them to the
home-assistant/brands repository. This writes the two that HACS and the
frontend look for:

    custom_components/heathrow_arrivals/brand/icon.png      256x256
    custom_components/heathrow_arrivals/brand/icon@2x.png   512x512

No logo is supplied; the icon is used as the logo fallback.

    python3 scripts/build_brand_icon.py

Needs Pillow. The design is a runway seen from above, angled, with threshold
bars and a centreline. It is drawn at 4x and downsampled so it stays clean at
the ~48px HACS renders it at - which is also why the strip is light on a dark
tile rather than asphalt on navy: tone separation survives the downscale,
fine detail does not.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

BRAND = Path(__file__).resolve().parent.parent / "custom_components" / "heathrow_arrivals" / "brand"

S = 2048                        # supersampled canvas
NAVY = (13, 33, 54, 255)        # tile
STRIP = (237, 242, 247, 255)    # runway surface
MARK = (13, 33, 54, 255)        # markings, knocked out of the strip
RADIUS = int(S * 0.22)          # rounded-square tile
ANGLE = -35                     # runway bearing on the tile


def render() -> Image.Image:
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle([0, 0, S - 1, S - 1], RADIUS, fill=NAVY)

    runway = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(runway)

    length, width = int(S * 0.80), int(S * 0.235)
    cx = cy = S // 2
    x0, y0 = cx - length // 2, cy - width // 2
    x1, y1 = cx + length // 2, cy + width // 2
    draw.rectangle([x0, y0, x1, y1], fill=STRIP)

    # Threshold bars: fewer and chunkier than the real thing so they survive 48px.
    bars, bar_w = 4, int(width * 0.13)
    gap = (width - bars * bar_w) / (bars + 1)
    inset, bar_len = int(S * 0.022), int(length * 0.105)
    for i in range(bars):
        by = y0 + gap * (i + 1) + bar_w * i
        draw.rectangle([x0 + inset, by, x0 + inset + bar_len, by + bar_w], fill=MARK)
        draw.rectangle([x1 - inset - bar_len, by, x1 - inset, by + bar_w], fill=MARK)

    dash_l, dash_gap, dash_w = int(length * 0.085), int(length * 0.05), int(width * 0.10)
    x = x0 + inset + bar_len + dash_gap
    limit = x1 - inset - bar_len - dash_gap
    while x + dash_l <= limit:
        draw.rectangle([x, cy - dash_w // 2, x + dash_l, cy + dash_w // 2], fill=MARK)
        x += dash_l + dash_gap

    tile.alpha_composite(runway.rotate(ANGLE, resample=Image.BICUBIC, center=(cx, cy)))
    return tile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=BRAND, help="defaults to the brand directory")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    tile = render()
    for name, size in (("icon@2x.png", 512), ("icon.png", 256)):
        path = args.out / name
        tile.resize((size, size), Image.LANCZOS).save(path, "PNG", optimize=True)
        print(f"wrote {path} at {size}x{size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
