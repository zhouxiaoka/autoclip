"""Regression tests for 1.5.9-rc dual-platform QA acceptance findings (07a83512).

Covers:
1. cover_brief.choose_copy preserves translated cross-language cover titles
   (e.g., Chinese title on an English-speech source clip) instead of replacing
   them with an untranslated English subtitle sentence.
"""
from __future__ import annotations

from backend.services import cover_brief as cb


def test_choose_copy_keeps_translated_cross_language_title():
    en_rows = [
        {"start": 0.0, "end": 14.48, "text": "I mean, you mentioned pre-training. We over-diversified on product."},
        {"start": 14.4, "end": 45.04, "text": "We need to refocus on the core model."},
    ]
    zh_title = "奥特曼复盘：做浏览器和Sora拖慢了OpenAI"
    assert cb.choose_copy(zh_title, en_rows, False) == zh_title

    zh_rows = [
        {"start": 0.0, "end": 10.0, "text": "过去十二个月我们在产品上确实想做太多了。"},
    ]
    en_title = "Why we over-diversified our product"
    assert cb.choose_copy(en_title, zh_rows, False) == en_title

    # Same-language automatic extraction continues to pick the best literal sentence.
    assert cb.choose_copy("Over-diversified product", en_rows, False) == "We over-diversified on product."
