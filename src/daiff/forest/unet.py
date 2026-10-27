"""U-Net forest/non-forest challenger (D-14, FR-F1).

Trained on Google Colab (never on the local GPU); the local CPU build only runs tiny shape tests.
"""

from __future__ import annotations

import torch
from torch import nn


def _block(c_in: int, c_out: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(c_in, c_out, 3, padding=1, bias=False),
        nn.BatchNorm2d(c_out),
        nn.ReLU(inplace=True),
        nn.Conv2d(c_out, c_out, 3, padding=1, bias=False),
        nn.BatchNorm2d(c_out),
        nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    """4-level U-Net (about 2 M parameters at base=16); input H and W must be divisible by 16."""

    def __init__(self, in_bands: int = 12, n_classes: int = 2, base: int = 16) -> None:
        super().__init__()
        widths = [base * 2**i for i in range(5)]  # 16, 32, 64, 128, 256
        self.enc = nn.ModuleList(
            _block(c_in, c_out)
            for c_in, c_out in zip([in_bands, *widths[:3]], widths[:4], strict=True)
        )
        self.pool = nn.MaxPool2d(2)
        self.mid = _block(widths[3], widths[4])
        self.up = nn.ModuleList(
            nn.ConvTranspose2d(widths[i + 1], widths[i], 2, stride=2) for i in (3, 2, 1, 0)
        )
        self.dec = nn.ModuleList(_block(2 * widths[i], widths[i]) for i in (3, 2, 1, 0))
        self.head = nn.Conv2d(widths[0], n_classes, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        skips = []
        for block in self.enc:
            x = block(x)
            skips.append(x)
            x = self.pool(x)
        x = self.mid(x)
        for up, dec, skip in zip(self.up, self.dec, reversed(skips), strict=True):
            x = dec(torch.cat([up(x), skip], dim=1))
        return self.head(x)


def count_params(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
