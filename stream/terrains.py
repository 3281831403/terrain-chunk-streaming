"""Terrain chunk streaming contracts.

Chunk dictionaries always have exactly these five keys::

    {"cx": int, "cz": int, "lod": int, "size": int, "loaded": bool}

``cx``/``cz`` are integer chunk coordinates (not world coordinates).
``lod`` is a non-negative level where 0 is the finest level and larger values
are coarser. ``size`` is the resident cost in bytes. ``loaded`` says whether
the chunk is currently resident.
"""

import heapq
import math


class StreamError(Exception):
    """Raised when a streaming request or its configuration is invalid."""


def ring_resident(center, radius, lod):
    """Return sorted chunk coordinates that should be resident around a camera.

    ``center`` is an ``(cx, cz)`` integer pair.

    ``radius`` is the horizontal range in chunks. It must be a positive
    integer; ``radius <= 0`` raises :class:`StreamError`. ``lod`` must be a
    non-negative integer and is validated here, but it does not change the
    horizontal coverage.

    Coverage is a ring-like disk of chunks: a chunk is resident when the
    Euclidean distance between its center and ``center`` is at most
    ``radius + 0.5`` chunks. The half-chunk margin is the one-chunk corner
    tolerance (容差 1 块): ``radius == 1`` returns all 9 chunks of the 3x3
    block, while ``radius == 2`` omits the four diagonal corner chunks.

    The result is a list of ``(cx, cz)`` tuples sorted by ``(cz, cx)``.
    """
    raise NotImplementedError


def select_lod(distance, lod_distances):
    """Select an LOD level for a chunk distance.

    ``distance`` is a non-negative distance in chunks. ``lod_distances`` is a
    sequence of ``(max_distance, lod)`` pairs and may be unsorted. A pair
    covers the distance when ``distance <= max_distance``.

    Return the ``lod`` of the covering pair with the smallest
    ``max_distance``; if several pairs have the same ``max_distance``, return
    the smaller ``lod``. When the distance lies beyond every threshold,
    return the maximum ``lod`` present in the table. An empty table or a
    negative distance raises :class:`StreamError`.
    """
    raise NotImplementedError


def plan_stream(requested, resident, budget):
    """Plan one frame's loads and unloads within a byte budget.

    ``requested`` is the desired chunk list for the frame and ``resident`` is
    the currently loaded chunk list. ``budget`` is a non-negative integer
    number of bytes for newly loaded chunks.

    Return exactly ``{"load": [...], "unload": [...]}``. Both lists contain
    chunk dictionaries and must not mutate the input dictionaries.

    * ``load`` contains chunks that are not already resident. Process
      ``requested`` in its original order, keep only the first occurrence of
      each ``(cx, cz)``, and greedily add a chunk only when its ``size`` fits
      in the remaining budget. The sum of ``size`` over ``load`` must not
      exceed ``budget``; chunks that do not fit are skipped.
    * ``unload`` contains resident chunks whose coordinate is absent from the
      deduplicated requested set, in resident order.
    * Chunks in ``load`` have ``loaded=True``; chunks in ``unload`` have
      ``loaded=False``.

    A negative budget raises :class:`StreamError`.
    """
    raise NotImplementedError


def prioritize(chunks, camera):
    """Return chunks ordered by a stable distance/LOD priority.

    ``camera`` is an ``(cx, cz)`` pair. For each chunk compute the Euclidean
    distance in chunks and the score::

        distance * (lod + 1)

    Sort ascending by score, with the original input order as the stable
    tie-breaker. Return a new list and do not mutate ``chunks``. The
    tie-breaker must not compare chunk dictionaries (a common ``heapq``
    failure with equal scores). Negative LOD values raise
    :class:`StreamError`.
    """
    raise NotImplementedError


def adopt(chunks, loaded):
    """Adopt incoming chunks and release only unreferenced old chunks.

    ``chunks`` is the incoming desired chunk list. ``loaded`` maps an old
    resident coordinate ``(cx, cz)`` to its reference count (a non-negative
    integer).

    Incoming chunks are deduplicated by coordinate; the last occurrence
    wins (new replaces old). Old coordinates that also appear in ``chunks``
    are replaced and are not part of the unload list. Old coordinates that
    are absent from ``chunks`` are retained while their reference count is
    greater than 0, and unloaded only when the count is exactly 0.

    Return ``{"adopted": [...], "retained": [...], "unloaded": [...]}``:

    * ``adopted``: deduplicated incoming chunk dictionaries with
      ``loaded=True``, in last-occurrence order;
    * ``retained``: ``(coordinate, refcount)`` pairs for old chunks kept
      because they are still referenced;
    * ``unloaded``: coordinates of old chunks released because their
      reference count was 0.

    Do not mutate either input.
    """
    raise NotImplementedError


def budget_check(load, budget):
    """Return a list of human-readable problems in a proposed load list.

    ``load`` is a chunk list and ``budget`` is a non-negative byte budget.
    Every issue string starts with one of these stable codes followed by a
    colon:

    * ``over_budget``: the sum of ``size`` exceeds ``budget``;
    * ``duplicate``: the same ``(cx, cz)`` occurs more than once;
    * ``lod_jump``: two edge-adjacent chunks (Manhattan distance 1) differ
      in LOD by more than 1, which would leave a terrain hole.

    Return ``[]`` for a clean list. A negative budget raises
    :class:`StreamError`. The function only reports problems; it does not
    modify or deduplicate ``load``.
    """
    raise NotImplementedError


def stall_frames(load, bytes_per_frame):
    """Estimate how many frames loading ``load`` will stall rendering.

    Sum the ``size`` values of the chunks in ``load`` and divide by the
    positive integer ``bytes_per_frame``. Return the ceiling, so any
    remainder still costs a whole frame; an empty load returns 0. A
    non-positive ``bytes_per_frame`` raises :class:`StreamError`.
    """
    raise NotImplementedError


def stream_batch(frames, config):
    """Plan several frames atomically, or roll the whole batch back.

    ``frames`` is a sequence of frames; each frame is a sequence of requested
    chunk dictionaries. ``config`` is a mapping with a non-negative integer
    ``"budget"`` in bytes and an optional ``"resident"`` initial chunk list.

    Every frame is planned independently from the same initial resident
    snapshot; frame N must not see chunks loaded or unloaded by frame N-1
    (no shared resident state between frames). Frame order is preserved.

    A frame is invalid when it is malformed or when ``budget_check`` finds
    any issue in its planned load (for example an LOD jump). If any frame is
    invalid, no frame is committed.

    Return exactly::

        {"committed": True,  "plans": [plan, ...], "error": None}
        {"committed": False, "plans": [],         "error": "<reason>"}

    On success ``plans`` is in input frame order, so batches that succeed
    keep the original order. Block coordinates are integer chunk
    coordinates; a one-chunk boundary tolerance applies when deciding
    whether two blocks are adjacent for the LOD-jump check.
    """
    raise NotImplementedError
