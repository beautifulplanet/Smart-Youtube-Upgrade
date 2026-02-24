"""
YouTube Data Fetcher
Fetches video metadata, comments, and other data using YouTube Data API
"""

import re
import httpx
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# --- Comment analysis constants ---
MAX_COMMENT_TEXT_LENGTH = 1000     # Truncation limit per comment (ReDoS prevention)
LIKE_WEIGHT_DIVISOR = 10           # Divisor for comment likes weighting
MAX_SAFETY_WARNINGS = 10           # Max safety warning comments to collect
MAX_AI_WARNINGS = 5                # Max AI content warning comments to collect
WARNING_RATIO_MULTIPLIER = 50      # Multiplier for warning ratio penalty
TOP_CONCERNS_LIMIT = 5             # Number of top concerns to return
COMMENT_SEVERITY_WEIGHTS = {"high": 30, "medium": 15, "low": 5}  # Penalty per severity level


@dataclass
class VideoMetadata:
    title: str
    description: str
    channel: str
    tags: list[str]
    category: str


@dataclass 
class Comment:
    text: str
    likes: int
    author: str


class YouTubeDataFetcher:
    """
    Fetches YouTube video data including comments.
    Can work with or without API key (limited functionality without).
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional YouTube Data API key."""
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def __aenter__(self) -> "YouTubeDataFetcher":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
    
    async def get_comments(self, video_id: str, max_results: int = 100) -> list[Comment]:
        """
        Fetch top comments from a video.
        Requires YouTube Data API key for full access.
        Falls back to scraping if no API key.
        """
        if self.api_key:
            return await self._fetch_comments_api(video_id, max_results)
        else:
            return await self._scrape_comments(video_id, max_results)
    
    async def _make_request_with_retry(self, url: str, params: dict, retries: int = 3) -> Optional[httpx.Response]:
        """Make HTTP request with retry logic for transient errors"""
        import asyncio
        delay = 1.0
        last_exception = None
        
        for attempt in range(retries):
            try:
                response = await self.client.get(url, params=params)
                # Success or client error (4xx) - return immediately
                # 429 (Too Many Requests) or 403 (Forbidden) with quote errors should arguably stop retries, 
                # but for simplicity we treat 5xx as retryable
                if response.status_code < 500:
                    return response
                
                # Server error 5xx - retry
                logger.warning(f"Server error {response.status_code}, retrying (attempt {attempt+1}/{retries})...")
            except (httpx.RequestError, httpx.TimeoutException) as e:
                # Network error - retry
                last_exception = e
                logger.warning(f"Network error {e!r}, retrying (attempt {attempt+1}/{retries})...")
            
            if attempt < retries - 1:
                await asyncio.sleep(delay)
                delay *= 2.0
                
        if last_exception:
            raise last_exception
        return None

    async def _fetch_comments_api(self, video_id: str, max_results: int) -> list[Comment]:
        """Fetch comments using official YouTube Data API"""
        url = "https://www.googleapis.com/youtube/v3/commentThreads"
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": min(max_results, 100),
            "order": "relevance",  # Top comments first
            "key": self.api_key
        }
        
        try:
            response = await self._make_request_with_retry(url, params)
            if response and response.status_code == 200:
                data = response.json()
                comments = []
                for item in data.get("items", []):
                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    comments.append(Comment(
                        text=snippet["textDisplay"],
                        likes=snippet.get("likeCount", 0),
                        author=snippet["authorDisplayName"]
                    ))
                return comments
            else:
                logger.error(f"YouTube API error: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching comments: {e}")
            return []
    
    async def _scrape_comments(self, video_id: str, max_results: int) -> list[Comment]:
        """
        Fallback: Try to get comments without API key.
        This is limited and may not always work.
        """
        # For now, return empty - scraping YouTube is complex
        # The API key method is recommended
        logger.info("Note: YouTube API key required for comment analysis")
        return []
    
    async def get_video_metadata(self, video_id: str) -> Optional[VideoMetadata]:
        """Fetch video title, description, tags"""
        if self.api_key:
            return await self._fetch_metadata_api(video_id)
        return None
    
    async def _fetch_metadata_api(self, video_id: str) -> Optional[VideoMetadata]:
        """Fetch metadata using YouTube Data API"""
        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "snippet",
            "id": video_id,
            "key": self.api_key
        }
        
        try:
            response = await self._make_request_with_retry(url, params)
            if response and response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    snippet = data["items"][0]["snippet"]
                    return VideoMetadata(
                        title=snippet.get("title", ""),
                        description=snippet.get("description", ""),
                        channel=snippet.get("channelTitle", ""),
                        tags=snippet.get("tags", []),
                        category=snippet.get("categoryId", "")
                    )
        except Exception as e:
            logger.error(f"Error fetching metadata: {e}")
        return None
    
    async def close(self) -> None:
        await self.client.aclose()


# Comment danger patterns - STRICT patterns for actual safety warnings
# Pre-compiled at module load for performance
COMMENT_WARNING_PATTERNS = [
    (re.compile(p, re.IGNORECASE), s, d) for p, s, d in [
    # Direct danger warnings - must be explicit warnings
    (r"this is (dangerous|unsafe|a hazard)", "high", "Users flagging content as dangerous"),
    (r"(don'?t|do not|never) (do|try|attempt) this", "high", "Users warning against attempting this"),
    (r"(could|will|can) (catch fire|start a fire|burn down)", "high", "Fire hazard warnings"),
    (r"(could|can|will|might) (kill|die|be fatal)", "high", "Lethal danger warnings"),
    (r"(went to|ended up in|landed in) (the )?(hospital|er|emergency)", "high", "Reports of injuries"),
    (r"toxic (fumes|gas|smoke|chemicals)", "high", "Toxic exposure warnings"),
    
    # Specific material/safety concerns
    (r"not food (safe|grade)", "high", "Material safety concerns"),
    (r"galvanized.*(heat|toxic|fumes|poison)", "high", "Galvanized metal warnings"),
    (r"(dryer|aluminum).*(duct|vent|hose).*(toxic|fumes|poison|heat)", "high", "Improper material for heat"),
    (r"melting point|will melt|starts melting", "high", "Heat rating warnings"),
    
    # Toxic fumes/coatings - expanded patterns
    (r"fumes.*(toxic|dangerous|poison)", "high", "Toxic fumes warning"),
    (r"toxic.*(coating|fume|material|metal|plastic|liner)", "high", "Toxic material warning"),
    (r"(ducting|duct|hose|tube|pipe|tubing).*(toxic|poison|dangerous|fumes)", "high", "Unsafe tubing/ducting warning"),
    (r"not rated for (heat|food|cooking|high temp)", "high", "Material not rated for use"),
    (r"(will|can|does) (release|off-?gas|emit|give off).*(fumes|chemicals|toxins|poison)", "high", "Off-gassing warning"),
    (r"(when|if) heated.*(toxic|poison|fumes|dangerous)", "high", "Heat releases toxins warning"),
    (r"heated to high temp.*(toxic|poison|dangerous|fumes)", "high", "High heat toxicity warning"),
    (r"(dangerous|toxic).*(when|if) heated", "high", "Heat danger warning"),
    (r"insanely dangerous", "critical", "Extreme danger warning"),
    
    # DIY cooking/grilling dangers
    (r"(dryer|foil|flex|aluminum) (duct|hose|vent|tube)", "medium", "DIY ducting used (check for heat safety)"),
    (r"not (meant|designed|rated|safe) for (cooking|food|heat|smoking|grilling)", "high", "Material not meant for cooking"),
    (r"(zinc|galvanized|plastic|pvc).*(fumes|heat|cook|food|grill|smok)", "high", "Unsafe material for cooking"),
    (r"food.*(contact|safe|grade).*no", "high", "Not food safe warning"),
    (r"(don'?t|do not|never).*(cook|grill|smoke|bbq|barbecue).*(this|that|these|those)", "high", "Warning against cooking method"),
    
    # Carbon monoxide specific
    (r"carbon monoxide|co poisoning", "critical", "Carbon monoxide warnings"),
    (r"metal fume fever|zinc (fumes|fever|poisoning)", "critical", "Metal fume fever warnings"),
    
    # Explicit professional warnings
    (r"(call|hire|consult) (a |an )?(professional|electrician|plumber|doctor)", "medium", "Professional consultation needed"),
    (r"against (building |fire )?code|code violation", "medium", "Building code violations"),
]]

# AI/Fake content detection patterns - pre-compiled
AI_CONTENT_PATTERNS = [
    (re.compile(p, re.IGNORECASE), s, d) for p, s, d in [
    # Direct AI mentions (most common comment types)
    # NOTE: Require standalone "ai" or "Ai" as ENTIRE comment (max ~10 chars) to avoid
    # false positives from remarks like "I got RickRolled by my AI assistant"
    (r"^(?:this is )?ai[\.\!\?]?$", "high", "AI content confirmed by comment"),
    (r"^fake[\.\!\?]?$", "high", "Fake content identified"),
    (r"^this is ai\b", "high", "AI content confirmed"),
    (r"^fake\b", "high", "Fake content identified"),
    (r"\bai (slop|generated|made|content|video|image)\b", "high", "AI-generated content detected"),
    (r"this is (ai|fake|cgi|generated|not real)\b", "high", "Users identifying AI/fake content"),
    (r"(clearly |obviously )(ai|fake|cgi|generated)\b", "medium", "Users suspect AI content"),
    (r"made (with|by|using) ai\b", "high", "AI-generated content"),
    (r"(deepfake|deep fake)\b", "critical", "Deepfake content detected"),
    (r"(fake|ai) (video|image|picture|story)\b", "high", "Fake media identified"),
    (r"\bnot real\b.*(?:ai|fake|cgi|generated)\b|\b(?:ai|fake|cgi|generated)\b.*\bnot real\b", "medium", "Content authenticity questioned"),
    (r"(rage ?bait|click ?bait|engagement bait)\b", "medium", "Bait content identified"),
    (r"(midjourney|dall-?e|stable diffusion|sora|runway|pika|kling)\b", "high", "AI tool mentioned"),
    (r"(bot|spam) comment\b", "low", "Bot activity suspected"),
    (r"\bthanks? ai\b", "high", "Sarcastic AI acknowledgment"),
    (r"\bai (garbage|trash|crap|shit|bs)\b", "high", "Negative AI reaction"),
    (r"\b100% (ai|fake|cgi)\b", "high", "Strong AI/fake claim"),
    (r"\bso fake\b|\bso ai\b", "high", "Fake/AI content noted"),
]]


def analyze_comments(comments: list[Comment]) -> dict:
    """
    Analyze comments for safety warnings and AI content detection.
    Returns aggregated warning signals.
    """
    results = {
        "total_comments": len(comments),
        "warning_comments": 0,
        "ai_comments": 0,
        "warnings": [],
        "warning_score": 100,  # Starts high, decreases with warnings
        "top_concerns": [],
        "has_ai_content": False
    }
    
    concern_counts = {}
    ai_concern_counts = {}
    
    for comment in comments:
        text = comment.text[:MAX_COMMENT_TEXT_LENGTH].lower()  # Truncate to prevent ReDoS
        matched = False

        # Check safety warning patterns
        for pattern, severity, description in COMMENT_WARNING_PATTERNS:
            if pattern.search(text):
                results["warning_comments"] += 1
                matched = True

                # Weight by likes (popular warnings are more significant)
                weight = 1 + (comment.likes / LIKE_WEIGHT_DIVISOR)

                if description not in concern_counts:
                    concern_counts[description] = {"count": 0, "weight": 0, "severity": severity}
                concern_counts[description]["count"] += 1
                concern_counts[description]["weight"] += weight

                if len(results["warnings"]) < MAX_SAFETY_WARNINGS:
                    results["warnings"].append({
                        "severity": severity,
                        "category": "Community Warning",
                        "message": f"Comment: \"{comment.text[:100]}...\"" if len(comment.text) > 100 else f"Comment: \"{comment.text}\"",
                        "likes": comment.likes,
                        "source": f"@{comment.author}"
                    })
                break

        # Check AI content patterns (separate from safety)
        if not matched:
            for pattern, severity, description in AI_CONTENT_PATTERNS:
                if pattern.search(text):
                    results["ai_comments"] += 1
                    results["has_ai_content"] = True

                    weight = 1 + (comment.likes / LIKE_WEIGHT_DIVISOR)

                    if description not in ai_concern_counts:
                        ai_concern_counts[description] = {"count": 0, "weight": 0, "severity": severity}
                    ai_concern_counts[description]["count"] += 1
                    ai_concern_counts[description]["weight"] += weight

                    # Add AI warnings separately
                    if len([w for w in results["warnings"] if w["category"] == "AI Content"]) < MAX_AI_WARNINGS:
                        results["warnings"].append({
                            "severity": severity,
                            "category": "AI Content",
                            "message": f"Comment: \"{comment.text[:100]}...\"" if len(comment.text) > 100 else f"Comment: \"{comment.text}\"",
                            "likes": comment.likes,
                            "source": f"@{comment.author}"
                        })
                    break

    # Calculate warning score based on community feedback
    if comments:
        warning_ratio = results["warning_comments"] / len(comments)
        severity_penalty = sum(
            c["weight"] * COMMENT_SEVERITY_WEIGHTS.get(c["severity"], 5)
            for c in concern_counts.values()
        )
        results["warning_score"] = max(0, min(100, 100 - int(severity_penalty) - int(warning_ratio * WARNING_RATIO_MULTIPLIER)))
    
    # Top concerns sorted by weight
    results["top_concerns"] = sorted(
        [{"concern": k, **v} for k, v in concern_counts.items()],
        key=lambda x: x["weight"],
        reverse=True
    )[:TOP_CONCERNS_LIMIT]
    
    return results
