export const ROOT_SCOPE_V1 = "root_scope_v1";
export const ROOT_SCOPE = Object.freeze({ kind: "root", path: "" });

export function assertRootScopeV1(scope) {
  if (!scope || scope.kind !== "root" || scope.path !== "" || Object.keys(scope).sort().join(",") !== "kind,path") {
    const error = new Error("Agent Edit authority supports only root_scope_v1 {kind:'root', path:''}.");
    error.code = "unsupported_scope";
    throw error;
  }
  return ROOT_SCOPE;
}

export function assertRootGraphV1(graph) {
  if (!graph || typeof graph !== "object") throw new TypeError("graph must be an object.");
  if (graph.definitions && typeof graph.definitions === "object" && Object.keys(graph.definitions).length) {
    const error = new Error("Definitions/subgraphs are unsupported in root_scope_v1."); error.code = "unsupported_scope"; throw error;
  }
  for (const group of Array.isArray(graph.groups) ? graph.groups : []) {
    if (group && String(group.scope_path ?? "") !== "") {
      const error = new Error("Nested group scopes are unsupported in root_scope_v1."); error.code = "unsupported_scope"; throw error;
    }
  }
}
