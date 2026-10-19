"""Lossless bounded JSON values for executable skill state, never log summaries.

The same trusted transport is used for B and C. Accepted objects retain every
key, value and list order. Oversized or non-JSON values raise before publication;
there is no pruning, sentinel insertion, key coercion or partial replacement.
Transport work is host infrastructure, not stored-procedure opcodes. Its elapsed
time remains inside the common episode deadline. These limits do not raise any
planner, physics, model-call, checkpoint or per-skill execution allowance.
"""
from __future__ import annotations

import json
import hashlib
import math

MAX_DEPTH = 128
MAX_NODES = 250_000
MAX_BYTES = 8 * 1024 * 1024
MAX_STRING_BYTES = 1024 * 1024
MAX_INTEGER = (1 << 53) - 1


class MemoryTransportError(ValueError):
    """The state is not an exact supported JSON tree."""


class MemoryTransportLimit(MemoryTransportError):
    """An explicit transport guard rejected the complete proposed update."""


def clone_json(value, *, max_depth=MAX_DEPTH, max_nodes=MAX_NODES,
               max_bytes=MAX_BYTES, max_string_bytes=MAX_STRING_BYTES, with_metadata=False):
    """Return an independent exact JSON tree, or raise without mutating value.

    Shared acyclic references are copied independently, as JSON would do. Actual
    cycles are rejected. Exact builtin types prevent subclass behavior from
    running at this boundary. Dict keys must already be strings; tuples, sets,
    nonfinite floats and integers outside the interoperable exact range reject.
    """
    for name, limit in (("max_depth", max_depth), ("max_nodes", max_nodes),
                        ("max_bytes", max_bytes), ("max_string_bytes", max_string_bytes)):
        if type(limit) is not int or limit < 1:
            raise ValueError(name + " must be a positive integer")
    nodes = 0
    deepest = 0
    encoded_bytes = 0
    active = set()

    def consume(size):
        nonlocal encoded_bytes
        encoded_bytes += size
        if encoded_bytes > max_bytes:
            raise MemoryTransportLimit("state JSON byte limit exceeded")

    def string_size(item):
        try:
            size = len(item.encode("utf-8"))
        except UnicodeEncodeError as exc:
            raise MemoryTransportError("state string is not valid UTF-8") from exc
        if size > max_string_bytes:
            raise MemoryTransportLimit("state string byte limit exceeded")
        # Account escaped JSON bytes while visiting, before constructing a full
        # large clone/encoding. Each temporary string is independently bounded.
        consume(len(json.dumps(item, ensure_ascii=False).encode('utf-8')))

    def visit(item, depth):
        nonlocal nodes, deepest
        deepest = max(deepest, depth)
        nodes += 1
        if nodes > max_nodes:
            raise MemoryTransportLimit("state node limit exceeded")
        if depth > max_depth:
            raise MemoryTransportLimit("state depth limit exceeded")
        kind = type(item)
        if item is None or kind is bool:
            consume(4 if item is None or item is True else 5)
            return item
        if kind is str:
            string_size(item)
            return item
        if kind is int:
            if abs(item) > MAX_INTEGER:
                raise MemoryTransportError("state integer exceeds exact JSON range")
            consume(len(str(item)))
            return item
        if kind is float:
            if not math.isfinite(item):
                raise MemoryTransportError("state float must be finite")
            consume(len(json.dumps(item, allow_nan=False)))
            return item
        if kind not in (dict, list):
            raise MemoryTransportError("unsupported state value type: " + kind.__name__)
        identity = id(item)
        if identity in active:
            raise MemoryTransportError("state contains a cycle")
        active.add(identity)
        try:
            consume(2 + max(0, len(item) - 1))  # braces/brackets and commas
            if kind is list:
                return [visit(child, depth + 1) for child in item]
            result = {}
            for key, child in item.items():
                if type(key) is not str:
                    raise MemoryTransportError("state dictionary keys must be strings")
                string_size(key)
                consume(1)  # colon
                result[key] = visit(child, depth + 1)
            return result
        finally:
            active.remove(identity)

    result = visit(value, 0)
    # Encoding proves a complete, finite UTF-8 JSON representation. The bound is
    # checked before a state update is committed, never used to slice its bytes.
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    if len(encoded) != encoded_bytes:
        raise MemoryTransportError("state JSON byte accounting mismatch")
    if len(encoded) > max_bytes:
        raise MemoryTransportLimit("state JSON byte limit exceeded")
    if with_metadata:
        return result, {"sha256": hashlib.sha256(encoded).hexdigest(),
                        "bytes": len(encoded), "nodes": nodes, "depth": deepest,
                        "encoding": "UTF-8 compact insertion-order JSON", "lossless": True}
    return result


def clone_skill_state(value, *, with_metadata=False):
    """Validate/copy an optional empty or nonempty episode-local memory dict."""
    if value is None:
        value = {}
    if type(value) is not dict:
        raise MemoryTransportError("skill state must be a dictionary")
    return clone_json(value, with_metadata=with_metadata)
