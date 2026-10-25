"""NFR-5: time 5 map-layer tiles (< 3 s each) and the sub-basin table (< 1 s) on a running server.

Usage: uv run python scripts/nfr5_timing.py [http://127.0.0.1:8000]
Network throttling to 10 Mbps is done in the browser's developer tools for the formal test; this
script records the server-side component and appends a row per request to docs/perf/.
"""

import math
import platform
import sys
import time
from datetime import date
from pathlib import Path

import httpx

LAYERS = ["forest", "loss", "susceptibility", "riskclass", "delta_s"]


def tile_xy(lon: float, lat: float, z: int) -> tuple[int, int]:
    n = 2**z
    return int((lon + 180) / 360 * n), int(
        (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    )


def main(base: str) -> int:
    meta = httpx.get(f"{base}/api/meta", timeout=30).json()
    year = meta["years"][-1]
    fc = httpx.get(f"{base}/api/subbasins?year={year}", timeout=30).json()
    ring = fc["features"][0]["geometry"]["coordinates"][0]
    lon = sum(p[0] for p in ring) / len(ring)
    lat = sum(p[1] for p in ring) / len(ring)
    x, y = tile_xy(lon, lat, 12)
    rows, ok = [], True
    for layer in LAYERS:
        t = time.perf_counter()
        r = httpx.get(f"{base}/api/tiles/{layer}/{year}/12/{x}/{y}.png", timeout=30)
        sec = time.perf_counter() - t
        ok &= r.status_code == 200 and sec < 3
        rows.append((f"tile {layer}", sec, 3.0))
    t = time.perf_counter()
    httpx.get(f"{base}/api/subbasins/{year}.csv", timeout=30)
    sec = time.perf_counter() - t
    ok &= sec < 1
    rows.append(("sub-basin table", sec, 1.0))
    out = Path(__file__).resolve().parents[1] / "docs" / "perf" / f"{date.today()}-nfr5.md"
    if not out.exists():
        out.write_text("| machine | request | seconds | budget | run_id |\n|---|---|---|---|---|\n")
    with out.open("a", encoding="utf-8") as f:
        for name, sec, budget in rows:
            f.write(f"| {platform.node()} | {name} | {sec:.3f} | {budget} | {meta['run_id']} |\n")
            print(f"{name:22s} {sec:6.3f} s (budget {budget} s)")
    print("NFR-5 PASS" if ok else "NFR-5 FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"))
