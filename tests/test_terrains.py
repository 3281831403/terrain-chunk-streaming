import pytest

from stream.terrains import (
    StreamError,
    adopt,
    budget_check,
    plan_stream,
    prioritize,
    ring_resident,
    select_lod,
    stall_frames,
    stream_batch,
)


def _chunk(cx, cz, lod=0, size=1, loaded=False):
    return {
        "cx": cx,
        "cz": cz,
        "lod": lod,
        "size": size,
        "loaded": loaded,
    }


def _coords(chunks):
    return [(chunk["cx"], chunk["cz"]) for chunk in chunks]


# 缺陷 1：驻留按矩形而不是环，角落超载。
def test_ring_resident_excludes_rectangle_corners():
    cells = ring_resident((0, 0), 2, 0)

    assert len(cells) == 21
    assert (2, 2) not in cells
    assert (2, 1) in cells


# 缺陷 2：LOD 距离数组无序，选错层级。
def test_select_lod_handles_unsorted_distances():
    lod_distances = [(40, 1), (10, 0), (100, 2)]

    assert select_lod(5, lod_distances) == 0
    assert select_lod(25, lod_distances) == 1
    assert select_lod(80, lod_distances) == 2
    assert select_lod(10_000, lod_distances) == 2


# 缺陷 3：预算只按块数，忽略块大小。
def test_plan_stream_respects_byte_budget():
    requested = [
        _chunk(0, 0, size=60),
        _chunk(1, 0, size=60),
    ]

    plan = plan_stream(requested, [], 100)

    assert len(plan["load"]) == 1
    assert _coords(plan["load"]) == [(0, 0)]
    assert sum(chunk["size"] for chunk in plan["load"]) <= 100


# 缺陷 4：优先队列用 heapq 但元组含 dict，比较抛错。
def test_prioritize_is_stable_with_equal_scores():
    chunks = [
        _chunk(1, 0, lod=0),
        _chunk(0, 1, lod=1),
        _chunk(2, 0, lod=0),
        _chunk(0, 2, lod=0),
    ]

    ordered = prioritize(chunks, (0, 0))

    assert _coords(ordered) == [(1, 0), (0, 1), (2, 0), (0, 2)]


# 缺陷 5：卸载不检查引用计数，正在用的块被释放。
def test_adopt_keeps_referenced_chunks():
    loaded = {(0, 0): 2, (1, 0): 0, (2, 0): 1}
    incoming = [_chunk(0, 0), _chunk(3, 0)]

    result = adopt(incoming, loaded)

    assert _coords(result["adopted"]) == [(0, 0), (3, 0)]
    assert set(result["unloaded"]) == {(1, 0)}
    assert dict(result["retained"]) == {(2, 0): 1}


# 缺陷 6：重复块不去重，同一块加载两次。
def test_plan_stream_deduplicates_requested_chunks():
    requested = [
        _chunk(0, 0, lod=0, size=10),
        _chunk(0, 0, lod=1, size=10),
        _chunk(1, 0, lod=0, size=10),
    ]

    plan = plan_stream(requested, [], 100)

    assert len(plan["load"]) == 2
    assert _coords(plan["load"]) == [(0, 0), (1, 0)]
    assert plan["load"][0]["lod"] == 0


# 缺陷 7：LOD 跳跃不检测，出现空洞。
def test_budget_check_detects_lod_jump():
    load = [
        _chunk(0, 0, lod=0, size=10),
        _chunk(1, 0, lod=3, size=10),
    ]

    issues = budget_check(load, 100)

    assert any(issue.startswith("lod_jump") for issue in issues)


# 缺陷 8：加载帧数向下取整，永远差一帧。
def test_stall_frames_rounds_up():
    load = [
        _chunk(0, 0, size=90),
        _chunk(1, 0, size=60),
    ]

    assert stall_frames(load, 100) == 2


# 缺陷 9：批量共用驻留集合，帧之间串；并验证非法帧整体回滚。
def test_stream_batch_isolates_frames_and_rolls_back():
    config = {"budget": 100, "resident": []}
    frames = [
        [_chunk(0, 0)],
        [_chunk(5, 0)],
    ]

    batch = stream_batch(frames, config)

    assert batch["committed"] is True
    assert len(batch["plans"]) == 2
    assert batch["plans"][1]["unload"] == []
    assert _coords(batch["plans"][1]["load"]) == [(5, 0)]

    invalid_frames = [
        [_chunk(0, 0)],
        [_chunk(10, 0, lod=0), _chunk(11, 0, lod=2)],
    ]

    rolled_back = stream_batch(invalid_frames, config)

    assert rolled_back["committed"] is False
    assert rolled_back["plans"] == []
    assert rolled_back["error"]


# 缺陷 10：radius=0 不校验，返回空集导致除零。
def test_ring_resident_rejects_zero_radius():
    with pytest.raises(StreamError):
        ring_resident((0, 0), 0, 0)


def test_ring_radius_one_returns_nine_chunks():
    cells = set(ring_resident((0, 0), 1, 0))
    expected = {(cx, cz) for cx in (-1, 0, 1) for cz in (-1, 0, 1)}

    assert len(cells) == 9
    assert cells == expected


def test_plan_stream_exact_budget_loads_all():
    requested = [
        _chunk(0, 0, size=40),
        _chunk(1, 0, size=60),
    ]

    plan = plan_stream(requested, [], 100)

    assert len(plan["load"]) == 2
    assert sum(chunk["size"] for chunk in plan["load"]) == 100


def test_empty_request_returns_empty_plan():
    assert plan_stream([], [], 100) == {"load": [], "unload": []}


def test_negative_radius_raises_stream_error():
    with pytest.raises(StreamError):
        ring_resident((0, 0), -1, 0)


def test_stream_batch_success_preserves_frame_order():
    frames = [
        [_chunk(2, 0)],
        [_chunk(0, 0)],
        [_chunk(1, 0)],
    ]

    batch = stream_batch(frames, {"budget": 100, "resident": []})

    assert batch["committed"] is True
    assert len(batch["plans"]) == 3
    assert [_coords(plan["load"])[0] for plan in batch["plans"]] == [
        (2, 0),
        (0, 0),
        (1, 0),
    ]
