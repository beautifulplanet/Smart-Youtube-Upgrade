import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from types import SimpleNamespace
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        # Note: api_quota intentionally removed from public endpoint (security finding #17)

    @pytest.mark.asyncio
    async def test_health_has_security_headers(self, client):
        response = await client.get("/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"


class TestAnalyzeEndpoint:
    def _make_fetcher_mock(self, title="Test", description="", channel="Ch", tags=None):
        mock_instance = AsyncMock()
        mock_instance.get_video_metadata.return_value = SimpleNamespace(
            title=title, description=description,
            channel=channel, tags=tags or [], category="22",
        )
        mock_instance.get_comments.return_value = []
        mock_class = MagicMock()
        mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_class.return_value.__aexit__ = AsyncMock(return_value=False)
        return mock_class

    @pytest.mark.asyncio
    async def test_analyze_valid_video(self, client):
        mock_class = self._make_fetcher_mock(title="Safe Video")
        mock_segment = MagicMock()
        mock_segment.text = "This is a safe transcript."

        with patch("analyzer.YouTubeDataFetcher", mock_class):
            with patch("analyzer.YouTubeTranscriptApi") as MockTranscript:
                mock_api = MockTranscript.return_value
                mock_api.fetch.return_value = [mock_segment]

                response = await client.post("/analyze", json={
                    "video_id": "dQw4w9WgXcQ",
                    "title": "Safe Video",
                    "channel": "TestChannel",
                })

                assert response.status_code == 200
                data = response.json()
                assert "safety_score" in data
                assert "warnings" in data
                assert "categories" in data
                assert "summary" in data
                assert data["video_id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_analyze_invalid_video_id(self, client):
        response = await client.post("/analyze", json={"video_id": "invalid!"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_empty_video_id(self, client):
        response = await client.post("/analyze", json={"video_id": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_missing_video_id(self, client):
        response = await client.post("/analyze", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_analyze_response_shape(self, client):
        mock_class = self._make_fetcher_mock()
        with patch("analyzer.YouTubeDataFetcher", mock_class):
            with patch("analyzer.YouTubeTranscriptApi") as MockTranscript:
                mock_api = MockTranscript.return_value
                mock_api.fetch.side_effect = Exception("No transcript")

                response = await client.post("/analyze", json={
                    "video_id": "dQw4w9WgXcQ",
                })

                assert response.status_code == 200
                data = response.json()
                assert isinstance(data["safety_score"], int)
                assert isinstance(data["warnings"], list)
                assert isinstance(data["categories"], dict)
                assert isinstance(data["transcript_available"], bool)


class TestSignaturesEndpoint:
    @pytest.mark.asyncio
    async def test_get_signatures(self, client):
        response = await client.get("/signatures")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_categories(self, client):
        response = await client.get("/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)


class TestInputValidation:
    @pytest.mark.asyncio
    async def test_video_id_sql_injection(self, client):
        response = await client.post("/analyze", json={
            "video_id": "'; DROP TABLE--"
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_video_id_xss(self, client):
        response = await client.post("/analyze", json={
            "video_id": "<script>alert(1)</script>"
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_title_truncated(self, client):
        """Titles over max_length should be rejected by Pydantic."""
        long_title = "A" * 501
        response = await client.post("/analyze", json={
            "video_id": "dQw4w9WgXcQ",
            "title": long_title,
        })
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_oversized_description_truncated(self, client):
        long_desc = "B" * 5001
        response = await client.post("/analyze", json={
            "video_id": "dQw4w9WgXcQ",
            "description": long_desc,
        })
        assert response.status_code == 422
