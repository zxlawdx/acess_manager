# Phase 3 (part 1): inventory ES Module and sanitized API error boundary

**Base:** main includes #47 and post-merge operator-write/diagnostic alignment #48.
**Scope:** inventory view, legacy bridge, management clipboard reuse, generic
Vela API exception privacy. Other screens remain in classic scripts deliberately.

## Inventory module

`static/js/management/inventory_view.js` exports
`createInventoryView({ body, onSelect, relativeTime, onCheckedChange })`.
An instance is created after the DOM has parsed via `type="module"` and
published as `window.managementInventoryView`. The only event bridge to
the classic script is:

- `management:inventory-ready` → call the existing
  `renderManagementInventory()` shim.
- `management:inventory-select` with `detail.id` → update the existing
  `managementState.selectedDeviceId`, rerender, notify the technician.
- `window.managementRelativeTime` → reuse the existing Portuguese
  relative-time formatter without duplicating it.

This retains the existing IDs `managementInventoryBody`,
`managementInventorySearch`, `management-device-check`, and
`data-device-id`. Every cell is inserted using structured DOM construction
and `textContent`, not a large `innerHTML` string.

The component owns `checkedIds: Set<number>`. Batch actions consume the
Set through the shim's `checkedManagementDevices()`, including selections
temporarily hidden by search. Entries absent from an updated inventory are
pruned. Only two delegated event listeners are ever attached to the tbody;
`dispose()` aborts both via `AbortController`, preventing repeated handler
registration on every render.

Vela still serves static files through `{{ static(...) }}`. Legacy scripts
remain classic, in their original order, while the new view is loaded as an
ES Module; no dependency or bundler was introduced.

The management-panel copy button now uses the existing Phase 2
`window.desktopClipboard` implementation. Windows uses the native Win32
backend only, with manual textarea selection if unavailable. It never
reads the User-Agent or uses the browser clipboard as a Windows fallback.

## Generic Vela error handler

`api.py::_safe_call` retains all pre-existing `error` and `type` JSON
fields. Unexpected exceptions now return an additional `error_id` UUID
alongside an actionable generic message. Restricted application logs include
only the identifier, sanitized internal action/type and traceback **frame
basename/function/line**, without logging raw exception strings, URLs, IPs,
credentials, payload dumps or source snippets.

Validation/state/timeout messages preserve their previous public contract.
Future domain-specific review should replace any potentially unsafe
`ValueError`/`RuntimeError` originating directly from untrusted firmware
with typed, safe application errors; changing those now would risk altering
many legacy UI error messages.

## Regression and boundaries

```bash
python -m unittest tests.test_api_error_sanitization -v
node tests/test_inventory_view.cjs
node tests/test_desktop_clipboard.cjs
python -m unittest discover -s tests -v
```

The Node inventory regression imports the module as an actual ES Module and
uses a dependency-free synthetic DOM to verify text safety, search, checkbox
persistence, batch selection, selected row, event delegation and disposal.
Both Linux CI and a targeted Windows contract runner exercise these paths.

**Not claimed:** browser-level drag-and-drop or GUI smoke tests (Windows Qt
and Linux WebKit require real packaged builds); unrelated HTML/CSS or the
remaining 3k/4k-line classic scripts have not yet been decomposed.
