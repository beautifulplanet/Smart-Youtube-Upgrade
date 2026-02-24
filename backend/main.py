"""
YouTube Safety Inspector - Backend API
Copyright (c) 2026 beautifulplanet
Licensed under MIT License

FastAPI server for video analysis and safety assessment.

Data provided by YouTube Data API
https://developers.google.com/youtube
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

import re
import time
import asyncio
import secrets
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, field_validator, Field
from typing import Optional
import uvicorn

# Security: Video ID validation pattern (11 chars, alphanumeric + hyphen/underscore)
VIDEO_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{11}$')

def validate_video_id(video_id: str) -> str:
    """Validate YouTube video ID format to prevent injection attacks"""
    if not video_id or not VIDEO_ID_PATTERN.match(video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID format")
    return video_id

from analyzer import SafetyAnalyzer
from safety_db import SafetyDatabase
from alternatives_finder import SafeAlternativesFinder, get_alternatives_finder

# Vision analyzer is optional (requires yt-dlp and ffmpeg)
try:
    from vision_analyzer import VisionAnalyzer
    VISION_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Vision analyzer not available: {e}")
    VISION_AVAILABLE = False
    VisionAnalyzer = None

app = FastAPI(
    title="YouTube Safety Inspector API",
    description="Analyzes YouTube videos for potentially dangerous or misleading content",
    version="3.0.1"
)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Attach security headers (X-Content-Type-Options, X-Frame-Options, etc.)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # X-XSS-Protection removed: deprecated in modern browsers, can introduce vulnerabilities
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

# API Key Authentication middleware (optional — set API_SECRET_KEY in .env to enable)
_api_secret = os.environ.get("API_SECRET_KEY", "").strip()
# Endpoints that don't require authentication
_PUBLIC_ENDPOINTS = {"/health", "/docs", "/openapi.json", "/redoc"}

if _api_secret:
    logger.info("API authentication: ENABLED (API_SECRET_KEY set)")
else:
    logger.warning("API authentication: DISABLED. Set API_SECRET_KEY in .env to require auth.")

@app.middleware("http")
async def api_key_middleware(request: Request, call_next):
    """Require X-API-Key header on protected endpoints when API_SECRET_KEY is configured."""
    if not _api_secret:
        return await call_next(request)

    path = request.url.path.rstrip("/")
    if path in _PUBLIC_ENDPOINTS or request.method == "OPTIONS":
        return await call_next(request)

    provided_key = request.headers.get("X-API-Key", "")
    if not secrets.compare_digest(provided_key, _api_secret):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})

    return await call_next(request)

# Per-IP rate limiting middleware
_rate_limit_store: dict[str, list[float]] = {}
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMITS = {
    "/analyze": 10,      # 10 requests per minute
    "/health": 60,       # 60 requests per minute
    "/ai-tutorials": 15,
    "/ai-entertainment": 15,
    "/real-alternatives": 15,
}
DEFAULT_RATE_LIMIT = 30  # For unlisted endpoints

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Enforce per-IP, per-endpoint rate limits using a sliding window."""
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path.rstrip("/")
    limit = RATE_LIMITS.get(path, DEFAULT_RATE_LIMIT)
    key = f"{client_ip}:{path}"

    now = time.time()
    timestamps = _rate_limit_store.get(key, [])
    # Remove old timestamps outside the window
    timestamps = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]

    if len(timestamps) >= limit:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={"detail": f"Rate limit exceeded. Max {limit} requests per minute for {path}."}
        )

    timestamps.append(now)
    _rate_limit_store[key] = timestamps

    # Periodic cleanup of old entries (every ~200 requests)
    if len(_rate_limit_store) > 200:
        cutoff = now - RATE_LIMIT_WINDOW
        stale_keys = [
            k for k, v in _rate_limit_store.items()
            if not v or v[-1] < cutoff
        ]
        for k in stale_keys:
            del _rate_limit_store[k]

    return await call_next(request)

# CORS for Chrome extension and local development
# Security: Only allow specific extension IDs (set ALLOWED_EXTENSION_IDS in .env)
_allowed_ext_ids = os.environ.get("ALLOWED_EXTENSION_IDS", "").strip()

if _allowed_ext_ids:
    # Production: Only allow specific extension IDs + restricted localhost
    _ext_id_list = [eid.strip() for eid in _allowed_ext_ids.split(",") if eid.strip()]
    _ext_pattern = "|".join(re.escape(eid) for eid in _ext_id_list)
    ALLOWED_ORIGIN_REGEX = rf"^(http://localhost:8000|http://127\.0\.0\.1:8000|chrome-extension://({_ext_pattern}))$"
    logger.info(f"CORS: Locked to {len(_ext_id_list)} extension ID(s)")
else:
    # Dev mode: Allow any extension ID + localhost:8000 only (not arbitrary ports)
    ALLOWED_ORIGIN_REGEX = r"^(http://localhost:8000|http://127\.0\.0\.1:8000|chrome-extension://[a-z]{32})$"
    logger.warning("CORS: No ALLOWED_EXTENSION_IDS set - allowing any extension (dev mode). Set ALLOWED_EXTENSION_IDS in .env for production.")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=ALLOWED_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Initialize components
# Set YOUTUBE_API_KEY environment variable for comment analysis
youtube_api_key = os.environ.get("YOUTUBE_API_KEY")
openai_api_key = os.environ.get("OPENAI_API_KEY")
anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")

# AI Context Reviewer — verifies metadata signature matches (debunking vs promoting)
from ai_reviewer import AIContextReviewer
ai_reviewer = AIContextReviewer(
    openai_api_key=openai_api_key,
    anthropic_api_key=anthropic_api_key,
    provider=os.environ.get("AI_PROVIDER", "auto"),
)

safety_db = SafetyDatabase()
analyzer = SafetyAnalyzer(safety_db, youtube_api_key=youtube_api_key, ai_reviewer=ai_reviewer)
alternatives_finder = SafeAlternativesFinder(api_key=youtube_api_key)

# Vision analyzer is optional
if VISION_AVAILABLE and openai_api_key:
    vision_analyzer = VisionAnalyzer(api_key=openai_api_key)
else:
    vision_analyzer = None

# Startup validation - log feature availability
_features = {
    "comment_analysis": bool(youtube_api_key),
    "vision_analysis": VISION_AVAILABLE and bool(openai_api_key),
    "alternatives_search": bool(youtube_api_key),
    "ai_context_review": ai_reviewer.is_ai_enabled,
    "ai_provider": ai_reviewer.provider,
    "ai_model": ai_reviewer.model,
}
logger.info("=== Feature Availability ===")
for feature, enabled in _features.items():
    if isinstance(enabled, str):
        logger.info(f"  {feature}: {enabled}")
    else:
        status = "ENABLED" if enabled else "DISABLED"
        logger.info(f"  {feature}: {status}")
if not youtube_api_key:
    logger.warning("YOUTUBE_API_KEY not set. Comment analysis and alternatives search disabled. Set env var to enable.")
if not (VISION_AVAILABLE and openai_api_key):
    logger.warning("Vision analysis disabled. Requires OPENAI_API_KEY + yt-dlp + ffmpeg.")
if not ai_reviewer.is_ai_enabled:
    logger.warning("AI context review: using HEURISTIC fallback. Set OPENAI_API_KEY or ANTHROPIC_API_KEY for near-perfect accuracy.")

# API Quota Tracking (YouTube daily limit: 10,000)
API_QUOTA_LIMIT = 10000
API_QUOTA_WARN = 9000  # Warn at 90%
api_quota_tracker = {"count": 0, "date": time.strftime("%Y-%m-%d")}
_quota_lock = asyncio.Lock()

async def check_quota_available(cost: int = 1) -> bool:
    """Check if API quota is available before making a call"""
    async with _quota_lock:
        today = time.strftime("%Y-%m-%d")
        if api_quota_tracker["date"] != today:
            api_quota_tracker["count"] = 0
            api_quota_tracker["date"] = today
        return (api_quota_tracker["count"] + cost) <= API_QUOTA_LIMIT

async def log_api_call(cost: int):
    """Track YouTube API quota usage with daily reset and enforcement"""
    async with _quota_lock:
        today = time.strftime("%Y-%m-%d")
        if api_quota_tracker["date"] != today:
            api_quota_tracker["count"] = 0
            api_quota_tracker["date"] = today

        # Enforce hard limit
        if api_quota_tracker["count"] + cost > API_QUOTA_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Daily API quota exceeded ({API_QUOTA_LIMIT}). Try again tomorrow."
            )

        api_quota_tracker["count"] += cost

        if api_quota_tracker["count"] > API_QUOTA_WARN:
            logger.warning(f"Quota warning: {api_quota_tracker['count']}/{API_QUOTA_LIMIT} daily YouTube API quota used!")

        return api_quota_tracker["count"]

# Request/Response models
class AnalyzeRequest(BaseModel):
    video_id: str
    # Optional: Extension can pass scraped metadata (works without YOUTUBE_API_KEY)
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    channel: Optional[str] = Field(None, max_length=200)
    
    @field_validator('video_id')
    @classmethod
    def validate_video_id_format(cls, v):
        if not v or not VIDEO_ID_PATTERN.match(v):
            raise ValueError('Invalid video ID format (must be 11 characters, alphanumeric with hyphens/underscores)')
        return v
    
class EvidenceItem(BaseModel):
    type: str  # title, description, channel, hashtag, co_occurrence, other
    label: str
    value: str

class Warning(BaseModel):
    category: str
    severity: str  # high, medium, low
    message: str
    evidence: Optional[list[EvidenceItem]] = None
    timestamp: Optional[str] = None
    
class CategoryResult(BaseModel):
    emoji: str
    flagged: bool
    score: int
    
class VisionResult(BaseModel):
    is_ai_generated: bool = False
    ai_confidence: int = 0
    safety_issues: bool = False
    concerns: list[str] = []
    frames_analyzed: int = 0
    message: str = ""

class AlternativeVideo(BaseModel):
    id: str
    title: str
    channel: str
    thumbnail: str
    url: str
    badge: str = "📚 Educational"
    is_trusted: bool = False

class AlternativesResult(BaseModel):
    enabled: bool = False
    alternatives: list[AlternativeVideo] = []
    message: str = ""
    category_type: str = ""

class AnalysisResponse(BaseModel):
    video_id: str
    safety_score: int
    warnings: list[Warning]
    categories: dict[str, CategoryResult]
    summary: str
    transcript_available: bool
    ai_generated: bool = False
    ai_confidence: float = 0.0
    ai_reasons: list[str] = []
    alternatives: list[AlternativeVideo] = []
    detected_animal: str = ""
    is_debunking: bool = False
    vision_analysis: VisionResult = None
    safe_alternatives: AlternativesResult = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "version": "3.0.1"
        # SECURITY: API quota details removed from public endpoint (finding #17)
    }


@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_video(request: AnalyzeRequest):
    """
    Analyze a YouTube video for safety concerns.
    
    This endpoint:
    1. Fetches the video transcript
    2. Analyzes content against safety signatures  
    3. Uses AI to detect contextual dangers
    4. Optionally analyzes video frames with AI vision
    5. Returns a safety score and warnings
    """
    try:
        # Pass optional metadata from extension (allows AI detection without API key)
        results = await analyzer.analyze(
            request.video_id,
            scraped_title=request.title,
            scraped_description=request.description,
            scraped_channel=request.channel
        )
        
        # Add vision analysis if available (runs in parallel)
        if vision_analyzer and vision_analyzer.enabled:
            try:
                vision_results = await vision_analyzer.analyze_video_frames(
                    request.video_id, 
                    num_frames=5
                )
                
                results['vision_analysis'] = {
                    'is_ai_generated': vision_results.get('is_ai_generated', False),
                    'ai_confidence': 0,
                    'safety_issues': vision_results.get('safety_issues', False),
                    'concerns': vision_results.get('concerns', []),
                    'frames_analyzed': vision_results.get('frames_analyzed', 0),
                    'message': vision_results.get('message', '')
                }
                
                # Add vision concerns as warnings
                for concern in vision_results.get('concerns', []):
                    results['warnings'].append({
                        'category': 'AI Vision Analysis',
                        'severity': 'high',
                        'message': concern,
                        'timestamp': None
                    })
                
                # If AI-generated detected by vision, add warning
                if vision_results.get('is_ai_generated'):
                    results['warnings'].append({
                        'category': 'AI Content',
                        'severity': 'high',
                        'message': 'AI Vision detected this video appears to be AI-generated',
                        'timestamp': None
                    })
                    
            except Exception as ve:
                logger.warning(f"Vision analysis error (non-fatal): {ve}")
                results['vision_analysis'] = {
                    'is_ai_generated': False,
                    'ai_confidence': 0,
                    'safety_issues': False,
                    'concerns': [],
                    'frames_analyzed': 0,
                    'message': 'Vision analysis temporarily unavailable'
                }
        else:
            results['vision_analysis'] = {
                'is_ai_generated': False,
                'ai_confidence': 0,
                'safety_issues': False,
                'concerns': [],
                'frames_analyzed': 0,
                'message': 'Vision analysis disabled - no OpenAI API key'
            }
        
        # Find safe alternatives if dangerous content or AI content detected
        is_dangerous = results.get('safety_score', 100) < 50
        has_ai_content = any(w.get('category') == 'AI Content' for w in results.get('warnings', []))
        flagged_categories = [
            name for name, data in results.get('categories', {}).items() 
            if data.get('flagged')
        ]
        
        # Check for debunking content: metadata signatures provide targeted debunk searches
        debunk_searches = results.get('debunk_searches', [])
        has_debunk_content = bool(debunk_searches)
        
        if is_dangerous or has_ai_content or flagged_categories:
            try:
                # Get video title for context
                video_title = results.get('video_title', '') or results.get('summary', '')[:100]
                
                if has_debunk_content:
                    # Use targeted debunk search queries from matched signatures
                    alt_results = await alternatives_finder.search_debunking_videos(
                        debunk_queries=debunk_searches,
                        max_results=8
                    )
                else:
                    # Use category-based safe alternatives (original behavior)
                    # Also pass category IDs for mapping lookup
                    matched_cat_ids = results.get('matched_metadata_categories', [])
                    combined_categories = flagged_categories + matched_cat_ids
                    
                    alt_results = await alternatives_finder.find_safe_alternatives(
                        danger_categories=combined_categories,
                        original_title=video_title,
                        is_ai_content=has_ai_content,
                        max_results=10
                    )
                
                results['safe_alternatives'] = {
                    'enabled': alt_results.get('enabled', False),
                    'alternatives': alt_results.get('alternatives', []),
                    'message': alt_results.get('message', ''),
                    'category_type': alt_results.get('category_type', ''),
                    'detected_animal': alt_results.get('detected_animal') or '',
                    'is_debunking': has_debunk_content
                }
                
            except Exception as ae:
                logger.warning(f"Alternatives finder error (non-fatal): {ae}")
                results['safe_alternatives'] = {
                    'enabled': False,
                    'alternatives': [],
                    'message': 'Could not find alternatives at this time',
                    'category_type': ''
                }
        else:
            results['safe_alternatives'] = {
                'enabled': True,
                'alternatives': [],
                'message': 'No alternatives needed - content appears safe',
                'category_type': ''
            }
        
        # Log API quota usage (comments: 1, metadata: 1, search: 100 if alternatives)
        quota_cost = 2  # Base: comments + metadata
        if results.get('safe_alternatives', {}).get('alternatives'):
            quota_cost += 100  # Search API call
        current_usage = await log_api_call(quota_cost)
        results['api_quota_used'] = current_usage
        
        # Flatten safe_alternatives into top-level fields for frontend compatibility
        sa = results.get('safe_alternatives') or {}
        results['alternatives'] = sa.get('alternatives', [])
        results['detected_animal'] = sa.get('detected_animal') or ''
        # is_debunking: True if AI review determined content is debunking/educational
        results['is_debunking'] = results.get('is_debunking', False) or sa.get('is_debunking', False)
        
        return results
    except Exception as e:
        logger.error(f"Analysis endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Internal analysis error")


# Request model for AI content discovery
class AIContentRequest(BaseModel):
    subject: Optional[str] = Field(None, max_length=100)  # e.g., "dogs", "landscapes"
    prefer_shorts: bool = False
    max_results: int = Field(8, ge=1, le=50)

class AIContentResponse(BaseModel):
    enabled: bool
    alternatives: list[AlternativeVideo]
    message: str
    category_type: str
    detected_subject: Optional[str] = None
    is_shorts: bool = False


@app.post("/ai-tutorials")
async def get_ai_tutorials(request: AIContentRequest):
    """
    Get AI video creation tutorials.
    For users who want to LEARN how to make AI videos.
    High engagement content - tutorials, guides, tool reviews.
    """
    try:
        results = await alternatives_finder.find_ai_tutorials(
            detected_subject=request.subject,
            prefer_shorts=request.prefer_shorts,
            max_results=request.max_results
        )
        return results
    except Exception as e:
        logger.error(f"AI tutorials endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AI tutorials")


@app.post("/ai-entertainment")
async def get_ai_entertainment(request: AIContentRequest):
    """
    Get quality AI entertainment content.
    For users who WANT to watch AI-generated videos.
    Curated, high-quality AI content.
    """
    try:
        results = await alternatives_finder.find_ai_entertainment(
            detected_subject=request.subject,
            prefer_shorts=request.prefer_shorts,
            max_results=request.max_results
        )
        return results
    except Exception as e:
        logger.error(f"AI entertainment endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch AI entertainment")


@app.post("/real-alternatives")
async def get_real_alternatives(request: AIContentRequest):
    """
    Get real/verified video alternatives.
    For users who want verified, non-AI content.
    Returns curated content from trusted channels based on detected animal.
    """
    try:
        max_results = request.max_results or 8
        subject = request.subject.lower() if request.subject else None
        
        # Get animal-specific videos if we detected an animal
        if subject and subject in alternatives_finder.fallback_real_animals:
            real_videos = alternatives_finder.fallback_real_animals[subject][:max_results]
            animal_name = subject.title()
        else:
            real_videos = alternatives_finder.fallback_real_animals["default"][:max_results]
            animal_name = "Wildlife"
        
        return {
            "enabled": True,
            "alternatives": real_videos,
            "category_type": "real_videos",
            "message": f"🦁 {len(real_videos)} real {animal_name} videos from trusted channels",
            "detected_subject": subject
        }
    except Exception as e:
        logger.error(f"Real alternatives endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch alternatives")


@app.get("/report/{video_id}", response_class=HTMLResponse)
async def get_full_report(video_id: str):
    """Generate a full HTML report for a video analysis"""
    # Security: Validate video ID before processing
    video_id = validate_video_id(video_id)
    try:
        results = await analyzer.analyze(video_id)
        return generate_report_html(results)
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@app.get("/signatures")
async def get_signatures():
    """Get safety signature metadata (trigger patterns stripped to prevent evasion)"""
    safe_sigs = []
    for sig in safety_db.get_all_signatures():
        safe_sigs.append({
            "id": sig.get("id"),
            "category": sig.get("category"),
            "severity": sig.get("severity"),
            "warning_message": sig.get("warning_message"),
            "trigger_count": len(sig.get("triggers", [])),
        })
    return safe_sigs


@app.get("/categories")
async def get_categories():
    """Get all safety categories"""
    return safety_db.get_categories()



def generate_report_html(results: dict) -> str:
    """Generate a detailed HTML report"""
    import html
    
    score = results.get('safety_score', 0)
    if score < 40:
        score_class = 'danger'
        score_label = 'DANGEROUS'
    elif score < 70:
        score_class = 'warning'
        score_label = 'USE CAUTION'
    else:
        score_class = 'safe'
        score_label = 'SAFE'
    
    warnings_html = ""
    for w in results.get('warnings', []):
        severity = html.escape(str(w.get('severity', 'low')))
        category = html.escape(str(w.get('category', 'Unknown')))
        message = html.escape(str(w.get('message', '')))
        
        warnings_html += f"""
        <div class="warning-item {severity}">
            <div class="warning-header">
                <span class="severity-badge">{severity.upper()}</span>
                <span class="category">{category}</span>
            </div>
            <p>{message}</p>
        </div>
        """
    
    if not warnings_html:
        warnings_html = '<p class="no-warnings">✅ No safety concerns detected</p>'
    
    categories_html = ""
    for name, data in results.get('categories', {}).items():
        status = 'flagged' if data.get('flagged') else 'safe'
        safe_name = html.escape(str(name))
        emoji = html.escape(str(data.get('emoji', '')))
        score_val = data.get('score', 0)
        
        categories_html += f"""
        <div class="category-card {status}">
            <span class="emoji">{emoji}</span>
            <span class="name">{safe_name}</span>
            <span class="score">{score_val}/100</span>
        </div>
        """
    
    video_id_safe = html.escape(str(results.get('video_id', '')))
    summary_safe = html.escape(str(results.get('summary', 'Analysis complete.')))
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Safety Report - {video_id_safe}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                color: #eee;
                min-height: 100vh;
                padding: 40px;
            }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            header {{
                text-align: center;
                margin-bottom: 40px;
            }}
            h1 {{
                font-size: 32px;
                margin-bottom: 10px;
            }}
            .video-id {{
                color: #888;
                font-size: 14px;
            }}
            .score-section {{
                text-align: center;
                margin-bottom: 40px;
            }}
            .score-circle {{
                width: 150px;
                height: 150px;
                border-radius: 50%;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                margin: 0 auto 15px;
                font-size: 48px;
                font-weight: 700;
            }}
            .score-circle.danger {{ background: rgba(255,68,68,0.2); border: 4px solid #ff4444; color: #ff4444; }}
            .score-circle.warning {{ background: rgba(255,170,0,0.2); border: 4px solid #ffaa00; color: #ffaa00; }}
            .score-circle.safe {{ background: rgba(0,255,136,0.2); border: 4px solid #00ff88; color: #00ff88; }}
            .score-label {{
                font-size: 14px;
                letter-spacing: 2px;
            }}
            .section {{
                background: rgba(255,255,255,0.05);
                border-radius: 15px;
                padding: 25px;
                margin-bottom: 25px;
            }}
            .section h2 {{
                font-size: 20px;
                margin-bottom: 20px;
                padding-bottom: 10px;
                border-bottom: 1px solid rgba(255,255,255,0.1);
            }}
            .warning-item {{
                padding: 15px;
                margin-bottom: 15px;
                border-radius: 10px;
                border-left: 4px solid;
            }}
            .warning-item.high {{ background: rgba(255,68,68,0.1); border-color: #ff4444; }}
            .warning-item.medium {{ background: rgba(255,170,0,0.1); border-color: #ffaa00; }}
            .warning-item.low {{ background: rgba(0,212,255,0.1); border-color: #00d4ff; }}
            .warning-header {{
                display: flex;
                gap: 10px;
                margin-bottom: 8px;
            }}
            .severity-badge {{
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            .warning-item.high .severity-badge {{ background: #ff4444; }}
            .warning-item.medium .severity-badge {{ background: #ffaa00; color: #1a1a2e; }}
            .warning-item.low .severity-badge {{ background: #00d4ff; color: #1a1a2e; }}
            .category {{ color: #888; font-size: 13px; }}
            .no-warnings {{
                color: #00ff88;
                text-align: center;
                padding: 20px;
            }}
            .categories-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 15px;
            }}
            .category-card {{
                background: rgba(255,255,255,0.05);
                border-radius: 10px;
                padding: 20px;
                text-align: center;
            }}
            .category-card.flagged {{ background: rgba(255,68,68,0.1); border: 1px solid rgba(255,68,68,0.3); }}
            .category-card.safe {{ background: rgba(0,255,136,0.05); border: 1px solid rgba(0,255,136,0.2); }}
            .category-card .emoji {{ font-size: 30px; display: block; margin-bottom: 8px; }}
            .category-card .name {{ font-size: 13px; display: block; margin-bottom: 5px; }}
            .category-card .score {{ font-size: 11px; color: #888; }}
            .summary {{
                line-height: 1.6;
                color: #ccc;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>🛡️ Safety Analysis Report</h1>
                <p class="video-id">Video ID: {video_id_safe}</p>
            </header>
            
            <div class="score-section">
                <div class="score-circle {score_class}">
                    {score}
                    <span class="score-label">{score_label}</span>
                </div>
            </div>
            
            <div class="section">
                <h2>⚠️ Warnings</h2>
                {warnings_html}
            </div>
            
            <div class="section">
                <h2>📋 Categories Analyzed</h2>
                <div class="categories-grid">
                    {categories_html}
                </div>
            </div>
            
            <div class="section">
                <h2>📝 Summary</h2>
                <p class="summary">{summary_safe}</p>
            </div>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    logger.info("YouTube Safety Inspector API")
    logger.info("Starting server at http://127.0.0.1:8000")
    logger.info("API docs: http://127.0.0.1:8000/docs")
    # SECURITY: bind to localhost only — never 0.0.0.0 without authentication
    uvicorn.run(app, host="127.0.0.1", port=8000)
