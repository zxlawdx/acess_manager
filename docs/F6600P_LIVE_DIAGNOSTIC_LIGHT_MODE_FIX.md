# F6600P live-test: Advanced discovery, full support progress and Qt light-mode contrast

## Evidence and root cause

A real F6600P using V9.0.10P6N34 authenticated successfully and populated
the Equipment page. Captured logs included successful HTTP responses for
status, PON, WAN, Wi-Fi, DNS and client menuData GETs. **HTTP 200 alone does
not prove every endpoint returned semantically valid firmware data.**

1. The Advanced bootstrap compared `ZXHN F6600P` against `F6600P`
   literally after stripping punctuation; a genuine vendor prefix made the
   catalog profile fail to match, and the initial tracker grid remained
   at the template's permanent "waiting for identification" text.
   Furthermore, the screen awaited slower serial router probes before
   showing the local native capabilities catalog.
2. The full support diagnosis is a single long-running, serialized HTTP
   operation; the UI showed a blocking overlay without collector progress.
   SQLite exceptions during final report/history storage could also discard
   an otherwise successful diagnosis.
3. The legacy telecom theme specified dark popup `select option` backgrounds,
   `#121316` advanced cards and `#121316` login flow tiles outside of
   theme selectors. Existing light styles did not explicitly cover these
   surfaces or native QtWebEngine popup colors.

## Changes

- `advanced.js`: use *actual server-reported* identity and catalog aliases
  to normalize a vendor-prefixed F6600P without rewriting authenticated
  session identity. Display the lightweight bootstrap **before** any
  `menuView/menuData` probe. For the native identified models, render
  `/device/capabilities` before auto probes. Unknown capabilities are
  clearly marked **not tested**, never falsely "confirmed".
  Native catalog/probing is independent of `writes_enabled`.
- `support_diagnostic_service.py` + `zte_service.py`: expose sanitized,
  per-collector progress through an independent lock.
  New `GET /api/diagnostics/support/progress` returns only
  `{running,stage,completed,total}`, without dumping router data or taking
  the ONT's serial `RLock`. Optional history failures no longer erase a
  completed diagnosis.
- `support_diagnostics.js`: show true collector progress while the original
  `POST /api/diagnostics/support` runs. A four-minute frontend deadline
  clears the overlay and informs the operator when the backend may still be
  busy (the UI never reports an unverified success). Every diagnosis section
  renders independently: a malformed optional collector cannot blank the
  other sections. The F6201B captured full-form path is unchanged.
- `neutral_console.css`, `style.css`, `telecom_console.css`,
  `light_mode_refine.css`: theme-dependent native option tokens plus
  light-only high-contrast `select/option/optgroup`, advanced cards,
  model-discovery operation rows and login steps; dark CSS palette stays
  unchanged.

## Regression checks

```sh
python -m unittest tests.test_f6600p_support_progress -v
node tests/test_discovery_bootstrap.cjs
node tests/test_f6600p_advanced_ui.cjs
node tests/test_f6600p_support_ui.cjs
node tests/test_f6600p_light_popups.cjs
python -m unittest discover -s tests -v
```

CI covers Python+Node contracts on Linux and focused Python+Node contracts
on Windows. It does **not** replace packaged QtWebEngine visual regression
or full-speedtest acceptance against the actual equipment. Validate the
Qt6 native option popup, support progress, report outcomes and unchanged
dark theme in the real Windows executable before merging into production.
