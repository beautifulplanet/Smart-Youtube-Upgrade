import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from types import SimpleNamespace
from analyzer import SafetyAnalyzer
from safety_db import SafetyDatabase


@pytest.fixture
def mock_safety_db():
    db = MagicMock(spec=SafetyDatabase)
    db.signatures = []
    db.get_all_signatures.return_value = []
    db.categories = {}
    return db


@pytest.fixture
def analyzer(mock_safety_db):
    return SafetyAnalyzer(mock_safety_db)


def _make_fetcher_mock(title="Safe Video", description="", channel="TestChannel", tags=None):
    """Create a properly mocked YouTubeDataFetcher that supports async with."""
    mock_instance = AsyncMock()
    mock_instance.get_video_metadata.return_value = SimpleNamespace(
        title=title,
        description=description,
        channel=channel,
        tags=tags or [],
    )
    mock_instance.get_comments.return_value = []

    # Support `async with YouTubeDataFetcher(...) as fetcher:`
    mock_class = MagicMock()
    mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
    mock_class.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_class, mock_instance


class TestSafetyAnalyzerPatterns:
    @pytest.fixture(autouse=True)
    def setup(self, analyzer):
        self.analyzer = analyzer

    def test_impossible_content_detection(self):
        # AI trope: animals talking/conversing
        assert self.analyzer._detect_impossible_content("Two parrots having a political debate") is not None
        assert self.analyzer._detect_impossible_content("Cat and dog talking to each other") is not None

        # AI trope: animals doing human jobs
        assert self.analyzer._detect_impossible_content("My cat is a lawyer now") is not None
        assert self.analyzer._detect_impossible_content("Dog driving a car to work") is not None

        # AI trope: animals ordering things
        assert self.analyzer._detect_impossible_content("Parrot ordering pizza on doordash") is not None

        # Normal content should not trigger
        assert self.analyzer._detect_impossible_content("Cute cat playing with yarn") is None
        assert self.analyzer._detect_impossible_content("Training my dog to sit") is None

    def test_dangerous_animal_child_detection(self):
        # Dangerous: Baby with large bird
        assert self.analyzer._detect_dangerous_animal_child("Baby sleeping with my macaw") is not None

        # Dangerous: Baby with large dog unsupervised
        assert self.analyzer._detect_dangerous_animal_child("Pitbull watching over sleeping baby") is not None

        # Dangerous: Child with exotic animal
        assert self.analyzer._detect_dangerous_animal_child("My toddler playing with 5ft python") is not None

        # Safe-ish content
        assert self.analyzer._detect_dangerous_animal_child("Kid feeding ducks at park") is None


class TestSafetyAnalyzerFlow:
    @pytest.fixture(autouse=True)
    def setup(self):
        mock_db = MagicMock(spec=SafetyDatabase)
        mock_db.get_all_signatures.return_value = []
        mock_db.categories = {}
        self.analyzer = SafetyAnalyzer(mock_db)

    @pytest.mark.asyncio
    async def test_analyze_flow_safe(self):
        mock_class, _ = _make_fetcher_mock(
            title="Safe Video",
            description="Just a safe video",
            channel="SafeChannel",
            tags=["safe", "video"],
        )

        with patch("analyzer.YouTubeDataFetcher", mock_class):
            with patch("analyzer.YouTubeTranscriptApi") as MockTranscriptApi:
                mock_api_instance = MockTranscriptApi.return_value
                mock_segment = MagicMock()
                mock_segment.text = "This is a safe video transcript content."
                mock_api_instance.fetch.return_value = [mock_segment]

                result = await self.analyzer.analyze("safe_id_123")

                assert result["safety_score"] >= 90
                assert len(result["warnings"]) == 0

    @pytest.mark.asyncio
    async def test_analyze_flow_dangerous(self):
        mock_class, _ = _make_fetcher_mock(
            title="Baby playing with cobra",
            description="So cute",
            channel="WildChannel",
            tags=["snake", "baby"],
        )

        with patch("analyzer.YouTubeDataFetcher", mock_class):
            with patch("analyzer.YouTubeTranscriptApi") as MockTranscriptApi:
                mock_api_instance = MockTranscriptApi.return_value
                mock_api_instance.fetch.side_effect = Exception("No transcript")

                result = await self.analyzer.analyze("danger_id_123")

                # Should have low score due to dangerous pattern
                assert result["safety_score"] < 90

    @pytest.mark.asyncio
    async def test_trusted_channel_skips_ai_warnings(self):
        """Trusted channels should not trigger AI content warnings."""
        mock_class, _ = _make_fetcher_mock(
            title="Cat driving a car",
            description="Funny video",
            channel="National Geographic",
            tags=[],
        )

        with patch("analyzer.YouTubeDataFetcher", mock_class):
            with patch("analyzer.YouTubeTranscriptApi") as MockTranscriptApi:
                mock_api_instance = MockTranscriptApi.return_value
                mock_api_instance.fetch.side_effect = Exception("No transcript")

                result = await self.analyzer.analyze("trusted_id_123")

                # Trusted channels should not flag AI content
                ai_warnings = [w for w in result["warnings"] if w.get("category") == "AI Content"]
                assert len(ai_warnings) == 0

    @pytest.mark.asyncio
    async def test_no_api_key_uses_scraped_data(self):
        """When no API key, analyzer should use scraped metadata."""
        mock_class, _ = _make_fetcher_mock()

        with patch("analyzer.YouTubeDataFetcher", mock_class):
            with patch("analyzer.YouTubeTranscriptApi") as MockTranscriptApi:
                mock_api_instance = MockTranscriptApi.return_value
                mock_api_instance.fetch.side_effect = Exception("No transcript")

                result = await self.analyzer.analyze(
                    "test_id",
                    scraped_title="My test video",
                    scraped_channel="TestChannel",
                )

                assert "safety_score" in result
                assert "warnings" in result
