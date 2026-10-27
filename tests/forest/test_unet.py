import pytest

torch = pytest.importorskip("torch")

from daiff.forest.unet import UNet, count_params  # noqa: E402


def test_fr_f1_unet_forward_shape_on_64px_chip():
    net = UNet(in_bands=12, n_classes=2)
    out = net(torch.zeros(2, 12, 64, 64))
    assert out.shape == (2, 2, 64, 64)


def test_fr_f1_unet_has_about_two_million_parameters():
    n = count_params(UNet(in_bands=12, n_classes=2))
    assert 1_500_000 <= n <= 2_800_000


def test_fr_f1_unet_is_deterministic_for_a_fixed_seed():
    torch.manual_seed(0)
    a = UNet(12, 2)(torch.ones(1, 12, 32, 32))
    torch.manual_seed(0)
    b = UNet(12, 2)(torch.ones(1, 12, 32, 32))
    assert torch.equal(a, b)
