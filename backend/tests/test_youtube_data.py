import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from youtube_data import (
    YouTubeDataFetcher, VideoMetadata, Comment,
    analyze_comments, MAX_SAFETY_WARNINGS, MAX_AI_WARNINGS,
)


class TestYouTubeDataFetcherContextManager:
    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with YouTubeDataFetcher(api_key="fake-key") as fetcher:
            assert fetcher.api_key == "fake-key"
            assert fetcher.client is not None

    @pytest.mark.asyncio
    async def test_close(self):
        fetcher = YouTubeDataFetcher(api_key="fake-key")
        await fetcher.close()
        # Client should be closed (aclose called)
        assert fetcher.client.is_closed


class TestGetVideoMetadata:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self):
        async with YouTubeDataFetcher(api_key=None) as fetcher:
            result = await fetcher.get_video_metadata("test123")
            assert result is None

    @pytest.mark.asyncio
    async def test_parses_api_response(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [{
                "snippet": {
                    "title": "Test Video",
                    "description": "A description",
                    "channelTitle": "TestChannel",
                    "tags": ["tag1", "tag2"],
                    "categoryId": "22",
                }
            }]
        }

        async with YouTubeDataFetcher(api_key="fake-key") as fetcher:
            with patch.object(fetcher, "_make_request_with_retry", new_callable=AsyncMock, return_value=mock_response):
                result = await fetcher.get_video_metadata("test123")

                assert isinstance(result, VideoMetadata)
                assert result.title == "Test Video"
                assert result.description == "A description"
                assert result.channel == "TestChannel"
                assert result.tags == ["tag1", "tag2"]
                assert result.category == "22"

    @pytest.mark.asyncio
    async def test_empty_items_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}

        async with YouTubeDataFetcher(api_key="fake-key") as fetcher:
            with patch.object(fetcher, "_make_request_with_retry", new_callable=AsyncMock, return_value=mock_response):
                result = await fetcher.get_video_metadata("nonexistent")
                assert result is None

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 403

        async with YouTubeDataFetcher(api_key="fake-key") as fetcher:
            with patch.object(fetcher, "_make_request_with_retry", new_callable=AsyncMock, return_value=mock_response):
                result = await fetcher.get_video_metadata("test123")
                assert result is None


class TestGetComments:
    @pytest.mark.asyncio
    async def test_parses_comment_threads(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "textDisplay": "Great video!",
                                "likeCount": 5,
                                "authorDisplayName": "User1",
                            }
                        }
                    }
                },
                {
                    "snippet": {
                        "topLevelComment": {
                            "snippet": {
                                "textDisplay": "Very informative",
                                "likeCount": 0,
                                "authorDisplayName": "User2",
                            }
                        }
                    }
                },
            ]
        }

        async with YouTubeDataFetcher(api_key="fake-key") as fetcher:
            with patch.object(fetcher, "_make_request_with_retry", new_callable=AsyncMock, return_value=mock_response):
                comments = await fetcher.get_comments("test123")

                assert len(comments) == 2
                assert comments[0].text == "Great video!"
                assert comments[0].likes == 5
                assert comments[0].author == "User1"

    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty(self):
        async with YouTubeDataFetcher(api_key=None) as fetcher:
            comments = await fetcher.get_comments("test123")
            assert comments == []


class TestAnalyzeComments:
    def test_empty_comments(self):
        result = analyze_comments([])
        assert result["total_comments"] == 0
        assert result["warning_comments"] == 0
        assert result["ai_comments"] == 0
        assert result["warning_score"] == 100
        assert result["has_ai_content"] is False

    def test_detects_safety_warnings(self):
        comments = [
            Comment(text="This is dangerous, don't try this at home!", likes=10, author="User1"),
            Comment(text="Could kill someone doing this", likes=5, author="User2"),
        ]
        result = analyze_comments(comments)
        assert result["warning_comments"] >= 1
        assert result["warning_score"] < 100
        assert len(result["warnings"]) >= 1

    def test_detects_ai_content(self):
        comments = [
            Comment(text="This is AI", likes=3, author="User1"),
            Comment(text="Clearly ai generated", likes=8, author="User2"),
            Comment(text="Made with AI", likes=1, author="User3"),
        ]
        result = analyze_comments(comments)
        assert result["has_ai_content"] is True
        assert result["ai_comments"] >= 1
        ai_warnings = [w for w in result["warnings"] if w["category"] == "AI Content"]
        assert len(ai_warnings) >= 1

    def test_safe_comments_no_warnings(self):
        comments = [
            Comment(text="Great video, very helpful!", likes=5, author="User1"),
            Comment(text="Thanks for sharing this", likes=2, author="User2"),
            Comment(text="I learned a lot from this", likes=0, author="User3"),
        ]
        result = analyze_comments(comments)
        assert result["warning_comments"] == 0
        assert result["ai_comments"] == 0
        assert result["warning_score"] == 100
        assert result["has_ai_content"] is False

    def test_max_warnings_respected(self):
        # Create many warning comments that should trigger
        comments = [
            Comment(text=f"This is dangerous attempt {i}", likes=1, author=f"User{i}")
            for i in range(20)
        ]
        result = analyze_comments(comments)
        safety_warnings = [w for w in result["warnings"] if w["category"] == "Community Warning"]
        assert len(safety_warnings) <= MAX_SAFETY_WARNINGS

    def test_top_concerns_sorted_by_weight(self):
        comments = [
            Comment(text="This is dangerous!", likes=100, author="User1"),
            Comment(text="Could catch fire easily", likes=50, author="User2"),
            Comment(text="Don't try this at home", likes=200, author="User3"),
        ]
        result = analyze_comments(comments)
        if len(result["top_concerns"]) >= 2:
            weights = [c["weight"] for c in result["top_concerns"]]
            assert weights == sorted(weights, reverse=True)

    def test_like_weighting(self):
        # High-like warning should have more weight than low-like
        comments_high = [Comment(text="This is dangerous!", likes=100, author="User1")]
        comments_low = [Comment(text="This is dangerous!", likes=0, author="User1")]

        result_high = analyze_comments(comments_high)
        result_low = analyze_comments(comments_low)

        # Both should detect warnings
        assert result_high["warning_comments"] == 1
        assert result_low["warning_comments"] == 1

        # High-like comment should have higher weight in concerns
        if result_high["top_concerns"] and result_low["top_concerns"]:
            assert result_high["top_concerns"][0]["weight"] > result_low["top_concerns"][0]["weight"]
