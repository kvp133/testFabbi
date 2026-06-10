"""Cache key & invalidation tests."""

import uuid

from app.api.v1.todos import (
    todos_list_cache_key,
    todos_user_cache_pattern,
)


def test_cache_key_is_scoped_per_user():
    """Two users on the same page must produce different cache keys."""
    user_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    user_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    assert todos_list_cache_key(user_a, 1, 20) != todos_list_cache_key(user_b, 1, 20)


def test_cache_key_is_scoped_per_page():
    """Different pagination windows must not collide."""
    user_id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

    assert todos_list_cache_key(user_id, 1, 20) != todos_list_cache_key(user_id, 2, 20)
    assert todos_list_cache_key(user_id, 1, 20) != todos_list_cache_key(user_id, 1, 50)


def test_invalidation_pattern_matches_only_owners_keys():
    """The glob used for invalidation must include the user's namespace."""
    user_a = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    user_b = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

    pattern = todos_user_cache_pattern(user_a)
    assert str(user_a) in pattern
    assert str(user_b) not in pattern
    assert pattern.endswith("*")
