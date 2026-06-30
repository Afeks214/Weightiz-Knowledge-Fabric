from pathlib import Path

from wzkf.storage.hashing import canonical_json_hash, sha256_bytes, sha256_text
from wzkf.storage.raw_store import RawStore


def test_hashes_are_stable_and_sensitive_to_tamper():
    assert sha256_text("Limit Order Book") == sha256_text("Limit Order Book")
    assert sha256_text("Limit Order Book") != sha256_text("Market Depth")
    assert sha256_bytes(b"abc") == sha256_text("abc")


def test_canonical_json_hash_is_order_independent():
    left = {"b": 2, "a": ["x", "y"]}
    right = {"a": ["x", "y"], "b": 2}

    assert canonical_json_hash(left) == canonical_json_hash(right)


def test_raw_store_is_content_addressed_and_idempotent(tmp_path: Path):
    store = RawStore(tmp_path)

    first = store.put("doc-1", "html", b"<html>alpha</html>")
    second = store.put("doc-1", "html", b"<html>alpha</html>")
    changed = store.put("doc-1", "html", b"<html>beta</html>")

    assert first.sha256 == second.sha256
    assert first.storage_path == second.storage_path
    assert changed.sha256 != first.sha256
    assert Path(first.storage_path).exists()
