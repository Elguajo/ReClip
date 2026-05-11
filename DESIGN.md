---
version: alpha
name: ReClip
description: A compact, self-hosted media downloader UI for AV workflow operators.
colors:
  primary: "#1a1a1d"
  bg: "#f4f1eb"
  fg: "#3a3a38"
  accent: "#e85d2a"
  accent-hover: "#d04e1f"
  muted: "#9c9889"
  card: "#ffffff"
  card-border: "#e2ded6"
  success: "#2d8a4e"
  error: "#c43d3d"
  dark-bg: "#1a1a1d"
  dark-fg: "#e4e2dd"
  dark-accent: "#f0743a"
  dark-accent-hover: "#e85d2a"
  dark-muted: "#8f8f88"
  dark-card: "#2a2a2d"
  dark-card-border: "#3a3a3d"
  dark-success: "#45a869"
  dark-error: "#e05a5a"
  on-accent: "#1a1a1d"
typography:
  brand:
    fontFamily: Instrument Serif
    fontSize: 4.2rem
    fontWeight: 400
    lineHeight: 1
    letterSpacing: -0.03em
  brand-mobile:
    fontFamily: Instrument Serif
    fontSize: 3rem
    fontWeight: 400
    lineHeight: 1
    letterSpacing: -0.03em
  card-title:
    fontFamily: Instrument Serif
    fontSize: 1rem
    fontWeight: 400
    lineHeight: 1.3
  control:
    fontFamily: DM Mono
    fontSize: 0.82rem
    fontWeight: 500
    lineHeight: 1
    letterSpacing: 0.04em
  label:
    fontFamily: DM Mono
    fontSize: 0.68rem
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0.03em
  body:
    fontFamily: DM Mono
    fontSize: 0.88rem
    fontWeight: 400
    lineHeight: 1.4
rounded:
  control: 10px
  card: 14px
  media: 8px
  select: 6px
  pill: 999px
spacing:
  xs: 4px
  sm: 8px
  md: 14px
  lg: 24px
  xl: 48px
  page-x: 24px
  page-y: 60px
components:
  page:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.fg}"
    width: 620px
    padding: 60px 24px 80px
  page-dark:
    backgroundColor: "{colors.dark-bg}"
    textColor: "{colors.dark-fg}"
    width: 620px
    padding: 60px 24px 80px
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: 10px 20px
  button-primary-hover:
    backgroundColor: "{colors.accent-hover}"
  button-primary-dark:
    backgroundColor: "{colors.dark-accent}"
    textColor: "{colors.primary}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: 10px 20px
  button-primary-dark-hover:
    backgroundColor: "{colors.dark-accent-hover}"
  button-secondary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.bg}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: 6px 14px
  icon-button:
    backgroundColor: "{colors.card}"
    textColor: "{colors.fg}"
    rounded: "{rounded.control}"
    width: 38px
    height: 38px
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.fg}"
    rounded: "{rounded.card}"
    padding: 14px
  card-dark:
    backgroundColor: "{colors.dark-card}"
    textColor: "{colors.dark-fg}"
    rounded: "{rounded.card}"
    padding: 14px
  select:
    backgroundColor: "{colors.card}"
    textColor: "{colors.fg}"
    rounded: "{rounded.select}"
    padding: 5px 26px 5px 10px
  select-dark:
    backgroundColor: "{colors.dark-card}"
    textColor: "{colors.dark-fg}"
    rounded: "{rounded.select}"
    padding: 5px 26px 5px 10px
  metadata:
    textColor: "{colors.muted}"
    typography: "{typography.label}"
  metadata-dark:
    textColor: "{colors.dark-muted}"
    typography: "{typography.label}"
  progress-track:
    backgroundColor: "{colors.card-border}"
    rounded: "{rounded.pill}"
    height: 6px
  progress-track-dark:
    backgroundColor: "{colors.dark-card-border}"
    rounded: "{rounded.pill}"
    height: 6px
  progress-fill:
    backgroundColor: "{colors.accent}"
    rounded: "{rounded.pill}"
    height: 6px
  status-success:
    textColor: "{colors.success}"
    typography: "{typography.label}"
  status-success-dark:
    textColor: "{colors.dark-success}"
    typography: "{typography.label}"
  status-error:
    textColor: "{colors.error}"
    typography: "{typography.label}"
  status-error-dark:
    textColor: "{colors.dark-error}"
    typography: "{typography.label}"
---

## Overview

ReClip is a quiet production tool, not a marketing site. The interface should feel like a reliable desktop utility for AV engineers: compact, readable, fast to scan, and tolerant of repeated use.

The current visual identity is warm editorial minimalism: a serif wordmark, mono controls, off-white surfaces, dark ink text, and one orange interaction color. Keep the product experience focused on the paste -> fetch -> choose quality/preset -> download workflow.

## Colors

Use the CSS custom properties in `templates/index.html` as the source of truth. The warm light theme is the default; the dark theme mirrors the same hierarchy without introducing a new palette.

- **Background (`#f4f1eb`):** warm paper surface for the whole app.
- **Foreground (`#3a3a38`):** primary text and dark action buttons.
- **Accent (`#e85d2a`):** primary interaction, progress, active status, and the `Clip` brand emphasis.
- **Muted (`#9c9889`):** metadata, hints, inactive controls, and secondary status.
- **Card (`#ffffff`) and border (`#e2ded6`):** job cards, inputs, selects, and icon buttons.
- **Success and error:** reserved for completed jobs, reveal actions, failed fetches, conversion failures, and cancellation feedback.

Do not add extra brand colors for new phases. Conversion, quality, Windows parity, and release-related UI should reuse these tokens.

## Typography

Use only the two existing Google fonts:

- **Instrument Serif:** brand title and media card titles. It gives the app a distinctive editorial tone without adding UI complexity.
- **DM Mono:** controls, metadata, inputs, buttons, status text, and footer. It reinforces the utility/workflow character and keeps technical labels aligned.

Controls are uppercase with modest tracking. Avoid long prose inside the app; the user should understand the workflow from control placement and state changes.

## Layout

The first screen is the actual downloader, not a landing page. Keep the app as a centered single-column workspace with a maximum width of roughly `620px`.

Primary layout rules:

- Header: brand on the left, folder/theme icon buttons on the right.
- Input area: URL textarea, short hint, save-location text, then format/fetch controls.
- Results: vertical stack of cards with thumbnails, title, metadata, actions, quality select, conversion select, keep-original control, and progress states.
- Mobile: cards become single-column, thumbnails expand full width, and the fetch button spans the row.

Avoid sidebars, dashboards, nested cards, decorative panels, and marketing sections. This is a one-task utility.

## Elevation & Depth

ReClip uses borders and warm surfaces instead of shadows. Depth should come from:

- `1.5px` borders on inputs, cards, icon buttons, selects, and segmented controls.
- Subtle state color changes on hover/focus.
- Skeleton shimmer while metadata loads.
- A small slide-up animation for newly inserted cards.

Do not introduce heavy drop shadows, glass effects, gradients, or decorative blobs. They make the app feel less like a dependable local tool.

## Shapes

The shape language is soft but controlled:

- Main cards and textareas use `14px`.
- Icon buttons, fetch button, segmented controls, and download-all buttons use `10px`.
- Thumbnails use `8px`.
- Selects and compact card actions use `6px` to `7px`.
- Progress tracks are fully rounded.

Keep future controls within this scale. Do not mix sharp corners or oversized pill cards into the workflow.

## Components

### Brand Header

The brand must read as `ReClip`, with `Clip` in accent italic serif. Header actions are icon-only buttons with native `title` tooltips.

### URL Input

The textarea is the primary entry point. It should stay visually calm, with an accent focus ring and no inline instructional blocks beyond the existing short hint.

### Format Toggle

Video/audio selection is a compact segmented control. Active state uses foreground-on-background inversion, not accent fill. This keeps the orange accent available for fetch/progress.

### Fetch Button

Fetch is the main action before cards exist. It uses the accent color, uppercase mono text, and disabled opacity while metadata is loading.

### Job Card

Each card represents one URL. Keep it horizontally scannable on desktop:

- Thumbnail or audio/no-thumbnail icon on the left.
- Title in Instrument Serif.
- Uploader and duration as uppercase mono metadata.
- Actions and selects in one wrapping row.

Do not place cards inside larger cards or add extra card chrome around the results stack.

### Quality Select

Quality choices must come from actual `yt-dlp` formats. The default label is `Maximum available`; explicit heights use friendly labels and size estimates when available.

### Conversion Select

Conversion presets are workflow controls, not advanced settings. Show them compactly beside download actions, and reveal `Keep original` only when a non-`none` preset is selected.

### Progress

Use one progress row for downloading and converting. Downloading may show ETA; converting should show `Converting` without ETA unless the backend provides a trustworthy estimate.

### Completion Actions

`Show` is the primary completed action and uses success green. `Save As` remains secondary with the standard dark action treatment.

## Do's and Don'ts

- Do keep the downloader workflow visible on the first screen.
- Do use existing CSS custom properties before adding any new token.
- Do keep labels short, operational, and useful under pressure.
- Do preserve light/dark parity whenever adding UI.
- Do use dark ink text on orange accent buttons for small control text; this is the contrast-safe target for future UI edits.
- Do keep vanilla HTML/CSS/JS and no frontend build step.
- Do test new UI against long titles, many URLs, disabled quality selects, conversion states, and mobile width.
- Don't add framework-specific design assumptions.
- Don't add marketing copy, hero sections, decorative illustrations, or large explanatory panels.
- Don't introduce new dependencies just to support visual polish.
- Don't hardcode quality heights in UI; format availability belongs to metadata.
- Don't use color alone for status when text can carry the state clearly.
