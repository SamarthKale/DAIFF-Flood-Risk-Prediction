import numpy as np
import pandas as pd

from daiff.gee.review import PX, build_page, pick_windows, score_review, to_data_uri
from daiff.grid import Grid


def test_pick_windows_stay_inside_valid_footprint():
    g = Grid.from_bounds("EPSG:32646", (300000, 2900000, 310000, 2910000), res=30)
    valid = np.zeros(g.shape, bool)
    valid[50:250, 60:260] = True
    pts = pick_windows(valid, g, n=20, seed=1)
    assert len(pts) == 20 and len(set(pts)) == 20
    for x, y in pts:
        c = int((x - g.transform.c) / g.res)
        r = int((g.transform.f - y) / g.res)
        assert valid[r - 16 : r + 17, c - 16 : c + 17].all()


def test_pick_windows_is_deterministic_and_handles_small_footprint():
    g = Grid.from_bounds("EPSG:32646", (300000, 2900000, 310000, 2910000), res=30)
    valid = np.zeros(g.shape, bool)
    valid[0:10, 0:10] = True  # smaller than a 1 km window
    assert pick_windows(valid, g, n=5, seed=1) == []
    valid[:, :] = True
    assert pick_windows(valid, g, 5, 3) == pick_windows(valid, g, 5, 3)


def test_page_embeds_images_and_scores_reviews(tmp_path):
    rgb = np.full((PX, PX, 3), 120, dtype=np.uint8)
    items = [
        {"id": i, "year": y, "lat": 26.0, "lon": 92.0, "img": to_data_uri(rgb)}
        for y in (2018, 2022)
        for i in range(1, 21)
    ]
    page = build_page(items, tmp_path / "p.html", "kopili")
    html = page.read_text(encoding="utf-8")
    assert html.count("data:image/png;base64,") == 40 and "Download results" in html
    rows = [
        (y, i, "clean" if not (y == 2022 and i <= 3) else "remnants")
        for y in (2018, 2022)
        for i in range(1, 21)
    ]
    csv = tmp_path / "r.csv"
    pd.DataFrame(rows, columns=["year", "window", "verdict"]).assign(reviewer="x").to_csv(
        csv, index=False
    )
    s = score_review(csv)
    assert s["per_year"][2018]["clean"] == 20 and s["per_year"][2022]["clean"] == 17
    assert s["pass"] is False
    pd.DataFrame(
        rows[:20] + [(2022, i, "clean") for i in range(1, 21)],
        columns=["year", "window", "verdict"],
    ).to_csv(csv, index=False)
    assert score_review(csv)["pass"] is True
