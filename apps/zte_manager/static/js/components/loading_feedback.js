"use strict";

const ACTION_FEEDBACK_MS = 620;

export function createLoadingFeedback({
    requestState,
    documentRef = globalThis.document,
    setTimeoutImpl = globalThis.setTimeout?.bind(globalThis),
    clearTimeoutImpl = globalThis.clearTimeout?.bind(globalThis),
    now = () => Date.now(),
} = {}) {
    if (!requestState || typeof requestState.subscribe !== "function") {
        throw new TypeError("LoadingFeedback requer RequestState observável.");
    }

    let snapshot = requestState.snapshot();
    let statusTimer = null;
    let overlayTimer = null;
    let clickFeedbackUntil = 0;

    function elements() {
        return {
            overlay: documentRef?.getElementById?.("busyOverlay") || null,
            label: documentRef?.getElementById?.("busyText") || null,
            indicator: documentRef?.getElementById?.("requestStatusIndicator") || null,
        };
    }

    function renderOverlay() {
        const {overlay, label} = elements();
        if (!overlay || !label) return;
        if (overlayTimer !== null) clearTimeoutImpl(overlayTimer);
        const clickPending = now() < clickFeedbackUntil;
        const active = snapshot.busy || snapshot.pending > 0 || clickPending;
        overlay.classList.toggle("hidden", !active);
        overlay.setAttribute("aria-busy", String(active));
        if (active) {
            label.textContent = snapshot.busy
                ? snapshot.busyText
                : snapshot.lastOperation;
        }
        if (!snapshot.busy && snapshot.pending === 0 && clickPending) {
            overlayTimer = setTimeoutImpl(
                renderOverlay,
                Math.max(0, clickFeedbackUntil - now()) + 15,
            );
        }
    }

    function renderStatus() {
        const {indicator} = elements();
        if (!indicator) return;
        if (statusTimer !== null) clearTimeoutImpl(statusTimer);
        if (snapshot.lastError) {
            indicator.textContent = "Falha na operação: " + snapshot.lastError.message;
            indicator.classList.add("is-error");
            indicator.classList.remove("hidden");
            statusTimer = setTimeoutImpl(() => {
                requestState.clearError();
            }, 5500);
            return;
        }
        indicator.classList.remove("is-error");
        if (snapshot.pending > 0) {
            indicator.textContent = `Carregando... ${snapshot.pending} requisição(ões)`;
            indicator.classList.remove("hidden");
            return;
        }
        indicator.textContent = "Operação finalizada";
        statusTimer = setTimeoutImpl(
            () => indicator.classList.add("hidden"),
            1350,
        );
    }

    function render(nextSnapshot = requestState.snapshot()) {
        snapshot = nextSnapshot;
        renderOverlay();
        renderStatus();
    }

    const unsubscribe = requestState.subscribe(render);

    function setBusy(busy, text = "Processando...") {
        requestState.setBusy(Boolean(busy), text);
    }

    function startActionFeedback(button) {
        if (!button || button.disabled) return;
        if (button.matches?.(
            ".menu-item, .management-tab, .zoom-button, [data-page], [data-jump]",
        )) return;
        const raw = String(button.textContent || "").replace(/\s+/g, " ").trim();
        const label = (raw.slice(0, 85) || "Executando ação") + "...";
        requestState.setLastOperation(label);
        clickFeedbackUntil = now() + ACTION_FEEDBACK_MS;
        renderOverlay();
    }

    function reportError(error) {
        const id = requestState.begin({operation: snapshot.lastOperation});
        requestState.fail(id, error);
    }

    return Object.freeze({
        render,
        renderOverlay,
        renderStatus,
        setBusy,
        startActionFeedback,
        reportError,
        dispose() {
            unsubscribe();
            if (statusTimer !== null) clearTimeoutImpl(statusTimer);
            if (overlayTimer !== null) clearTimeoutImpl(overlayTimer);
        },
    });
}
