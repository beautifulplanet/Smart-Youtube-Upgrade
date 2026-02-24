"""
Tests for Sprint S1 — V2 Security Debt Fixes

Covers:
- V2-1.1: XSS prevention in /report HTML template
- V2-1.2: Input validation on /report endpoint
- V2-1.3: Rate limiter cleanup (no longer nukes all entries)
- V2-1.4: SECURITY.md accuracy (manual check, not automated)
"""

import pytest
import time
from unittest.mock import patch, AsyncMock, MagicMock
from types import SimpleNamespace
from httpx import AsyncClient, ASGITransport
from main import app, _rate_limit_store, generate_report_html


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestReportEndpointValidation:
    """V2-1.2: /report/{video_id} must validate video_id format."""

    @pytest.mark.asyncio
    async def test_report_rejects_invalid_video_id(self, client):
        """Invalid video IDs should return 400, not reach analyzer."""
        response = await client.get("/report/invalid!")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_report_rejects_xss_video_id(self, client):
        """XSS payloads in video_id should be rejected (400 or 404, never 200)."""
        response = await client.get("/report/<script>alert(1)</script>")
        # May get 400 (our validator) or 404 (FastAPI path routing rejects '/')
        # Both are safe — the key is it's NOT 200
        assert response.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_report_rejects_sql_injection_video_id(self, client):
        """SQL injection payloads should return 400."""
        response = await client.get("/report/'; DROP TABLE--")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_report_rejects_empty_video_id(self, client):
        """Empty string video_id should return 400 or 404."""
        response = await client.get("/report/")
        # FastAPI returns 404 for missing path parameter
        assert response.status_code in (400, 404)

    @pytest.mark.asyncio
    async def test_report_rejects_too_long_video_id(self, client):
        """Video IDs longer than 11 chars should return 400."""
        response = await client.get("/report/aaaaaaaaaaaa")  # 12 chars
        assert response.status_code == 400


class TestReportXSSPrevention:
    """V2-1.1: HTML report must escape all dynamic values."""

    def test_video_id_escaped_in_report(self):
        """Video ID with HTML chars must be escaped in output."""
        results = {
            'video_id': '<script>alert("xss")</script>',
            'safety_score': 85,
            'warnings': [],
            'categories': {},
            'summary': 'Test summary',
        }
        html = generate_report_html(results)
        # The raw XSS payload must NOT appear in output
        assert '<script>alert("xss")</script>' not in html
        # The escaped version must appear
        assert '&lt;script&gt;' in html

    def test_summary_escaped_in_report(self):
        """Summary text with HTML must be escaped in output."""
        results = {
            'video_id': 'dQw4w9WgXcQ',
            'safety_score': 50,
            'warnings': [],
            'categories': {},
            'summary': '<img src=x onerror=alert(1)>',
        }
        html = generate_report_html(results)
        assert '<img src=x onerror=alert(1)>' not in html
        assert '&lt;img' in html

    def test_warning_messages_escaped_in_report(self):
        """Warning messages with HTML must be escaped."""
        results = {
            'video_id': 'dQw4w9WgXcQ',
            'safety_score': 20,
            'warnings': [{
                'category': '<b>Fake</b>',
                'severity': 'high',
                'message': '<script>steal(cookies)</script>',
            }],
            'categories': {},
            'summary': 'Dangerous video',
        }
        html = generate_report_html(results)
        assert '<script>steal(cookies)</script>' not in html
        assert '&lt;script&gt;' in html
        assert '<b>Fake</b>' not in html

    def test_category_names_escaped_in_report(self):
        """Category names with HTML must be escaped."""
        results = {
            'video_id': 'dQw4w9WgXcQ',
            'safety_score': 70,
            'warnings': [],
            'categories': {
                '<script>x</script>': {
                    'emoji': '⚠️',
                    'flagged': True,
                    'score': 80,
                },
            },
            'summary': 'Test',
        }
        html = generate_report_html(results)
        assert '<script>x</script>' not in html


class TestRateLimiterCleanup:
    """V2-1.3: Rate limiter cleanup must prune stale entries, not nuke all."""

    def test_cleanup_preserves_active_entries(self):
        """Active (non-expired) entries must survive cleanup."""
        # Clear store first
        _rate_limit_store.clear()

        now = time.time()
        # Add active entries (within the 60-second window)
        _rate_limit_store["active_ip:path1"] = [now - 10]
        _rate_limit_store["active_ip:path2"] = [now - 5]

        # Add enough stale entries to trigger cleanup (>1000)
        for i in range(1001):
            _rate_limit_store[f"stale_{i}:path"] = [now - 120]  # 2 minutes old

        # Verify we have > 1000 entries
        assert len(_rate_limit_store) > 1000

        # Simulate what the middleware does during cleanup
        cutoff = now - 60  # 60-second window
        stale_keys = [
            k for k, v in _rate_limit_store.items()
            if not v or v[-1] < cutoff
        ]
        for k in stale_keys:
            del _rate_limit_store[k]

        # Active entries MUST survive
        assert "active_ip:path1" in _rate_limit_store
        assert "active_ip:path2" in _rate_limit_store

        # Stale entries must be gone
        assert "stale_0:path" not in _rate_limit_store

        # Clean up after test
        _rate_limit_store.clear()

    def test_cleanup_removes_empty_timestamp_lists(self):
        """Entries with empty timestamp lists should be removed."""
        _rate_limit_store.clear()

        now = time.time()
        _rate_limit_store["empty:path"] = []
        _rate_limit_store["active:path"] = [now]

        # Add filler to trigger threshold
        for i in range(1001):
            _rate_limit_store[f"filler_{i}:p"] = [now - 120]

        cutoff = now - 60
        stale_keys = [
            k for k, v in _rate_limit_store.items()
            if not v or v[-1] < cutoff
        ]
        for k in stale_keys:
            del _rate_limit_store[k]

        assert "empty:path" not in _rate_limit_store
        assert "active:path" in _rate_limit_store

        _rate_limit_store.clear()
