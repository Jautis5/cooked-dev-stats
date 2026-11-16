---
name: Social Stats
description: Organic content, channels and observed performance in one workspace.
colors:
  ink: "#20242c"
  muted: "#69717c"
  line: "#e6e8ec"
  paper: "#f7f8fa"
  surface: "#fff"
  rail: "#1d2129"
  rail-text: "#c1c6d0"
  accent: "#e77962"
  accent-ink: "#8e3522"
  tint: "#fff0eb"
  green: "#247354"
  orange: "#906427"
  focus: "#aa4630"
  chart-green: "#35866a"
  action: "#252a34"
  action-hover: "#3c4350"
  nav-active: "#f6f7f9"
  nav-hover: "#2a2f39"
  brand-active: "#343a45"
  range-bg: "#f4f5f7"
  field-line: "#dde2e8"
typography:
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "32px"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-.03em"
  metric:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "34px"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-.03em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "17px"
    fontWeight: 650
    lineHeight: 1.5
    letterSpacing: "-.02em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "12px"
    fontWeight: 550
    lineHeight: 1.5
  table-heading:
    fontFamily: "-apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "10px"
    fontWeight: 550
    lineHeight: 1.5
    letterSpacing: ".03em"
rounded:
  tag: "4px"
  range: "5px"
  thumbnail: "6px"
  field: "7px"
  control: "8px"
  content: "12px"
  surface: "14px"
  dialog: "16px"
spacing:
  tight: "4px"
  small: "8px"
  compact: "12px"
  control: "16px"
  row: "20px"
  panel: "24px"
  large: "28px"
  section: "32px"
  desktop-gutter: "36px"
components:
  button-refresh:
    backgroundColor: "{colors.action}"
    textColor: "{colors.surface}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    height: "37px"
  button-refresh-hover:
    backgroundColor: "{colors.action-hover}"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
    height: "37px"
  search-field:
    backgroundColor: "{colors.surface}"
    textColor: "#4a5564"
    rounded: "{rounded.field}"
    padding: "8px 10px 8px 13px"
    height: "37px"
  section-navigation:
    textColor: "{colors.rail-text}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
    height: "44px"
  section-navigation-active:
    backgroundColor: "{colors.nav-active}"
    textColor: "{colors.ink}"
  publication-link:
    backgroundColor: "#f2f7f4"
    textColor: "#38684d"
    rounded: "{rounded.tag}"
    padding: "4px 6px"
  surface-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
  chart-range:
    backgroundColor: "{colors.range-bg}"
    rounded: "{rounded.field}"
    padding: "3px"
  data-disclosure:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 9px"
    height: "37px"
  metric-strip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
  data-table:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
---

# Design System: Social Stats

## Overview

**Creative North Star: "Organic content workspace"**

An English-language organic-content workspace with a fixed graphite navigation rail and white, bordered work surfaces on a cool off-white ground. System sans typography, large tabular totals, restrained warm accents and a green recorded-view chart support quick comparison without a promotional hero.

Keep the same navigation while switching between all channels and one brand. Put detailed freshness, coverage, collection failures and number definitions inside Data status; retain truthful approximation marks and missing values in the content being read. The implemented primary Refresh action is graphite, and the active section is pale; coral is a small brand/detail accent.

**Key Characteristics:**

- Stable section and brand navigation.
- White bordered surfaces with generous internal spacing.
- Large measured totals; quiet supporting labels.
- Recorded history and explicit data states.

The actual implementation in `site/styles.css`, `site/index.html` and `site/app.js` is the source for these tokens. The accepted product and surface constraints are in `PRODUCT.md` and `.impeccable/surfaces/overview.md`. Desktop and mobile evidence is in `../review/desktop-verified.jpg` and `../review/mobile-verified.jpg`. Existing brand logos and source thumbnails are reused unchanged from the original tracker. No raster assets were generated or newly sourced; top-content cards without a source thumbnail display the existing channel logo as a contained fallback avatar.

## Colors

The frontmatter is normative. Sidecar tonal strips are synthesized display metadata, not additional implementation palette tokens.

### Primary

- **Graphite action** (`action`, `action-hover`): Refresh, with white text. The implemented high-priority action is dark.
- **Warm coral** (`accent`, `accent-ink`, `tint`): retained palette tokens for small brand and warm detail treatments; they do not replace the graphite action or pale section selection.

### Secondary

- **Measured green** (`green`, `chart-green`): positive measured deltas and the recorded-view line. Green publication links identify confirmed URLs.
- **Muted amber** (`orange` and component-specific amber values): limited coverage, saved/delayed states and warning indicators.

### Neutral

- **Ink / muted**: primary content and quieter context.
- **Paper / surface / line**: off-white canvas, white containers and thin dividers.
- **Rail / rail text**: dark navigation and readable muted labels. `nav-active` is a pale selected section; `brand-active` is a lighter graphite selected brand; `nav-hover` lifts inactive rows.
- **Focus**: a visible warm outline distinct from ordinary borders.

## Typography

Use the system sans stack in the frontmatter; no webfont is required. Headings are compact and bold, body copy is regular, and numbers use `font-variant-numeric: tabular-nums`.

- **Headline**: page title; mobile uses (28px).
- **Metric**: summary totals; widths at or below (1250px) use (29px), and (1600px) or wider use (39px). Phone totals use (31px); the full-width email total uses (32px).
- **Title**: section titles. Chart titles use (16px) at narrower widths.
- **Body**: supporting text and inherited control font.
- **Label**: buttons and compact controls. Smaller (10–11px) metadata belongs in secondary contexts and disclosures.
- **Table heading**: uppercase with modest tracking. Table body is (12px); numerical columns align right.

## Layout

The desktop rail is fixed at (232px), reduced to (210px) at or below (1250px). The topbar is (70px) high. Main content has a (1530px) maximum width, centered within the remaining shell, with (32px 36px 20px) padding. Repeated gaps use the frontmatter scale, usually (20–24px) inside panel groups and (26–32px) between sections.

The overview has four social metric cells; a Cooked Dev Kit cell makes five only in All channels or Cooked Dev scope. The metric strip is one bordered surface with internal dividers. The chart and channel list use a (1.75fr / 1fr) grid with a (290px) minimum side column. Between (901px) and (1050px), that grid becomes one column, channel rows form two columns and top content becomes two columns. At (701–900px), the hidden rail releases space and the chart/list and four-card grids return to their wider layout.

At or below (900px), navigation becomes a (270px) drawer and the topbar is (64px). At or below (700px), use (16px) side gutters, two metric columns with a full-width Kit row, chart before channels, and two top-content columns. Data status becomes a fixed inset panel. Filters use a two-column grid with full-width search. Tables remain horizontally scrollable rather than compressing columns. A narrow-phone adjustment at (370px) reduces selected type and image sizes.

## Elevation & Depth

Bordered white surfaces and the dark rail establish structure at rest. Broad shadows are reserved for floating disclosure and dialog layers; content cards gain a light shadow on hover.

- **Data panel**: (`0 14px 55px #15213a26`).
- **Dialog**: (`0 20px 80px #11182733`); backdrop (`#141b2980`).
- **Chart tooltip**: (`0 5px 18px #182c2525`) on a dark green surface.
- **Card hover**: (`0 6px 20px #2636500c`).
- **Selected chart range**: (`0 1px 3px #20242c12`).

## Shapes

Use the radius scale in the frontmatter: compact tags and controls are tighter than content containers, while dialogs have the largest corners. Main surfaces have a (1px) border. Logos retain their original artwork and are cropped to modest rounded squares in navigation and channel rows; the small card identity logo is circular. Dots, play indicators and close buttons are circular. Avoid decorative geometry and background gradients; the chart alone has a subtle green area fade expressing its series.

## Components

### Buttons and fields

Refresh is a compact dark action with a darker-to-lighter hover change. Secondary buttons are white with a thin border and quiet gray hover. Search and selects use the field radius, a thin field border and (37px) minimum height; phone search becomes (40px). Disabled buttons use (.55) opacity and a waiting cursor. Every ordinary interactive target uses a (2px) focus outline with (4px) offset.

### Navigation and mobile drawer

Overview, Content library and Connections are separate section links; the brand list preserves the current section when changing scope. Active links expose `aria-current="page"`. Section rows have a (44px) minimum height and brand rows (41px). Inactive rows lighten on hover. The drawer opens with focus on its close control, makes main content inert and loops Tab within its visible links/buttons. Escape, close and backdrop dismiss it and restore focus to the trigger. Choosing a route closes the drawer and focuses the page title; the closed mobile rail is inert. A skip link focuses the main content.

### Metric strip and status disclosure

Totals are compact only in the main strip; exact values and observation times remain available on focus/hover where implemented. A small coverage indicator directs readers to Data status. The Kit cell always identifies “Cooked Dev · Kit”, links to Subscribers and shows Auto-updated or Saved; other brand scopes omit it. Native disclosure holds collector freshness, failures, metric coverage and number definitions. Escape also closes Data status.

### Recorded-view chart

The (240px) SVG plot uses a (2.5px) green line and dashed horizontal grid. Its area fades from (#2b9567 at .14 opacity) to (.01 opacity). At wide desktop widths the chart display height is (260px). Range buttons expose `aria-pressed` for 24h, 7d, 30d and All. Saved observations alone are plotted; combined history begins only once every scoped source has an observation. No-source/no-history/no-period states use explicit empty messages and an em dash. Pointer, focus and click reveal a point tooltip with exact value and Vilnius timestamp; left/right arrows move between points. The active guide and dot reinforce selection.

### Channel rows, content cards and tables

Channel rows pair a logo and video count with a right-aligned view total; clicking enters that brand. Top content shows up to four videos ranked by observed views. Cards have a fixed media area, platform labels, two-line caption and measured view total; clicking opens details rather than claiming inline playback. Source thumbnails fill the media area; existing-logo fallbacks are contained with padding. Hover enlarges the media by (1.025) and adds the light card shadow.

Content library combines search, channel/platform/coverage filters, sorting and Reset filters. Export CSV follows visible filters and is disabled for no results. Confirmed publication chips are green external links; unconfirmed chips are dashed neutral labels. Missing confirmation is explicitly not proof of nonpublication. Tables use thin row separators and a subtle row hover. Details use a native modal dialog with platform status and observed metrics; close control, backdrop click and native Escape dismiss it. Scheduled records remain inside a separate disclosure and are excluded from published counts and performance totals.

### Loading, errors and motion

Initial metrics show a restrained pulsing placeholder. Refresh disables during loading. Saved fallback observations retain their real timestamps; missing sources do not acquire guessed values. A workspace load failure has an explicit alert and retry instruction. Empty top-content and filtered-table states provide literal explanations. Copy/export feedback appears in a short status toast.

State transitions are usually (.18s); card/toast transitions use (.2s), media hover (.25s ease-out), and the drawer (.22s cubic-bezier(.16,1,.3,1)). `prefers-reduced-motion: reduce` removes animations and transitions and restores automatic scroll behavior.

## Do's and Don'ts

### Do:

- Do retain the registered brand identities and their original asset links.
- Do use tabular numerals, ≈ for rounded values, and — for unknown values.
- Do preserve keyboard focus, drawer focus management and reduced-motion behavior.
- Do put detailed source diagnostics behind Data status and keep the overview focused on results and content.

### Don't:

- Don't introduce ads-manager controls, invented growth, deduplicated audience claims or publishing capabilities.
- Don't replace missing observations with zero or draw estimated history.
- Don't present a fallback brand avatar as a video frame or a newly produced thumbnail.
- Don't promote the tiny source counters and technical paragraphs back into the opening layout.

Documented manually from the finished source. The finish reviewer returned ship for the five material requested fixes; that verdict does not establish a general backend or security audit. No Impeccable installation or detector pass is claimed.
