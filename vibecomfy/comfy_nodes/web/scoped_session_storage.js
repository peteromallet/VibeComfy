// ── Scoped session-storage persistence ────────────────────────────────────
//
// sessionStorage is scoped to the browser tab origin, providing natural tab
// isolation so duplicate tabs of the same workflow fork their conversations
// (SD2).  localStorage holds a legacy `vibecomfy_active_session_id` scalar
// that is migrated into the first scope that requests it, then cleared so it
// cannot leak into another scope or tab.
//
// This module has zero dependencies on ComfyUI internals (`app`, `api`, etc.)
// so it can be unit-tested in Node.js without a full browser harness.

// ── sessionStorage helpers (safe wrappers — tolerate missing/throwing storage) ─

const SS_SCOPE_SESSION_PREFIX = "vibecomfy_scope_session:";
const SS_TAB_NONCE_KEY = "vibecomfy_tab_nonce";
const LS_LEGACY_ACTIVE_SESSION_KEY = "vibecomfy_active_session_id";
let _memoryTabNonce = null;

function _safeStorage(storageKind) {
  try {
    const s = typeof globalThis !== "undefined" && globalThis[storageKind] !== null
      ? globalThis[storageKind]
      : undefined;
    return s || null;
  } catch (_e) {
    return null;
  }
}

function _storageGet(storageKind, key) {
  try {
    const storage = _safeStorage(storageKind);
    if (!storage) return null;
    return storage.getItem(key);
  } catch (_e) {
    return null;
  }
}

function _storageSet(storageKind, key, value) {
  try {
    const storage = _safeStorage(storageKind);
    if (!storage) return;
    storage.setItem(key, value);
  } catch (_e) {
    // Best-effort.
  }
}

function _storageRemove(storageKind, key) {
  try {
    const storage = _safeStorage(storageKind);
    if (!storage) return;
    storage.removeItem(key);
  } catch (_e) {
    // Best-effort.
  }
}

// ── localStorage helpers (same contract as existing _lsGet/_lsSet/_lsRemove) ─

function _lsGet(key) {
  return _storageGet("localStorage", key);
}

function _lsSet(key, value) {
  _storageSet("localStorage", key, value);
}

function _lsRemove(key) {
  _storageRemove("localStorage", key);
}

// ── sessionStorage helpers ─────────────────────────────────────────────────

function _ssGet(key) {
  return _storageGet("sessionStorage", key);
}

function _ssSet(key, value) {
  _storageSet("sessionStorage", key, value);
}

function _ssRemove(key) {
  _storageRemove("sessionStorage", key);
}

// ── Per-tab nonce ─────────────────────────────────────────────────────────
// Each browser tab gets a unique nonce on first access.  This nonce is the
// scope identity for this tab: two tabs of the same workflow get different
// nonces and therefore different scope→session bindings, forking the
// conversation per duplicate-tab rule (SD2).

function _tabNonce() {
  // Re-read sessionStorage on every call when it is available.  Besides
  // preserving the browser's per-tab value, this handles a storage reset
  // (for example, a duplicated test tab) without returning a stale module
  // memory value.
  const storage = _safeStorage("sessionStorage");
  let storageReadable = false;
  if (storage) {
    try {
      storage.getItem(SS_TAB_NONCE_KEY);
      storageReadable = true;
    } catch (_e) {
      // Fall back to the module-lifetime value when storage is inaccessible.
    }
  }
  if (!storageReadable && _memoryTabNonce) {
    return _memoryTabNonce;
  }
  let nonce = _storageGet("sessionStorage", SS_TAB_NONCE_KEY);
  if (!nonce) {
    nonce = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
    _ssSet(SS_TAB_NONCE_KEY, nonce);
  }
  _memoryTabNonce = nonce;
  return _memoryTabNonce;
}

// ── Scoped session-id persistence ─────────────────────────────────────────
// Maps a workflow fingerprint (scopeId) to the active backend session id for
// THIS browser tab only.  Duplicate tabs get different nonces and therefore
// independent scope→session bindings (SD2).

function _scopeSessionKey(scopeId) {
  return `${SS_SCOPE_SESSION_PREFIX}${scopeId}`;
}

function getScopedSessionId(scopeId) {
  if (typeof scopeId !== "string" || !scopeId) {
    return null;
  }
  return _ssGet(_scopeSessionKey(scopeId)) || null;
}

function setScopedSessionId(scopeId, sessionId) {
  if (typeof scopeId !== "string" || !scopeId) {
    return;
  }
  if (typeof sessionId === "string" && sessionId) {
    _ssSet(_scopeSessionKey(scopeId), sessionId);
  } else {
    _ssRemove(_scopeSessionKey(scopeId));
  }
}

function forgetScopedSessionId(scopeId) {
  if (typeof scopeId !== "string" || !scopeId) {
    return;
  }
  _ssRemove(_scopeSessionKey(scopeId));
}

// Scope identity used to append the structural fingerprint even when a
// workflow UUID was available. Migrate the binding for the currently loaded
// revision into the stable UUID-owned scope so upgrades retain that thread.
function migrateFingerprintScopedSessionId(scopeId, fingerprint) {
  if (typeof scopeId !== "string" || !scopeId
    || typeof fingerprint !== "string" || !fingerprint) {
    return null;
  }
  const current = getScopedSessionId(scopeId);
  if (current) {
    return current;
  }
  const legacyScopeId = `${scopeId}:${fingerprint}`;
  const legacy = getScopedSessionId(legacyScopeId);
  if (!legacy) {
    return null;
  }
  setScopedSessionId(scopeId, legacy);
  return legacy;
}

// ── Legacy localStorage migration ─────────────────────────────────────────
// `vibecomfy_active_session_id` in localStorage was the pre-scope global
// active session.  When a scope resolves its session for the first time and
// finds no scoped binding, this function migrates the legacy value into the
// scope ONCE and then removes the legacy key so it cannot leak into another
// scope or tab (SD2 one-time migration).

function _migrateLegacySessionOnce(scopeId) {
  if (typeof scopeId !== "string" || !scopeId) {
    return null;
  }
  const legacy = _lsGet(LS_LEGACY_ACTIVE_SESSION_KEY);
  if (!legacy) {
    return null;
  }
  // Migrate into the current scope and clear the legacy scalar so it cannot
  // be consumed by another tab/scope.
  setScopedSessionId(scopeId, legacy);
  _lsRemove(LS_LEGACY_ACTIVE_SESSION_KEY);
  return legacy;
}

function resolveScopeSessionId(scopeId) {
  if (typeof scopeId !== "string" || !scopeId) {
    return null;
  }
  const scoped = getScopedSessionId(scopeId);
  if (scoped) {
    return scoped;
  }
  // One-time legacy migration — consume the legacy scalar if present.
  const migrated = _migrateLegacySessionOnce(scopeId);
  if (migrated) {
    return migrated;
  }
  return null;
}

export {
  _tabNonce,
  getScopedSessionId,
  setScopedSessionId,
  forgetScopedSessionId,
  migrateFingerprintScopedSessionId,
  resolveScopeSessionId,
};
