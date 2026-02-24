"""Tests for alternatives_finder.py — safe alternative suggestions engine.

Covers:
- Initialization and config loading
- Animal detection from titles
- Animal-related content detection
- Search query building
- Message generation
- Fallback behavior without API key
- find_safe_alternatives flow (disabled / AI content / danger categories)
- find_ai_tutorials / find_ai_entertainment fallback paths
- search_debunking_videos disabled path
- Singleton factory
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from alternatives_finder import SafeAlternativesFinder, get_alternatives_finder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def finder(monkeypatch):
    """Finder with NO API key (disabled) — tests pure-logic methods."""
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    return SafeAlternativesFinder(api_key=None)


@pytest.fixture
def finder_enabled():
    """Finder with fake API key (enabled) — for testing search paths."""
    return SafeAlternativesFinder(api_key="fake-key-for-testing")


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_disabled_without_api_key(self, finder):
        assert finder.enabled is False

    def test_enabled_with_api_key(self, finder_enabled):
        assert finder_enabled.enabled is True

    def test_loads_config_files(self, finder):
        """Config files should load even without API key."""
        assert isinstance(finder.animal_keywords, dict)
        assert isinstance(finder.safe_search_mappings, dict)
        assert isinstance(finder.trusted_channels, list)
        assert isinstance(finder.fallback_tutorials, list)
        assert isinstance(finder.fallback_entertainment, list)
        assert isinstance(finder.fallback_real_animals, dict)

    def test_fallback_real_videos_populated(self, finder):
        """fallback_real_videos is the 'default' list from fallback_real_animals."""
        assert isinstance(finder.fallback_real_videos, list)


# ---------------------------------------------------------------------------
# Animal detection
# ---------------------------------------------------------------------------

class TestDetectAnimal:
    def test_detects_parrot(self, finder):
        # Only test if the config has parrot keywords
        if "parrot" in finder.animal_keywords:
            result = finder._detect_animal("Amazing Talking Parrot Video")
            assert result == "parrot"

    def test_detects_cat(self, finder):
        if "cat" in finder.animal_keywords:
            result = finder._detect_animal("Funny Cat Compilation")
            assert result == "cat"

    def test_returns_none_for_non_animal(self, finder):
        result = finder._detect_animal("React Programming Tutorial 2024")
        assert result is None

    def test_returns_none_for_empty(self, finder):
        assert finder._detect_animal("") is None
        assert finder._detect_animal(None) is None


class TestIsAnimalRelated:
    @pytest.mark.parametrize("title", [
        "Cute puppy videos", "Lion documentary", "Zoo animals",
        "Wildlife safari", "Pet care tips", "Shark attack footage",
    ])
    def test_animal_titles_detected(self, finder, title):
        assert finder._is_animal_related(title) is True

    @pytest.mark.parametrize("title", [
        "JavaScript tutorial", "Cooking pasta recipe",
        "How to fix plumbing", "Stock market analysis",
    ])
    def test_non_animal_titles_not_detected(self, finder, title):
        assert finder._is_animal_related(title) is False


# ---------------------------------------------------------------------------
# Search query building
# ---------------------------------------------------------------------------

class TestBuildAnimalSearches:
    def test_returns_list(self, finder):
        result = finder._build_animal_searches("parrot")
        assert isinstance(result, list)
        assert len(result) > 0

    def test_respects_max_queries(self, finder):
        result = finder._build_animal_searches("dog", max_queries=3)
        assert len(result) <= 3

    def test_includes_bbc_and_natgeo(self, finder):
        result = finder._build_animal_searches("lion")
        combined = " ".join(result).lower()
        assert "bbc" in combined
        assert "national geographic" in combined


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class TestGetMessage:
    def test_zero_count(self, finder):
        msg = finder._get_message("real_animals", 0)
        assert "no alternatives" in msg.lower()

    def test_real_animals_with_animal(self, finder):
        msg = finder._get_message("real_animals", 5, "parrot")
        assert "Parrot" in msg
        assert "5" in msg

    def test_safe_tutorial(self, finder):
        msg = finder._get_message("safe_tutorial", 3)
        assert "3" in msg
        assert "safer" in msg.lower() or "professional" in msg.lower()

    def test_unknown_category_uses_default(self, finder):
        msg = finder._get_message("unknown_xyz", 2)
        assert "2" in msg


# ---------------------------------------------------------------------------
# Disabled paths (no API key)
# ---------------------------------------------------------------------------

class TestDisabledPaths:
    @pytest.mark.asyncio
    async def test_find_safe_alternatives_disabled(self, finder):
        result = await finder.find_safe_alternatives(["medical"])
        assert result["enabled"] is False
        assert result["alternatives"] == []

    @pytest.mark.asyncio
    async def test_find_real_animal_videos_disabled(self, finder):
        result = await finder.find_real_animal_videos()
        assert result["enabled"] is False

    @pytest.mark.asyncio
    async def test_search_debunking_videos_disabled(self, finder):
        result = await finder.search_debunking_videos(["flat earth debunked"])
        assert result["enabled"] is False
        assert result["category_type"] == "debunking"

    @pytest.mark.asyncio
    async def test_find_ai_tutorials_returns_fallback(self, finder):
        result = await finder.find_ai_tutorials()
        assert result["enabled"] is True
        assert result["category_type"] == "ai_tutorials"
        # Should return fallback list (may be empty if config file is empty)
        assert isinstance(result["alternatives"], list)

    @pytest.mark.asyncio
    async def test_find_ai_entertainment_returns_fallback(self, finder):
        result = await finder.find_ai_entertainment()
        assert result["enabled"] is True
        assert result["category_type"] == "ai_entertainment"
        assert isinstance(result["alternatives"], list)


# ---------------------------------------------------------------------------
# Enabled paths with mocked YouTube API
# ---------------------------------------------------------------------------

class TestEnabledPaths:
    def _mock_search(self, videos=None):
        """Create an async mock for _search_youtube."""
        if videos is None:
            videos = [{
                "id": "abc12345678",
                "title": "Safe Test Video",
                "channel": "Test Channel",
                "thumbnail": "https://img.youtube.com/vi/abc12345678/mqdefault.jpg",
                "description": "A safe video",
                "url": "https://www.youtube.com/watch?v=abc12345678",
                "is_trusted": False,
                "badge": "📚 Educational",
            }]
        return AsyncMock(return_value=videos)

    @pytest.mark.asyncio
    async def test_find_safe_alternatives_ai_content(self, finder_enabled):
        with patch.object(finder_enabled, "_search_youtube", self._mock_search()):
            result = await finder_enabled.find_safe_alternatives(
                danger_categories=[],
                original_title="Talking Parrot Amazing Video",
                is_ai_content=True,
            )
            assert result["enabled"] is True
            assert isinstance(result["alternatives"], list)

    @pytest.mark.asyncio
    async def test_find_safe_alternatives_danger_categories(self, finder_enabled):
        with patch.object(finder_enabled, "_search_youtube", self._mock_search()):
            result = await finder_enabled.find_safe_alternatives(
                danger_categories=["medical", "cooking"],
                original_title="Cure Cancer with Bleach",
            )
            assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_find_safe_alternatives_no_categories(self, finder_enabled):
        result = await finder_enabled.find_safe_alternatives(
            danger_categories=[],
            original_title="Normal Video",
            is_ai_content=False,
        )
        assert result["enabled"] is True
        assert result["alternatives"] == []

    @pytest.mark.asyncio
    async def test_search_deduplicates_by_id(self, finder_enabled):
        """Same video from multiple queries should appear only once."""
        same_video = [{
            "id": "DUPLICATE_ID1",
            "title": "Duplicate",
            "channel": "Ch",
            "thumbnail": "",
            "description": "",
            "url": "https://www.youtube.com/watch?v=DUPLICATE_ID1",
            "is_trusted": False,
            "badge": "📚 Educational",
        }]
        with patch.object(finder_enabled, "_search_youtube", AsyncMock(return_value=same_video)):
            result = await finder_enabled.find_safe_alternatives(
                danger_categories=["medical"],
                original_title="Miracle Cure",
            )
            ids = [v["id"] for v in result["alternatives"]]
            assert len(ids) == len(set(ids)), "Duplicate video IDs found"

    @pytest.mark.asyncio
    async def test_search_error_fallback(self, finder_enabled):
        """Search errors should be caught — not crash."""
        with patch.object(finder_enabled, "_search_youtube", AsyncMock(side_effect=Exception("API down"))):
            result = await finder_enabled.find_safe_alternatives(
                danger_categories=["medical"],
                original_title="Test",
            )
            assert result["enabled"] is True
            # May have 0 results but should not raise


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_alternatives_finder_returns_instance(self):
        instance = get_alternatives_finder()
        assert isinstance(instance, SafeAlternativesFinder)

    def test_singleton_returns_same_instance(self):
        a = get_alternatives_finder()
        b = get_alternatives_finder()
        assert a is b
