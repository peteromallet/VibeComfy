export async function fulfillNodePackInstallRequest(panel, obligations = {}, deps = {}) {
  const request = obligations.nodePackInstallRequest;
  if (!request || typeof request !== "object") {
    return;
  }
  const fetchImpl = deps.fetch || globalThis.fetch;
  const transition = deps.transition;
  const fulfillLifecycleTransitionObligations = deps.fulfillLifecycleTransitionObligations;
  const renderLifecycleTransition = deps.renderLifecycleTransition;
  if (
    typeof fetchImpl !== "function"
    || typeof transition !== "function"
    || typeof fulfillLifecycleTransitionObligations !== "function"
    || typeof renderLifecycleTransition !== "function"
  ) {
    throw new Error("Node pack installer dependencies are incomplete.");
  }

  const installKey = obligations.nodePackInstallKey || null;
  const body = request.body && typeof request.body === "object" ? request.body : {};
  const candidate = body.candidate || null;
  try {
    const res = await fetchImpl(request.endpoint || "/vibecomfy/node-packs/install", {
      method: request.method || "POST",
      headers: request.headers || { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = await res.json();
    const transitionName = res.ok && result?.ok !== false
      ? "NODE_PACK_INSTALL_SUCCEEDED"
      : "NODE_PACK_INSTALL_FAILED";
    const nextObligations = transition(panel, transitionName, { result, candidate, installKey });
    fulfillLifecycleTransitionObligations(panel, nextObligations);
    renderLifecycleTransition(panel, nextObligations);
  } catch (error) {
    const result = {
      ok: false,
      status: "validation_failed",
      validation_status: "validation_failed",
      error: String(error?.message || error),
      message: "Node pack install request failed.",
    };
    const nextObligations = transition(panel, "NODE_PACK_INSTALL_FAILED", { result, candidate, installKey });
    fulfillLifecycleTransitionObligations(panel, nextObligations);
    renderLifecycleTransition(panel, nextObligations);
  }
}
