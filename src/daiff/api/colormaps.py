"""Fixed server-side styling for map layers (P2 Global Constraints)."""

from __future__ import annotations

RISK_COLORS = {
    1: "#1a9850",
    2: "#91cf60",
    3: "#fee08b",
    4: "#fc8d59",
    5: "#d73027",
}

# layer -> (colormap name in rio-tiler, value range); None range = categorical/RGB
STYLES: dict[str, tuple[str | None, tuple[float, float] | None]] = {
    "forest": ("greens", (0.0, 1.0)),
    "loss": ("reds", (0.0, 1.0)),
    "susceptibility": ("viridis", (0.0, 1.0)),
    "delta_s": ("rdbu_r", (-0.2, 0.2)),
    "riskclass": (None, None),
    "preview": (None, None),
}

LEGENDS = {
    "forest": {
        "type": "continuous",
        "min": 0,
        "max": 1,
        "label": "Forest fraction",
        "cmap": "greens",
    },
    "loss": {
        "type": "continuous",
        "min": 0,
        "max": 1,
        "label": "Forest loss since t0",
        "cmap": "reds",
    },
    "susceptibility": {
        "type": "continuous",
        "min": 0,
        "max": 1,
        "label": "Flood susceptibility",
        "cmap": "viridis",
    },
    "delta_s": {
        "type": "continuous",
        "min": -0.2,
        "max": 0.2,
        "label": "Change in susceptibility",
        "cmap": "rdbu_r",
    },
    "riskclass": {
        "type": "categorical",
        "label": "Flood risk class",
        "classes": [
            {"value": k, "color": v, "name": n}
            for (k, v), n in zip(
                RISK_COLORS.items(),
                ["Very low", "Low", "Moderate", "High", "Very high"],
                strict=True,
            )
        ],
    },
    "preview": {"type": "rgb", "label": "Sentinel-2 dry-season composite"},
}


def hex_to_rgba(h: str) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


RISK_CMAP = {k: hex_to_rgba(v) for k, v in RISK_COLORS.items()}
