"""Offline unit tests — no network / credentials required."""

import pytest

from higgsfield_unlimited_mcp import dimensions, models
from higgsfield_unlimited_mcp.client import (
    extract_job_id,
    extract_result_urls,
    normalize_status,
)


def test_model_counts_match_readme():
    counts = models.category_counts()
    assert counts["image"] == 32
    assert counts["video"] == 31
    assert counts["audio"] == 1


def test_registry_lookup():
    assert models.is_known("nano-banana-2")
    assert models.get_model("veo3-1").category == "video"
    assert not models.is_known("does-not-exist")


@pytest.mark.parametrize(
    "ar,res",
    [("16:9", "2k"), ("9:16", "4k"), ("1:1", "1k"), ("21:9", "2k")],
)
def test_dimensions_are_multiples_of_32(ar, res):
    w, h = dimensions.get_dimensions(ar, res)
    assert w % 32 == 0 and h % 32 == 0
    assert w > 0 and h > 0


def test_dimensions_reject_unknown():
    with pytest.raises(ValueError):
        dimensions.get_dimensions("7:3", "2k")
    with pytest.raises(ValueError):
        dimensions.get_dimensions("16:9", "8k")


def test_extract_job_id_variants():
    assert extract_job_id({"id": "abc"}) == "abc"
    assert extract_job_id({"job_id": "xyz"}) == "xyz"
    assert extract_job_id({"job": {"uuid": "u1"}}) == "u1"
    assert extract_job_id({"data": {"id": 42}}) == "42"
    assert extract_job_id({"nothing": 1}) is None


def test_normalize_status():
    assert normalize_status({"status": "succeeded"}) == "completed"
    assert normalize_status({"state": "in_progress"}) == "running"
    assert normalize_status({"status": "queued"}) == "queued"
    assert normalize_status({"job": {"status": "failed"}}) == "failed"


def test_extract_result_urls_dedup():
    payload = {
        "results": [
            {"url": "https://cdn/x.png"},
            {"image_url": "https://cdn/y.png"},
        ],
        "extra": {"url": "https://cdn/x.png"},  # duplicate
    }
    urls = [r["url"] for r in extract_result_urls(payload)]
    assert urls == ["https://cdn/x.png", "https://cdn/y.png"]
