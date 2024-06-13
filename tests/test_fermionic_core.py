import pytest

import symmray as sr
import numpy as np


@pytest.mark.parametrize("symmetry", ["Z2", "U1"])
def test_fermi_norm(symmetry):
    x = sr.utils.get_rand_symmetric(
        symmetry,
        (3, 4, 5, 6),
        fermionic=True,
    )
    x.phase_flip(1, 3, inplace=True)
    assert x.phases
    ne = x.norm()
    xc = x.conj()
    assert xc.phases != x.phases
    xx = sr.tensordot(x, xc, axes=4)
    n1 = float(xx) ** 0.5
    assert ne == pytest.approx(n1)
    xx = sr.tensordot(xc, x, axes=4)
    n2 = float(xx) ** 0.5
    assert ne == pytest.approx(n2)
    xd = x.H
    assert xd.phases != x.phases
    assert xd.phases != xc.phases
    xx = sr.tensordot(xd, x, axes=[(3, 2, 1, 0), (0, 1, 2, 3)])
    n3 = float(xx) ** 0.5
    assert ne == pytest.approx(n3)
    xx = sr.tensordot(x, xd, axes=[(0, 1, 2, 3), (3, 2, 1, 0)])
    n4 = float(xx) ** 0.5
    assert ne == pytest.approx(n4)


# def test_transpose():
#     rng = np.random.default_rng(seed)
#     x = get_rand_u1_fermionic_array((3, 4, 5, 6), seed=rng)
#     perm = tuple(rng.permutation(x.ndim))


@pytest.mark.parametrize("seed", range(100))
def test_fuse_with_tensordot(seed):
    rng = np.random.default_rng(seed)

    ixs = {
        "a": sr.BlockIndex({0: 2, 1: 3}, flow=rng.choice([0, 1])),
        "b": sr.BlockIndex({0: 3, 1: 4}, flow=rng.choice([0, 1])),
        "c": sr.BlockIndex({0: 4, 1: 5}, flow=rng.choice([0, 1])),
        "d": sr.BlockIndex({0: 2, 1: 1}, flow=rng.choice([0, 1])),
        "e": sr.BlockIndex({0: 1, 1: 2}, flow=rng.choice([0, 1])),
    }

    ndim_left = rng.integers(1, 6)
    ndim_right = rng.integers(1, 6)
    left = rng.choice(list(ixs.keys()), size=ndim_left, replace=False).tolist()
    right = rng.choice(
        list(ixs.keys()), size=ndim_right, replace=False
    ).tolist()
    shared = set(left).intersection(right)
    ncon = len(shared)
    nleft = ndim_left - ncon
    nright = ndim_right - ncon
    ndim_out = nleft + nright
    perm_reverse = (*range(nright, ndim_out), *range(nright))

    axes_x = tuple(left.index(c) for c in shared)
    axes_y = tuple(right.index(c) for c in shared)

    x = sr.Z2FermionicArray.random(
        indices=[ixs[k] for k in left],
        seed=rng,
    )
    y = sr.Z2FermionicArray.random(
        indices=[ixs[k].conj() for k in right],
        seed=rng,
    )

    # basic
    z_b = sr.tensordot(x, y, axes=(axes_x, axes_y), mode="blockwise")

    # fused tensordot
    z_f = sr.tensordot(x, y, axes=(axes_x, axes_y), mode="fused")
    assert z_b.allclose(z_f)

    # reversed then transposed
    z_rb = sr.tensordot(y, x, axes=(axes_y, axes_x), mode="blockwise")
    z_rb.transpose(perm_reverse, inplace=True)
    assert z_b.allclose(z_rb)

    # reversed then transposed
    z_rf = sr.tensordot(y, x, axes=(axes_y, axes_x), mode="fused")
    z_rf.transpose(perm_reverse, inplace=True)
    assert z_b.allclose(z_rf)

    if axes_x:
        faxes_a = (min(axes_x),)
    else:
        faxes_a = ()

    if axes_y:
        faxes_b = (min(axes_y),)
    else:
        faxes_b = ()

    # fused-explicit then blockwise
    z_efb = sr.tensordot(
        x.fuse(axes_x),
        y.fuse(axes_y),
        [faxes_a, faxes_b],
        mode="blockwise",
    )
    assert z_b.allclose(z_efb)

    # fused-explicit then fused contraction
    z_eff = sr.tensordot(
        x.fuse(axes_x),
        y.fuse(axes_y),
        [faxes_a, faxes_b],
        mode="fused",
    )
    assert z_b.allclose(z_eff)

    # reverse fused-explicit then blockwise
    z_refb = sr.tensordot(
        y.fuse(axes_y),
        x.fuse(axes_x),
        [faxes_b, faxes_a],
        mode="blockwise",
    ).transpose(perm_reverse)
    assert z_b.allclose(z_refb)

    # reverse fused-explicit then fused contraction
    z_reff = sr.tensordot(
        y.fuse(axes_y),
        x.fuse(axes_x),
        [faxes_b, faxes_a],
        mode="fused",
    ).transpose(perm_reverse)
    assert z_b.allclose(z_reff)


@pytest.mark.parametrize("seed", range(10))
def test_transpose_vs_pyblock3(seed):
    pytest.importorskip("pyblock3")

    rng = np.random.default_rng(seed)

    ixs = [
        sr.BlockIndex({0: 2, 1: 3}, flow=rng.choice([0, 1])),
        sr.BlockIndex({0: 3, 1: 2}, flow=rng.choice([0, 1])),
        sr.BlockIndex({0: 3, 1: 3}, flow=rng.choice([0, 1])),
        sr.BlockIndex({0: 2, 1: 2}, flow=rng.choice([0, 1])),
        sr.BlockIndex({0: 2, 1: 2}, flow=rng.choice([0, 1])),
    ]
    x = sr.Z2FermionicArray.random(
        indices=ixs,
        dist="uniform",
        seed=rng,
    )

    perm = tuple(rng.permutation(x.ndim))

    pb1 = x.to_pyblock3().transpose(perm)
    pb2 = x.transpose(perm).to_pyblock3()

    assert (pb1 - pb2).norm() == pytest.approx(0.0)


@pytest.mark.parametrize("seed", range(10))
@pytest.mark.parametrize(
    "method",
    [
        "blockwise",
        "blockwise-switch",
        "fused",
        "fused-switch",
        "fused-explicit",
        "fused-explicit-switch",
    ],
)
def test_tensordot_vs_pyblock3(seed, method):
    pytest.importorskip("pyblock3")

    rng = np.random.default_rng(seed)

    ixs = {
        "a": sr.BlockIndex({0: 2, 1: 3}, flow=rng.choice([1])),
        "b": sr.BlockIndex({0: 3, 1: 4}, flow=rng.choice([1])),
        "c": sr.BlockIndex({0: 4, 1: 5}, flow=rng.choice([1])),
        "d": sr.BlockIndex({0: 2, 1: 1}, flow=rng.choice([1])),
    }
    sx = "".join(rng.permutation(list(ixs)))
    sy = "".join(rng.permutation(list(ixs)))

    axes_x = tuple(sx.index(c) for c in ixs)
    axes_y = tuple(sy.index(c) for c in ixs)

    x = sr.Z2FermionicArray.random(
        indices=[ixs[c] for c in sx],
        dist="uniform",
        seed=rng,
    )

    y = sr.Z2FermionicArray.random(
        indices=[ixs[c].conj() for c in sy],
        dist="uniform",
        seed=rng,
    )

    expected = np.tensordot(x.to_pyblock3(), y.to_pyblock3(), [axes_x, axes_y])

    if "switch" in method:
        x, y = y, x
        axes_x, axes_y = axes_y, axes_x

    if "blockwise" in method:
        z = sr.tensordot(x, y, axes=(axes_x, axes_y), mode="blockwise")

    elif "fused-explicit" in method:
        x = x.fuse(axes_x)
        y = y.fuse(axes_y)
        z = sr.tensordot(x, y, 1)

    elif "fused" in method:
        z = sr.tensordot(x, y, axes=(axes_x, axes_y), mode="fused")

    assert float(z) == pytest.approx(expected)
