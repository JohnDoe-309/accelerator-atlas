from accelerator_atlas.export.sample import allocate


def test_allocate_sums_to_total_and_respects_batch_sizes() -> None:
    sizes = [1, 35, 236, 206]
    quotas = allocate(75, sizes)
    assert sum(quotas) == 75
    assert all(0 <= q <= s for q, s in zip(quotas, sizes))
    assert quotas == [0, 6, 37, 32]


def test_allocate_takes_everything_when_pool_is_small() -> None:
    assert allocate(75, [10, 20]) == [10, 20]


def test_allocate_breaks_ties_by_position() -> None:
    assert allocate(2, [1, 1, 1]) == [1, 1, 0]
