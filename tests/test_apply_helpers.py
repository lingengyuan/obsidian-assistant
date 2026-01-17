from __future__ import annotations

from oka.core.apply import (
    append_anchor_block,
    apply_frontmatter_fields,
    remove_anchor_block,
    remove_frontmatter_keys,
)


def test_anchor_block_insert_and_remove() -> None:
    content = "# Note\n\nBody\n"
    block = "## Related\n<!-- oka_related_v1 -->\n- [[beta]] (0.50)\n"
    updated, changed = append_anchor_block(content, "oka_related_v1", block)
    assert changed is True
    assert "oka_related_v1" in updated

    repeat, changed_repeat = append_anchor_block(updated, "oka_related_v1", block)
    assert changed_repeat is False
    assert repeat.count("oka_related_v1") == 1

    removed, removed_flag = remove_anchor_block(updated, "oka_related_v1")
    assert removed_flag is True
    assert "oka_related_v1" not in removed


def test_frontmatter_add_and_remove() -> None:
    content = "# Note\n\nBody\n"
    fields = {"keywords": ["alpha", "beta"], "related": ["gamma"]}
    updated, inserted = apply_frontmatter_fields(content, fields)
    assert "keywords" in inserted
    assert "related" in inserted
    assert updated.startswith("---")

    removed, removed_keys = remove_frontmatter_keys(updated, inserted)
    assert set(removed_keys) == set(inserted)
    assert "keywords" not in removed
    assert "related" not in removed
