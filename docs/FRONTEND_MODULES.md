# Modular frontend template

The Vela app runs one prebuilt `index.html` so existing DOM hooks, local
`static()` links and packaged Windows/Linux resources continue to work.

**Edit the sources** in `apps/zte_manager/templates/source/`:
`shell_start.html`, twelve page modules under `pages/`, and
`shell_end.html`. The checked-in `index.html` is a generated artifact.

After editing HTML run:

```sh
python tools/build_frontend_template.py
python tools/build_frontend_template.py --check
```

The compiler only concatenates static UTF-8 fragments without changing
the DOM, data attributes, forms or runtime session bindings. Both GitHub
test and release workflows reject unsynchronized generated markup.

Shared visual components are separated under
`static/css/tangerine*.css`; editor behavior is separated under
`static/js/tangerine_forms.js`, independent of ONT session control.
