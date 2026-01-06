# YouTube Safety Inspector v2.0 🛡️

YouTube-native safety assistant that flags risky or AI-generated content, and helps users pivot to safer, high‑quality alternatives — without breaking the watching flow.

## What's New in v2.0

### 🎛️ Comprehensive Settings Panel
- **15+ configurable options** via gear icon in popup
- Detection toggles: Safety warnings, AI detection, Auto-analyze
- Video type filters: Regular videos, Shorts
- Suggestion controls: Real alternatives, AI tutorials, AI entertainment
- Banner behavior: Modal/Corner/Bar styles, auto-dismiss timer
- Alert options: Sound alerts, visual effects, periodic reminders
- Sensitivity levels: Low/Medium/High for AI and safety detection
- **Trusted channels list**: Add/remove channels that bypass AI warnings
- Privacy options: Analytics opt-in, result caching
- Export/Import settings as JSON
- Reset to defaults

### 🔧 Core Features
- AI content detection from community comments and optional vision analysis
- Trusted channel bypass (BBC Earth, Nat Geo, Discovery, etc.)
- Ad detection to avoid overlaying banners during ads
- Smart animal detection (e.g., raccoon vs dog) with targeted real‑animal alternatives
- YouTube‑styled modal with video grid and badges
- "Interested in AI?" options: learn to make AI videos (tutorials) or watch curated AI content
- Shorts vs Long‑form toggle for AI content discovery

## Architecture

```
Chrome Extension (Content + Background)
    ↓ (message passing)
Python FastAPI Backend (analyzer + alternatives)
    ↓
Safety Database (danger signatures + categories)
```

## Features

- Safety scoring with category breakdowns (Fitness, DIY, Cooking, Medical, Electrical, etc.)
- Comment analysis using YouTube Data API (requires `YOUTUBE_API_KEY`)
- Optional frame‑based vision analysis (requires `OPENAI_API_KEY`, `yt‑dlp`, `ffmpeg`)
- AI content banner that feels native to YouTube and shows:
  - Real video alternatives (prioritizing trusted sources)
  - Detected animal name when relevant (e.g., “Watch Real Dog Videos Instead”)
  - AI learning and entertainment options with Shorts/Long‑form toggle
- Trusted channels whitelist to reduce false positives
- Ad detection to suppress overlays while ads play
- Periodic subtle AI flash and end‑of‑video reminder when AI content is detected

## Repository Structure

- `extension/` — Chrome extension content and background scripts, YouTube‑styled UI
- `backend/` — FastAPI server, analyzer, alternatives finder
- `safety-db/` — JSON danger signatures and categories

## Setup (Windows)

1) Backend (FastAPI)

```powershell
cd youtube-safety-inspector/backend
pip install -r requirements.txt
$env:YOUTUBE_API_KEY = "<YOUR_YOUTUBE_API_KEY>"
# Optional (vision analysis): requires OpenAI + yt-dlp + ffmpeg
# $env:OPENAI_API_KEY = "<YOUR_OPENAI_API_KEY>"
python main.py
```

## Setup (Mac/Linux)

```bash
cd youtube-safety-inspector/backend
pip install -r requirements.txt
export YOUTUBE_API_KEY="<YOUR_YOUTUBE_API_KEY>"
# Optional: export OPENAI_API_KEY="<YOUR_OPENAI_API_KEY>"
python main.py
```

2) Extension (Chrome)

- Open Chrome → `chrome://extensions`
- Enable “Developer mode”
- Click “Load unpacked” → select the `extension/` folder
- After code changes, click Reload (🔄)

## Usage

- Navigate to any YouTube video or Shorts
- The extension automatically analyzes the video (via background API call)
- Click the **extension icon** to see safety score and details
- Click the **⚙️ gear icon** to access settings
- If AI content is detected:
  - A YouTube‑styled modal appears with real alternatives
  - Bottom section offers:
    - "🎓 Learn to Make AI Videos" (tutorials)
    - "🎨 Watch More AI Content" (curated entertainment)
    - Format toggle: 📺 Long‑form / ⚡ Shorts

## Settings Overview

| Setting | Description |
|---------|-------------|
| Safety Warnings | Detect dangerous DIY, medical, cooking content |
| AI Detection | Flag AI-generated or fake videos |
| Auto-Analyze | Automatically check videos on page load |
| Regular Videos | Analyze standard YouTube videos |
| Shorts | Analyze YouTube Shorts |
| Real Alternatives | Suggest real videos from trusted channels |
| AI Tutorials | Show "Learn to make AI" section |
| AI Entertainment | Show quality AI content suggestions |
| Banner Style | Modal (center), Corner badge, or Top bar |
| Auto-Dismiss | Auto-hide banner after 10s/30s/60s or never |
| Sound Alerts | Play sound when AI/danger detected |
| Visual Effects | Animated borders and highlights |
| Sensitivity | Low/Medium/High strictness levels |
| Trusted Channels | Channels that bypass AI warnings |
| Cache Results | Remember analysis for faster loading |

## Configuration

- `YOUTUBE_API_KEY` (required): Enables comment analysis and YouTube search
- `OPENAI_API_KEY` (optional): Enables vision analysis (disabled without it)
- Vision dependencies (optional): `yt‑dlp`, `ffmpeg`

## API Reference (Backend)

Base URL: `http://localhost:8000`

### POST `/analyze`

Request:

```json
{ "video_id": "En6lhg53DTA" }
```

Response (subset):

```json
{
  "video_id": "En6lhg53DTA",
  "safety_score": 98,
  "warnings": [{ "category": "AI Content", "severity": "high", "message": "Comment: \"AI\"" }],
  "categories": { "AI Content": { "emoji": "🤖", "flagged": false, "score": 100 } },
  "summary": "…",
  "vision_analysis": { "is_ai_generated": false, "message": "Vision analysis disabled - no OpenAI API key" },
  "safe_alternatives": {
    "enabled": true,
    "alternatives": [{ "id": "c7or0y2towI", "title": "…", "channel": "BBC Earth", "url": "…", "is_trusted": true }],
    "message": "🐕 6 REAL Dog videos to watch instead!",
    "category_type": "real_animals",
    "detected_animal": "dog"
  }
}
```

### POST `/ai-tutorials`

Find tutorials on how to make AI videos.

Request:

```json
{ "subject": "dogs", "prefer_shorts": false, "max_results": 8 }
```

Response (subset):

```json
{
  "enabled": true,
  "category_type": "ai_tutorials",
  "alternatives": [{ "title": "How to Make Viral AI Dog Videos", "badge": "🎓 Tutorial" }]
}
```

### POST `/ai-entertainment`

Find curated AI entertainment content.

Request:

```json
{ "subject": "dogs", "prefer_shorts": true, "max_results": 4 }
```

Response (subset):

```json
{
  "enabled": true,
  "category_type": "ai_entertainment",
  "alternatives": [{ "title": "Best AI Dogs Shorts", "badge": "🤖 AI Content" }]
}
```

### GET `/report/{video_id}`

Returns a full HTML report summarizing analysis.

### GET `/health`

Simple health check.

## Development & Testing

Run analyzer quick tests:

```powershell
cd youtube-safety-inspector/backend
python quick_test.py
python test_analyzer.py
```

Test endpoints manually:

```powershell
$body = '{"video_id":"dQw4w9WgXcQ"}'
Invoke-RestMethod -Uri "http://localhost:8000/analyze" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 10

$body = '{"subject":"dogs","prefer_shorts":false,"max_results":6}'
Invoke-RestMethod -Uri "http://localhost:8000/ai-tutorials" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 5

$body = '{"subject":"dogs","prefer_shorts":true,"max_results":4}'
Invoke-RestMethod -Uri "http://localhost:8000/ai-entertainment" -Method POST -Body $body -ContentType "application/json" | ConvertTo-Json -Depth 5
```

## Troubleshooting

- Server exits immediately when run in the same terminal as requests: start the server in a separate window or background process.
- Vision analyzer warnings: expected if `OPENAI_API_KEY`, `yt‑dlp`, or `ffmpeg` are missing.
- Transcript extraction blocked: YouTube may rate‑limit or block IPs; see `youtube_transcript_api` README for proxy guidance.
- CORS issues: the extension routes API calls via the background script with `chrome.runtime.sendMessage`.
- Ads causing overlays: the extension detects ads and suppresses banners during ad playback.
- Trusted channels flagged: add channel names (lowercase) to the analyzer’s `TRUSTED_CHANNELS` list.

## Safety Categories

| Category | Examples |
|----------|----------|
| 🏋️ Fitness | Dangerous exercises, bad form advice |
| 🔧 DIY | Wrong materials, unsafe tools |
| 🍳 Cooking | Food safety, temperature hazards |
| ⚡ Electrical | Improper wiring, fire hazards |
| 💊 Medical | Unverified health claims |
| 🧪 Chemical | Dangerous mixing, toxic exposure |
| 🚗 Driving Safety | Aggressive/unsafe driving, poor instruction |
| 🧰 OSHA Workplace | Missing PPE, unsafe procedures |
| 🧑‍⚕️ Physical Therapy | Non‑professional rehab advice |
| 🐾 AI Content | Community/vision indicators of AI‑generated media |

## Security

This extension implements several security measures:

| Protection | Description |
|------------|-------------|
| 🔐 No hardcoded secrets | API keys loaded from environment variables only |
| ✅ Video ID validation | Regex validation prevents injection attacks |
| 🛡️ XSS protection | All user content escaped before rendering |
| ⚡ Rate limiting | 30s cooldown per video, 100 videos/day limit |
| 📊 Quota enforcement | Hard limits on YouTube API quota usage |
| 🔒 Security headers | X-Content-Type-Options, X-Frame-Options, etc. |
| 📦 Pinned dependencies | Exact versions prevent supply chain attacks |

### API Key Security

- **Never commit API keys** - use `.env` files (excluded via `.gitignore`)
- Copy `.env.example` to `.env` and add your keys there
- The extension reads keys from environment variables only

### Production Deployment

For production use, configure the API URL in Chrome storage:

```javascript
chrome.storage.sync.set({ apiBaseUrl: 'https://your-api-server.com' });
```

## Contributing

- Add new danger signatures to `safety-db/signatures/` following the existing JSON schema.
- PRs welcome for UI improvements, additional trusted channels, new animal keywords, or alternative sources.
- Run security scans before submitting PRs (recommended: `truffleHog`, `gitleaks`)

## License

MIT
