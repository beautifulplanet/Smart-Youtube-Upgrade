# YouTube Safety Inspector v4.0 — Detailed Scope & Implementation Plan

> [!IMPORTANT]
> **Goal:** Fix the "broken" feeling extensions by implementing the missing playback features and fixing the data fetching errors. This Plan replaces all previous plans.

## 🚨 Critical Fixes & "The Player" (Sprint 1)

This sprint focuses solely on getting the extension to *work* reliably: playing videos, showing real suggestions, and not throwing errors.

---

### Task 1.1: Stop the "403 Forbidden" Bridge Errors
**Problem:** The extension is trying to fetch raw video files (`videoplayback`) via `bridge.js`. This is blocked by YouTube and causes errors.
**Goal:** Stop these requests. We don't need raw files for an IFrame player.

#### Plan A — Remove the offending fetch code (Recommended)
1.  **Locate:** Find the `fetch` call in `bridge.js` (lines 260-270 based on logs).
2.  **Analyze:** Determine *why* it was added (likely for an older analysis method).
3.  **Action:** Comment out or remove the fetch block.
4.  **Verify:** Reload extension, check console. 403 errors should be gone.

#### Plan B — Filter/Guard the fetch
1.  **If:** The fetch is absolutely required for analysis (unlikely given we have a backend), add a check.
2.  **Action:** Only fetch if `url` matches a safe pattern, or wrap in a `try/catch` that suppresses the 403 log.
3.  **Risk:** Masking the issue doesn't fix the underlying architecture flaw.

---

### Task 1.2: Fix Backend `API Error`
**Problem:** `analysis.js` reports `API Error: Analysis failed`. This means the extension can't talk to `localhost:8000`.
**Goal:** Reliable communication between Extension and Python Backend.

#### Plan A — Fix CORS & Fetch (Recommended)
1.  **Backend:** Check `main.py`. Ensure `allow_origins` includes the extension ID (or `*` for dev).
2.  **Frontend:** In `background.js` and `analysis.js`, ensure `API_BASE_URL` is `http://127.0.0.1:8000` (localhost can sometimes be ambiguous).
3.  **Action:** Add error logging to `background.js` to print the exact fetched URL and response status.
4.  **Verify:** Click "Analyze". Terminal should show `200 OK`.

#### Plan B — Proxy via Background Script
1.  **If:** Content scripts are blocked by CORB/CORS from hitting localhost directly.
2.  **Action:** Move all `fetch` calls to `background.js`. Content script sends message `FETCH_ANALYSIS` -> Background -> Backend -> Background -> Content.
3.  **Why:** Background scripts have fewer CORS restrictions in MV3.

---

### Task 2.1: Implement the Missing "Player" (Phase 3)
**Problem:** The panels are just static HTML. Users expect a video player.
**Goal:** Panel 1 (or the "Aktiv" panel) contains a working YouTube IFrame.

#### Plan A — The "Active Panel" Strategy (Hybrid)
1.  **Concept:** One panel is "Active" (Player). Three are "Passive" (Cards).
2.  **HTML:** Add `<div id="ysi-player"></div>` to the active panel's structure.
3.  **JS:** Initialize `new YT.Player('ysi-player', ...)` on load.
4.  **Wiring:** When a Passive panel is clicked:
    *   Get `videoId` from clicked panel.
    *   Call `player.loadVideoById(videoId)`.
    *   (Optional) Swap the visual content so the clicked video "moves" to the player slot.

#### Plan B — The "Simple Iframe" Strategy (Fallback)
1.  **Concept:** Just replace the thumbnail with an `<iframe>`.
2.  **Action:** On click, `innerHTML = '<iframe src="https://www.youtube.com/embed/..." allow="autoplay"></iframe>'`.
3.  **Pros:** Zero dependencies, very robust.
4.  **Cons:** Can't programmatically pause/mute/get progress comfortably. Harder to get "Next" button working.

---

### Task 2.2: Fix "Stupid Thumbnails" (UI Polish)
**Problem:** Thumbnails look broken or don't play.
**Goal:** Thumbnails should look clickable and clearly indicate "Click to Play".

#### Plan A — CSS Overlay & Hover
1.  **CSS:** Add `.ysi-card:hover .play-icon { opacity: 1; }`.
2.  **Icon:** Add a central "Play" SVG icon over the thumbnail.
3.  **Cursor:** `cursor: pointer`.
4.  **Verify:** Hovering a card feels interactive.

#### Plan B — "Play" Button below
1.  **Action:** Add a distinct "Play" button in the control bar below the thumbnail.
2.  **Why:** Clearer affordance if the hover/overlay is tricky with YouTube's z-index.

---

### Task 3.1: Fix "Suggestions" / "Modes"
**Problem:** Suggestions aren't working / "Modes" don't match reality.
**Goal:** The 4 panels should show relevant, different suggestions.

#### Plan A — Mock Data First (Verification)
1.  **Action:** Hardcode 4 known safe video IDs (e.g., TED talks, Tutorials) into `sidebar.js` / initial state.
2.  **Verify:** Ensure the grid renders 4 distinct items.
3.  **Why:** Proves the UI grid works before fighting the API/Scraper.

#### Plan B — Restore Scraper
1.  **Action:** Debug `bridge.js` to see why it returns 0 videos initially.
2.  **Fix:** `ytInitialData` is often available before DOM. Parse that JSON instead of `document.querySelectorAll`.

---

## 📅 Execution Order (Tiny Micro-Tasks)

1.  **[ ] Task 1.1:** Analyze `bridge.js` and remove the 403-causing fetch.
2.  **[ ] Task 1.2:** Verify Backend is running and reachable (curl/postman).
3.  **[ ] Task 1.3:** Create `player.js` (empty file) to start the Player component.
4.  **[ ] Task 2.1:** Embed a hardcoded YouTube IFrame in Panel 1 (Plan A).
5.  **[ ] Task 2.2:** Verify IFrame plays video.
6.  **[ ] Task 2.3:** Wire Panel 2 click -> Update Panel 1 IFrame.

## 📝 Verification Prompts (for User)
- "Does the 403 error stop appearing in the console?"
- "Can you see the red 'Play' button on the first panel?"
- "When you click the second panel, does the first panel start playing that video?"
