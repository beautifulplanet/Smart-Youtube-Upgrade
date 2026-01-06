"""
YouTube Safety Inspector - Backend API
Copyright (c) 2026 beautifulplanet
Licensed under MIT License

FastAPI server for video analysis and safety assessment.

Data provided by YouTube Data API
https://developers.google.com/youtube
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import uvicorn

from analyzer import SafetyAnalyzer
from safety_db import SafetyDatabase
from alternatives_finder import SafeAlternativesFinder, get_alternatives_finder

# Vision analyzer is optional (requires yt-dlp and ffmpeg)
try:
    from vision_analyzer import VisionAnalyzer
    VISION_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Vision analyzer not available: {e}")
    VISION_AVAILABLE = False
    VisionAnalyzer = None

app = FastAPI(
    title="YouTube Safety Inspector API",
    description="Analyzes YouTube videos for potentially dangerous or misleading content",
    version="1.0.0"
)

# CORS for Chrome extension (restricted to secure origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["chrome-extension://*", "http://localhost:*", "http://127.0.0.1:*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
# Set YOUTUBE_API_KEY environment variable for comment analysis
youtube_api_key = os.environ.get("YOUTUBE_API_KEY")
openai_api_key = os.environ.get("OPENAI_API_KEY")
safety_db = SafetyDatabase()
analyzer = SafetyAnalyzer(safety_db, youtube_api_key=youtube_api_key)
alternatives_finder = SafeAlternativesFinder(api_key=youtube_api_key)

# Vision analyzer is optional
if VISION_AVAILABLE and openai_api_key:
    vision_analyzer = VisionAnalyzer(api_key=openai_api_key)
else:
    vision_analyzer = None

if youtube_api_key:
    print("✅ YouTube API key found - comment analysis enabled")
else:
    print("⚠️ No YOUTUBE_API_KEY - comment analysis disabled (set env var to enable)")

if VISION_AVAILABLE and openai_api_key:
    print("✅ OpenAI API key found - Vision analysis enabled")
else:
    print("⚠️ Vision analysis disabled (requires OPENAI_API_KEY + yt-dlp + ffmpeg)")

# API Quota Tracking (YouTube daily limit: 10,000)
import time
api_quota_tracker = {"count": 0, "date": time.strftime("%Y-%m-%d")}

def log_api_call(cost: int):
    """Track YouTube API quota usage with daily reset"""
    today = time.strftime("%Y-%m-%d")
    if api_quota_tracker["date"] != today:
        api_quota_tracker["count"] = 0
        api_quota_tracker["date"] = today
    api_quota_tracker["count"] += cost
    if api_quota_tracker["count"] > 9000:  # Warn at 90% quota
        print(f"⚠️ WARNING: {api_quota_tracker['count']}/10000 daily YouTube API quota used!")
    return api_quota_tracker["count"]

# Request/Response models
class AnalyzeRequest(BaseModel):
    video_id: str
    # Optional: Extension can pass scraped metadata (works without YOUTUBE_API_KEY)
    title: Optional[str] = None
    description: Optional[str] = None
    channel: Optional[str] = None
    
class Warning(BaseModel):
    category: str
    severity: str  # high, medium, low
    message: str
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
    vision_analysis: VisionResult = None
    safe_alternatives: AlternativesResult = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "version": "1.0.0",
        "api_quota": {
            "used_today": api_quota_tracker["count"],
            "daily_limit": 10000,
            "remaining": 10000 - api_quota_tracker["count"],
            "date": api_quota_tracker["date"]
        }
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
                print(f"Vision analysis error (non-fatal): {ve}")
                results['vision_analysis'] = {
                    'is_ai_generated': False,
                    'ai_confidence': 0,
                    'safety_issues': False,
                    'concerns': [],
                    'frames_analyzed': 0,
                    'message': f'Vision analysis unavailable: {str(ve)}'
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
        
        if is_dangerous or has_ai_content or flagged_categories:
            try:
                # Get video title for context
                video_title = results.get('video_title', '') or results.get('summary', '')[:100]
                
                alt_results = await alternatives_finder.find_safe_alternatives(
                    danger_categories=flagged_categories,
                    original_title=video_title,
                    is_ai_content=has_ai_content,
                    max_results=10  # More results for the grid
                )
                
                results['safe_alternatives'] = {
                    'enabled': alt_results.get('enabled', False),
                    'alternatives': alt_results.get('alternatives', []),
                    'message': alt_results.get('message', ''),
                    'category_type': alt_results.get('category_type', ''),
                    'detected_animal': alt_results.get('detected_animal', '')
                }
                
            except Exception as ae:
                print(f"Alternatives finder error (non-fatal): {ae}")
                results['safe_alternatives'] = {
                    'enabled': False,
                    'alternatives': [],
                    'message': f'Could not find alternatives: {str(ae)}',
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
        current_usage = log_api_call(quota_cost)
        results['api_quota_used'] = current_usage
        
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Request model for AI content discovery
class AIContentRequest(BaseModel):
    subject: Optional[str] = None  # e.g., "dogs", "landscapes" - detected from original video
    prefer_shorts: bool = False
    max_results: int = 8

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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        if subject and subject in alternatives_finder.FALLBACK_REAL_ANIMALS:
            real_videos = alternatives_finder.FALLBACK_REAL_ANIMALS[subject][:max_results]
            animal_name = subject.title()
        else:
            real_videos = alternatives_finder.FALLBACK_REAL_ANIMALS["default"][:max_results]
            animal_name = "Wildlife"
        
        return {
            "enabled": True,
            "alternatives": real_videos,
            "category_type": "real_videos",
            "message": f"🦁 {len(real_videos)} real {animal_name} videos from trusted channels",
            "detected_subject": subject
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/report/{video_id}", response_class=HTMLResponse)
async def get_full_report(video_id: str):
    """Generate a full HTML report for a video analysis"""
    try:
        results = await analyzer.analyze(video_id)
        return generate_report_html(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signatures")
async def get_signatures():
    """Get all safety signatures (danger patterns) from database"""
    return safety_db.get_all_signatures()


@app.get("/categories")
async def get_categories():
    """Get all safety categories"""
    return safety_db.get_categories()


def generate_report_html(results: dict) -> str:
    """Generate a detailed HTML report"""
    
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
        warnings_html += f"""
        <div class="warning-item {w['severity']}">
            <div class="warning-header">
                <span class="severity-badge">{w['severity'].upper()}</span>
                <span class="category">{w['category']}</span>
            </div>
            <p>{w['message']}</p>
        </div>
        """
    
    if not warnings_html:
        warnings_html = '<p class="no-warnings">✅ No safety concerns detected</p>'
    
    categories_html = ""
    for name, data in results.get('categories', {}).items():
        status = 'flagged' if data['flagged'] else 'safe'
        categories_html += f"""
        <div class="category-card {status}">
            <span class="emoji">{data['emoji']}</span>
            <span class="name">{name}</span>
            <span class="score">{data['score']}/100</span>
        </div>
        """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Safety Report - {results['video_id']}</title>
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
                <p class="video-id">Video ID: {results['video_id']}</p>
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
                <p class="summary">{results.get('summary', 'Analysis complete.')}</p>
            </div>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    print("🛡️ YouTube Safety Inspector API")
    print("=" * 40)
    print("Starting server at http://localhost:8000")
    print("API docs: http://localhost:8000/docs")
    print("=" * 40)
    uvicorn.run(app, host="0.0.0.0", port=8000)
