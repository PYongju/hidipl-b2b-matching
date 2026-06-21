---
version: 1.1
name: HiDipl Design System
description: A clarity-first B2B interface for AV/display equipment procurement. Clean utility surfaces and focused data presentation, with Pretendard typography and a blue-purple palette drawn from the HiDipl logo. UI chrome recedes so data can speak — no decorative gradients, no shadows on chrome, only soft elevation on floating surfaces.

colors:
  # Brand & Accent — HiDipl 로고 색 기반
  primary: "#5064C8"           # 로고 메인 블루퍼플 — 버튼, 링크, 액션
  primary-hover: "#3D50B8"     # primary 다크 — hover
  primary-light: "#EEF0FB"     # primary 연한 배경 — 선택 영역, 파란 배지 (#eff6ff 대체)
  primary-on-dark: "#A0AEFF"   # 다크 서피스 위 링크
  accent: "#7864B4"            # 로고 미드 퍼플 — 배지 포인트, active 상태
  accent-hover: "#6450A0"      # accent 다크

  # Focus
  focus: "#5064C8"             # focus ring

  # Surface — 실제 코드베이스 기준 유지
  canvas: "#ffffff"            # 카드·패널 흰 배경
  canvas-subtle: "#f8fafc"     # 페이지 배경 (body, .flow-page, .app-shell) — slate-50
  canvas-muted: "#f1f5f9"      # 테이블 헤더, 배지 배경, 섹션 배경 — slate-100
  canvas-hover: "#f0f7ff"      # 테이블 행 hover (파란 톤)
  surface-card: "#ffffff"
  surface-sidebar: "#f8fafc"
  surface-dark: "#1E293B"      # 글로벌 네비 — slate-800
  surface-dark-2: "#0F172A"    # 더 깊은 다크 서피스

  # Text — 실제 코드베이스 기준 유지
  ink: "#0F172A"               # 주요 텍스트
  ink-muted: "#475569"         # 본문 보조, 통계 라벨 — slate-600
  ink-subtle: "#94a3b8"        # placeholder, 비활성 — slate-400
  ink-secondary: "#64748b"     # 보조 텍스트, 라벨 — slate-500
  on-dark: "#f8fafc"           # 다크 서피스 위 텍스트
  on-dark-muted: "#CBD5E1"     # 다크 서피스 위 보조 텍스트

  # Status
  status-success: "#059669"
  status-warning: "#D97706"
  status-error: "#DC2626"
  status-info: "#5064C8"       # primary와 통일
  status-success-bg: "#ECFDF5"
  status-warning-bg: "#FFFBEB"
  status-error-bg: "#FEF2F2"
  status-info-bg: "#EEF0FB"    # primary-light와 통일

  # Borders — 실제 코드베이스 기준 유지
  border: "#d7dde8"            # 카드·입력·칩 테두리 (가장 흔함)
  border-table: "#e2e8f0"      # 테이블·비교표 구분선 — slate-200
  border-admin: "#e8edf4"      # admin 테이블
  hairline: "#f1f5f9"          # 행 구분선 (미세)

  # Utility
  on-primary: "#ffffff"
  on-accent: "#ffffff"
  overlay: "rgba(15, 23, 42, 0.48)"

typography:
  display-lg:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 36px
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: -0.5px
  display-md:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 28px
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: -0.3px
  heading-lg:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: -0.2px
  heading-md:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: -0.1px
  heading-sm:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  body-strong:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 600
    lineHeight: 1.6
    letterSpacing: 0
  body:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  body-sm:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  label:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: 0
  caption:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  caption-strong:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: 0
  nav-link:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 13px
    fontWeight: 500
    lineHeight: 1.0
    letterSpacing: 0
  table-header:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 12px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.3px
  table-cell:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0
  numeric:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: -0.1px
    fontVariantNumeric: tabular-nums
  fine-print:
    fontFamily: "Pretendard, system-ui, sans-serif"
    fontSize: 11px
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: 0

rounded:
  none: 0px
  xs: 4px
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  pill: 9999px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  section: 64px

components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 10px 20px
    height: 40px
  button-secondary:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary}"
    border: "1px solid {colors.primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 10px 20px
    height: 40px
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-muted}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 10px 20px
    height: 40px
  button-danger:
    backgroundColor: "{colors.status-error}"
    textColor: "{colors.on-primary}"
    typography: "{typography.body-strong}"
    rounded: "{rounded.md}"
    padding: 10px 20px
    height: 40px
  button-sm:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: 6px 14px
    height: 32px
  badge-teal:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  badge-status-success:
    backgroundColor: "{colors.status-success-bg}"
    textColor: "{colors.status-success}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  badge-status-warning:
    backgroundColor: "{colors.status-warning-bg}"
    textColor: "{colors.status-warning}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  badge-status-error:
    backgroundColor: "{colors.status-error-bg}"
    textColor: "{colors.status-error}"
    typography: "{typography.caption-strong}"
    rounded: "{rounded.pill}"
    padding: 2px 10px
  global-nav:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    typography: "{typography.nav-link}"
    height: 56px
    padding: 0 24px
  sidebar:
    backgroundColor: "{colors.surface-sidebar}"
    textColor: "{colors.ink}"
    width: 240px
    borderRight: "1px solid {colors.border}"
  card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    border: "1px solid {colors.border}"
    padding: 24px
  card-compact:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    border: "1px solid {colors.border}"
    padding: 16px
  table-container:
    backgroundColor: "{colors.canvas}"
    rounded: "{rounded.lg}"
    border: "1px solid {colors.border}"
    overflow: hidden
  table-header-row:
    backgroundColor: "{colors.canvas-muted}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.table-header}"
    height: 44px
  table-row:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.table-cell}"
    height: 52px
    borderBottom: "1px solid {colors.hairline}"
  table-row-hover:
    backgroundColor: "{colors.canvas-subtle}"
  input:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border-strong}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 10px 14px
    height: 40px
  input-focus:
    border: "2px solid {colors.steel}"
    outline: none
  select:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.border-strong}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: 10px 14px
    height: 40px
  tag:
    backgroundColor: "{colors.canvas-muted}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 3px 8px
  floating-bar:
    backgroundColor: "rgba(248, 250, 252, 0.88)"
    backdropFilter: "blur(12px)"
    textColor: "{colors.ink}"
    borderTop: "1px solid {colors.border}"
    height: 64px
    padding: 0 24px
  tooltip:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    typography: "{typography.caption}"
    rounded: "{rounded.sm}"
    padding: 6px 10px
  divider:
    color: "{colors.border}"
    height: 1px
---

## Overview

HiDipl is a **data-first B2B procurement interface** for AV/display equipment. Every screen is organized around tables, comparison grids, and workflow status — not marketing surfaces. UI chrome stays minimal so procurement data can be read at a glance. One primary accent color (`{colors.primary}` — Deep Navy) carries all interactive elements; Vivid Teal (`{colors.accent}`) is reserved for status highlights and badges only.

Density is intentionally moderate — not as airy as a marketing site, not as packed as a spreadsheet. Each card and table row breathes enough to be scannable on a single monitor during a client meeting.

**Key Characteristics:**
- Data-first layout: tables and comparison grids are first-class citizens, not afterthoughts.
- Single primary interactive color (`{colors.primary}` — Deep Navy). Teal is accent-only, never for actions.
- Two button grammars: solid primary (`{rounded.md}`) for actions, pill (`{rounded.pill}`) for badges only.
- Pretendard at weight 400 / 500 / 600 / 700. Weight 500 exists for numeric/label contexts (unlike strictly binary systems). No weight 300.
- Soft elevation only on floating surfaces (nav, sticky bars, modals). Cards use border, not shadow.
- Hairline borders (`{colors.border}`) provide structure without visual noise.
- Dark header (`{colors.surface-dark}`) anchors the top of every page; all other surfaces are light.

---

## Colors

### Brand & Accent
- **Deep Navy** (`{colors.primary}` — #0D47A1): The single interactive color. All primary buttons, text links, focus rings, active nav states.
- **Deep Navy Hover** (`{colors.primary-hover}` — #1565C0): Hover state for primary interactive elements.
- **Light Blue on Dark** (`{colors.primary-on-dark}` — #64B5F6): Links and interactive elements on dark surfaces where Deep Navy would disappear.
- **Vivid Teal** (`{colors.accent}` — #00ACC1): Status badges, "확정 완료" indicators, active workflow steps. **Never used as a button color.**
- **Steel Blue** (`{colors.steel}` — #1E88E5): Focus rings, secondary interactive highlights.

### Surface
- **Pure White** (`{colors.canvas}` — #ffffff): Card interiors, table rows, input backgrounds.
- **Near-White** (`{colors.canvas-subtle}` — #F8FAFC): Default page background. Just different enough from white to make cards read as elevated.
- **Muted** (`{colors.canvas-muted}` — #F1F5F9): Table header rows, alternate section backgrounds, empty state fills.
- **Dark Header** (`{colors.surface-dark}` — #0F172A): Global nav bar and hero sections.
- **Dark 2** (`{colors.surface-dark-2}` — #1E293B): Sidebar, dark modal surfaces.

### Text
- **Ink** (`{colors.ink}` — #0F172A): All primary text — headings, table cell content.
- **Ink Muted** (`{colors.ink-muted}` — #475569): Secondary labels, column headers, helper text.
- **Ink Subtle** (`{colors.ink-subtle}` — #94A3B8): Placeholder text, disabled states.
- **On Dark** (`{colors.on-dark}` — #F8FAFC): Text on `{colors.surface-dark}` surfaces.
- **On Dark Muted** (`{colors.on-dark-muted}` — #CBD5E1): Secondary text on dark surfaces.

### Status
All status colors have a paired background (`-bg`) for use inside badges and status cells.
- **Success** (`{colors.status-success}` — #059669): 확정 완료, 매칭 성공.
- **Warning** (`{colors.status-warning}` — #D97706): 컨펌 요청, OCR 확인 필요.
- **Error** (`{colors.status-error}` — #DC2626): 오류, 만료.
- **Info** (`{colors.status-info}` — #0284C7): 진행 중, 일반 안내.

### Borders
- **Border** (`{colors.border}` — #E2E8F0): Default card border, table outer border.
- **Border Strong** (`{colors.border-strong}` — #CBD5E1): Input borders, dividers that need to be clearly visible.
- **Hairline** (`{colors.hairline}` — #F1F5F9): Table row separators, subtle internal dividers.

---

## Typography

### Font Family
**Pretendard** — primary typeface across all surfaces and weights. Falls back to system-ui for cross-platform consistency.

```css
font-family: 'Pretendard', system-ui, sans-serif;
```

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|
| `{typography.display-lg}` | 36px | 700 | 1.15 | -0.5px | Page hero titles |
| `{typography.display-md}` | 28px | 700 | 1.2 | -0.3px | Section titles, modal headers |
| `{typography.heading-lg}` | 22px | 600 | 1.3 | -0.2px | Card headings, panel titles |
| `{typography.heading-md}` | 18px | 600 | 1.4 | -0.1px | Sub-section headings |
| `{typography.heading-sm}` | 15px | 600 | 1.4 | 0 | Small section labels |
| `{typography.body-strong}` | 15px | 600 | 1.6 | 0 | Button labels, emphasized body |
| `{typography.body}` | 15px | 400 | 1.6 | 0 | Default paragraph, form help text |
| `{typography.body-sm}` | 13px | 400 | 1.55 | 0 | Secondary descriptions |
| `{typography.label}` | 13px | 500 | 1.4 | 0 | Form labels, sidebar nav items |
| `{typography.table-header}` | 12px | 600 | 1.4 | 0.3px | Table column headers (all-caps optional) |
| `{typography.table-cell}` | 14px | 400 | 1.5 | 0 | Table cell content |
| `{typography.numeric}` | 14px | 500 | 1.4 | -0.1px | Prices, quantities — always tabular-nums |
| `{typography.caption}` | 12px | 400 | 1.5 | 0 | Helper text, timestamps |
| `{typography.caption-strong}` | 12px | 600 | 1.5 | 0 | Badge labels, status chips |
| `{typography.nav-link}` | 13px | 500 | 1.0 | 0 | Global nav, sidebar links |
| `{typography.fine-print}` | 11px | 400 | 1.5 | 0 | Legal copy, footnotes |

### Principles
- **Negative letter-spacing on display sizes only.** Headings at 22px and above use slight tightening (-0.2 to -0.5px). Body and below use 0.
- **Body at 15px.** Slightly larger than the 14px default common in dense B2B apps — gives the interface a more readable, less fatiguing feel during long sessions.
- **Tabular numerals everywhere numbers are compared.** `font-variant-numeric: tabular-nums` on all price, quantity, and percentage columns so digits align vertically.
- **Weight ladder: 400 / 500 / 600 / 700.** 500 is for labels and numerics where 400 is too light but 600 is too assertive. No 300 or 800.
- **Table headers at 12px / 600 / 0.3px tracking.** The slight positive tracking at small size improves scanability without all-caps.

---

## Layout

### Spacing System
- **Base unit:** 8px. All structural layout snaps to multiples of 8.
- **Tokens:** `{spacing.xxs}` 4px · `{spacing.xs}` 8px · `{spacing.sm}` 12px · `{spacing.md}` 16px · `{spacing.lg}` 24px · `{spacing.xl}` 32px · `{spacing.xxl}` 48px · `{spacing.section}` 64px.
- **Card padding:** `{spacing.lg}` (24px). Compact cards: `{spacing.md}` (16px).
- **Table cell padding:** 12px vertical, 16px horizontal.
- **Page content padding:** 24px on mobile, 32px on tablet, 40px on desktop.

### Grid & Breakpoints

| Breakpoint | Width | Layout |
|---|---|---|
| Mobile | < 768px | Single column, sidebar hidden, stacked cards |
| Tablet | 768px – 1023px | Sidebar collapsible, 2-column grid |
| Desktop | 1024px – 1279px | Sidebar fixed, main content area |
| Wide | ≥ 1280px | Sidebar fixed, wider content, up to 3-column grid |

- **Sidebar width:** 240px (fixed on desktop, overlay on mobile).
- **Content max-width:** 1200px inside the main content area.
- **Column grid:** 12-column, 24px gutters on desktop; 4-column, 16px gutters on mobile.

### Whitespace Philosophy
Whitespace is a productivity tool, not decoration. Tables and cards need enough breathing room to be scannable without scrolling mentally. Each card section starts with at least `{spacing.lg}` (24px) above its heading. Table rows at 52px height give enough vertical space to read Korean text comfortably without feeling padded.

---

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Flat | No shadow, 1px border | Cards, table containers, inputs |
| Raised | `0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)` | Dropdown menus, popovers |
| Floating | `0 4px 16px rgba(0,0,0,0.10), 0 2px 4px rgba(0,0,0,0.06)` | Modals, sticky bars, tooltips |
| Overlay | `0 20px 60px rgba(0,0,0,0.18)` | Full modal dialogs |

**Shadow philosophy:** Cards use border (`{colors.border}`), not shadow. Shadow is reserved for elements that float above the page — dropdowns, modals, sticky bars. This keeps the flat data surface readable and avoids visual noise in dense table views.

---

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.none}` | 0px | Table rows (no corner rounding between rows) |
| `{rounded.xs}` | 4px | Inline code, micro chips |
| `{rounded.sm}` | 6px | Small buttons (`{component.button-sm}`), tags |
| `{rounded.md}` | 8px | Default buttons, inputs, selects, card-compact |
| `{rounded.lg}` | 12px | Cards, table containers, modals |
| `{rounded.xl}` | 16px | Large modal dialogs, page-level panels |
| `{rounded.pill}` | 9999px | Badges, status chips — never buttons |
| `{rounded.full}` | 9999px | Avatar circles, icon buttons |

---

## Components

### Global Nav
**`global-nav`** — Persistent dark bar pinned to the top. Background `{colors.surface-dark}`, height 56px, text `{colors.on-dark}` in `{typography.nav-link}`. Left: logo + product name. Center: primary nav links. Right: user avatar, notifications. On mobile (< 768px), collapses to hamburger menu.

### Sidebar
**`sidebar`** — 240px fixed sidebar on desktop. Background `{colors.surface-sidebar}`, `1px solid {colors.border}` right border. Nav links in `{typography.label}`. Active link: `{colors.primary}` text + `{colors.canvas-muted}` background + 3px left border in `{colors.primary}`. On tablet and below, becomes an overlay drawer.

### Buttons
**`button-primary`** — Default action. Background `{colors.primary}`, text `{colors.on-primary}` in `{typography.body-strong}`, `{rounded.md}` (8px), 40px height. Active: `transform: scale(0.97)`. Focus: 2px solid `{colors.steel}` outline, 2px offset.

**`button-secondary`** — Secondary action. White background, `{colors.primary}` text, `1px solid {colors.primary}` border. Same sizing as primary.

**`button-ghost`** — Tertiary action or cancel. Transparent background, `{colors.ink-muted}` text. Used inside modals and sidebars.

**`button-danger`** — Destructive actions only. Background `{colors.status-error}`. Use sparingly.

**`button-sm`** — Inline table or card action (e.g., "견적 보기", "확인"). Height 32px, `{rounded.sm}` (6px).

### Cards
**`card`** — Default content container. White background, `1px solid {colors.border}`, `{rounded.lg}` (12px), 24px padding. No shadow. Content: heading in `{typography.heading-lg}` → body in `{typography.body}` → actions at bottom.

**`card-compact`** — Tighter variant for dashboard stat tiles and sidebar sections. 16px padding, `{rounded.md}`.

### Tables
**`table-container`** — Outer wrapper: white background, `1px solid {colors.border}`, `{rounded.lg}`, `overflow: hidden` (so header row corners match container).

**`table-header-row`** — Background `{colors.canvas-muted}`, height 44px, text `{colors.ink-muted}` in `{typography.table-header}` (12px / 600 / 0.3px tracking).

**`table-row`** — Background `{colors.canvas}`, height 52px, `1px solid {colors.hairline}` bottom border. Hover: `{component.table-row-hover}` background.

Numeric columns (`{typography.numeric}`) must use `font-variant-numeric: tabular-nums` so prices and quantities align vertically.

### Badges & Status Chips
**`badge-teal`** — Used for primary category tags and featured items. Background `{colors.accent}` (Vivid Teal), white text, pill shape.

**`badge-status-*`** — Four variants mapping to `{colors.status-*}` tokens. Used for workflow status (결재 상태), OCR results, match scores. Pill shape, 12px / 600 text.

Korean workflow status mapping:
- `"컨펌 요청"` → `badge-status-warning`
- `"확정 완료"` → `badge-status-success`
- `"검토 중"` → `badge-status-info`
- `"반려"` → `badge-status-error`

### Inputs & Forms
**`input`** — White background, `1px solid {colors.border-strong}`, `{rounded.md}`, 40px height, 15px body text. Focus: border upgrades to `2px solid {colors.steel}`.

**`select`** — Same spec as input with trailing chevron icon.

Form label: `{typography.label}` (13px / 500) above the input, 6px gap.
Helper text: `{typography.caption}` in `{colors.ink-subtle}` below the input, 4px gap.
Error text: `{typography.caption}` in `{colors.status-error}` below the input, input border turns `{colors.status-error}`.

### Floating Bar
**`floating-bar`** — Sticky bottom bar on step-by-step workflow pages. `rgba(248, 250, 252, 0.88)` background with `backdrop-filter: blur(12px)`, 64px height, `1px solid {colors.border}` top border. Left: current step summary. Right: primary action button.

### Tags
**`tag`** — Small inline label for equipment categories, vendor attributes. Background `{colors.canvas-muted}`, `{colors.ink-muted}` text, `{rounded.sm}`, 3px × 8px padding.

### Tooltip
**`tooltip`** — Dark background `{colors.surface-dark}`, white text in `{typography.caption}`, `{rounded.sm}`, appears on hover after 300ms delay.

---

## Do's and Don'ts

### Do
- Use `{colors.primary}` (Deep Navy) for every interactive element — buttons, links, active states. One interactive color only.
- Use `{colors.accent}` (Vivid Teal) for status badges and highlights only. Never as a button color.
- Set card borders to `1px solid {colors.border}`. No card shadows — shadow is for floating elements only.
- Use `font-variant-numeric: tabular-nums` on every numeric column in tables.
- Keep table row height at 52px to support comfortable Korean text reading.
- Use `{rounded.lg}` (12px) for cards and containers, `{rounded.md}` (8px) for buttons and inputs. Don't mix.
- Map Korean workflow status labels to the correct `badge-status-*` variant consistently across all views.
- Apply `transform: scale(0.97)` on button active/press states for tactile feedback.

### Don't
- Don't use `{colors.accent}` (Teal) as a button background — it's for status indication only.
- Don't add shadows to cards — use `{colors.border}` instead. Shadow is reserved for dropdowns, modals, and sticky bars.
- Don't use gradients. Surface rhythm comes from alternating `{colors.canvas}` and `{colors.canvas-subtle}`, not decorative gradients.
- Don't set body text below 15px — 13px is the floor for secondary labels; 15px for readable body content.
- Don't use weight 300. The weight ladder is 400 / 500 / 600 / 700.
- Don't apply `{rounded.pill}` to buttons — pill shape is for badges and status chips only.
- Don't use `{colors.primary-on-dark}` (Light Blue) on light surfaces — it's the dark-surface-only variant.
- Don't tighten letter-spacing on body text — negative tracking is for display sizes (22px+) only.

---

## Responsive Behavior

### Breakpoints

| Name | Width | Key Changes |
|---|---|---|
| Mobile | < 768px | Sidebar hidden (overlay), single-column layout, nav collapses to hamburger, floating bar full-width |
| Tablet | 768px – 1023px | Sidebar collapsible, 2-column card grid, tables horizontally scrollable |
| Desktop | 1024px – 1279px | Sidebar fixed 240px, main content fills remaining width |
| Wide | ≥ 1280px | Sidebar fixed, wider content area, up to 3-column dashboard grid |

### Table Behavior at Small Sizes
- Tables below 768px: horizontal scroll container, pinned first column (project name / vendor name).
- Column priority order for hiding at tablet: secondary metadata columns first, status and price always visible.

### Touch Targets
- Minimum 44 × 44px for all interactive elements.
- `{component.button-primary}` at 40px height is 4px below the minimum — add `min-height: 44px` on touch devices.
- Table row actions (`{component.button-sm}` at 32px) should have minimum 44px touch target via padding compensation.

---

## Iteration Guide

1. Reference tokens by key — never inline hex or hardcoded px values.
2. Status badge variants live as separate entries in `components:` — use the correct one for each Korean workflow label.
3. Table and card borders use `{colors.border}` or `{colors.hairline}` — choose based on prominence needed.
4. When adding a new component, define background, text, border, rounded, and padding tokens first.
5. Floating elements (modals, dropdowns, sticky bars) always get a shadow from the elevation scale. Static elements never do.
6. New interactive colors require a design decision — the system is intentionally single-accent. Propose before adding.