# YouTube Safety Inspector — Scaling & Bottleneck Analysis

> **Purpose**: Document every scaling bottleneck in the current architecture and the migration path to handle 1B+ users. Written proactively before building new features.
>
> **Last Updated**: 2026-02-18

---

## Executive Summary

The current architecture is a **single-process FastAPI backend** with **in-memory state** and a **browser extension client**. This works perfectly for development and small-scale deployment (~1–100 users), but has 14 identified bottlenecks that would prevent horizontal scaling.

The good news: **the extension client scales inherently** (each user runs their own copy). The bottlenecks are entirely in the backend and the YouTube API quota. Both are solvable with standard patterns.

---

## Bottleneck Inventory

### 🔴 Critical (Breaks at ~100 concurrent users)

| # | Component | File | What | Why It Breaks |
|---|-----------|------|------|---------------|
| B1 | Rate Limiter | `main.py:76` | `_rate_limit_store: dict` — in-memory sliding window | Lost on restart. Not shared across workers/processes. `.clear()` bug wipes ALL entries when store > 1000. |
| B2 | API Quota Tracker | `main.py:172` | `api_quota_tracker: dict` — in-memory counter | Lost on restart. Each uvicorn worker has its own counter → quota can be exceeded by N× workers. |
| B3 | Single Process | `main.py:727` | `uvicorn.run(app)` — single worker | Can't utilize multiple CPU cores. No load balancing. One crash kills everything. |
| B4 | YouTube API Quota | YouTube API | 10,000 units/day per project | At 1M DAU × 5 calls/user = 5M calls/day. Quota is 500× insufficient. **This is the #1 wall.** |

### 🟡 High (Breaks at ~1,000 concurrent users)

| # | Component | File | What | Why It Breaks |
|---|-----------|------|------|---------------|
| B5 | No External Cache | Architecture | No Redis/Memcached | Every identical video analysis repeats full computation. Two users analyzing the same viral video = 2× API calls, 2× CPU. |
| B6 | JSON File Database | `safety_db.py:38` | Signatures loaded from `safety-db/*.json` at startup | Can't update signatures at runtime without restart. File I/O on every cold start. Not queryable. |
| B7 | Singleton Globals | `main.py:144-146` | `analyzer`, `safety_db`, `alternatives_finder` — module-level globals | Not fork-safe. Gunicorn `--preload` needed or each worker re-initializes. State not shared. |
| B8 | httpx Client Lifecycle | `youtube_data.py:48` | New `httpx.AsyncClient()` per `YouTubeDataFetcher` instance | Connection pool not reused. SSL handshake per request. Should use a shared client with connection pooling. |

### 🟢 Medium (Breaks at ~10,000+ concurrent users or causes degradation)

| # | Component | File | What | Why It Breaks |
|---|-----------|------|------|---------------|
| B9 | Vision Analyzer | `vision_analyzer.py:110` | `yt-dlp` + `ffmpeg` subprocess per video | Spawns OS processes, downloads video, writes to disk, encodes frames. CPU + disk + bandwidth heavy. 5+ seconds per request. |
| B10 | Regex Compilation | `analyzer.py:99-189` | ~30 compiled regexes in `SafetyAnalyzer.__init__` | Compiled once per instance (OK), but some patterns are very long (~500 chars with alternation). CPU cost per match scales linearly with text length. |
| B11 | No Request Queue | Architecture | Requests processed synchronously in event loop | Long-running analysis blocks the event loop. Vision analysis (5+ sec) starves other requests. |
| B12 | Fallback Data in Memory | `alternatives_finder.py:32-44` | 8 JSON files loaded into memory at init | ~50-100KB per instance. Multiplied by N workers = wasted RAM for identical data. |

### 🔵 Extension-Side (Different scaling model)

| # | Component | File | What | Why It Breaks |
|---|-----------|------|------|---------------|
| B13 | In-Memory Cache | `background.js:27` | `analysisCache = new Map()` | Lost when MV3 service worker sleeps (~30s idle). User re-analyzes same video repeatedly. |
| B14 | setInterval Cleanup | `background.js:253` | `setInterval(() => {...}, 60000)` | Never fires — service worker dies before 60s. Cache grows unbounded until worker restart. |

---

## Scaling Strategies

### Strategy 1: YouTube API Quota — The Hard Wall

**Current**: 10,000 units/day (free tier). A `search.list` call costs 100 units. A `videos.list` costs 1 unit. A `commentThreads.list` costs 1 unit.

**Math at scale**:

| Scale | DAU | Analyses/day | API Units Needed | Gap |
|-------|-----|--------------|-----------------|-----|
| 100 users | 100 | 500 | ~1,500 | ✅ Fine |
| 1K users | 1,000 | 5,000 | ~15,000 | ⚠️ 1.5× over quota |
| 10K users | 10,000 | 50,000 | ~150,000 | 🔴 15× over quota |
| 1M users | 1,000,000 | 5,000,000 | ~15,000,000 | 🔴 1,500× over quota |

**Solutions (in priority order)**:

1. **Curated Content DB** (Sprint S12-S13): Pre-populate categories with verified channel/video data. Random Mode and Learn Mode can serve from DB without any API call.
2. **Aggressive Server-Side Caching** (Redis): Cache video analysis results for 24 hours. Viral videos analyzed once, served to millions.
3. **Client-Side Caching** (chrome.storage): Cache results locally per user. Re-visiting a video never triggers API call.
4. **Reduce Search Calls**: `search.list` = 100 units. Replace with `playlistItems.list` = 1 unit. Use curated playlist IDs instead of search queries.
5. **Apply for Higher Quota**: Google allows quota increase requests for legitimate projects. With good documentation and usage metrics, 100K-1M units/day is achievable.
6. **Multiple API Keys**: Rotate keys across projects. Legal gray area — better to get quota increase.

**Target**: With strategies 1-4, we can reduce API calls by ~95%, making 10K units/day sufficient for ~100K users.

---

### Strategy 2: Backend Horizontal Scaling

**Current → Target Migration Path**:

```
CURRENT (Single Process)          TARGET (Horizontally Scalable)
┌─────────────────┐               ┌──────────────────┐
│  uvicorn (1)    │               │  Load Balancer   │
│  ┌────────────┐ │               │  (nginx/Caddy)   │
│  │ FastAPI    │ │               └──────┬───────────┘
│  │ + in-mem   │ │                      │
│  │   state    │ │               ┌──────┴───────────┐
│  └────────────┘ │               │ Gunicorn/uvicorn  │
└─────────────────┘               │ (N workers)       │
                                  ├───────────────────┤
                                  │ Worker 1 │ Worker 2│
                                  │ Worker 3 │ Worker N│
                                  └──────┬───────────┘
                                         │
                                  ┌──────┴───────────┐
                                  │    Redis Cache    │
                                  │  - Rate limits    │
                                  │  - Quota counter  │
                                  │  - Analysis cache │
                                  └──────────────────┘
```

**Migration steps** (future sprints):

| Step | What | Effort | When |
|------|------|--------|------|
| 1 | Move rate limiter → Redis | Low | When deploying |
| 2 | Move quota tracker → Redis | Low | When deploying |
| 3 | Add gunicorn with N workers | Low | When deploying |
| 4 | Add Redis analysis cache | Medium | Sprint S14+ |
| 5 | Move curated DB → PostgreSQL | Medium | If DB grows > 10MB |
| 6 | Add task queue (Celery/RQ) for vision | Medium | If vision usage grows |

**Key principle**: We design the interfaces NOW so migration is trivial later. Example: abstract the rate limiter behind a `RateLimiter` class so switching from dict → Redis is a single file change.

---

### Strategy 3: Caching Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Extension (Client)                 │
│                                                       │
│  L1: In-Memory (Map)     — Session-only, instant      │
│  L2: chrome.storage      — Persists across restarts   │
│      .session (temp)     — For rate limit state        │
│      .local (persistent) — For analysis cache (24h)    │
│      .sync (synced)      — For user settings           │
└──────────────────────────┬────────────────────────────┘
                           │ HTTP API
┌──────────────────────────┴────────────────────────────┐
│                    Backend (Server)                     │
│                                                         │
│  L3: Redis Cache         — Shared across workers        │
│      Key: video:{id}     — TTL: 24 hours                │
│      Key: rate:{ip}      — TTL: 60 seconds              │
│      Key: quota:daily    — TTL: until midnight           │
│                                                         │
│  L4: Curated DB (JSON→PG) — Permanent, queryable       │
│      Channels, playlists, category mappings             │
└─────────────────────────────────────────────────────────┘
```

**TTL Strategy**:

| Cache Layer | TTL | Rationale |
|-------------|-----|-----------|
| L1 (Map) | Session | Fastest, but lost on worker sleep |
| L2 (chrome.storage.local) | 24h | Survives restarts, per-user |
| L3 (Redis) | 24h for analysis, 60s for rate limits | Shared, saves API calls for popular videos |
| L4 (Curated DB) | Permanent + manual updates | Editorial content, rarely changes |

---

### Strategy 4: Extension-Side Fixes (Immediate)

These can be fixed NOW without infrastructure changes:

| Fix | What | Sprint |
|-----|------|--------|
| Migrate `analysisCache` Map → `chrome.storage.session` | Survives service worker sleep | S2 |
| Remove `setInterval` (dead code) | Service worker can't keep timers | S2 |
| Add cache TTL to stored results | Prevent stale data | S2 |
| Migrate `rateLimiter` Map → implicit cache check | Simpler, fewer moving parts | S2 |

---

## Architecture Decisions for V3 Features

### Sidebar (4-Panel System)
- **Scales fine**: Runs entirely in the user's browser. No backend interaction for UI rendering.
- **Watch for**: Memory usage with 4 embedded iframes. Cap at 1 active player + 3 thumbnail cards.

### Modes (Data, Random, Subject, Learn)
- **Random Mode**: Should pull from curated DB, NOT from YouTube search API. Zero API cost.
- **Subject Mode**: Can use `videos.list` (1 unit) with related video IDs instead of `search.list` (100 units).
- **Learn Mode**: Should pull from curated tutorial playlists. Zero API cost for playlist content.
- **Data Mode**: One `videos.list` call (1 unit) for statistics. Cache aggressively.

### Presets
- **Scales fine**: Stored in `chrome.storage.sync`. No backend interaction.

### Color Theming
- **Scales fine**: CSS custom properties, stored in `chrome.storage.sync`. Zero backend cost.

---

## Scalability Score

| Component | Current Score | After V3 (Planned) | At 1B Scale |
|-----------|--------------|--------------------|-|
| Extension UI | A | A | A |
| Settings/Presets | A | A | A |
| Client Caching | D | B | A |
| Rate Limiting | C | B | A (with Redis) |
| API Quota Usage | C | B | B (with caching + curated DB) |
| Backend Compute | D | C | A (with workers + queue) |
| Data Storage | C | B | A (with PostgreSQL) |
| Vision Analysis | D | D | B (with queue + GPU workers) |
| **Overall** | **D+** | **B** | **A-** |

---

## Immediate Actions (This Sprint)

These findings will influence upcoming sprints:

1. **S2**: Fix extension caching (B13, B14) — migrate to `chrome.storage.session`
2. **S4+**: Design mode endpoints to prefer curated DB over search API
3. **S10**: Abstract rate limiter behind interface for future Redis migration
4. **S12-S13**: Build curated DB as the primary content source, not a fallback
5. **S14**: Add caching headers to API responses, design for Redis-ready data access

No infrastructure changes needed yet. We design the interfaces to be swappable.

---

*This document will be updated as we build. Each sprint will note scaling implications.*
