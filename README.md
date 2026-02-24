# YouTube Safety Inspector 🛡️

![Backend Tests](https://img.shields.io/badge/backend_tests-260_passed-brightgreen)
![Frontend Tests](https://img.shields.io/badge/frontend_tests-73_passed-brightgreen)
![Version](https://img.shields.io/badge/version-3.0.1-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**A browser extension that analyzes YouTube videos for dangerous, misleading, and AI-generated content in real-time — powered by a Python analysis backend with transcript parsing, comment intelligence, and computer vision.**

<!-- Screenshot placeholder: Replace with actual screenshot -->
<!-- ![YouTube Safety Inspector](docs/images/screenshot.png) -->

> *333 tests (260 backend + 73 frontend). 10 safety categories. 11 signature files. Cross-browser. Docker-ready. Security-hardened with rate limiting, XSS prevention, and CSP compliance.*

---

## How to Read This README

This document serves **four audiences**. Jump to what you need:

| You are... | Start here | Time |
|---|---|---|
| **Hiring manager** wanting the highlights | [Part 1: Summary](#part-1-summary) | 30 seconds |
| **Senior engineer** evaluating the architecture | [Part 2: Tech Stack & Architecture](#part-2-tech-stack--architecture) | 2 minutes |
| **Developer** wanting to run it locally | [Part 3: Quick Start](#part-3-quick-start) | 2 minutes |
| **Learner** wanting to understand everything | [Part 4: Deep Dive](#part-4-deep-dive) | 15+ minutes |

---

# Part 1: Summary

*30 seconds. What this is, what it does, why it matters.*

### What

A YouTube content safety system that combines:
- **Pattern-matching analysis engine** — antivirus-style signature database with 25+ danger patterns across 10 categories
- **Multi-signal detection** — transcript extraction, comment sentiment analysis, metadata heuristics, hashtag/title AI detection
- **Computer vision (optional)** — GPT-4 Vision frame analysis via yt-dlp + ffmpeg pipeline
- **Safe alternative discovery** — finds real, educational, and tutorial replacements from trusted channels
- **Multi-panel sidebar** — YouTube-native 2×2 grid with 5 preset modes, individual playback controls
- **Cross-browser extension** — Chrome, Firefox, Edge from one codebase via Manifest V3

### Why It's Interesting (for Interviewers)

| Talking Point | Detail |
|---|---|
| Full-stack ownership | Python backend (FastAPI + analysis engine) + browser extension (Chrome MV3 + content scripts) + DevOps (Docker, CI) |
| Security hardening | Rate limiting, CSP compliance, XSS prevention, input validation, security headers — 333 tests including 11 security regression tests |
| Scaling analysis | 14 identified bottlenecks documented with migration paths from 100 → 1B users ([SCALING.md](SCALING.md)) |
| API design | RESTful with Pydantic validation, quota tracking, structured error responses, health checks |
| Content analysis engine | Signature matching (antivirus-style), weighted scoring, multi-source fusion (transcript + comments + metadata) |
| Production discipline | Docker multi-stage builds, pinned dependencies, pre-commit hooks, structured logging, graceful degradation |
| Extension architecture | Shadow DOM isolation, SPA navigation handling, service worker lifecycle, `chrome.storage` tiered caching |

### Key Numbers

| Metric | Value |
|---|---|
| Backend source | 7 modules, ~4,300 lines Python |
| Extension source | 10 content scripts + popup + background, ~6,400 lines JS/CSS/HTML |
| Safety categories | 10 (Fitness, DIY, Cooking, Electrical, Medical, Chemical, Driving, OSHA, Physical Therapy, AI Content) |
| Danger signatures | 25+ patterns across 11 JSON signature files |
| Test count | 333 tests — 260 backend (pytest) + 73 frontend (Vitest) |
| API endpoints | 6 (analyze, report, ai-tutorials, ai-entertainment, real-alternatives, health) |
| Security headers | 5 (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Content-Type) |

---

# Part 2: Tech Stack & Architecture

*2 minutes. What's used, how it fits together, and the key design decisions.*

### Stack

| Layer | Technology | Why |
|---|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn | Async-native, automatic OpenAPI docs, Pydantic validation |
| Analysis Engine | Custom Python (regex + heuristics) | Antivirus-style signature matching, weighted multi-source scoring |
| Transcript | youtube-transcript-api | Direct transcript extraction without API quota cost |
| YouTube Data | httpx + Google API Client | Comment fetching, metadata, video search with retry logic |
| Vision (optional) | GPT-4 Vision + yt-dlp + ffmpeg | Frame extraction and AI analysis for visual content |
| Extension | Chrome Manifest V3, JavaScript | Content scripts, service worker, popup, Shadow DOM sidebar |
| Cross-Browser | webextension-polyfill | API normalization across Chrome/Firefox/Edge |
| Build | Node.js + custom build.js | Cross-browser manifest handling, file watching, polyfill injection |
| Containerization | Docker (multi-stage) + docker-compose | Non-root user, health checks, env-based config |
| Testing | pytest + pytest-cov + pytest-asyncio | Async test support, coverage reporting |
| Linting | ESLint (frontend), ruff (backend) | Code quality enforcement |
| Security | Custom middleware (rate limiting, headers, validation) | Defense-in-depth without external dependencies |

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    Browser (YouTube.com)                    │
│                                                            │
│  ┌──────────┐  ┌────────────┐  ┌────────────┐             │
│  │ Sidebar  │  │  Content   │  │   Popup    │             │
│  │ (Shadow  │  │  Scripts   │  │  (Safety   │             │
│  │  DOM)    │  │  (Analysis │  │   Score)   │             │
│  │          │  │  + Overlay)│  │            │             │
│  └────┬─────┘  └─────┬──────┘  └──────┬─────┘             │
│       │              │                │                    │
│       └──────────────┼────────────────┘                    │
│                      │ chrome.runtime.sendMessage          │
│              ┌───────▼────────┐                            │
│              │ Service Worker │                            │
│              │ (Background)   │                            │
│              │ API proxy +    │                            │
│              │ caching        │                            │
│              └───────┬────────┘                            │
└──────────────────────┼─────────────────────────────────────┘
                       │ HTTP API
              ┌────────▼──────────────────┐
              │    FastAPI Backend         │
              │                           │
              │  ┌─────────────────────┐  │
              │  │ Security Middleware  │  │
              │  │ Rate Limit + Headers│  │
              │  └─────────┬───────────┘  │
              │            │              │
              │  ┌─────────▼───────────┐  │
              │  │  Safety Analyzer    │  │
              │  │  - Transcript       │  │
              │  │  - Signatures       │  │
              │  │  - Comments         │  │
              │  │  - AI Heuristics    │  │
              │  └─────────┬───────────┘  │
              │            │              │
              │  ┌─────────▼───────────┐  │
              │  │ Alternatives Finder │  │
              │  │ + Vision Analyzer   │  │
              │  └─────────────────────┘  │
              │            │              │
              │  ┌─────────▼───────────┐  │
              │  │ Safety Database     │  │
              │  │ (JSON signatures)   │  │
              │  └─────────────────────┘  │
              └───────────────────────────┘
```

### Analysis Pipeline

When a user visits a YouTube video, the system runs a multi-signal analysis:

```
Video URL → Extract Video ID
               │
    ┌──────────┼──────────┬────────────────┐
    ▼          ▼          ▼                ▼
Transcript  Comments   Metadata      Vision (opt.)
  (free)    (API: 1u)  (API: 1u)    (GPT-4 Vision)
    │          │          │                │
    └──────────┼──────────┘                │
               ▼                           │
    Signature Matching                     │
    (regex patterns ×                      │
     10 categories)                        │
               │                           │
               ▼                           │
    Score Calculation ◄────────────────────┘
    (weighted: 60% transcript
              40% comments)
               │
               ▼
    Safety Score (0-100)
    + Warnings + Categories
    + Safe Alternatives
```

### Key Design Decisions

| Decision | Rationale |
|---|---|
| Antivirus-style signatures | Extensible pattern database. Add new dangers by adding JSON — no code changes needed |
| Transcript-first analysis | youtube-transcript-api costs zero API quota. Comments and metadata supplement but aren't required |
| Weighted multi-source scoring | No single signal is reliable alone. Transcript (60%) + comments (40%) catches more than either individually |
| Shadow DOM sidebar | Complete CSS isolation from YouTube. Extension styles can't break YouTube, YouTube styles can't break extension |
| Service worker API proxy | All API calls route through background script. Content scripts never make direct HTTP requests (security + CORS) |
| In-memory rate limiter | Good enough for single-process. Documented as B1 bottleneck with Redis migration path ([SCALING.md](SCALING.md)) |
| Vision as optional layer | yt-dlp + ffmpeg + OpenAI API are heavy dependencies. Core analysis works without them. Vision adds depth for users who opt in |

---

# Part 3: Quick Start

*2 minutes. Clone, install, analyze.*

### Prerequisites

- **Python 3.11+** *(venv path only)*
- **Docker & Docker Compose** *(Docker path only)*
- **Node.js 18+** *(only for building the extension)*
- **YouTube Data API Key** *(optional — works without, but limited)*

### 1. Backend — pick one path

#### Option A: Docker (recommended)

```bash
cp .env.example .env          # then edit .env with your API keys
docker compose up --build
```

Verify: open **http://localhost:8000/health** — you should see `{"status":"healthy"}`.

#### Option B: Python venv

```bash
python -m venv .venv

# Activate:
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Mac / Linux:
source .venv/bin/activate

pip install -r backend/requirements.txt

# (Optional) Set API key for comments/search features:
# Windows:  $env:YOUTUBE_API_KEY = "<YOUR_KEY>"
# Mac/Linux: export YOUTUBE_API_KEY="<YOUR_KEY>"

cd backend
python main.py
# — or —
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Backend starts on **http://localhost:8000**.

> **Windows one-click alternative:** `.\START.ps1` — creates the venv, installs deps, and prompts for your API key.

### 2. Build the Extension

```bash
npm install
npm run build:chrome    # → dist/chrome/
npm run build:firefox   # → dist/firefox/
npm run build:edge      # → dist/edge/
```

### 3. Load in Browser

**Chrome / Edge:**
1. Go to `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode**
3. Click **Load unpacked** → select `dist/chrome/` (or `dist/edge/`)

**Firefox:**
1. Go to `about:debugging#/runtime/this-firefox`
2. Click **Load Temporary Add-on** → select `dist/firefox/manifest.json`

> **Important:** Always load from `dist/<browser>/`, not from `extension/`. The build step copies polyfills and the correct manifest.

### 4. Use It

1. Navigate to any YouTube video
2. The sidebar appears on the right side
3. Click the extension icon for the popup with safety score details
4. Each sidebar panel shows content based on its mode

### 5. Run Tests

```bash
cd backend
python -m pytest tests/ -v              # 297 tests, ~15s
python -m pytest tests/ --cov           # With coverage report
```

---

# Part 4: Deep Dive

*Complete reference for anyone wanting to understand, modify, or extend the system.*

---

## Table of Contents

- [A. Safety Analysis Engine](#a-safety-analysis-engine)
- [B. Safety Categories & Signatures](#b-safety-categories--signatures)
- [C. AI Content Detection](#c-ai-content-detection)
- [D. Extension Architecture](#d-extension-architecture)
- [E. Multi-Panel Sidebar System](#e-multi-panel-sidebar-system)
- [F. API Reference](#f-api-reference)
- [G. Security Model](#g-security-model)
- [H. Scaling Analysis](#h-scaling-analysis)
- [I. Testing Strategy](#i-testing-strategy)
- [J. Project Structure](#j-project-structure)
- [K. Configuration](#k-configuration)

---

## A. Safety Analysis Engine

The core analysis engine (`analyzer.py`, 694 lines) works like an antivirus scanner for video content.

### How It Works

**Step 1 — Transcript Extraction**
Uses `youtube-transcript-api` to download the video's transcript for free (no API quota cost). This is the primary data source.

**Step 2 — Comment Analysis**
Fetches up to 100 top comments via YouTube Data API. Analyzes for safety warnings, AI content indicators, and community sentiment. Comments are weighted by likes — a warning with 1,000 likes matters more than one with 2.

**Step 3 — Signature Matching**
Runs the combined text against the signature database. Each signature has:
- **Trigger patterns** — regex phrases that indicate danger
- **Category** — which safety domain (Fitness, Electrical, etc.)
- **Severity** — low, medium, high, critical
- **Description** — human-readable explanation

```python
# Example: Signature matching is like antivirus definitions
{
    "id": "fitness_dangerous_exercise",
    "category": "fitness",
    "severity": "high",
    "triggers": ["no spotter", "skip warmup", "ego lift", "max weight without"],
    "description": "Promotes dangerous exercise practices without safety precautions"
}
```

**Step 4 — Score Calculation**
Combines transcript analysis (60% weight) and comment analysis (40% weight) into a 0–100 safety score. When no transcript is available, comment weight increases to 70%.

**Step 5 — AI Heuristics**
Without any external AI API, the engine detects AI-generated content through:
- Title patterns ("This animal doesn't exist", "AI generated")
- Hashtag analysis (#aiart, #midjourney, #sora — threshold: 2+)
- Channel name patterns ("AI [Animal]", "[Animal] AI")
- "Impossible content" detection (animals doing impossible things)
- Dangerous animal + child combinations

**Step 6 — Vision Analysis (Optional)**
If configured with OpenAI API key + yt-dlp + ffmpeg:
1. Downloads video frames at key intervals
2. Sends to GPT-4 Vision for safety analysis
3. Detects visual dangers that text analysis misses

---

## B. Safety Categories & Signatures

10 categories, each with its own signature file:

| Category | Emoji | Examples | Signature File |
|---|---|---|---|
| Fitness | 🏋️ | Dangerous exercises, no spotter, bad form | `fitness.json` |
| DIY | 🔧 | Wrong materials, missing safety gear | `diy.json` |
| Cooking | 🍳 | Food safety violations, temperature hazards | `cooking.json` |
| Electrical | ⚡ | Improper wiring, fire hazards, live work | `electrical.json` |
| Medical | 💊 | Unverified health claims, self-diagnosis | `medical.json` |
| Chemical | 🧪 | Dangerous mixing, toxic exposure | `chemical.json` |
| Driving | 🚗 | Aggressive driving instruction, stunts | `driving.json` |
| OSHA | 🧰 | Missing PPE, unsafe work procedures | `osha.json` |
| Physical Therapy | 🧑‍⚕️ | Non-professional rehab advice | `physical_therapy.json` |
| AI Content | 🤖 | AI-generated/synthetic media indicators | `ai_content.json` |

**Adding new signatures:** Drop a JSON file in `safety-db/signatures/` following the schema. No code changes needed — the database loads all files at startup.

---

## C. AI Content Detection

The engine detects AI-generated content using **five independent signals** — no AI API required:

| Signal | How | Confidence |
|---|---|---|
| **Title patterns** | Regex matching: "doesn't exist", "AI made", "not real" | Medium |
| **Hashtag analysis** | Counts AI-related hashtags (#aiart, #midjourney, #sora, etc.). ≥2 = flagged | High |
| **Channel heuristics** | Channel name contains "AI [Animal]" or "[Animal] AI" pattern | Medium |
| **Impossible content** | Title + description describe physically impossible scenarios | High |
| **Dangerous combinations** | Detects children/babies with dangerous animals (safety concern) | Critical |

When AI content is detected, the extension offers three categories of alternatives:
1. **Real videos** — authentic content on the same subject from trusted channels
2. **AI tutorials** — learn how to make AI videos yourself
3. **AI entertainment** — quality AI content from curated creators

---

## D. Extension Architecture

### Manifest V3

Chrome extension using Manifest V3 with strict permissions:

```json
{
    "manifest_version": 3,
    "permissions": ["activeTab", "storage"],
    "content_security_policy": {
        "extension_pages": "script-src 'self'; object-src 'self'"
    }
}
```

No `<all_urls>`, no `webRequest`, no `tabs` — minimal privilege.

### Content Script Load Order

```
utils.js → overlay.js → analysis.js → content.js
```

| Script | Lines | Purpose |
|---|---|---|
| `utils.js` | 185 | Video ID extraction, ad detection, title/channel scraping, `escapeHtml()` |
| `overlay.js` | 387 | Safety warning overlay, AI content banner, alternative video cards |
| `analysis.js` | 235 | Video analysis orchestration, API communication |
| `content.js` | 160 | Entry point, SPA navigation handling (`yt-navigate-finish`), initialization |
| `panel.js` | 680 | Panel state model, rendering, queue management for the 4-panel system |
| `modes.js` | 350 | Mode handlers (Data, Random, Subject, Learn) |
| `sidebar.js` | 700 | Shadow DOM sidebar, layout adjustment, presets, events |
| `player.js` | 200 | Individual panel playback control |

### Service Worker (`background.js`)

- **API proxy** — routes all backend requests through the service worker (CORS-safe)
- **Endpoint allowlist** — only proxies to known safe endpoints
- **Caching** — in-memory analysis cache (migrating to `chrome.storage.session`)
- **Rate limiting** — 30-second per-video cooldown, daily quota enforcement

### Shadow DOM Isolation

The sidebar UI is rendered inside a Shadow DOM root:

```javascript
const host = document.createElement('div');
const shadow = host.attachShadow({ mode: 'closed' });
// All sidebar CSS and HTML lives inside shadow — zero leakage
```

This guarantees:
- Extension CSS cannot break YouTube's layout
- YouTube's CSS cannot affect extension appearance
- No class name collisions

---

## E. Multi-Panel Sidebar System

### 4-Panel Grid (v3.0)

The sidebar presents a 2×2 grid of mini-screens. Each panel independently displays content in one of four modes:

| Mode | What It Shows | API Cost |
|---|---|---|
| 📊 Data | Video statistics, engagement metrics | 1 API unit |
| 🎲 Random | Random interesting video from curated sources | 0 (from curated DB) |
| 🔍 Subject | Related videos on the same topic | 1 API unit |
| 📚 Learn | Educational content about the video's topic | 0 (from curated playlists) |

### Presets

5 one-click presets that configure all 4 panels at once:

| Preset | Panel 1 | Panel 2 | Panel 3 | Panel 4 | Use Case |
|---|---|---|---|---|---|
| 🔍 Explorer | Subject | Random | Data | Learn | General browsing |
| 🎯 Deep Dive | Subject | Data | Learn | Subject | Research a topic |
| 🎬 Creator | Data | Learn | Random | Data | Content creators |
| 🔬 Audit | Data | Subject | Data | Learn | Fact-checking |
| 😌 Chill | Random | Random | Random | Random | Lean back |

### Panel Controls

Each panel has independent:
- **Mute/unmute** — per-panel audio control
- **Play/pause** — individual playback
- **Next** — skip to next video in queue
- **Mode selector** — switch modes per panel
- **Promote** — click to make a panel's content the main YouTube player

---

## F. API Reference

Base URL: `http://localhost:8000`

### POST `/analyze`

Analyze a YouTube video for safety concerns.

```json
// Request
{
    "video_id": "dQw4w9WgXcQ",
    "title": "Optional scraped title",
    "description": "Optional scraped description",
    "channel": "Optional channel name"
}

// Response
{
    "video_id": "dQw4w9WgXcQ",
    "safety_score": 98,
    "warnings": [
        {
            "category": "AI Content",
            "severity": "high",
            "message": "Video appears to contain AI-generated content"
        }
    ],
    "categories": {
        "AI Content": { "emoji": "🤖", "flagged": false, "score": 100 },
        "Fitness": { "emoji": "🏋️", "flagged": false, "score": 100 }
    },
    "summary": "Video appears safe. No dangerous content detected.",
    "transcript_available": true,
    "vision_analysis": null,
    "safe_alternatives": {
        "enabled": true,
        "alternatives": [
            {
                "id": "abc123...",
                "title": "Safe Alternative Video",
                "channel": "BBC Earth",
                "thumbnail": "https://...",
                "url": "https://www.youtube.com/watch?v=...",
                "is_trusted": true
            }
        ]
    }
}
```

### POST `/ai-tutorials`

Find tutorials on how to create AI content.

```json
{ "subject": "dogs", "prefer_shorts": false, "max_results": 8 }
```

### POST `/ai-entertainment`

Find quality AI entertainment from curated creators.

```json
{ "subject": "dogs", "prefer_shorts": true, "max_results": 4 }
```

### GET `/report/{video_id}`

Full HTML analysis report for a video. Renders server-side with escaped output.

### GET `/health`

Health check. Returns service status and component availability.

### GET `/signatures` / GET `/categories`

Return the loaded signature database and category definitions.

### Rate Limits

| Endpoint | Limit | Window |
|---|---|---|
| `/analyze` | 10 requests | 1 minute |
| `/ai-tutorials` | 15 requests | 1 minute |
| `/ai-entertainment` | 15 requests | 1 minute |
| `/real-alternatives` | 15 requests | 1 minute |
| `/health` | 60 requests | 1 minute |
| All others | 30 requests | 1 minute |

---

## G. Security Model

### Defense-in-Depth

```
Layer 1: Input Validation        → Video ID regex (^[a-zA-Z0-9_-]{11}$), Pydantic field limits
Layer 2: Security Headers        → X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
Layer 3: Rate Limiting           → Per-IP, per-endpoint sliding window
Layer 4: XSS Prevention          → escapeHtml() on all dynamic content, severity whitelisting
Layer 5: CSP Compliance          → No inline onclick/onerror, delegated event handlers
Layer 6: API Proxy               → Extension → Service Worker → Backend (never direct)
Layer 7: Shadow DOM Isolation    → Sidebar CSS sandboxed, zero leakage to/from YouTube
Layer 8: CORS Whitelisting       → Only allowed extension IDs and localhost origins
Layer 9: Settings Import         → Schema validation with type checking and enum enforcement
```

### Security Hardening Completed

| Fix | Description |
|---|---|
| XSS in `/report` | HTML template now uses `html.escape()` for all dynamic values |
| Input validation | Video ID validated via regex before processing |
| Rate limiter bug | Cleanup now prunes stale entries instead of clearing all |
| CSP violations | Inline `onclick`/`onerror` replaced with `data-*` attributes + `addEventListener` |
| innerHTML injection | `warning.severity` whitelisted, `data.emoji` sanitized to emoji-only characters |
| Import validation | `importSettings()` validates types, enum values, and array contents |
| External links | `rel="noopener noreferrer"` added to all `target="_blank"` links |
| Secret management | No hardcoded secrets — all API keys from environment variables |
| Dependency pinning | Exact versions in `requirements.txt` for reproducible builds |

### Ongoing Security Items

| Item | Status | Sprint |
|---|---|---|
| ~~V2-1.1 Fix XSS in /report~~ | ✅ Done | S1 |
| ~~V2-1.2 Input validation~~ | ✅ Done | S1 |
| ~~V2-1.3 Rate limiter bug~~ | ✅ Done | S1 |
| ~~V2-1.4 SECURITY.md update~~ | ✅ Done | S1 |
| ~~V2-2.1 CSP inline onclick~~ | ✅ Done | S2 |
| ~~V2-2.2 innerHTML sanitization~~ | ✅ Done | S2 |
| ~~V2-2.3 Import schema validation~~ | ✅ Done | S2 |
| ~~V2-2.4 rel=noopener~~ | ✅ Done | S2 |
| V2-3.x Service worker caching | 🔲 Planned | S3 |
| V2-4.x Dead code cleanup | 🔲 Planned | S3 |

See [SECURITY.md](SECURITY.md) for full vulnerability reporting instructions.

---

## H. Scaling Analysis

The system has **14 documented bottlenecks** with migration paths. Full analysis in [SCALING.md](SCALING.md).

### Current Architecture (Portfolio Scale: ~100 concurrent users)

| Component | Current State | Scalability |
|---|---|---|
| Extension UI | Runs per-user in browser | ✅ Infinite — each user runs their own copy |
| Settings/Presets | `chrome.storage.sync` | ✅ Infinite — per-user |
| Backend | Single FastAPI process | ⚠️ Single-core, single-process |
| Rate limiting | In-memory dict | ❌ Lost on restart, not shared across workers |
| API quota | In-memory counter | ❌ Lost on restart, per-worker fragmentation |
| Analysis cache | None (server-side) | ❌ Every request recomputes |
| Safety DB | JSON files loaded at startup | ⚠️ Not queryable, no runtime updates |

### The Hard Wall: YouTube API Quota

| Scale | Daily API Units Needed | Available | Gap |
|---|---|---|---|
| 100 users | ~1,500 | 10,000 | ✅ Fine |
| 1K users | ~15,000 | 10,000 | ⚠️ 1.5× over |
| 10K users | ~150,000 | 10,000 | 🔴 15× over |

**Mitigation strategy**: Curated content DB (zero API cost for Random/Learn modes), aggressive caching (viral videos analyzed once), transcript-first analysis (free), reduced use of `search.list` (100 units → `playlistItems.list` at 1 unit).

### Scaling Roadmap

| Phase | Users | Changes | Est. Cost |
|---|---|---|---|
| 0 (Current) | 10–100 | Single process + Docker | $0–6/mo |
| 1 | 100–1K | Redis caching, Gunicorn workers | $15–30/mo |
| 2 | 1K–10K | PostgreSQL, curated content DB, 4+ workers | $100–300/mo |
| 3 | 10K–100K | Multi-region, CDN, task queue (Celery) | $1K–5K/mo |

---

## I. Testing Strategy

### Test Suites

```bash
# Run all backend tests
cd backend
python -m pytest tests/ -v             # 260 tests, ~13s

# With coverage
python -m pytest tests/ --cov          # Coverage report
```

| Suite | File | Tests | Covers |
|---|---|---|---|
| Analyzer | `test_analyzer.py` | 6 | Pattern matching, analysis flow, trusted channels, API-less mode |
| Integration | `test_integration.py` | 13 | All API endpoints, input validation, security headers |
| Safety DB | `test_safety_db.py` | 13 | Database loading, categories, signatures, schema validation |
| YouTube Data | `test_youtube_data.py` | 15 | Context managers, metadata parsing, comment analysis, error handling |
| Security (S1) | `test_security_s1.py` | 11 | XSS prevention, video ID validation, rate limiter cleanup |
| AI Reviewer | `test_ai_reviewer.py` | 61 | Heuristic debunking, AI provider init, content review, keyword coverage |
| Edge Cases | `test_edge_cases.py` | 141 | Boundary conditions, malformed input, regression tests |

### What's Tested

| Layer | Coverage |
|---|---|
| API endpoint responses | ✅ All 6 endpoints |
| Input validation (SQL injection, XSS, overflow) | ✅ 5 attack vectors |
| Security headers on every response | ✅ Verified |
| Rate limiter logic (window, cleanup, edge cases) | ✅ 2 focused tests |
| HTML report XSS prevention | ✅ 4 injection tests |
| Safety score calculation | ✅ Safe + dangerous flows |
| Transcript extraction flow | ✅ With/without API key |
| Comment sentiment analysis | ✅ 7 scenarios |

### What's Not Tested (Honest Assessment)

| Gap | Why | Plan |
|---|---|---|
| Vision analyzer | Requires yt-dlp + ffmpeg + OpenAI API | Excluded from coverage |
| E2E browser tests | No Playwright/Puppeteer setup | Planned |
| Current coverage | Improving — 260 backend + 73 frontend tests | Expanding incrementally |

---

## J. Project Structure

```
youtube-safety-inspector/
├── extension/                   # Browser extension source
│   ├── manifest.json            # Chrome Manifest V3
│   ├── manifests/               # Per-browser manifests
│   │   ├── manifest.chrome.json
│   │   ├── manifest.firefox.json
│   │   └── manifest.edge.json
│   ├── content/                 # Content scripts + CSS
│   │   ├── content.js           # Entry point, SPA navigation
│   │   ├── analysis.js          # Video analysis orchestration
│   │   ├── overlay.js           # Safety overlays + AI banner
│   │   ├── sidebar.js           # Shadow DOM sidebar (700 lines)
│   │   ├── panel.js             # 4-panel state model (680 lines)
│   │   ├── modes.js             # Data/Random/Subject/Learn modes
│   │   ├── player.js            # Panel playback control
│   │   ├── utils.js             # Shared utilities, escapeHtml
│   │   ├── content.css          # Content script styles
│   │   └── sidebar.css          # Sidebar-specific styles
│   ├── background/
│   │   └── background.js        # Service worker: API proxy, caching
│   ├── popup/
│   │   ├── popup.html           # Popup UI
│   │   ├── popup.css            # Popup styles
│   │   └── popup.js             # Popup logic: score display, settings
│   └── icons/
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
│
├── backend/                     # Python FastAPI server
│   ├── main.py                  # API endpoints + middleware (753 lines)
│   ├── analyzer.py              # Safety analysis engine (1,174 lines)
│   ├── ai_reviewer.py           # AI contextual reviewer + debunking (684 lines)
│   ├── alternatives_finder.py   # Safe video discovery (574 lines)
│   ├── safety_db.py             # Signature database loader (500 lines)
│   ├── youtube_data.py          # YouTube API client (308 lines)
│   ├── vision_analyzer.py       # GPT-4 Vision frame analysis (294 lines)
│   ├── requirements.txt         # Pinned dependencies
│   ├── pyproject.toml           # Project config + test settings
│   └── tests/                   # pytest suite (260 tests)
│       ├── conftest.py          # Fixtures
│       ├── test_analyzer.py     # Analyzer unit tests
│       ├── test_ai_reviewer.py  # AI reviewer unit tests (61 tests)
│       ├── test_edge_cases.py   # Boundary & regression tests (141 tests)
│       ├── test_integration.py  # API endpoint tests
│       ├── test_safety_db.py    # Database tests
│       ├── test_youtube_data.py # Data fetcher tests
│       └── test_security_s1.py  # Security regression tests
│
├── safety-db/                   # Danger signature database
│   ├── categories.json          # Category definitions (10 categories)
│   └── signatures/              # Per-category pattern files (11 files)
│       ├── fitness.json
│       ├── diy.json
│       ├── cooking.json
│       ├── electrical.json
│       ├── medical.json
│       ├── chemical.json
│       ├── driving.json
│       ├── osha.json
│       ├── physical_therapy.json
│       ├── ai_content.json
│       └── ...
│
├── store/                       # Chrome Web Store assets
│   ├── listing.md               # Store listing copy
│   └── privacy-policy.md        # Privacy policy
│
├── build.js                     # Cross-browser build script
├── package.json                 # npm scripts + deps
├── Dockerfile                   # Multi-stage production build
├── docker-compose.yml           # One-command deployment
├── .env.example                 # Environment variable template
├── START.ps1                    # One-click Windows setup
├── .eslintrc.json               # ESLint config
├── pre-commit-hook.sh           # Pre-commit quality checks
│
├── SECURITY.md                  # Vulnerability reporting + security posture
├── SCALING.md                   # 14 bottlenecks + migration paths
├── CHANGELOG.md                 # Version history
├── CONTRIBUTING.md              # Contribution guidelines
└── LICENSE                      # MIT
```

---

## K. Configuration

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `YOUTUBE_API_KEY` | Recommended | YouTube Data API for comments, search, metadata |
| `OPENAI_API_KEY` | Optional | GPT-4 Vision frame analysis |
| `ALLOWED_EXTENSION_IDS` | Optional | CORS whitelist for specific extension IDs |

### System Dependencies (Optional)

| Tool | Purpose | Required For |
|---|---|---|
| `yt-dlp` | Video frame download | Vision analysis only |
| `ffmpeg` | Frame extraction from video | Vision analysis only |

### Build Commands

| Command | Description |
|---|---|
| `npm run build` | Build all browsers |
| `npm run build:chrome` | Chrome only → `dist/chrome/` |
| `npm run build:firefox` | Firefox only → `dist/firefox/` |
| `npm run build:edge` | Edge only → `dist/edge/` |
| `npm run build:dev` | Chrome dev build |
| `npm run watch` | Chrome + file watcher |
| `npm run clean` | Delete `dist/` |
| `npm run lint` | ESLint check |
| `npm run test:backend` | Run pytest suite |
| `npm run test:frontend` | Run Vitest frontend suite |
| `npm run test` | Run Vitest frontend suite |

### Without Any API Keys

The extension still works without API keys:
- **Transcript analysis** — extracted directly, no API needed
- **Title/description/channel heuristics** — scraped from the page
- **Signature matching** — works offline against the local database
- **AI detection heuristics** — pattern-based, no API needed

With API keys enabled, you additionally get:
- Comment analysis (community sentiment)
- Safe alternative video discovery
- Video metadata enrichment
- Vision-based frame analysis (with OpenAI key)

---

## Troubleshooting

| Problem | Solution |
|---|---|
| Sidebar not showing | Make sure you loaded from `dist/chrome/`, not `extension/`. Navigate to a video page (not homepage). |
| Server exits immediately | Start the backend in a separate terminal window |
| Vision warnings | Expected without `OPENAI_API_KEY` / `yt-dlp` / `ffmpeg` |
| CORS errors | API calls route through the service worker — check it's loaded |
| Sidebar overlaps content | Hard refresh the YouTube page after extension reload |
| `pip install` failures | Ensure Python 3.11+ is installed. Use `pip install --upgrade pip` first. |

---

## Version History

| Version | Date | Changes |
|---|---|---|
| v3.0.1 | Feb 2026 | AI contextual reviewer (684 lines), debunking detection, 260-test pytest suite, 73 Vitest frontend tests, CWS compliance fixes |
| v3.0.0 | Feb 2026 | Multi-screen sidebar, 4-panel grid, 5 presets, cross-browser build, YouTube-native UI |
| v2.1.0 | Feb 13, 2026 | Security hardening (8 fixes), 58-test pytest suite, accessibility, keyboard shortcuts |
| v2.0.0 | Jan 2026 | Settings panel, 15+ options, trusted channels, export/import |
| v1.0.0 | Jan 2026 | Initial release: AI detection, safety scoring, alternatives |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

- Add danger signatures to `safety-db/signatures/` following the existing JSON schema
- Run `npm run lint` and `npm run test:backend` before submitting PRs
- Security scans recommended: `truffleHog`, `gitleaks`

---

## License

[MIT](LICENSE)

---

*Built with Python, FastAPI, and Chrome Manifest V3. 333 tests. 10 safety categories. 14 documented scaling bottlenecks. Zero inline scripts.*
