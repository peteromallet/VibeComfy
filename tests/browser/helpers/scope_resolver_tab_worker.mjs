import { parentPort, workerData } from "node:worker_threads";

const sessionStore = new Map();
globalThis.sessionStorage = {
  getItem(key) {
    return sessionStore.has(String(key)) ? sessionStore.get(String(key)) : null;
  },
  setItem(key, value) {
    sessionStore.set(String(key), String(value));
  },
  removeItem(key) {
    sessionStore.delete(String(key));
  },
};

try {
  const resolverUrl = new URL(
    "../../../vibecomfy/comfy_nodes/web/scope_resolver.js",
    import.meta.url,
  );
  const storageUrl = new URL(
    "../../../vibecomfy/comfy_nodes/web/scoped_session_storage.js",
    import.meta.url,
  );
  const resolver = await import(resolverUrl.href);
  const storage = await import(storageUrl.href);
  const first = resolver.captureInitialScopeId(workerData.graph);
  const nonce = storage._tabNonce();
  const sessionId = `session:${nonce}`;
  storage.setScopedSessionId(first.scopeId, sessionId);
  const second = resolver.captureInitialScopeId(workerData.graph);
  parentPort.postMessage({
    nonce,
    first,
    second,
    sessionId: storage.getScopedSessionId(second.scopeId),
  });
} catch (error) {
  parentPort.postMessage({ error: error instanceof Error ? error.stack : String(error) });
}
