# YouTube Safety Inspector v4.0 — Project Status (Reset & Re-plan)

> [!IMPORTANT]
> **Status:** PLANNING / RECOVERY
> **Current Focus:** Fixing the "broken" feel by strictly implementing the missing Player (Phase 3) and fixing the Data Bridge.

## 🎯 Immediate Goals (The "Fix It" Scope)

| Priority | Feature | Status | The Issue |
|----------|---------|--------|-----------|
| 1 | **The Player** | 🔴 Missing | Sidebar has panels but no actual video player. Users see "stupid thumbnails" that don't play. |
| 2 | **Data Bridge** | 🔴 Broken | `bridge.js` is getting 403 Forbidden errors trying to fetch video streams directly. |
| 3 | **Analysis API** | 🔴 Broken | Backend connection (`/analyze`) is failing (`API Error`). |
| 4 | **UI Polish** | 🟡 Rough | "Suggestions" and thumbnails look bad/broken. |

---

## 📋 Micro-Task Roadmap (Sprint 1: The "It Works" Update)

This roadmap breaks down the "Redesign & Fix" into tiny, verifiable steps.

### Phase 1: Fix the Foundation (Data & Backend)
| Task ID | Task Name | Plan A | Plan B | Status |
|---------|-----------|--------|--------|--------|
| **1.1** | **Stop `bridge.js` 403 Errors** | **Remove raw video fetching.** The bridge is trying to GET `videoplayback` urls. We don't need this for an IFrame player. Stop it. | **Filter requests.** If we validly need these, add proper referer headers (unlikely to work). | ⬜ |
| **1.2** | **Fix DOM Scraper** | **Resilient Selectors.** Update selectors for new YouTube layout (`ytd-rich-grid-media`). | **Fallback to JSON.** Parse `ytInitialData` global object. | ⬜ |
| **1.3** | **Backend API Health** | **Fix CORS/Port.** Ensure `main.py` is running on 8000 and extension requests it correctly. | **Proxy.** Route requests through a background service worker proxy. | ⬜ |

### Phase 2: The Player (Making it Play)
| Task ID | Task Name | Plan A | Plan B | Status |
|---------|-----------|--------|--------|--------|
| **2.1** | **Embed YouTube IFrame** | **API Mode.** Inject `YT.Player` into the "Active" panel (Panel 1). | **Simple IFrame.** Just an `<iframe src="...">` tag (less control). | ⬜ |
| **2.2** | **Panel State Wiring** | **State Promotion.** Clicking a thumbnail (Panels 2-4) updates Panel 1's `videoId` state. | **Direct DOM.** Click handler directly changes iframe `src`. | ⬜ |
| **2.3** | **Active Playing Badge** | **CSS Overlay.** "Playing" badge on the active panel thumbnail. | **Border Highlight.** Simple color border. | ⬜ |

### Phase 3: The "Smart" Features (Suggestions coverage)
| Task ID | Task Name | Plan A | Plan B | Status |
|---------|-----------|--------|--------|--------|
| **3.1** | **Populate 4 Panels** | **Mock Data.** Fill panels with hardcoded valid IDs first to prove UI works. | **Real Scrape.** Use the fixed scraper from 1.2. | ⬜ |
| **3.2** | **Mode Selector** | **Simple Dropdown.** Fix the "Mode" dropdown to actually switch data sources. | **Fixed Modes.** Hardcode Panel 1=Subject, Panel 2=Random, etc. for now. | ⬜ |

---

## 📉 Known Issues & Regressions
- **Bridge 403:** `GET .../videoplayback 403`. Cause: Attempting to unauthorized download/stream video. Fix: Stop doing that. Use IFrame.
- **API Error:** `Analysis failed`. Cause: Likely CORS or backend not running/reachable.
- **Unload Policy:** `Permissions policy violation: unload`. Cause: Old-school cleanup code. Low priority but noisy.

## 📝 Session Log
- **2026-02-19:** Project Reset. Created V4 Status. Acknowledged missing Player component.
