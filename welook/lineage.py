"""Stable identity for the immutable source-file set behind a snapshot."""

import hashlib


def source_registry_hash(source_ids) -> str:
    values = sorted(set(source_ids))
    if not values:
        raise ValueError("At least one source file is required")
    return hashlib.sha256("\n".join(values).encode()).hexdigest()
