# QtWebEngine: sidebar, typography and support diagnostics

This note records the root cause and concrete prevention rules for the
September 2026 layout regression. It does **not** constitute certification
against a physical ONT or the packaged Windows application.

## Observed failures

At 100–120% sizing the sidebar could remain visually wide after collapsing
while the workspace began at the rail width, causing the sidebar to cover
headings and action buttons. The automatic support workbench reserved a
narrow sticky column for its controls and a large column for an empty result,
then rendered multiple firmware feature fieldsets as columns *inside* the
narrow control column. The result was text breaking into single characters.

## Root causes found in repository

- `style.css` defines a fixed sidebar and a workspace offset.
- `telecom_console.css` had **seven** independent `.workspace` sizing
  rules, including subtraction of `--sidebar-width` and multiple zoom
  workarounds. The obsolete width rules were removed.
- `tangerine.css` had an independent collapse offset and an inverse
  `calc(100% / --am-zoom)` workaround. These were removed.
- `app.js` used CSS `zoom` on the complete `.app-shell`; that does not
  give the same viewport-responsive behavior as a native browser zoom.
- `tangerine_workflows.css` forced a narrow sticky support form and used
  viewport media queries rather than accommodating the actual nested space.

## Ownership boundaries

- `css/components/shell_layout.css` is the **single source** of themed
  sidebar/workspace geometry. Sidebar rail width comes from one CSS variable
  and an HTML dataset; the main content occupies `minmax(0,1fr)`.
- `tangerine_shell.js` owns sidebar preference, compact drawer and Escape
  close. It does not change routes or ONT sessions.
- `app.js` A+/A− now scale typography only. Do not reinstate body or shell
  CSS `zoom`, inverse body widths or JS left margins. The existing storage
  key is retained for prior user preferences.
- `tangerine_workflows.css` owns the support diagnostic layout. The form
  uses a full-width, non-sticky responsive grid. The empty state is compact.
- `support_diagnostics.js` displays verified capabilities as actionable
  controls. Unconfirmed candidates remain in an initially collapsed details
  section. A failed read must **not** mean firmware incompatibility.

## Verification recorded

- Source/template generation: 14 modular HTML parts joined exactly into
  `templates/index.html`; 424 unique `id` values and no duplicates.
- Targeted V8 harness: **17/17** existing and new UI smoke cases passed
  after the refactor. This harness emulates Node test interfaces and is not
  a real QtWebEngine process.
- Additional focused V8 smoke: **5/5** new layout and progressive-disclosure
  cases passed.
- Four modified CSS files: brace counts matched; three changed JS files:
  JavaScript syntax parsed.
- Synthetic headless Chromium geometry fixture: **30/30** combinations of
  viewport width (760, 920, 1024, 1440, 1680), rail state and type scaling
  (100%, 120%, 160%) did not overlap the sidebar/workspace or overflow the
  viewport. The fixture validates browser layout fundamentals but is *not*
  a screenshot of the complete application.
- The release workflow now includes the shell/support tests and checks for
  the new CSS component in both packaged builds. **That amended workflow
  has not yet been run**; it is tag-triggered.

## Desktop acceptance (manual)

On a fresh Windows package from a new tag after these changes, check 100%,
120% and 160% text sizes with the sidebar expanded/collapsed; resize the
window above/below 930px; verify the drawer opens/closes and the support form
stays legible. Connect the F6600P and confirm that firmware detection and
selected diagnostics still call their existing backend handlers. Repeat
with any physically available alternative firmware. Report what was
physically tested separately from synthetic test coverage.
