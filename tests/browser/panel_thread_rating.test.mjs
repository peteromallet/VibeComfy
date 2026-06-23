import test from "node:test";
import assert from "node:assert/strict";

import { createBrowserHarness } from "./harness.mjs";
import {
  populateAgentBubbleDetail,
  renderRatingWidget,
} from "../../vibecomfy/comfy_nodes/web/panel_thread.js";

async function waitFor(predicate, { attempts = 200 } = {}) {
  for (let index = 0; index < attempts; index += 1) {
    if (predicate()) {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
  throw new Error("waitFor timed out");
}

function renderPanelWithMessages(mod, messages) {
  const panel = mod.ensureAgentPanel();
  panel.state.sessionId = "sess-rating";
  panel.state.turnId = "0002";
  panel.state.chatLoaded = true;
  panel.state.chatMessages = messages;
  mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });
  return panel;
}

function ratingWidgets(document) {
  return document.body.querySelectorAll((node) => node.dataset?.vibecomfyRatingWidget === "1");
}

function ratingButton(widget, value) {
  return widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingValue === String(value))[0];
}

function makeWidgetDeps(document, submitRating, overrides = {}) {
  const el = (tagName, text) => {
    const node = document.createElement(tagName);
    if (text != null) {
      node.textContent = String(text);
    }
    return node;
  };
  return {
    el,
    button: (label, onClick) => {
      const node = el("button", label);
      node.onclick = onClick;
      return node;
    },
    showIssueModal: () => {},
    submitRating,
    ...overrides,
  };
}

function makeBubbleDetailDeps(document, overrides = {}) {
  const el = (tagName, text) => {
    const node = document.createElement(tagName);
    if (text != null) {
      node.textContent = String(text);
    }
    return node;
  };
  const appendTextLine = (target, text) => {
    const node = el("div", text);
    target.appendChild(node);
    return node;
  };
  return {
    appendAuditDetail: () => {},
    appendCandidateDetail: (target) => appendTextLine(target, "candidate detail"),
    appendDebugDetail: () => {},
    appendFailureDetail: () => {},
    appendQueueDetail: () => {},
    appendTextLine,
    changeDetailsForMessage: () => null,
    clearNode: (node) => {
      node.textContent = "";
    },
    createBubbleDetailSection: (label) => {
      const section = el("section");
      const heading = el("h3", label);
      const body = el("div");
      section.appendChild(heading);
      section.appendChild(body);
      return { section, body };
    },
    createDetails: (label, detail) => el("pre", `${label}: ${JSON.stringify(detail)}`),
    el,
    ...overrides,
  };
}

test("bubble detail renders canonical selector field changes without message field_changes aliases", async () => {
  const harness = await createBrowserHarness();
  try {
    const target = harness.document.createElement("div");
    const panel = {
      state: {
        sessionId: "sess-canonical",
        routeStatus: { kind: "ready", requestedRoute: "revise" },
      },
    };
    const message = {
      role: "agent",
      text: "Candidate ready.",
      turn_id: "turn-canonical",
      response: {
        ok: true,
        message: "Candidate ready.",
        outcome: {
          kind: "candidate",
          changes: [{ uid: "seed", field_path: "widgets.seed", new: 42 }],
        },
        candidate: { graph: { nodes: [] }, graph_hash: "graph-hash" },
        eligibility: { applyable: true, reason: "ready", message: "" },
        turn_identity: { session_id: "sess-canonical", turn_id: "turn-canonical" },
        stage_snapshots: [{ stage: "candidate_review", ok: true, blocking: false }],
      },
    };

    populateAgentBubbleDetail(target, panel, message, null, makeBubbleDetailDeps(harness.document));

    assert.match(target.textContent, /widgets\.seed -> 42/);
    assert.match(target.textContent, /candidate detail/);
  } finally {
    await harness.dispose();
  }
});

test("bubble detail candidate section can be gated by reducer RouteStatus", async () => {
  const harness = await createBrowserHarness();
  try {
    const target = harness.document.createElement("div");
    const panel = {
      state: {
        sessionId: "sess-route-status",
        routeStatus: { kind: "ready", requestedRoute: "revise" },
      },
    };

    populateAgentBubbleDetail(
      target,
      panel,
      { role: "agent", text: "Route-ready response.", turn_id: "turn-route-status" },
      null,
      makeBubbleDetailDeps(harness.document),
    );

    assert.match(target.textContent, /Candidate/);
    assert.match(target.textContent, /candidate detail/);
  } finally {
    await harness.dispose();
  }
});

test("rating widget renders only below the latest assistant response and submits through the rating endpoint", async () => {
  const seen = [];
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/rating": ({ options }) => {
        const body = JSON.parse(options.body);
        seen.push(body);
        return { status: 201, body: { ok: true, rating_id: "rating-ui" } };
      },
    },
  });
  try {
    const mod = await harness.loadExtension();
    renderPanelWithMessages(mod, [
      { role: "user", text: "first ask", turn_id: "0000" },
      { role: "agent", text: "first answer", turn_id: "0001" },
      { role: "agent", text: "latest answer", turn_id: "0002" },
    ]);

    const widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);
    assert.equal(widgets[0].dataset.vibecomfyResponseId, "sess-rating/0002");
    const stepTwo = widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingStep === "2")[0];
    assert.equal(stepTwo.style.display, "none");

    ratingButton(widgets[0], 8).click();
    assert.equal(stepTwo.style.display, "grid");
    widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingComment === "1")[0].value = "helpful";
    widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingSubmit === "1")[0].click();

    await waitFor(() => (
      seen.length === 1
      && /Rating applied/.test(
        widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingStatus === "1")[0].textContent,
      )
    ));
    assert.deepEqual(seen[0], {
      response_id: "sess-rating/0002",
      session_id: "sess-rating",
      turn_id: "0002",
      rating: 8,
      pack_shared: false,
      pack_comment: null,
      comment: "helpful",
    });
    assert.notEqual(widgets[0].style.display, "none");
    assert.equal(ratingButton(widgets[0], 8).dataset.selected, "1");
    assert.match(
      widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingStatus === "1")[0].textContent,
      /Rating applied/,
    );
  } finally {
    await harness.dispose();
  }
});

test("thread reconciliation rerenders long markdown messages when only the tail changes", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    const prefix = "prefix ".repeat(40);
    renderPanelWithMessages(mod, [
      { role: "agent", text: `${prefix}**old tail**`, turn_id: "0002" },
    ]);
    assert.match(harness.document.body.textContent, /old tail/);

    renderPanelWithMessages(mod, [
      { role: "agent", text: `${prefix}**new tail**`, turn_id: "0002" },
    ]);
    assert.match(harness.document.body.textContent, /new tail/);
    assert.doesNotMatch(harness.document.body.textContent, /old tail/);
  } finally {
    await harness.dispose();
  }
});

test("rating widget submit passes the active panel and waits for a selected rating before showing Step 2", async () => {
  const harness = await createBrowserHarness();
  try {
    const activePanel = {
      state: { sessionId: "sess-widget", turnId: "0004" },
    };
    const calls = [];
    const widget = renderRatingWidget(
      activePanel,
      { role: "agent", text: "answer", turn_id: "0004" },
      makeWidgetDeps(harness.document, async (panel, options) => {
        calls.push({ panel, options });
        return { ok: true };
      }),
    );
    harness.document.body.appendChild(widget);

    const stepTwo = widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingStep === "2")[0];
    const submit = widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingSubmit === "1")[0];
    assert.equal(stepTwo.style.display, "none");
    submit.click();
    assert.equal(calls.length, 0);

    ratingButton(widget, 6).click();
    assert.equal(stepTwo.style.display, "grid");
    submit.click();

    await waitFor(() => calls.length === 1);
    assert.equal(calls[0].panel, activePanel);
    assert.deepEqual(calls[0].options, {
      rating: 6,
      comment: null,
      pack_shared: false,
      pack_comment: null,
      response_id: "sess-widget/0004",
      session_id: "sess-widget",
      turn_id: "0004",
    });
  } finally {
    await harness.dispose();
  }
});

test("rating widget scrolls to the bottom when a score is selected", async () => {
  const harness = await createBrowserHarness();
  try {
    const activePanel = {
      state: { sessionId: "sess-scroll", turnId: "0004" },
      thread: { scrollHeight: 640, scrollTop: 0, dataset: {} },
    };
    const widget = renderRatingWidget(
      activePanel,
      { role: "agent", text: "answer", turn_id: "0004" },
      makeWidgetDeps(harness.document, async () => ({ ok: true })),
    );
    harness.document.body.appendChild(widget);

    ratingButton(widget, 6).click();

    assert.equal(activePanel.thread.scrollTop, 640);
    assert.equal(activePanel.thread.dataset.vibecomfyScrolledToBottom, "1");
    assert.equal(ratingButton(widget, 6).dataset.selected, "1");
  } finally {
    await harness.dispose();
  }
});

test("rating widget timer is not reset by comment typing and successful retry clears it", async () => {
  const harness = await createBrowserHarness();
  try {
    const panel = { state: { sessionId: "sess-timer", turnId: "0005" } };
    let attempt = 0;
    const widget = renderRatingWidget(
      panel,
      { role: "agent", text: "answer", turn_id: "0005" },
      makeWidgetDeps(harness.document, async () => {
        attempt += 1;
        return attempt === 1
          ? { ok: false, detail: "try again" }
          : { ok: true };
      }),
    );
    harness.document.body.appendChild(widget);

    ratingButton(widget, 4).click();
    const comment = widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingComment === "1")[0];
    const submit = widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingSubmit === "1")[0];
    submit.click();
    await waitFor(() => panel.__vibecomfyRatingTimers?.["sess-timer/0005"]);
    const scheduledTimer = panel.__vibecomfyRatingTimers["sess-timer/0005"];

    comment.value = "extra context";
    comment.oninput?.({ target: comment });
    comment.onchange?.({ target: comment });
    assert.equal(panel.__vibecomfyRatingTimers["sess-timer/0005"], scheduledTimer);

    submit.click();
    await waitFor(() => panel.state.ratingSubmittedResponseIds?.["sess-timer/0005"]);
    assert.equal(panel.__vibecomfyRatingTimers?.["sess-timer/0005"], undefined);
    assert.notEqual(widget.style.display, "none");
    assert.equal(ratingButton(widget, 4).dataset.selected, "1");
  } finally {
    await harness.dispose();
  }
});

test("rating widget ignores stale submit results after the widget disconnects", async () => {
  const harness = await createBrowserHarness();
  try {
    const panel = { state: { sessionId: "sess-stale", turnId: "0006" } };
    let resolveSubmit;
    const submitDone = new Promise((resolve) => {
      resolveSubmit = resolve;
    });
    const widget = renderRatingWidget(
      panel,
      { role: "agent", text: "answer", turn_id: "0006" },
      makeWidgetDeps(harness.document, async () => submitDone),
    );
    harness.document.body.appendChild(widget);

    ratingButton(widget, 10).click();
    widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingSubmit === "1")[0].click();
    widget.remove();
    resolveSubmit({ ok: true });

    await new Promise((resolve) => setTimeout(resolve, 0));
    assert.equal(panel.state.ratingSubmittedResponseIds, undefined);
    assert.equal(widget.style.display, "grid");
    assert.equal(panel.__vibecomfyRatingTimers?.["sess-stale/0006"], undefined);
  } finally {
    await harness.dispose();
  }
});

test("rating widget persists debug-pack default and honors the disable localStorage fallback", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    globalThis.localStorage.setItem("vibecomfy_pack_share_default", "1");
    renderPanelWithMessages(mod, [
      { role: "agent", text: "answer", turn_id: "0002" },
    ]);

    let widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);
    const checkbox = widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingPackShared === "1")[0];
    assert.equal(checkbox.checked, true);
    checkbox.checked = false;
    checkbox.onchange();
    assert.equal(globalThis.localStorage.getItem("vibecomfy_pack_share_default"), "0");

    globalThis.localStorage.setItem("vibecomfy_rating_widget_disabled", "1");
    renderPanelWithMessages(mod, [
      { role: "agent", text: "disabled answer", turn_id: "0003" },
    ]);
    widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("rating widget auto-hides after the 120-second expiry timer fires", async () => {
  const harness = await createBrowserHarness();
  const originalSetTimeout = globalThis.setTimeout;
  let expiryCallback;
  let expiryMs;
  globalThis.setTimeout = (callback, ms) => {
    expiryCallback = callback;
    expiryMs = ms;
    return 999;
  };
  try {
    const panel = { state: { sessionId: "sess-expiry", turnId: "0007" } };
    const widget = renderRatingWidget(
      panel,
      { role: "agent", text: "answer", turn_id: "0007" },
      makeWidgetDeps(harness.document, async () => ({ ok: true })),
    );
    harness.document.body.appendChild(widget);

    assert.equal(expiryMs, 120000);
    assert.equal(typeof expiryCallback, "function");
    expiryCallback();
    assert.equal(widget.style.display, "none");
    assert.equal(widget.textContent, "");
  } finally {
    globalThis.setTimeout = originalSetTimeout;
    await harness.dispose();
  }
});

test("rating widget cancels expiry timer when user selects a rating", async () => {
  const harness = await createBrowserHarness();
  const originalSetTimeout = globalThis.setTimeout;
  const originalClearTimeout = globalThis.clearTimeout;
  const scheduled = {};
  const cleared = new Set();
  let nextId = 1;
  globalThis.setTimeout = (callback, ms) => {
    const id = nextId;
    nextId += 1;
    scheduled[id] = { callback, ms };
    return id;
  };
  globalThis.clearTimeout = (id) => {
    cleared.add(id);
    delete scheduled[id];
  };
  try {
    const panel = { state: { sessionId: "sess-cancel", turnId: "0008" } };
    const widget = renderRatingWidget(
      panel,
      { role: "agent", text: "answer", turn_id: "0008" },
      makeWidgetDeps(harness.document, async () => ({ ok: true })),
    );
    harness.document.body.appendChild(widget);

    const expiryId = Object.keys(scheduled).find((id) => scheduled[id].ms === 120000);
    assert.ok(expiryId, "expiry timer scheduled");

    ratingButton(widget, 5).click();
    assert.ok(cleared.has(Number(expiryId)), "expiry timer cleared on rating selection");
    assert.equal(scheduled[expiryId], undefined);
  } finally {
    globalThis.setTimeout = originalSetTimeout;
    globalThis.clearTimeout = originalClearTimeout;
    await harness.dispose();
  }
});

test("rating widget does not render for non-agent assistant-role messages", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    renderPanelWithMessages(mod, [
      { role: "user", text: "ask", turn_id: "0000" },
      { role: "assistant", text: "legacy answer", turn_id: "0001" },
      { role: "agent", text: "latest answer", turn_id: "0002" },
    ]);

    const widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);
    assert.equal(widgets[0].dataset.vibecomfyResponseId, "sess-rating/0002");
  } finally {
    await harness.dispose();
  }
});

test("rating widget hides as soon as a new user message starts a pending turn", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    renderPanelWithMessages(mod, [
      { role: "agent", text: "last response", turn_id: "0002" },
    ]);

    let widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);

    // Simulate the user starting a new turn: the previous answer remains in
    // history, but a user message and pending agent bubble become latest.
    const panel = mod.ensureAgentPanel();
    panel.state.chatMessages = [
      { role: "agent", text: "last response", turn_id: "0002" },
      { role: "user", text: "next request", optimistic: true },
      { role: "agent", text: "", pending_response: true, executor_pending: true, local_id: "pending:0003" },
    ];
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("rating widget hides as soon as a new user message is appended", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    renderPanelWithMessages(mod, [
      { role: "agent", text: "last response", turn_id: "0002" },
    ]);

    let widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);

    const panel = mod.ensureAgentPanel();
    panel.state.chatMessages = [
      { role: "agent", text: "last response", turn_id: "0002" },
      { role: "user", text: "next request", optimistic: true },
    ];
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("rating widget keeps the selected score visible after successful submit and rerender", async () => {
  const harness = await createBrowserHarness({
    responses: {
      "/vibecomfy/agent-edit/rating": { status: 201, body: { ok: true, rating_id: "rating-rerender" } },
    },
  });
  try {
    const mod = await harness.loadExtension();
    const panel = renderPanelWithMessages(mod, [
      { role: "agent", text: "answer", turn_id: "0002" },
    ]);

    let widgets = ratingWidgets(harness.document);
    ratingButton(widgets[0], 9).click();
    widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingSubmit === "1")[0].click();
    await waitFor(() => panel.state.ratingSubmittedResponseIds?.["sess-rating/0002"]);

    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });
    widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);
    assert.equal(ratingButton(widgets[0], 9).dataset.selected, "1");
    assert.match(
      widgets[0].querySelectorAll((node) => node.dataset?.vibecomfyRatingStatus === "1")[0].textContent,
      /Rating applied/,
    );
  } finally {
    await harness.dispose();
  }
});

test("rating widget does not inherit panel turn id for pending responses", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    const panel = renderPanelWithMessages(mod, [
      { role: "user", text: "ask", optimistic: true },
      { role: "agent", text: "", pending_response: true, executor_pending: true, local_id: "pending:no-turn" },
    ]);
    panel.state.turnId = "previous-turn";
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 0);
  } finally {
    await harness.dispose();
  }
});

test("rating widget is keyed to the completed message turn, not current panel turn", async () => {
  const harness = await createBrowserHarness();
  try {
    const mod = await harness.loadExtension();
    const panel = renderPanelWithMessages(mod, [
      { role: "agent", text: "completed response", turn_id: "0009" },
    ]);
    panel.state.turnId = "0010";
    mod.renderAgentPanel(panel, { dirtySections: ["THREAD"] });

    const widgets = ratingWidgets(harness.document);
    assert.equal(widgets.length, 1);
    assert.equal(widgets[0].dataset.vibecomfyResponseId, "sess-rating/0009");
  } finally {
    await harness.dispose();
  }
});

test("rating widget shows Report issue button only for ratings below 5", async () => {
  const harness = await createBrowserHarness();
  try {
    const activePanel = { state: { sessionId: "sess-report", turnId: "0004" } };
    let issueCalls = [];
    const widget = renderRatingWidget(
      activePanel,
      { role: "agent", text: "answer", turn_id: "0004" },
      makeWidgetDeps(harness.document, async () => ({ ok: true }), {
        showIssueModal: (panel) => issueCalls.push(panel),
      }),
    );
    harness.document.body.appendChild(widget);

    const reportButton = widget.querySelectorAll((node) => node.dataset?.vibecomfyRatingReportIssue === "1")[0];
    assert.equal(reportButton.style.display, "none", "report button hidden initially");

    ratingButton(widget, 5).click();
    assert.equal(reportButton.style.display, "none", "report button hidden for rating 5");

    ratingButton(widget, 3).click();
    assert.equal(reportButton.style.display, "inline-block", "report button visible for rating 3");

    reportButton.click();
    assert.equal(issueCalls.length, 1);
    assert.equal(issueCalls[0], activePanel);
  } finally {
    await harness.dispose();
  }
});
