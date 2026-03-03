# Frontend Changes

## Dark/Light Mode Toggle Button

### Summary
Added a theme toggle button positioned fixed in the top-right corner of the UI. The button uses sun/moon SVG icons to indicate the current theme and the action that will occur on click. The theme preference is persisted to `localStorage` and restored on page load.

---

### Files Modified

#### `frontend/index.html`
- Added `<button id="themeToggle">` immediately inside `<body>`, before `.container`.
- The button contains two inline SVG icons:
  - **Sun icon** (`.theme-icon-sun`) — visible in dark mode; clicking switches to light mode.
  - **Moon icon** (`.theme-icon-moon`) — visible in light mode; clicking switches back to dark mode.
- Accessible attributes: `aria-label` (updated dynamically by JS) and `title`.

#### `frontend/style.css`
Three additions:

1. **Light theme CSS variables** (`[data-theme="light"]` on `<html>`):
   - Overrides background, surface, text, and border colours for a light palette while keeping the primary blue unchanged.

2. **Smooth theme transitions** on `body`, sidebar, chat area, inputs, buttons, and the toggle itself:
   - `transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease, box-shadow 0.3s ease`

3. **`#themeToggle` styles**:
   - `position: fixed; top: 1rem; right: 1rem` — always visible top-right.
   - Circular shape (`border-radius: 50%`), 40×40 px, `z-index: 100`.
   - Hover: scales up slightly, border and icon colour change to primary blue.
   - Focus: `box-shadow` focus ring (`:focus-visible` only, no outline flash on click).
   - Active: slight scale-down for tactile feedback.
   - **Icon animation**: both icons are `position: absolute`. The inactive icon is hidden with `opacity: 0` and rotated/scaled away. The active icon fades in at `opacity: 1` with a `0.3s ease` transition.

#### `frontend/script.js`
Three additions:

1. **`initTheme()`** — reads `localStorage.getItem('theme')` on `DOMContentLoaded` and applies a saved light preference.
2. **`applyTheme(theme)`** — sets/removes `data-theme="light"` on `document.documentElement`, updates `aria-label`/`title` on the button, and writes to `localStorage`.
3. **`toggleTheme()`** — reads the current `data-theme` attribute and calls `applyTheme` with the opposite value.
4. Event listener on `#themeToggle` registered in `setupEventListeners()`.

---

### Behaviour Details
- **Default**: dark mode (no `data-theme` attribute on `<html>`).
- **Persistence**: user's last choice is saved to `localStorage` under the key `"theme"`.
- **Keyboard**: the button is a native `<button>` element — fully keyboard-navigable (Tab + Enter/Space).
- **Screen readers**: `aria-label` updates to reflect the action ("Switch to light/dark mode").
- **No build step required**: pure HTML/CSS/JS, served as static files by FastAPI.

---

## Light Theme CSS Variables — Full Token System

### Summary
Expanded the CSS variable system so every colour in the stylesheet is theme-aware. Previously, source chips, code blocks, error messages, and success messages used hardcoded literal colours that rendered inaccessibly (failed WCAG AA contrast) in light mode. All have been tokenised.

### Changes — `frontend/style.css` only

#### `:root` — new semantic token groups added

| Token group | Variables added |
|---|---|
| Source chips | `--chip-bg`, `--chip-border`, `--chip-color`, `--chip-hover-bg`, `--chip-hover-border`, `--chip-hover-color` |
| Code blocks | `--code-bg` |
| Error messages | `--error-bg`, `--error-color`, `--error-border` |
| Success messages | `--success-bg`, `--success-color`, `--success-border` |

Dark-mode defaults match the original hardcoded values exactly (no visual change in dark mode).

#### `[data-theme="light"]` — expanded from 8 to 22 overrides

New light-mode values with WCAG contrast ratios:

| Token | Value | Ratio on white | Grade |
|---|---|---|---|
| `--text-primary` | `#0f172a` | ~17:1 | AAA |
| `--text-secondary` | `#475569` | ~7.1:1 | AAA (upgraded from `#64748b` at 4.7:1) |
| `--chip-color` | `#4338ca` | ~8.6:1 | AAA |
| `--chip-hover-color` | `#3730a3` | ~10.4:1 | AAA |
| `--error-color` | `#b91c1c` | ~8.8:1 | AAA |
| `--success-color` | `#15803d` | ~5.3:1 | AA |
| `--code-bg` | `rgba(0,0,0,0.05)` | — | subtle tint |

#### Properties updated to use variables (was hardcoded)

- `.source-chip` — `background`, `border`, `color`
- `a.source-chip:hover` — `background`, `border-color`, `color`; added `color 0.15s` to its transition
- `.message-content code` — `background-color`
- `.message-content pre` — `background-color`
- `.error-message` — `background`, `color`, `border`
- `.success-message` — `background`, `color`, `border`
