# YouTube Safety Inspector v3.0 — Master Project Plan

## 🎯 Vision

Transform the YouTube Safety Inspector from a **single-shot popup overlay** into a **persistent, multi-screen content intelligence sidebar** with 4 configurable mini-screens, individual audio/playback controls, preset modes, and rich data visualization — all without disrupting the main video, ads, or YouTube's native experience.

---

## 🏗️ Architecture Decisions (Locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Mini-Screens** | Hybrid: 1 embedded player + 3 preview cards | Balances interactivity with embedding restrictions |
| **Sidebar Position** | Right sidebar, collapsible to thin strip | Non-intrusive, natural YouTube layout extension |
| **Target Browsers** | Chrome + Firefox + Edge | Maximum reach, MV3 everywhere |
| **Data Strategy** | YouTube API + Our own curated DB | Quota resilience, quality control, reliable baseline |
| **Main Video** | Never interrupted, ads preserved | Core principle — we AUGMENT, never block |

---

## 📋 Phases & Tasks

### PHASE 0: Foundation & Build System
**Goal**: Set up cross-browser build pipeline, restructure project for the new architecture.

---

#### Task 0.1: Create Cross-Browser Build Configuration
**What**: Set up a build system that outputs separate builds for Chrome, Firefox, and Edge from a single codebase.

**Plan A — Webpack + webextension-polyfill**
- Install `webpack`, `webpack-cli`, `copy-webpack-plugin`, `webextension-polyfill`
- Create `webpack.config.js` with three build targets (chrome, firefox, edge)
- Each target copies the correct manifest (`manifest.chrome.json`, `manifest.firefox.json`, `manifest.edge.json`)
- Output to `dist/chrome/`, `dist/firefox/`, `dist/edge/`
- Technical:
  ```
  extension/
    src/           ← shared source
    manifests/     ← per-browser manifests
  webpack.config.js
  dist/
    chrome/
    firefox/
    edge/
  ```

**Plan B — Simple Node.js build script (no bundler)**
- Create `build.js` that uses `fs-extra` to copy files and swap manifests
- No bundling, just file copying + manifest replacement
- Simpler, no webpack learning curve, works for our file structure
- Technical: `node build.js --target=chrome`

**Acceptance**: Running `npm run build:chrome`, `npm run build:firefox`, `npm run build:edge` each produce a loadable extension.

---

#### Task 0.2: Create Per-Browser Manifest Files
**What**: Generate MV3 manifests for Chrome/Edge and Firefox (Firefox supports MV3 but has some differences).

**Plan A — Three separate manifests**
- `manifest.chrome.json` — Current manifest, unchanged
- `manifest.firefox.json` — Add `browser_specific_settings.gecko.id`, change `service_worker` to `scripts` array in background
- `manifest.edge.json` — Copy of Chrome manifest (Edge is Chromium-based, identical MV3)

**Plan B — Template manifest with build-time variable injection**
- Single `manifest.template.json` with placeholders like `{{BACKGROUND_TYPE}}`
- Build script replaces placeholders per target
- More DRY but harder to read

**Acceptance**: Each manifest file validates and loads in its target browser without errors.

---

#### Task 0.3: Initialize package.json and Dev Dependencies
**What**: Create `package.json` with build scripts, linting, and dev dependencies.

**Plan A — Full toolchain**
- `npm init` with scripts: `build`, `build:chrome`, `build:firefox`, `build:edge`, `dev`, `lint`, `test`
- Dev deps: `webpack`, `webextension-polyfill`, `eslint`, `prettier`
- Add `.eslintrc.json` with browser extension rules

**Plan B — Minimal toolchain**
- `package.json` with only build scripts and `fs-extra`
- No linter initially, add later
- Fastest to set up

**Acceptance**: `npm install` works, `npm run build:chrome` works.

---

#### Task 0.4: Restructure Extension Source Directory
**What**: Move extension source files into `extension/src/` to separate source from build output.

**Plan A — Full restructure**
- Move all `.js`, `.css`, `.html` into `extension/src/`
- Update manifest paths accordingly
- Keep `icons/` in `extension/src/icons/`
- Build copies from `extension/src/` to `dist/<browser>/`

**Plan B — Keep current structure, build copies from `extension/`**
- Don't move files, just have build script copy from `extension/` root
- Less disruption to existing code
- Manifests live in `extension/manifests/`

**Acceptance**: Extension loads from `dist/chrome/` after build and works identically to current version.

---

#### Task 0.5: Add webextension-polyfill for Cross-Browser API
**What**: Replace direct `chrome.*` API calls with `browser.*` from webextension-polyfill for Firefox/Edge compat.

**Plan A — Import polyfill at entry points**
- Add `webextension-polyfill` as a dependency
- In `content.js` and `background.js`, import at top
- Replace `chrome.runtime.*`, `chrome.storage.*` → `browser.runtime.*`, `browser.storage.*`
- Chrome shims `browser` to `chrome`, Firefox uses `browser` natively

**Plan B — Conditional wrapper**
- Create `browser-api.js` that exports a unified API:
  ```js
  const api = typeof browser !== 'undefined' ? browser : chrome;
  export default api;
  ```
- Simpler, no dependency, but less complete coverage

**Acceptance**: Extension works in Chrome AND Firefox with the same JS code.

---

#### Task 0.6: Add Development Hot-Reload (Optional but Recommended)
**What**: Enable auto-reload when source files change during development.

**Plan A — webpack watch mode + extension-reloader**
- Use `webpack --watch` for file changes
- Add `crx-hotreload` script to background for dev builds only
- Strips out in production build

**Plan B — Manual reload**
- Skip hot-reload entirely
- Developer manually reloads extension in `chrome://extensions`
- Simplest, zero risk of dev-only code leaking

**Acceptance**: File changes trigger rebuild (Plan A) or developer knows to reload manually (Plan B).

---

### PHASE 1: Core Sidebar UI Container
**Goal**: Inject a persistent, collapsible sidebar into YouTube pages.

---

#### Task 1.1: Create Sidebar Container HTML/CSS Shell
**What**: Build the sidebar DOM element that will house the 4 panels.

**Plan A — Shadow DOM isolation**
- Create sidebar as a custom element with Shadow DOM
- All CSS scoped inside shadow root — zero YouTube CSS conflicts
- Technical:
  ```js
  class SafetySidebar extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      this.shadowRoot.innerHTML = `<style>...</style><div class="sidebar">...</div>`;
    }
  }
  customElements.define('safety-sidebar', SafetySidebar);
  ```

**Plan B — Namespaced CSS with high-specificity selectors**
- Regular DOM element with all classes prefixed: `.ysi-sidebar`, `.ysi-panel`, etc.
- Add `!important` to critical layout properties
- Simpler but risk of YouTube CSS bleeding in

**Acceptance**: Sidebar appears on YouTube video pages, doesn't break YouTube's layout, is visually isolated.

---

#### Task 1.2: Inject Sidebar into YouTube DOM
**What**: Find the correct YouTube DOM insertion point and inject the sidebar.

**Plan A — Insert adjacent to YouTube's main content**
- Target `#content` or `ytd-watch-flexy` and insert sidebar as sibling
- Use `MutationObserver` to wait for YouTube's SPA to render before injecting
- Technical:
  ```js
  function injectSidebar() {
    const watchFlexy = document.querySelector('ytd-watch-flexy');
    if (!watchFlexy) return;
    const sidebar = document.createElement('safety-sidebar');
    watchFlexy.parentElement.insertBefore(sidebar, watchFlexy.nextSibling);
  }
  ```

**Plan B — Append to document.body as fixed-position overlay**
- Don't integrate into YouTube's layout, just position:fixed on the right
- Simpler DOM manipulation, but may overlap YouTube elements
- Need careful z-index management

**Acceptance**: Sidebar appears on video pages, YouTube player is not obscured, sidebar is visible next to or over the recommendations panel.

---

#### Task 1.3: Implement Sidebar Collapse/Expand Toggle
**What**: User can collapse sidebar to a thin strip (icon only) and expand it back.

**Plan A — CSS transition with state class**
- `.ysi-sidebar` default width: 380px
- `.ysi-sidebar.collapsed` width: 40px, only shows toggle icon
- CSS transition: `width 0.3s ease`
- Toggle button fixed at top of sidebar
- Save state to `chrome.storage.local`

**Plan B — Two separate DOM elements**
- Full sidebar element + collapsed strip element
- Show/hide with `display: none/block`
- No animation but simpler state management

**Acceptance**: Click toggle → sidebar collapses smoothly. Click again → expands. State persists across page navigations.

---

#### Task 1.4: Shrink YouTube Player When Sidebar is Open
**What**: When sidebar is expanded, reduce YouTube's main content width so nothing overlaps.

**Plan A — Modify YouTube's `#content` width via CSS**
- Inject a `<style>` tag that adjusts `ytd-watch-flexy` or `#primary` to shrink when sidebar is open
- When collapsed, remove the style to restore full width
- Technical:
  ```css
  body.ysi-sidebar-open #primary { 
    max-width: calc(100% - 400px) !important; 
  }
  ```

**Plan B — Don't shrink YouTube, overlay on top of recommendations**
- Sidebar sits on top of YouTube's recommendation panel
- Recommendation panel is less important than our content
- Simpler, no layout manipulation
- Add slight transparency so user knows recommendations are behind

**Acceptance**: Main video player is never covered. When sidebar opens, layout adjusts (Plan A) or sidebar overlays recommendations only (Plan B).

---

#### Task 1.5: Handle YouTube SPA Navigation for Sidebar
**What**: Sidebar must persist across YouTube's SPA page transitions (video to video, home to video, etc.).

**Plan A — Detect navigation, keep sidebar, update content**
- Use existing `yt-navigate-finish` listener
- On navigation: if on video page → show sidebar, update panels. If not → hide sidebar.
- Never destroy/recreate the sidebar DOM node — just show/hide
- Technical:
  ```js
  window.addEventListener('yt-navigate-finish', () => {
    const videoId = getVideoId();
    if (videoId) {
      showSidebar();
      updatePanelsForVideo(videoId);
    } else {
      hideSidebar();
    }
  });
  ```

**Plan B — Recreate sidebar on each navigation**
- Destroy and recreate sidebar on every page change
- Simpler state management but causes flicker
- Panels lose their state

**Acceptance**: Navigating between videos keeps sidebar visible and updates content. Going to non-video pages hides sidebar. No flicker.

---

#### Task 1.6: Sidebar Responsive Behavior for Small Screens
**What**: On small viewports (< 1200px), sidebar should auto-collapse or switch to a different layout.

**Plan A — Media query auto-collapse**
- Below 1200px: sidebar auto-collapses to strip
- Below 900px: sidebar becomes bottom drawer (horizontal)
- CSS media queries handle this

**Plan B — Always collapsible, no responsive breakpoints**
- Sidebar is always right-side, user manually collapses on small screens
- Simpler CSS, no breakpoint complexity
- May overlap on very small screens

**Acceptance**: Extension doesn't break YouTube layout on screens 1024px to 2560px wide.

---

### PHASE 2: 4-Panel Grid System
**Goal**: Create the 4 independently controllable panels inside the sidebar.

---

#### Task 2.1: Define Panel Data Model
**What**: Create the data structure that represents a panel's state.

**Plan A — Class-based Panel model**
```js
class Panel {
  constructor(id, mode) {
    this.id = id;             // 1-4
    this.mode = mode;         // 'data' | 'random' | 'subject' | 'learn' | 'custom'
    this.content = null;      // Current video/data object
    this.queue = [];          // Upcoming content
    this.history = [];        // Previously shown content
    this.isMuted = true;      // Audio state
    this.isPlaying = false;   // Playback state (for the active embedded player)
    this.isActive = false;    // Is this the panel with the embedded player?
  }
}
```

**Plan B — Plain object with factory function**
```js
function createPanel(id, mode) {
  return { id, mode, content: null, queue: [], history: [], isMuted: true, isPlaying: false, isActive: false };
}
```

**Acceptance**: Panel state can be created, updated, serialized, and restored.

---

#### Task 2.2: Build 4-Panel Grid Layout in Sidebar
**What**: Arrange 4 equal panels in a 2x2 grid inside the sidebar.

**Plan A — CSS Grid**
```css
.ysi-panel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 8px;
  height: calc(100% - 50px); /* minus header */
}
```

**Plan B — Flexbox with wrapping**
```css
.ysi-panel-grid {
  display: flex;
  flex-wrap: wrap;
}
.ysi-panel { width: 50%; height: 50%; }
```

**Acceptance**: 4 equal-sized panels visible in sidebar, responsive to sidebar width changes.

---

#### Task 2.3: Build Individual Panel Component
**What**: Each panel needs: thumbnail/player area, title, channel, controls bar.

**Plan A — Web Component per panel**
- Custom element `<ysi-panel>` with Shadow DOM
- Encapsulated styles per panel
- Attributes: `panel-id`, `mode`, `active`
- Internal layout:
  ```
  ┌─────────────────────┐
  │  Thumbnail/Player   │
  │  (16:9 aspect)      │
  ├─────────────────────┤
  │ Title (truncated)   │
  │ Channel name        │
  ├─────────────────────┤
  │ 🔇 ▶️ ⏭️  [Mode] │
  └─────────────────────┘
  ```

**Plan B — Regular DOM elements with BEM naming**
- `div.ysi-panel`, `div.ysi-panel__media`, `div.ysi-panel__info`, `div.ysi-panel__controls`
- No Shadow DOM, relies on namespaced CSS
- Simpler, but less isolation

**Acceptance**: Each panel renders with correct layout, shows placeholder content, has clickable control buttons.

---

#### Task 2.4: Panel Mute/Unmute Control
**What**: Each panel has an independent mute toggle.

**Plan A — Per-panel audio state in Panel model**
- Mute button toggles `panel.isMuted`
- If panel is the active embedded player: control iframe `player.mute()` / `player.unMute()`
- If panel is a preview card: mute is relevant only when promoted to active player
- Visual: 🔇 / 🔊 icon toggle

**Plan B — Global audio: only one panel audible at a time**
- Clicking unmute on any panel auto-mutes all others
- Simpler, prevents audio overlap
- Less flexible but better UX for most users

**Acceptance**: Clicking mute icon toggles audio. Visual indicator updates. No audio leaks between panels.

---

#### Task 2.5: Panel Play/Pause/Next Controls
**What**: Each panel needs play, pause, and skip-to-next controls.

**Plan A — Full control bar**
- Play/Pause toggle: for active player, controls iframe playback. For cards, "play" promotes to active player.
- Next (⏭️): Advance to next item in panel's content queue.
- Controls disabled when queue is empty.
- Technical: `postMessage` to YouTube iframe API for playback control.

**Plan B — Click-to-play only**
- Clicking thumbnail of any card promotes it to active player
- No explicit play/pause/next buttons
- Simpler, fewer controls to maintain

**Acceptance**: User can control playback per panel. Next loads new content from queue.

---

#### Task 2.6: Click-to-Promote (Card → Active Player)
**What**: Clicking a preview card's thumbnail swaps it into the active embedded player position.

**Plan A — Swap positions**
- Clicking card in panel 3 → panel 3 becomes active player, previous active panel becomes a card
- Active panel gets iframe embedded player
- Previous active panel's iframe is destroyed, replaced with thumbnail card
- Smooth transition animation

**Plan B — Fixed active panel**
- Panel 1 is ALWAYS the embedded player
- Clicking a card in panels 2-4 loads that video into panel 1's player
- Panel 2-4 stay as cards
- Simpler state management

**Acceptance**: User can switch which video is actively playing by clicking a card. Transition is smooth.

---

#### Task 2.7: Panel Header with Mode Indicator
**What**: Each panel shows which mode it's currently in (Data, Random, Subject, Learn).

**Plan A — Dropdown mode selector per panel**
- Small dropdown in panel header: 📊 Data | 🎲 Random | 🎯 Subject | 🎓 Learn
- Changing mode triggers content refresh for that panel
- Mode stored in Panel model

**Plan B — Fixed assignment via settings**
- Modes assigned in settings page, not changeable per-panel in real-time
- Simpler but less dynamic

**Acceptance**: Each panel's current mode is clearly labeled. User can identify what each panel is doing.

---

### PHASE 3: Embedded Player & Preview Cards
**Goal**: Build the hybrid playback system — one YouTube iframe player + three thumbnail preview cards.

---

#### Task 3.1: Create YouTube IFrame Player Component
**What**: Embed a YouTube video player using the IFrame Player API.

**Plan A — YouTube IFrame API**
- Load YouTube IFrame API: `https://www.youtube.com/iframe_api`
- Create player:
  ```js
  new YT.Player('ysi-player', {
    videoId: 'VIDEO_ID',
    playerVars: { autoplay: 0, controls: 1, modestbranding: 1 },
    events: { onReady: ..., onStateChange: ... }
  });
  ```
- Player lives inside the active panel's media area
- Size: match panel dimensions (16:9 aspect ratio)

**Plan B — Simple iframe without API**
- Plain `<iframe src="https://www.youtube.com/embed/VIDEO_ID">` 
- No programmatic control (can't mute/pause via JS)
- Simpler but loses mute/play/pause control
- Would need to rely on user interacting with iframe controls directly

**Acceptance**: A YouTube video plays inside one panel. We can programmatically play, pause, mute, and load new videos.

---

#### Task 3.2: Create Preview Card Component
**What**: Build the thumbnail + metadata card for non-active panels.

**Plan A — Rich preview card**
```
┌────────────────────┐
│ [Thumbnail Image]  │  ← YouTube thumbnail URL
│  ▶ 12:34          │  ← Duration badge
├────────────────────┤
│ Video Title Here...│  ← Truncated to 2 lines
│ Channel Name       │  ← 1 line
│ 1.2M views · 3d    │  ← metadata
└────────────────────┘
```
- Thumbnail: `https://img.youtube.com/vi/{VIDEO_ID}/mqdefault.jpg`
- Click anywhere → promote to active player (Task 2.6)
- Hover effect: slight scale + play icon overlay

**Plan B — Minimal card (thumbnail + title only)**
- Just thumbnail and title, no metadata
- Faster to render, less API data needed
- Less informative for user

**Acceptance**: Three preview cards render with thumbnails and metadata. Clicking them works.

---

#### Task 3.3: Handle IFrame Content Security Policy
**What**: Ensure YouTube iframe embedding works within the extension's CSP.

**Plan A — Update manifest CSP for iframes**
- Current CSP: `"script-src 'self'; object-src 'self'"`
- Add `frame-src https://www.youtube.com https://www.youtube-nocookie.com` if needed
- YouTube iframe API loaded as external script may need `script-src` update
- Test in all three browsers

**Plan B — Use youtube-nocookie.com domain**
- YouTube provides `https://www.youtube-nocookie.com/embed/` for privacy-enhanced embedding
- May have fewer CSP restrictions
- Test compatibility

**Acceptance**: YouTube iframe loads inside extension sidebar without CSP errors in console.

---

#### Task 3.4: Panel Content Transition Animations
**What**: Smooth transitions when content changes in a panel (new video loads, mode switches).

**Plan A — CSS transitions with opacity + transform**
```css
.ysi-panel__media { transition: opacity 0.3s ease, transform 0.3s ease; }
.ysi-panel__media.loading { opacity: 0; transform: scale(0.95); }
.ysi-panel__media.loaded { opacity: 1; transform: scale(1); }
```
- Fade out old content, fade in new content
- Loading spinner during transition

**Plan B — No animations, instant swap**
- Content changes immediately
- Simpler, no animation overhead
- Snappier feel

**Acceptance**: Content transitions are smooth (Plan A) or instant without visual artifacts (Plan B).

---

### PHASE 4: Mode/Preset Architecture
**Goal**: Build the system that powers the 4 content modes and custom presets.

---

#### Task 4.1: Define Mode Interface
**What**: Each mode must implement a standard interface for fetching and displaying content.

**Plan A — Mode class hierarchy**
```js
class BaseMode {
  constructor(panelId) { this.panelId = panelId; }
  async fetchContent(context) { throw new Error('Not implemented'); }
  getDisplayConfig() { throw new Error('Not implemented'); }
  onActivate() {}
  onDeactivate() {}
}

class RandomMode extends BaseMode { ... }
class SubjectMode extends BaseMode { ... }
class DataMode extends BaseMode { ... }
class LearnMode extends BaseMode { ... }
```

**Plan B — Function-based modes**
```js
const modes = {
  random: { fetch: async (ctx) => {...}, display: () => {...} },
  subject: { fetch: async (ctx) => {...}, display: () => {...} },
  data: { fetch: async (ctx) => {...}, display: () => {...} },
  learn: { fetch: async (ctx) => {...}, display: () => {...} },
};
```

**Acceptance**: Any mode can be assigned to any panel and produces content output.

---

#### Task 4.2: Build Mode Manager (Controller)
**What**: Central controller that assigns modes to panels and coordinates content fetching.

**Plan A — ModeManager class**
```js
class ModeManager {
  constructor() { this.panels = []; this.presets = {}; }
  assignMode(panelId, modeName) { ... }
  switchPreset(presetName) { ... }  // Apply preset to all 4 panels
  refreshPanel(panelId) { ... }     // Re-fetch content for a panel
  refreshAll() { ... }              // Re-fetch all panels
}
```
- Manages state for all 4 panels
- Coordinates API calls to prevent quota waste (batch requests)

**Plan B — Event-driven approach**
- No central manager
- Each panel listens for events and manages its own mode
- Panels emit events when they need data
- Background script handles API coordination via message passing

**Acceptance**: Modes can be assigned, switched, and refreshed without errors.

---

#### Task 4.3: Preset Data Model
**What**: Define what a "preset" is — a saved configuration of 4 panel modes.

**Plan A — JSON preset schema**
```json
{
  "name": "Discovery Mode",
  "icon": "🔍",
  "panels": [
    { "position": 1, "mode": "subject", "options": { "depth": "deep" } },
    { "position": 2, "mode": "random", "options": { "category": "any" } },
    { "position": 3, "mode": "data", "options": { "metrics": ["views", "engagement"] } },
    { "position": 4, "mode": "learn", "options": { "type": "tutorials" } }
  ]
}
```
- Stored in `chrome.storage.sync` (synced across devices)
- Default presets ship with extension, users can create custom ones

**Plan B — Simpler flat preset**
```json
{
  "name": "Discovery Mode",
  "panel1": "subject",
  "panel2": "random",
  "panel3": "data",
  "panel4": "learn"
}
```
- No per-panel options, just mode names
- Faster to implement, add options later

**Acceptance**: Presets can be saved, loaded, switched, exported, and imported.

---

#### Task 4.4: Default Presets
**What**: Ship 4-5 built-in presets so users have great defaults out of the box.

**Plan A — Five curated presets**
1. **Explorer** — Random / Subject / Data / Learn
2. **Deep Dive** — Subject / Subject / Subject / Data
3. **Creator Studio** — Learn / Learn / Data / Random
4. **Safety Audit** — Data / Data / Subject / Subject
5. **Chill Mode** — Random / Random / Random / Random

**Plan B — Three minimal presets**
1. **Balanced** — One of each mode
2. **All Data** — All 4 panels show data
3. **All Random** — All 4 panels show random

**Acceptance**: Default presets appear in settings and preset switcher on first install.

---

#### Task 4.5: Preset Switcher UI
**What**: Quick preset switch button in sidebar header.

**Plan A — Dropdown with preset previews**
- Button in sidebar header shows current preset name/icon
- Click → dropdown with all presets, each showing its 4-panel configuration
- Click preset → all panels switch simultaneously

**Plan B — Cycle button**
- Single button that cycles through presets: click → next preset
- Long-press → opens preset list
- Simpler UI

**Acceptance**: User can switch presets and all 4 panels update.

---

#### Task 4.6: Custom Preset Creator
**What**: User can create their own presets from the settings page.

**Plan A — Settings page preset editor**
- In popup settings: "Create Preset" button
- Form with: Name, Icon picker, Mode selector for each panel
- Save to `chrome.storage.sync`
- Edit/Delete existing custom presets

**Plan B — "Save Current Layout" button**
- User configures panels manually, then clicks "Save as Preset"
- Names it, saves
- No explicit editor, just snapshot current state

**Acceptance**: User can create, save, name, and delete custom presets.

---

### PHASE 5: Video Data Mode
**Goal**: Build the "Data Mode" that shows analytics, metrics, and insights about the current or selected video.

---

#### Task 5.1: Define Data Mode Metrics Set
**What**: Decide what metrics/data to show in Data Mode.

**Plan A — Rich metrics dashboard**
- View count + view velocity (views/day)
- Like/dislike ratio (estimated)
- Comment sentiment summary
- Channel subscriber count
- Channel upload frequency
- Video duration vs. category average
- Safety score (from our analyzer)
- AI detection confidence
- Category tags
- Publish date + age
- Engagement rate (comments + likes / views)

**Plan B — Essential metrics only**
- Safety score
- AI detection status
- View count
- Channel info
- Category

**Acceptance**: Data mode panel shows relevant metrics for the current video.

---

#### Task 5.2: Create Data Visualization Components
**What**: Build reusable chart/gauge/stat components for Data Mode.

**Plan A — Custom SVG/Canvas components**
- Safety score: circular gauge (SVG arc)
- View count: animated number counter
- Engagement: horizontal bar chart
- Sentiment: emoji scale (😡→😐→😊)
- All lightweight, no external charting library

**Plan B — Text-only data display**
- All metrics shown as styled text/numbers
- No charts, just labels + values
- Color coding for good/warning/danger values
- Simplest, smallest footprint

**Acceptance**: Data renders clearly and readably within the small panel dimensions.

---

#### Task 5.3: Data Mode Panel Layout
**What**: Design the layout for data inside a mini-panel.

**Plan A — Scrollable card layout**
```
┌─────────────────────┐
│ ⭐ Safety: 87/100   │
│ 🤖 AI: Not Detected │
├─────────────────────┤
│ 👁️ 1.2M views       │
│ 📈 12K/day velocity │
│ 💬 94% positive     │
│ 📺 Channel: 2.1M    │
│ 📅 Published: 3d ago│
│ ⏱️ Duration: 12:34  │
└─────────────────────┘
```
- Scrollable vertically if content exceeds panel height
- Compact, information-dense

**Plan B — Tabbed data view**
- Tab 1: Safety (score, warnings)
- Tab 2: Metrics (views, engagement)
- Tab 3: Channel info
- Tabs allow more data without scrolling

**Acceptance**: Data mode shows metrics in a readable, compact format within the panel.

---

#### Task 5.4: Backend Endpoint for Enriched Video Data
**What**: Create API endpoint that returns comprehensive video metadata beyond what the current `/analyze` endpoint provides.

**Plan A — New `/video-data` endpoint**
```python
@app.get("/video-data/{video_id}")
async def get_video_data(video_id: str):
    # Fetch from YouTube Data API: statistics, snippet, contentDetails
    # Merge with our safety analysis
    # Return enriched data object
    return {
        "video_id": video_id,
        "title": "...",
        "channel": { "name": "...", "subscribers": "...", "video_count": ... },
        "stats": { "views": ..., "likes": ..., "comments": ... },
        "safety": { "score": ..., "ai_detected": ..., "warnings": [...] },
        "published_at": "...",
        "duration": "..."
    }
```

**Plan B — Extend existing `/analyze` endpoint**
- Add `?enriched=true` query param to existing endpoint
- When enriched, return additional fields
- Reuses existing code path

**Acceptance**: API returns comprehensive video data including stats, safety, and channel info.

---

### PHASE 6: Random Mode
**Goal**: Build the "Random Mode" that surfaces serendipitous, safe, high-quality content.

---

#### Task 6.1: Random Content Source Strategy
**What**: Define how "random" content is selected.

**Plan A — Curated pool + random selection**
- Our curated DB has trusted channels with playlists/categories
- Random mode picks a random category → random channel → random video from that channel
- Guarantees quality since all sources are pre-vetted
- API call: YouTube Data API `playlistItems` for channel uploads, pick random

**Plan B — YouTube search with random safe terms**
- Maintain a list of "safe search terms" in our DB
- Pick a random term, search YouTube, filter results
- Less predictable, may surface lower-quality content
- Uses more API quota

**Acceptance**: Random mode produces genuinely varied, safe content that surprised the user.

---

#### Task 6.2: Random Mode Content Queue
**What**: Pre-fetch a queue of random videos so "next" is instant.

**Plan A — Background pre-fetch queue of 10**
- On mode activation, fetch 10 random videos
- Store in panel's `queue[]`
- "Next" pops from queue
- When queue < 3, auto-fetch more in background

**Plan B — Fetch on demand**
- Each "next" triggers a fresh API call
- Simpler, but slower transitions
- More API calls

**Acceptance**: Clicking "next" in random mode shows new content within 500ms.

---

#### Task 6.3: Backend Endpoint for Random Content
**What**: API endpoint that returns random safe videos.

**Plan A — `/random-videos` endpoint**
```python
@app.get("/random-videos")
async def get_random_videos(count: int = 5, category: str = None):
    # Select random entries from curated DB
    # Optionally filter by category
    # Return video objects with thumbnails, titles, channel info
```

**Plan B — Client-side random selection from curated DB**
- Ship curated channel/playlist list to extension
- Extension picks randomly and fetches video data directly from YouTube oEmbed/thumbnail URLs
- No backend call needed for random selection
- Backend only used for enrichment if needed

**Acceptance**: Random content is returned quickly and is genuinely varied.

---

### PHASE 7: Stay on Subject Mode
**Goal**: Build the "Subject Mode" that finds related, safe, high-quality content in the same topic.

---

#### Task 7.1: Subject Detection from Current Video
**What**: Determine the "subject" from the video the user is currently watching.

**Plan A — Backend subject extraction**
- Send video title + description + transcript to backend
- Backend extracts key topics using keyword extraction (TF-IDF or simple NLP)
- Returns subject tags: `["cooking", "pasta", "italian", "homemade"]`

**Plan B — Client-side simple extraction**
- Parse video title for keywords
- Use YouTube's own category tag
- Match against our category database
- Less accurate but no API call

**Acceptance**: Subject mode correctly identifies the topic of the current video.

---

#### Task 7.2: Subject-Related Content Fetching
**What**: Find videos in the same subject from trusted sources.

**Plan A — YouTube search filtered by trusted channels**
- Take extracted subjects → YouTube search API with `channelId` filter
- Search within our trusted channels for matching content
- Rank by relevance + recency

**Plan B — Our curated DB keyword matching**
- Match subjects against tags in our curated channel/playlist DB
- Return pre-vetted videos from those categories
- No YouTube search API call (saves quota)

**Acceptance**: Subject mode shows relevant, on-topic videos from quality sources.

---

#### Task 7.3: Backend Endpoint for Subject Content
**What**: API endpoint that returns subject-related videos.

**Plan A — `/subject-videos` endpoint**
```python
@app.get("/subject-videos")
async def get_subject_videos(
    subject: str, 
    exclude_ids: list[str] = [],
    count: int = 5
):
    # Search curated DB + YouTube API for subject match
    # Exclude already-shown videos
    # Return ranked results
```

**Plan B — Extend `/real-alternatives` endpoint**
- Current endpoint already finds alternatives
- Add `?mode=subject` parameter
- Reuses existing logic

**Acceptance**: Subject videos are topically relevant to what the user is watching.

---

### PHASE 8: Learn-to-Make Mode
**Goal**: Build the "Learn Mode" that shows tutorials on how to create the type of content the user is watching.

---

#### Task 8.1: Content Type Classification
**What**: Classify what TYPE of video is being watched (not just topic, but format/style).

**Plan A — Format classification system**
- Categories: Vlog, Tutorial, Review, Unboxing, Reaction, Music Video, Documentary, Short Film, Livestream, Gaming, Cooking Show, DIY, etc.
- Backend analyzes title/description patterns to classify
- e.g., "How to..." → Tutorial, "I tried..." → Vlog/Challenge, "[REACTION]" → Reaction

**Plan B — Simple genre mapping**
- Map YouTube's built-in category tags to tutorial types
- Less granular but zero ML needed
- "Gaming" → "How to make gaming videos"

**Acceptance**: Learn mode correctly identifies the video type/format, not just the topic.

---

#### Task 8.2: Tutorial Content Sourcing
**What**: Find tutorials about making videos of the classified type.

**Plan A — Curated tutorial database**
- Our DB includes tutorial channel/playlist mappings:
  ```json
  {
    "video_type": "cooking",
    "tutorials": [
      { "search": "how to film cooking videos", "channels": ["Think Media", "Ali Abdaal"] },
      { "search": "food photography for YouTube", "channels": ["Peter McKinnon"] }
    ]
  }
  ```
- Pre-vetted, high-quality tutorial recommendations

**Plan B — Dynamic YouTube search**
- Construct search query: `"how to make {video_type} videos"`
- Filter by trusted education/tutorial channels
- More dynamic, but quality varies

**Acceptance**: Learn mode shows relevant "how to create this type of content" tutorials.

---

#### Task 8.3: Backend Endpoint for Learn Content
**What**: API endpoint for learn-mode tutorial videos.

**Plan A — `/learn-videos` endpoint**
```python
@app.get("/learn-videos")
async def get_learn_videos(
    video_type: str, 
    subject: str = None,
    count: int = 5
):
    # Match video_type to tutorial mappings in DB
    # Optionally include subject for more specific tutorials
    # Return tutorial video objects
```

**Plan B — Reuse `/ai-tutorials` endpoint with broader scope**
- Current endpoint only does AI tutorials
- Expand to handle any tutorial type
- Less clean API design but reuses existing code

**Acceptance**: Learn endpoint returns relevant tutorial content based on video type.

---

### PHASE 9: Curated Content Database Expansion
**Goal**: Build a rich curated database of trusted channels, playlists, and content mappings to power all modes.

---

#### Task 9.1: Design Curated DB Schema
**What**: Define the JSON schema for our curated content database.

**Plan A — Category-based JSON files**
```
safety-db/
  curated/
    categories.json        ← master category list
    channels/
      cooking.json         ← trusted cooking channels
      science.json         
      diy.json             
      ...
    tutorials/
      video_types.json     ← "how to make X" mappings
    search_terms/
      random_pool.json     ← safe search terms for random mode
      subject_map.json     ← subject → search term mappings
```

**Plan B — Single curated.json file**
- Everything in one large JSON file
- Simpler file management
- Harder to maintain as it grows

**Acceptance**: Curated DB schema is defined and at least 5 categories are populated.

---

#### Task 9.2: Populate Cooking Category
**What**: Add trusted cooking channels and content mappings.

- Channels: Gordon Ramsay, Bon Appétit, Joshua Weissman, Binging with Babish, America's Test Kitchen, etc.
- Search terms for random: "easy recipes", "cooking basics", "meal prep", etc.
- Tutorial mappings: "how to film cooking videos", "food photography tips"

**Plan A**: Manually curate top 15-20 channels with playlist IDs
**Plan B**: Start with 5 channels, expand over time

**Acceptance**: Cooking category has enough content to power all 4 modes.

---

#### Task 9.3: Populate Science/Education Category
**Same structure as 9.2 for science content.**
- Channels: Veritasium, Kurzgesagt, SmarterEveryDay, Mark Rober, etc.

---

#### Task 9.4: Populate DIY/Maker Category
**Same structure for DIY/Maker content.**
- Channels: This Old House, See Jane Drill, I Like To Make Stuff, etc.

---

#### Task 9.5: Populate Fitness/Health Category
**Same structure for fitness content.**

---

#### Task 9.6: Populate Technology Category
**Same structure for tech content.**

---

#### Task 9.7: Populate Nature/Animals Category
**Same structure for nature content (already partially exists in current DB).**

---

#### Task 9.8: Populate Music/Creative Category
**Same structure for music/creative content.**

---

#### Task 9.9: Populate Gaming Category
**Same structure for gaming content.**

---

#### Task 9.10: Populate News/Documentary Category
**Same structure for news/documentary content.**

---

### PHASE 10: Backend API Expansion
**Goal**: Create all new API endpoints needed by the 4 modes.

---

#### Task 10.1: Refactor Backend for Mode Endpoints
**What**: Organize backend code to support new endpoint structure.

**Plan A — Router-based organization**
```python
# main.py — App setup + middleware
# routers/
#   analyze.py    — /analyze endpoint (existing)
#   video_data.py — /video-data endpoint (new)
#   random.py     — /random-videos endpoint (new)  
#   subject.py    — /subject-videos endpoint (new)
#   learn.py      — /learn-videos endpoint (new)
#   curated.py    — /curated/* endpoints (new)
```
- FastAPI `APIRouter` for each module
- Clean separation of concerns

**Plan B — All endpoints in main.py**
- Keep everything in `main.py` like current structure
- Add new endpoints below existing ones
- Simpler but file gets large

**Acceptance**: All endpoints work, code is organized, routes don't conflict.

---

#### Task 10.2: Implement `/video-data/{video_id}` Endpoint
**What**: Return enriched video data for Data Mode (Task 5.4).
- Merge YouTube Data API stats with our safety analysis
- Cache results for 1 hour

---

#### Task 10.3: Implement `/random-videos` Endpoint
**What**: Return random safe videos for Random Mode (Task 6.3).
- Accept optional `category` and `count` params
- Draw from curated DB

---

#### Task 10.4: Implement `/subject-videos` Endpoint
**What**: Return subject-related videos for Subject Mode (Task 7.3).
- Accept `subject` keywords, `exclude_ids`, `count`

---

#### Task 10.5: Implement `/learn-videos` Endpoint
**What**: Return tutorial videos for Learn Mode (Task 8.3).
- Accept `video_type`, optional `subject`, `count`

---

#### Task 10.6: Implement `/presets` Endpoint
**What**: Serve default preset configurations.

**Plan A — API-served presets**
```python
@app.get("/presets")
async def get_presets():
    return load_json("presets/defaults.json")
```
- Presets can be updated server-side without extension update

**Plan B — Presets bundled in extension**
- Ship presets as JSON in extension package
- No API call needed
- Requires extension update to change presets

**Acceptance**: Default presets are available to the extension.

---

#### Task 10.7: API Quota Management System
**What**: Smart quota management across all new endpoint types.

**Plan A — Token bucket rate limiter with priority queues**
- Assign priority: Data Mode (high) > Subject (medium) > Random/Learn (low)
- Track daily quota usage
- When quota is low: serve from curated DB only, skip YouTube API
- Cache aggressively

**Plan B — Simple daily counter with hard cutoff**
- Count total API calls per day
- At 80% quota: switch to curated-only mode
- At 100%: return cached/curated results only

**Acceptance**: Extension never exceeds YouTube API daily quota. Graceful degradation when quota is low.

---

### PHASE 11: Data Visualization Engine
**Goal**: Build the data display system that can show metrics in any panel.

---

#### Task 11.1: SVG Gauge Component (Safety Score)
**What**: Circular gauge that shows safety score 0-100.

**Plan A — Custom SVG**
- SVG circle with `stroke-dasharray` for progress
- Color transitions: red (0-30) → orange (31-60) → green (61-100)
- Animated fill on load

**Plan B — CSS-only gauge**
- `conic-gradient` on a div
- Simpler, fewer bytes, good browser support

**Acceptance**: Gauge renders correctly, animates, and is readable at small panel sizes.

---

#### Task 11.2: Stat Cards Component
**What**: Compact stat display (icon + label + value).

- Reusable for views, likes, subscribers, etc.
- Color-coded: green for good, red for concerning
- Responsive to panel width

---

#### Task 11.3: Mini Bar Chart Component
**What**: Simple horizontal bar chart for engagement metrics.

- Pure CSS bars with percentage widths
- Labels on left, values on right
- No external library

---

#### Task 11.4: Trend Indicator Component
**What**: Show if a metric is trending up, down, or stable.

- ↗️ Up / ↘️ Down / → Stable arrows
- Green for positive trends, red for negative
- Based on comparison to category averages

---

### PHASE 12: Settings Integration
**Goal**: Update settings UI to support new sidebar, panel, and preset features.

---

#### Task 12.1: Add Sidebar Settings Section
**What**: Settings to control sidebar behavior.

- Enable/disable sidebar
- Default state: expanded/collapsed
- Sidebar width (slider: 300-500px)
- Show on: video pages only / all YouTube pages

---

#### Task 12.2: Add Panel Configuration Settings
**What**: Settings for each panel's default mode and behavior.

- Default mode per panel
- Auto-refresh interval (off / 30s / 1min / 5min)
- Max queue size per panel

---

#### Task 12.3: Add Preset Management Settings
**What**: Settings for creating, editing, deleting presets.

- List of saved presets
- Create new preset form
- Edit/Delete buttons
- Import/Export presets as JSON

---

#### Task 12.4: Add Data Mode Settings
**What**: Which metrics to show in Data Mode.

- Checklist of available metrics
- Metric display order (drag to reorder or numbered list)
- Show/hide chart components

---

#### Task 12.5: Migrate Existing Settings to New Architecture
**What**: Ensure old v2.x settings don't break in v3.0.

**Plan A — Migration function**
- On extension update, check for old settings format
- Transform to new format
- Preserve user's existing toggles

**Plan B — Reset settings on v3.0 update**
- Notify user that settings were reset due to major update
- Simpler but loses user customization

**Acceptance**: Upgrading from v2.x to v3.0 doesn't break or lose user settings.

---

### PHASE 13: Cross-Browser Compatibility
**Goal**: Ensure extension works identically on Chrome, Firefox, and Edge.

---

#### Task 13.1: Firefox MV3 Manifest Adaptation
**What**: Create Firefox-specific manifest with gecko settings.

- Add `browser_specific_settings.gecko.id`
- Change background from `service_worker` to `scripts` (if Firefox still requires this)
- Test all permissions

---

#### Task 13.2: Firefox API Compatibility Testing
**What**: Test all browser API usage paths in Firefox.

- `browser.storage` vs `chrome.storage`
- `browser.runtime.sendMessage` behavior differences
- Content script injection timing
- IFrame embedding behavior

---

#### Task 13.3: Edge Compatibility Testing
**What**: Test in Edge (Chromium-based, should be near-identical to Chrome).

- Load extension via `edge://extensions`
- Test all features
- Edge-specific quirks (if any)

---

#### Task 13.4: Cross-Browser Automated Testing Setup
**What**: Set up testing infrastructure.

**Plan A — Playwright with browser extensions**
- Playwright can load extensions in Chrome/Edge
- Automated UI tests across browsers

**Plan B — Manual testing checklist**
- Document test matrix
- Manual verification for each browser
- Faster to set up, slower to execute

**Acceptance**: All features work in Chrome, Firefox, and Edge without browser-specific bugs.

---

### PHASE 14: Performance & Optimization
**Goal**: Ensure the extension is fast, lightweight, and doesn't degrade YouTube's performance.

---

#### Task 14.1: Lazy Load Panel Content
**What**: Only fetch content for visible panels; defer hidden/collapsed panels.

**Plan A — Intersection Observer**
- Use `IntersectionObserver` to detect when panels are visible
- Only fetch content when panel enters viewport
- Unload content when panel is scrolled away

**Plan B — Simple visibility check**
- Check `panel.offsetParent !== null` before fetching
- Cruder but effective

---

#### Task 14.2: Content Caching Layer
**What**: Cache API responses to reduce network calls and quota usage.

**Plan A — Multi-tier cache**
- L1: In-memory Map (current session)
- L2: `chrome.storage.local` (persists across sessions, 30min TTL)
- Check L1 → L2 → API

**Plan B — In-memory only**
- Simple Map cache, cleared on page refresh
- No persistence, but simplest

---

#### Task 14.3: Thumbnail Lazy Loading
**What**: Only load thumbnail images for preview cards that are visible.

- Use `loading="lazy"` on `<img>` tags
- Or Intersection Observer for more control
- Reduces initial page load impact

---

#### Task 14.4: Bundle Size Optimization
**What**: Ensure extension JS/CSS is minimal.

- No large libraries (all custom components)
- Minify JS/CSS in production builds
- Tree-shake unused code
- Target: < 100KB total extension size (excluding icons)

---

#### Task 14.5: Memory Leak Prevention
**What**: Ensure sidebar doesn't leak memory during long YouTube sessions.

- Clean up event listeners on navigation
- Limit queue/history sizes per panel
- Destroy iframe players when not active
- Profile memory usage in DevTools

---

### PHASE 15: Testing & QA
**Goal**: Comprehensive testing across all features.

---

#### Task 15.1: Unit Tests for Mode Logic
- Test each mode's content fetching
- Test preset switching
- Test panel state management
- Test caching logic

---

#### Task 15.2: Unit Tests for Backend Endpoints
- Test each new API endpoint
- Test quota management
- Test curated DB loading
- Test error handling

---

#### Task 15.3: Integration Tests (Extension ↔ Backend)
- Test full flow: sidebar loads → panels fetch → content renders
- Test mode switching end-to-end
- Test preset save/load/switch

---

#### Task 15.4: UI Tests (Visual Regression)
**Plan A**: Screenshot comparison tests with Playwright
**Plan B**: Manual visual QA checklist

---

#### Task 15.5: YouTube Compatibility Tests
- Test with different YouTube layouts (old, new, Shorts, etc.)
- Test with YouTube dark/light mode
- Test during ad playback
- Test with YouTube Premium (no ads)

---

#### Task 15.6: Performance Benchmarks
- Measure Time to Interactive for sidebar
- Measure memory usage after 1 hour session
- Measure API quota usage per session
- Measure thumbnail load times

---

### PHASE 16: Polish & Store Submission
**Goal**: Final polish, documentation, and submission to browser extension stores.

---

#### Task 16.1: Accessibility Audit
- Keyboard navigation for all sidebar controls
- Screen reader labels (ARIA)
- Color contrast compliance
- Focus management

---

#### Task 16.2: Update README and Documentation
- New architecture docs
- Setup instructions for development
- API documentation
- User guide

---

#### Task 16.3: Chrome Web Store Listing
- Update store description
- New screenshots with sidebar UI
- Privacy policy update (new data sources)

---

#### Task 16.4: Firefox Add-ons Listing
- Create AMO listing
- Firefox-specific screenshots
- Review compliance

---

#### Task 16.5: Edge Add-ons Listing
- Create Edge listing
- Edge-specific screenshots

---

#### Task 16.6: Create Extension Demo Video
- Record demo of sidebar in action
- Show preset switching
- Show all 4 modes
- Upload to YouTube (meta!)

---

## 📊 Estimated Timeline

| Phase | Tasks | Estimated Effort | Priority |
|-------|-------|------------------|----------|
| Phase 0: Foundation | 6 tasks | 2-3 sessions | P0 - Critical |
| Phase 1: Sidebar UI | 6 tasks | 2-3 sessions | P0 - Critical |
| Phase 2: Panel System | 7 tasks | 2-3 sessions | P0 - Critical |
| Phase 3: Player & Cards | 4 tasks | 2 sessions | P0 - Critical |
| Phase 4: Mode Architecture | 6 tasks | 2 sessions | P0 - Critical |
| Phase 5: Data Mode | 4 tasks | 2 sessions | P1 - High |
| Phase 6: Random Mode | 3 tasks | 1-2 sessions | P1 - High |
| Phase 7: Subject Mode | 3 tasks | 1-2 sessions | P1 - High |
| Phase 8: Learn Mode | 3 tasks | 1-2 sessions | P1 - High |
| Phase 9: Curated DB | 10 tasks | 2-3 sessions | P1 - High |
| Phase 10: Backend API | 7 tasks | 2-3 sessions | P1 - High |
| Phase 11: Data Viz | 4 tasks | 1-2 sessions | P2 - Medium |
| Phase 12: Settings | 5 tasks | 1-2 sessions | P2 - Medium |
| Phase 13: Cross-Browser | 4 tasks | 2 sessions | P2 - Medium |
| Phase 14: Performance | 5 tasks | 1-2 sessions | P2 - Medium |
| Phase 15: Testing | 6 tasks | 2-3 sessions | P3 - Important |
| Phase 16: Polish & Store | 6 tasks | 2-3 sessions | P3 - Important |
| **TOTAL** | **93 tasks** | **~30-40 sessions** | |

---

## 🔑 Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| YouTube CSP blocks iframe embedding | High | Plan B: youtube-nocookie.com, or use thumbnail preview with YouTube link |
| YouTube API quota exhaustion | High | Curated DB fallback, aggressive caching, smart quota management |
| YouTube DOM changes break sidebar injection | Medium | MutationObserver + multiple selector fallbacks |
| Cross-browser API differences | Medium | webextension-polyfill + per-browser testing |
| Extension store rejection | Medium | Strict content policy compliance, privacy review |
| Performance degradation with 4 panels | Medium | Lazy loading, visibility-based fetching, memory profiling |

---

## 📝 Notes

- **Plan C Protocol**: If Plan A and Plan B both fail for any task, we document the blocker and brainstorm together.
- **Scope Lock**: All work MUST be within a defined task. No yak-shaving or feature creep outside the plan.
- **Incremental Delivery**: Each phase produces a working (if incomplete) extension. No "big bang" release.
- **Session = One focused coding session** (~2-4 hours of Opus work)

---

*Created: 2026-02-17*
*Last Updated: 2026-02-17*
*Version: 3.0-planning*
