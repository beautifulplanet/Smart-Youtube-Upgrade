"""Tests for AI Context Reviewer — debunking detection and false positive elimination.

Tests cover:
1. Heuristic debunking detection (no API key needed)
2. Integration with SafetyAnalyzer (metadata matches get reviewed)
3. Edge cases: satire, news coverage, educational content
"""

import pytest
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend directory to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from ai_reviewer import AIContextReviewer


# ================================================================
# Heuristic debunking detection tests
# ================================================================

class TestHeuristicDebunking:
    """Test the heuristic (no API key) debunking detection."""
    
    def setup_method(self):
        self.reviewer = AIContextReviewer()  # No API keys = heuristic only
    
    # --- Clear debunking cases (should suppress) ---
    
    def test_tartaria_debunked_title(self):
        """The exact false positive that triggered this feature: 'Tartaria Debunked in 2 Minutes'"""
        result = self.reviewer.heuristic_is_debunking(
            title="Tartaria Debunked in 2 Minutes",
            description="In this video we debunk the Tartaria conspiracy theory",
        )
        assert result["is_debunking"] is True
        assert result["confidence"] >= 0.3
        assert result["method"] == "heuristic"
        assert len(result["signals"]) > 0
    
    def test_flat_earth_debunked(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Flat Earth Theory: DEBUNKED with Science",
            description="Using basic physics to prove the earth is round",
        )
        assert result["is_debunking"] is True
        assert result["confidence"] >= 0.4
    
    def test_fact_check_title(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Fact-Checking Viral Health Claims",
            description="We fact check popular health misinformation",
        )
        assert result["is_debunking"] is True
    
    def test_myth_busting(self):
        result = self.reviewer.heuristic_is_debunking(
            title="5 Medical Myths Busted by a Doctor",
            description="Doctor Mike separates medical fact from fiction",
        )
        assert result["is_debunking"] is True
    
    def test_pseudoscience_exposed(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Crystal Healing: The Pseudoscience Exposed",
            description="Why crystal healing has no scientific basis",
        )
        assert result["is_debunking"] is True
    
    def test_hoax_title(self):
        result = self.reviewer.heuristic_is_debunking(
            title="The Tartaria Hoax: How It Started",
            description="Tracing the origins of the Tartaria conspiracy theory",
        )
        assert result["is_debunking"] is True
    
    def test_why_wrong(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Why Flat Earth Theory is Wrong",
        )
        assert result["is_debunking"] is True
    
    def test_scam_title(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Pineal Gland Detox: Complete Scam Breakdown",
        )
        assert result["is_debunking"] is True
    
    def test_skeptical_analysis(self):
        result = self.reviewer.heuristic_is_debunking(
            title="A Skeptical Look at Third Eye Activation",
            description="Examining the claims with a critical eye",
        )
        assert result["is_debunking"] is True
    
    def test_refuted_claims(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Ancient Tartaria: Claims Refuted by Historians",
        )
        assert result["is_debunking"] is True
    
    # --- Clear PROMOTING cases (should NOT suppress) ---
    
    def test_tartaria_promoting(self):
        """A video actually promoting Tartaria conspiracy should NOT be suppressed."""
        result = self.reviewer.heuristic_is_debunking(
            title="The HIDDEN Truth About Tartaria They Don't Want You to Know",
            description="The real history the government erased. Tartaria was a massive empire.",
        )
        assert result["is_debunking"] is False
    
    def test_third_eye_activation(self):
        result = self.reviewer.heuristic_is_debunking(
            title="How to Activate Your Third Eye in 7 Days",
            description="Step by step guide to pineal gland activation and spiritual awakening",
        )
        assert result["is_debunking"] is False
    
    def test_crystal_healing_guide(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Crystal Healing for Beginners: Complete Guide",
            description="Learn how to use crystals for healing and energy work",
        )
        assert result["is_debunking"] is False
    
    def test_fluoride_conspiracy(self):
        result = self.reviewer.heuristic_is_debunking(
            title="What Fluoride REALLY Does to Your Brain",
            description="The truth about fluoride they don't teach you in school",
        )
        assert result["is_debunking"] is False
    
    def test_mud_flood_promoting(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Mud Flood Evidence: Ancient Buildings Buried Underground",
            description="Hidden history of the great mud flood that buried entire cities",
        )
        assert result["is_debunking"] is False
    
    def test_occult_tarot_guide(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Tarot Reading for Beginners: Your Complete Guide",
            description="Learn how to read tarot cards and tap into your psychic abilities",
        )
        assert result["is_debunking"] is False
    
    # --- Edge cases ---
    
    def test_empty_inputs(self):
        result = self.reviewer.heuristic_is_debunking(title="", description="", transcript="")
        assert result["is_debunking"] is False
        assert result["confidence"] == 0.0
    
    def test_none_inputs(self):
        result = self.reviewer.heuristic_is_debunking(title=None, description=None, transcript=None)
        assert result["is_debunking"] is False
    
    def test_transcript_only_debunking(self):
        """When title is neutral but transcript reveals debunking content."""
        result = self.reviewer.heuristic_is_debunking(
            title="Tartaria: A History",
            description="",
            transcript="this is false and has been debunked by historians repeatedly. there is no evidence..."
        )
        # Transcript alone adds small signal
        assert result["confidence"] > 0
    
    def test_educational_signals(self):
        result = self.reviewer.heuristic_is_debunking(
            title="Tartaria Conspiracy Theory Analysis",
            description="Professor of History at MIT examines the conspiracy theory claims. Peer-reviewed sources cited.",
        )
        assert result["is_debunking"] is True  # Educational signals + "conspiracy theory" in desc


class TestHeuristicEdgeCases:
    """Test tricky edge cases that could fool the heuristic."""
    
    def setup_method(self):
        self.reviewer = AIContextReviewer()
    
    def test_explained_ambiguity(self):
        """'Explained' can be debunking OR just informational about promoting content."""
        # This is a valid debunking title
        result = self.reviewer.heuristic_is_debunking(
            title="Tartaria Explained and Debunked",
        )
        assert result["is_debunking"] is True
    
    def test_news_coverage(self):
        """News reporting on a conspiracy shouldn't be flagged as promoting."""
        result = self.reviewer.heuristic_is_debunking(
            title="Tartaria Conspiracy Theory Goes Viral on TikTok",
            description="CNN reports on the spread of the Tartaria conspiracy theory on social media. Misinformation experts weigh in.",
        )
        # "misinformation" in description is a signal
        assert result["confidence"] > 0


# ================================================================
# AI Context Reviewer initialization tests
# ================================================================

class TestAIReviewerInit:
    """Test AIContextReviewer initialization and provider selection.
    
    Note: openai/anthropic packages may not be installed in the test env.
    We mock _init_clients so provider selection logic is tested independently
    of package availability.
    """
    
    def test_no_keys_uses_heuristic(self):
        reviewer = AIContextReviewer()
        assert reviewer.provider == "heuristic"
        assert reviewer.model == "heuristic"
        assert reviewer.is_ai_enabled is False
    
    @patch.object(AIContextReviewer, '_init_clients')
    def test_openai_key_selects_openai(self, mock_init):
        reviewer = AIContextReviewer(openai_api_key="sk-test-key-123")
        assert reviewer.provider == "openai"
        assert "gpt" in reviewer.model
    
    @patch.object(AIContextReviewer, '_init_clients')
    def test_anthropic_key_selects_anthropic(self, mock_init):
        reviewer = AIContextReviewer(anthropic_api_key="sk-ant-test-key-123")
        assert reviewer.provider == "anthropic"
        assert "claude" in reviewer.model
    
    @patch.object(AIContextReviewer, '_init_clients')
    def test_both_keys_prefers_anthropic(self, mock_init):
        """When both keys are set with auto provider, prefer Anthropic."""
        reviewer = AIContextReviewer(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
        )
        assert reviewer.provider == "anthropic"
    
    @patch.object(AIContextReviewer, '_init_clients')
    def test_explicit_provider_override(self, mock_init):
        reviewer = AIContextReviewer(
            openai_api_key="sk-test",
            anthropic_api_key="sk-ant-test",
            provider="openai",
        )
        assert reviewer.provider == "openai"
    
    @patch.object(AIContextReviewer, '_init_clients')
    def test_custom_model(self, mock_init):
        reviewer = AIContextReviewer(
            openai_api_key="sk-test",
            model="gpt-4o-mini",
        )
        assert reviewer.model == "gpt-4o-mini"
    
    def test_heuristic_provider_no_api_calls(self):
        reviewer = AIContextReviewer(
            openai_api_key="sk-test",
            provider="heuristic",
        )
        assert reviewer.provider == "heuristic"
        assert reviewer.is_ai_enabled is False


# ================================================================
# Full review_flagged_content tests (heuristic path)
# ================================================================

class TestReviewFlaggedContent:
    """Test the full review_flagged_content flow (heuristic path)."""
    
    def setup_method(self):
        self.reviewer = AIContextReviewer()  # Heuristic only
    
    @pytest.mark.asyncio
    async def test_debunking_suppressed(self):
        result = await self.reviewer.review_flagged_content(
            title="Tartaria Debunked in 2 Minutes",
            description="Debunking the Tartaria conspiracy theory",
            channel="History Channel",
            transcript="",
            category="pseudohistorical_extremism",
            category_description="Content promoting pseudohistorical conspiracy theories",
        )
        assert result["should_suppress"] is True
        assert result["is_dangerous"] is False
        assert result["verdict"] == "debunking"
    
    @pytest.mark.asyncio
    async def test_promoting_not_suppressed(self):
        result = await self.reviewer.review_flagged_content(
            title="The HIDDEN Truth About Tartaria",
            description="They erased this empire from history",
            channel="TruthSeeker99",
            transcript="",
            category="pseudohistorical_extremism",
            category_description="Content promoting pseudohistorical conspiracy theories",
        )
        assert result["should_suppress"] is False
        assert result["is_dangerous"] is True
    
    @pytest.mark.asyncio
    async def test_method_is_heuristic(self):
        result = await self.reviewer.review_flagged_content(
            title="Flat Earth Debunked",
            description="",
            channel="",
            transcript="",
            category="pseudohistorical_extremism",
        )
        assert result["method"] == "heuristic"
    
    @pytest.mark.asyncio
    async def test_fact_check_suppressed(self):
        result = await self.reviewer.review_flagged_content(
            title="Fact-Checking Popular Health Conspiracy Theories",
            description="We fact check viral health claims",
            channel="SciShow",
            transcript="",
            category="spiritual_wellness_extremism",
        )
        assert result["should_suppress"] is True


# ================================================================
# Integration with SafetyAnalyzer
# ================================================================

class TestAnalyzerAIIntegration:
    """Test that SafetyAnalyzer correctly uses AIContextReviewer to suppress false positives."""
    
    @pytest.mark.asyncio
    async def test_debunking_video_not_flagged(self):
        """A debunking video whose metadata triggers signature patterns should be suppressed."""
        from safety_db import SafetyDatabase
        from analyzer import SafetyAnalyzer
        
        reviewer = AIContextReviewer()  # Heuristic
        db = SafetyDatabase()
        analyzer = SafetyAnalyzer(db, ai_reviewer=reviewer)
        
        # Craft content that WILL trigger pseudohistorical_extremism signatures:
        # - title matches "tartaria.*truth" pattern 
        # - co_occurrence: "tartaria" (architectural_terms) + "hidden truth" (cabal_terms)
        # BUT the word "Debunked" makes it clearly debunking content
        debunking_title = "Tartaria Truth DEBUNKED: Why This Hidden History is Fake"
        debunking_desc = ("Debunking the Tartaria conspiracy theory. The hidden truth about "
                         "this fake history and the new world order claims behind it. "
                         "No evidence supports the mud flood or cabal narratives.")
        
        with patch.object(analyzer, '_get_transcript', new_callable=AsyncMock, return_value=("", False)):
            with patch.object(analyzer, '_analyze_comments', new_callable=AsyncMock, return_value={
                "total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100
            }):
                with patch('analyzer.YouTubeDataFetcher') as mock_fetcher_cls:
                    mock_fetcher = AsyncMock()
                    mock_fetcher.__aenter__ = AsyncMock(return_value=mock_fetcher)
                    mock_fetcher.__aexit__ = AsyncMock(return_value=None)
                    mock_fetcher.get_video_metadata = AsyncMock(return_value=MagicMock(
                        title=debunking_title,
                        description=debunking_desc,
                        channel="HistoryMatters",
                        tags=["tartaria", "debunked", "history"],
                    ))
                    mock_fetcher_cls.return_value = mock_fetcher
                    
                    results = await analyzer.analyze(
                        "LQRHpB49X6o",
                        scraped_title=debunking_title,
                        scraped_description=debunking_desc,
                        scraped_channel="HistoryMatters",
                    )
        
        # The debunking video should NOT be flagged with metadata warnings
        assert results.get("is_debunking") is True
        
        # Check that no pseudohistorical_extremism warning survived
        metadata_warnings = [
            w for w in results.get("warnings", [])
            if "pseudohistorical" in w.get("category", "").lower()
            or "Pseudohistorical" in w.get("category", "")
        ]
        assert len(metadata_warnings) == 0, f"Debunking video should not be flagged: {metadata_warnings}"
    
    @pytest.mark.asyncio
    async def test_promoting_video_still_flagged(self):
        """A video actually promoting conspiracy theories should still be flagged."""
        from safety_db import SafetyDatabase
        from analyzer import SafetyAnalyzer
        
        reviewer = AIContextReviewer()  # Heuristic
        db = SafetyDatabase()
        analyzer = SafetyAnalyzer(db, ai_reviewer=reviewer)
        
        with patch.object(analyzer, '_get_transcript', new_callable=AsyncMock, return_value=("", False)):
            with patch.object(analyzer, '_analyze_comments', new_callable=AsyncMock, return_value={
                "total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100
            }):
                with patch('analyzer.YouTubeDataFetcher') as mock_fetcher_cls:
                    mock_fetcher = AsyncMock()
                    mock_fetcher.__aenter__ = AsyncMock(return_value=mock_fetcher)
                    mock_fetcher.__aexit__ = AsyncMock(return_value=None)
                    mock_fetcher.get_video_metadata = AsyncMock(return_value=MagicMock(
                        title="The Hidden Truth About Tartaria: The Empire They Erased",
                        description="Ancient Tartaria was a massive empire deliberately erased from history books.",
                        channel="TruthRevealedTV",
                        tags=["tartaria", "hidden history", "truth"],
                    ))
                    mock_fetcher_cls.return_value = mock_fetcher
                    
                    results = await analyzer.analyze(
                        "FAKEID12345",
                        scraped_title="The Hidden Truth About Tartaria: The Empire They Erased",
                        scraped_description="Ancient Tartaria was a massive empire deliberately erased from history",
                        scraped_channel="TruthRevealedTV",
                    )
        
        # This promoting video SHOULD still be flagged
        assert results.get("is_debunking") is False
    
    @pytest.mark.asyncio 
    async def test_analyzer_works_without_reviewer(self):
        """SafetyAnalyzer should still work when no AI reviewer is provided."""
        from safety_db import SafetyDatabase
        from analyzer import SafetyAnalyzer
        
        db = SafetyDatabase()
        analyzer = SafetyAnalyzer(db)  # No AI reviewer
        
        with patch.object(analyzer, '_get_transcript', new_callable=AsyncMock, return_value=("", False)):
            with patch.object(analyzer, '_analyze_comments', new_callable=AsyncMock, return_value={
                "total_comments": 0, "warning_comments": 0, "warnings": [], "warning_score": 100
            }):
                with patch('analyzer.YouTubeDataFetcher') as mock_fetcher_cls:
                    mock_fetcher = AsyncMock()
                    mock_fetcher.__aenter__ = AsyncMock(return_value=mock_fetcher)
                    mock_fetcher.__aexit__ = AsyncMock(return_value=None)
                    mock_fetcher.get_video_metadata = AsyncMock(return_value=MagicMock(
                        title="Safe Video",
                        description="Nothing dangerous here",
                        channel="SafeChannel",
                        tags=[],
                    ))
                    mock_fetcher_cls.return_value = mock_fetcher
                    
                    results = await analyzer.analyze(
                        "dQw4w9WgXcQ",
                        scraped_title="Safe Video",
                        scraped_description="Nothing dangerous here",
                        scraped_channel="SafeChannel",
                    )
        
        # Should complete without error
        assert "safety_score" in results
        assert "warnings" in results


# ================================================================ 
# Debunking keyword coverage tests
# ================================================================

class TestDebunkingKeywordCoverage:
    """Ensure comprehensive coverage of debunking language patterns."""
    
    def setup_method(self):
        self.reviewer = AIContextReviewer()
    
    @pytest.mark.parametrize("title", [
        "Flat Earth DEBUNKED",
        "Tartaria: Myth Busted",
        "Chemtrails: The Hoax Explained",
        "Why Homeopathy is a Scam",
        "Third Eye Activation: Pseudoscience",
        "Crystal Healing Fraud Exposed",
        "No, 5G Does NOT Cause Cancer",
        "QAnon Claims Disproven by FBI Data",
        "Stop Believing These Health Myths",
        "Is Tartaria Real? (Spoiler: No)",
        "Flat Earth vs. Reality",
        "Fact-Checking Anti-Vax Claims",
        "The Nonsense of Alkaline Water Cures",
        "Don't Fall for This MLM Health Scam",
        "A Skeptical Look at Energy Healing",
        "Mud Flood Theory Refuted by Geologists",
    ])
    def test_debunking_titles_detected(self, title):
        result = self.reviewer.heuristic_is_debunking(title=title)
        assert result["is_debunking"] is True, f"Failed to detect debunking in: '{title}'"
    
    @pytest.mark.parametrize("title", [
        "How to Activate Your Third Eye",
        "Tartaria: The Hidden Empire",
        "Fluoride Destroys Your Pineal Gland",
        "Ancient Technology Lost to History",
        "The Government Doesn't Want You to See This",
        "Mud Flood Evidence Found in Buildings",
        "Astral Projection Tutorial for Beginners",
        "Raw Water: Nature's Perfect Drink",
        "Why You Should Stop Drinking Tap Water",
    ])
    def test_promoting_titles_not_detected(self, title):
        result = self.reviewer.heuristic_is_debunking(title=title)
        assert result["is_debunking"] is False, f"Incorrectly detected debunking in: '{title}'"
