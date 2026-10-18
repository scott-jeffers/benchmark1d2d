import numpy as np

from references.macdonald import gvf_residual
from references.macdonald_random import commitment, draw


def test_exact_and_capped():
    for seed in (1, 2, 3, 4):
        for cap in (0.5, 0.9):
            c = draw(seed, cap)
            x = np.linspace(0, c["L"], 4001)
            h, z = c["depth"](x), c["bed"](x)
            assert abs(c["froude_max"] - cap) < 1e-3
            r = gvf_residual(x, h, z, c["Q"], c["B"], c["n_manning"])
            assert np.abs(r[2:-2]).max() < 1e-5


def test_same_seed_same_case():
    a, b = draw(7), draw(7)
    x = np.linspace(0, 1000, 11)
    assert np.array_equal(a["bed"](x), b["bed"](x))
    assert commitment(7, "ab") == commitment(7, "ab") != commitment(7, "ac")
    assert not np.array_equal(draw(8)["bed"](x), a["bed"](x))
