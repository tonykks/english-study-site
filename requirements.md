# Final Requirements Template (Complete Learning Page)

## Goal
Build a production-quality single-page English study app that is:
- fully data-driven from `data/*.txt`,
- visually polished (modern educational platform style),
- mobile-friendly and accessible,
- performance-optimized,
- reusable as a template for new content sets.

This template must preserve and include all implemented features below.

---

## Input Data Contract

Place files directly in the local `data/` folder:
- `data/00_meta.txt`
- `data/01_intro.txt`
- `data/02_core.txt`
- `data/03_summary.txt`
- `data/04_full_script.txt`
- `data/05_wordcard.txt`

### `00_meta.txt` required keys
- `title`
- `level`
- `source`
- `video_url`
- `video_id`

### `00_meta.txt` optional keys
- `description`
- `duration`
- `channel`
- `notes`
- any additional key-value (render as meta chips)

### `01_intro.txt`
- key-value format (`en`, `kr`)

### `02_core.txt`, `03_summary.txt`, `04_full_script.txt`
- block format:
  - `[Section Name]`
  - `en: ...`
  - `kr: ...`

### `05_wordcard.txt`
- repeated card blocks:
  - `[Card N]`
  - `headword`
  - `part_of_speech`
  - `meaning_kr`
  - `definition_en`
  - `definition_kr_literal`
  - `example_en`
  - `example_kr_literal`

---

## Output Files (Required)

Generate in current working directory:
- `index.html`
- `style.css`
- `script.js`
- `service-worker.js`

Use:
- Tailwind CSS CDN + custom CSS
- plain JavaScript (no framework/build tool)

---

## Core Feature Checklist

### ✅ Global Navigation + Platform Integration
- Sticky top header with brand:
  - logo icon
  - "English Study Hub"
  - subtitle
- Desktop nav:
  - home button (`../../../../index.html`)
  - dropdown for other content levels
- Mobile nav:
  - hamburger button
  - expandable menu links
- Breadcrumb:
  - `홈 > 듣기 연습 > Level X > [Title]`
  - level/title set dynamically from meta
- Footer:
  - prominent "메인으로 돌아가기"
  - quick links and platform text

### ✅ YouTube Integration
- Top-of-page responsive 16:9 player
- `video_id` from meta (fallback: extract from `video_url`)
- include title/channel/duration labels
- mobile optimized embed container

### ✅ Tabs + Content Rendering
- Tabs:
  - Intro
  - Core Sentences
  - Summary
  - Full Script
  - Hangman Game
  - Word Cards
- keyboard-support tab navigation
- sticky tabs
- smooth tab panel transitions
- render all content from `data/*.txt` only

### ✅ TTS (Speech Synthesis)
- browser `speechSynthesis` API, English voice preference
- TTS buttons on:
  - Intro EN
  - each Core sentence
  - each Summary item
  - each Full Script paragraph
  - Word Card word/definition/example
- features:
  - active speaking button highlight
  - stop-on-reclick behavior
  - global stop button
  - speed selector (`0.85x`, `0.95x`, `1.0x`, `1.1x`)
  - status line (`aria-live`) for speaking updates

### ✅ Enhanced Word Cards (3D Flip + Controls)
- card front:
  - headword
  - bookmark button
  - TTS icon
  - difficulty label
- card back:
  - part_of_speech | meaning_kr
  - definition_en + TTS
  - definition_kr_literal
  - example_en + TTS
  - example_kr_literal
- interaction:
  - smooth 3D flip animation
  - click / Enter / Space to flip
  - Escape to close flip
  - prevent flip when TTS/bookmark clicked
- Word Card control panel:
  - flip all
  - reset
  - shuffle
  - smart review
  - share progress
  - TTS speed + stop

### ✅ UX Enhancements
- dashboard block:
  - total cards
  - flipped cards
  - favorites
  - badges
  - session timer
  - online/offline status
- badges:
  - first flips
  - bookmark usage
  - deep reading
  - focus time
- search/filter:
  - text search (word/meaning/example)
  - difficulty filter
  - bookmark filter
  - clear filters
- share:
  - Web Share API
  - clipboard fallback

### ✅ Hangman Game (Word Order Trainer)
- Tab position:
  - 6th tab, next to Word Cards (`🎮 Hangman Game`)
- Theme/visual:
  - dark navy game area
  - left hangman graphic + right play zone
- Data source:
  - use `Core Sentences` EN/KR pairs
- Core gameplay:
  - show Korean sentence (`KR`) as prompt
  - show shuffled English words from target sentence (`EN`)
  - learner clicks words in correct English order
  - if clicked word matches current expected position:
    - word moves to upper answer slots
    - word is removed from lower word pool
  - if clicked word is wrong:
    - no move to answer area
    - wrong count increases
    - wrong visual feedback (shake) + wrong SFX
- Scoring:
  - success round: +1 score
  - failed round (hangman completed): +0
  - progress shown as `X/Y` sentence rounds
- Controls (single bottom row):
  - 선택 초기화
  - 정답 체크
  - 다음 문장
  - 점수 초기화
- Hangman status:
  - STEP displayed as `wrongCount / maxSteps`
  - hangman SVG body parts reveal by wrong count
- Audio feedback:
  - correct word click sound
  - victory sound on round clear (contrasts with death sound)
  - wrong sound on regular mistakes
  - separate death sound on final failure step
- Persistence:
  - score and current round index in localStorage
- Mobile:
  - responsive layout and button usability preserved

### ✅ Performance
- batch rendering with `DocumentFragment`
- event delegation for Word Card interactions
- avoid repeated heavy DOM listeners
- localStorage persistence for user state
- cached offline assets via service worker

### ✅ Accessibility
- skip-to-content link
- semantic sections + role attributes
- `aria-live` for TTS status
- keyboard operable tabs/cards/menu
- `aria-expanded` state on flip cards
- visible focus states
- reduced-motion support

### ✅ Mobile Optimization
- responsive layout across breakpoints
- touch-friendly controls (min tap target)
- horizontally scrollable tabs on small screens
- mobile menu and compact controls

---

## State Persistence Requirements

Persist in localStorage:
- flipped cards
- favorites
- difficulty map
- earned badges
- review scores
- accumulated study seconds
- selected theme (light/dark)

State should restore on reload.

---

## Offline Requirements

Implement `service-worker.js` to cache:
- html/css/js files
- all six data files
- offline-friendly revisit behavior

Show online/offline indicator in UI.

---

## Visual Requirements

- clean, modern educational UI
- balanced spacing and card hierarchy
- high readability for EN/KR mixed content
- subtle transitions; no noisy animation
- dark mode support with readable contrast

---

## Parsing and Data Robustness

Parser must:
- normalize line endings
- support multiline values
- support case-insensitive keys (`en`/`EN`, `kr`/`KR`)
- gracefully handle missing values with fallback text
- never assume JSON

Error handling:
- user-friendly message in UI
- console detail for debugging

---

## Final Acceptance Criteria

The generated page is accepted only if all are true:
1. Loads all `data/*.txt` content correctly.
2. YouTube embed works from meta `video_id`/`video_url`.
3. All tabs, TTS controls, and flip cards work on desktop/mobile.
4. Word Card controls (flip/reset/shuffle/search/filter/smart-review) work.
5. Dashboard stats and badges update during use.
6. State persists after refresh.
7. Keyboard-only navigation is usable.
8. Offline revisit works after first load.
9. No framework/build step required.
10. Ready to reuse for new content sets with same file format.

---

## Generator Instruction (For Future Content)

When generating a new content page from this template:
- reuse same architecture and quality level,
- keep all feature modules enabled by default,
- change only data-driven content and relative navigation paths if needed,
- do not remove UX/accessibility/performance features.

---

## Test Plan (Systematic)

Use this plan whenever a new content page is generated from this template.

### 1) Test Environment Matrix

#### Desktop Browsers
- Chrome (latest stable)
- Edge (latest stable)
- Firefox (latest stable)

#### Mobile Browsers
- Android Chrome (latest stable)
- iOS Safari (latest stable)

#### Viewports
- Mobile: 360x800, 390x844
- Tablet: 768x1024
- Desktop: 1366x768, 1920x1080

### 2) Functional Test Cases

#### A. Data Loading
- Given valid `data/00~05.txt`, page loads all sections without manual edits.
- Missing file case shows user-friendly error UI and keeps console detail.
- Meta fallback works if optional fields are absent.

#### B. Navigation
- Header links navigate correctly.
- Desktop dropdown opens and links are clickable.
- Mobile menu toggle works and links are reachable.
- Breadcrumb level/title matches meta values.
- Footer "메인으로 돌아가기" works.

#### C. YouTube
- Valid `video_id` renders embed player.
- If `video_id` missing, `video_url` parsing fallback works.
- Invalid ID shows safe placeholder message.
- Video remains 16:9 in all viewport sizes.

#### D. Tabs and Content
- All tabs switch without layout break.
- Keyboard arrows move between tabs.
- Tab panel only shows selected panel.
- Intro/Core/Summary/Full Script content count matches source files.
- Hangman tab exists and is reachable as 6th tab.

#### E. TTS
- TTS plays English text in all supported sections.
- Speed selector applies new playback rate.
- Stop button cancels active speech.
- Re-click behavior stops or switches correctly.
- Visual state (`is-speaking`) updates on start/end/error.

#### F. Word Cards
- Flip animation works on click and keyboard (Enter/Space).
- Escape closes flipped state.
- TTS/bookmark click does not trigger flip.
- Controls work:
  - flip all
  - reset
  - shuffle
  - smart review
  - share progress
- Search/filter/bookmark filters combine correctly.
- Smart review ordering updates card list.

#### G. State Persistence
- Refresh preserves:
  - flipped cards
  - bookmarks
  - difficulties
  - badges
  - theme
  - accumulated study time

#### H. Session and Dashboard
- Timer increments every second.
- Stats reflect real interactions.
- Badge area updates when conditions are met.
- Online/offline indicator changes with network state.

#### I. Offline Support
- Service worker registers successfully.
- After first load, cached assets open offline.
- Data text files are served from cache when network is down.

#### J. Hangman Game
- Korean prompt line displays only KR translation from current Core sentence.
- No duplicate instructional Korean text below prompt.
- Shuffled word chips are selectable and reorder exercise is playable.
- Correct word click:
  - chip disappears from pool
  - chip appears in next answer slot
  - correct SFX plays
- Wrong word click:
  - chip shakes
  - wrong SFX plays
  - hangman step increments
- Final failure step:
  - death SFX plays (distinct from wrong/correct)
- Round completion:
  - victory SFX plays
  - score +1 only on clear
- Bottom control row has all 4 buttons in one line (space permitting).

### 3) Regression Test Suite (Quick)

Run this after every change:
1. Page opens without console errors.
2. YouTube renders.
3. Tabs switch (mouse + keyboard).
4. TTS plays/stops.
5. Word card flip + bookmark + filter works.
6. Hangman: order selection / sound feedback / score works.
7. Refresh preserves state.
8. Mobile menu toggles.
9. Dark mode toggles and persists.

---

## Automated Quality Verification Checklist

Treat this as pass/fail gates before release.

### Gate A: Structure and Data
- [ ] `index.html`, `style.css`, `script.js`, `service-worker.js` exist.
- [ ] `data/00~05.txt` paths are correct.
- [ ] No hardcoded story body content in HTML.

### Gate B: Interaction Integrity
- [ ] No broken IDs/selectors used by script.
- [ ] No duplicate event handlers for the same control.
- [ ] Word card controls remain functional after shuffle/filter.
- [ ] Hangman order-selection logic matches expected-word progression.
- [ ] Hangman pool removal/answer insertion works without duplication.

### Gate C: Accessibility
- [ ] Skip link exists and is keyboard reachable.
- [ ] Interactive elements have clear labels or aria-label.
- [ ] `aria-live` status updates for TTS.
- [ ] Focus ring is visible for keyboard users.
- [ ] Color contrast remains readable in light/dark mode.

### Gate D: Performance
- [ ] Batch rendering uses `DocumentFragment` for list-heavy sections.
- [ ] Word card interactions use event delegation.
- [ ] Hangman interaction remains responsive during rapid wrong clicks.
- [ ] No blocking synchronous loops on large lists.
- [ ] Initial render remains responsive on mobile device profile.

### Gate E: Compatibility
- [ ] Works in Chrome/Edge/Firefox desktop.
- [ ] Works in Android Chrome + iOS Safari.
- [ ] No layout overflow at defined breakpoints.

---

## Cross-Browser Compatibility Procedure

For each target browser:
1. Hard refresh page.
2. Verify YouTube loads.
3. Verify text file fetch and rendering.
4. Verify speech synthesis availability and graceful fallback.
5. Verify sticky header/tabs and mobile menu behavior.
6. Verify localStorage persistence.
7. Verify service worker cache behavior (where supported).
8. Verify Web Audio SFX behavior (correct/wrong/death/win) and fallback stability.

Log results as:
- Browser / Version
- Pass/Fail per module
- Notes (UI deviation, console warnings, unsupported APIs)

---

## Accessibility Validation Procedure

### Keyboard-only
- Tab through all actionable controls.
- Confirm no keyboard trap.
- Confirm Enter/Space actions (tabs/cards/buttons).
- Confirm Escape behavior on word cards.

### Screen Reader Readability (basic)
- Check meaningful labels for:
  - menu buttons
  - TTS buttons
  - word cards
  - controls
- Confirm dynamic status via `aria-live` for TTS.

### Motion & Visual
- Enable reduced-motion OS setting.
- Confirm animations are reduced/disabled.
- Validate contrast in both themes.

---

## Performance Benchmarks and Measurement

### Target Benchmarks
- Initial interactive render: under 2.5s on mid-range desktop.
- Tab switch perceived response: under 150ms.
- Word card action (flip/filter): under 120ms perceived.
- No major jank during scroll on mobile.

### Measurement Method
- Use browser DevTools Performance panel:
  - record first load
  - record tab switch
  - record shuffle/filter on word cards
- Use Lighthouse (optional):
  - Performance: target 80+
  - Accessibility: target 90+
  - Best Practices: target 90+

### Optimization Actions if Below Target
- Reduce repeated DOM queries in hot paths.
- Re-check event delegation coverage.
- Minimize forced layout/reflow in animations.
- Keep cache list minimal but sufficient.

---

## Release Readiness Checklist (Final)

Release only when all are true:
- [ ] All functional tests passed.
- [ ] Regression quick suite passed.
- [ ] Accessibility procedure passed.
- [ ] Cross-browser matrix completed.
- [ ] Performance benchmarks met or documented with mitigation.
- [ ] No critical console errors.
- [ ] Template remains reusable for new content without code rewrites.

This requirements file is the canonical quality template for future auto-generated content pages.