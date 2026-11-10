"""E1 (v7.3 engine speed): the same generalized-winding inside test, split across threads.

Profiling 12 recorded checks of v7.2 retry 05902/first_B (110 s) put 82 % of the time in
disassembly_real_v3.source_collision._winding_inside (per point: solid angle of every
triangle; arctan2-bound). Measured on 2,220 captured calls / 150k points (05902 + 06146):
stacking points alone was bitwise identical but not faster (54.4 s -> 51.2 s); per-point
threads alone gave 2.0x at 4 threads (GIL-bound); stacked blocks of <= 64k point x triangle
elements split over 6 threads gave 4.7x (54.9 s -> 11.7 s) with identical decisions.
Points are independent and each row keeps the v3 per-point arithmetic order, so every
winding value is bitwise identical (max |diff| 0.0 on all captured points).
The preserved v3 file is not edited; `install()` swaps the module-level function that
signed_material_distance calls. Acceptance rule (fixed before use): every recorded
v7.1/v7.2 episode must replay with an identical trace (replay_verify), otherwise E1 is
dropped. Applied identically to A, B and C.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import os

import numpy as np

from disassembly_real_v3 import source_collision as sc

ORIGINAL = sc._winding_inside
ELEMENT_BUDGET = 64_000      # points x triangles per stacked block (cache-sized)
THREADS = int(os.environ.get('V73_GEOMETRY_THREADS', '6'))   # performance cores on the evaluation machine
MIN_POINTS_PER_THREAD = 4
_POOL = None


def _stacked_values(triangles, points):
    """Winding numbers of a block of points; each row is the v3 per-point arithmetic."""
    out = np.empty(len(points))
    step = max(1, ELEMENT_BUDGET // max(1, len(triangles)))
    for start in range(0, len(points), step):
        t = triangles[None] - points[start:start + step, None, None, :]
        a, b, c = t[:, :, 0], t[:, :, 1], t[:, :, 2]
        la, lb, lc = np.linalg.norm(a, axis=2), np.linalg.norm(b, axis=2), np.linalg.norm(c, axis=2)
        numerator = np.einsum('ptj,ptj->pt', a, np.cross(b, c))
        denominator = (la*lb*lc + np.einsum('ptj,ptj->pt', a, b)*lc
                       + np.einsum('ptj,ptj->pt', b, c)*la + np.einsum('ptj,ptj->pt', c, a)*lb)
        out[start:start + step] = np.sum(2*np.arctan2(numerator, denominator), axis=1)/(4*np.pi)
    return out


def threaded_winding_inside(mesh, points):
    global _POOL
    triangles = np.asarray(mesh.triangles)      # resolved once, in the calling thread
    points = np.asarray(points, dtype=float)
    if len(points) == 0:
        return np.asarray([], dtype=bool)
    blocks = min(THREADS, len(points) // MIN_POINTS_PER_THREAD)
    if blocks <= 1:
        return np.abs(_stacked_values(triangles, points)) > .5
    if _POOL is None:
        _POOL = ThreadPoolExecutor(THREADS, thread_name_prefix='winding')
    values = np.concatenate(list(_POOL.map(lambda p: _stacked_values(triangles, p), np.array_split(points, blocks))))
    return np.abs(values) > .5


def winding_values(mesh, points):
    """Raw winding numbers of the E1 computation (equality tests)."""
    return _stacked_values(np.asarray(mesh.triangles), np.asarray(points, dtype=float))


def original_winding_values(mesh, points):
    """The v3 per-point loop, returning the float winding instead of the boolean (test helper)."""
    triangles = np.asarray(mesh.triangles)
    answer = []
    for point in np.asarray(points):
        t = triangles-point
        a, b, c = t[:, 0], t[:, 1], t[:, 2]
        la, lb, lc = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1), np.linalg.norm(c, axis=1)
        numerator = np.einsum('ij,ij->i', a, np.cross(b, c))
        denominator = (la*lb*lc + np.einsum('ij,ij->i', a, b)*lc
                       + np.einsum('ij,ij->i', b, c)*la + np.einsum('ij,ij->i', c, a)*lb)
        answer.append(float(np.sum(2*np.arctan2(numerator, denominator))/(4*np.pi)))
    return np.asarray(answer)


def install(enabled=True):
    sc._winding_inside = threaded_winding_inside if enabled else ORIGINAL
    return enabled
