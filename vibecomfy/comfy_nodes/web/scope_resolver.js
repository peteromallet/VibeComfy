// ── Scope resolver ─────────────────────────────────────────────────────────
// Zero-dependency module that computes deterministic structural graph
// fingerprints and per-workflow chat scope identities.
//
// Depends ONLY on the browser built-in sessionStorage (via the scoped
// session storage helpers from scoped_session_storage.js) and standard
// JS (JSON, BigInt).  No ComfyUI runtime imports (app, api, etc.) so it
// can be unit-tested in Node.js without a full browser harness.
//
// This module is imported by vibecomfy_roundtrip.js and re-exported for
// external consumers.

import {
  _tabNonce,
} from "./scoped_session_storage.js";
import {
  buildStructuralGraphProjection,
} from "./graph_projection.js";
import { canonicalSessionJsonString } from "./canonical_hash.js";

// ── FNV-1a-64 hash ──────────────────────────────────────────────────────
const FNV_OFFSET_BASIS = BigInt("0xcbf29ce484222325");
const FNV_PRIME = BigInt("0x100000001b3");

function _fnv1a64(text) {
  let hash = FNV_OFFSET_BASIS;
  for (let i = 0; i < text.length; i += 1) {
    hash ^= BigInt(text.charCodeAt(i));
    hash = (hash * FNV_PRIME) & BigInt("0xffffffffffffffff");
  }
  return hash.toString(16).padStart(16, "0");
}

// ── Scope resolver public API ────────────────────────────────────────────

/**
 * computeStructuralGraphFingerprint(graph)
 *
 * Returns a deterministic hex fingerprint (16 hex chars, 64-bit FNV-1a)
 * of the graph's *structural* projection.  Two graphs that differ only in
 * widget values (positions, colors, preview data) produce the same
 * fingerprint.  Adding/removing/rewiring a node or changing a type/mode
 * produces a different fingerprint.
 *
 * @param {object} graph  ComfyUI UI JSON (nodes + links)
 * @returns {string}      16-char hex fingerprint
 */
export function computeStructuralGraphFingerprint(graph) {
  const projection = buildStructuralGraphProjection(graph);
  // Strip widget_values from nodes for fingerprint computation.
  // Widget values (prompts, seeds, sizes, etc.) are workflow data, not
  // structural identity.  Changing them should not invalidate the scope.
  const fingerprintProjection = {
    nodes: projection.nodes.map((node) => {
      const { widgets_values: _wv, ...rest } = node;
      return rest;
    }),
    links: projection.links,
  };
  const json = canonicalSessionJsonString(fingerprintProjection);
  return _fnv1a64(json);
}

/**
 * computeScopeId(graph)
 *
 * Builds the per-workflow-window chat scope identity for the current
 * browser tab.  The default scope id is:
 *
 *   <tab-nonce>:<structural-fingerprint>
 *
 * When a Comfy workflow-window id is supplied, the scope id is:
 *
 *   <tab-nonce>:<workflow-id>:<structural-fingerprint>
 *
 * This guarantees:
 *  - Same graph in the same tab → same scope id (session reused)
 *  - Same graph in different tabs → different scope ids (SD2 fork)
 *  - Different graphs in the same tab → different scope ids
 *  - Same/empty graph in different Comfy workflow tabs → different scope ids
 *
 * Returns null when the graph is empty (no nodes) and no workflow id is
 * supplied.
 *
 * @param {object} graph  ComfyUI UI JSON (nodes + links)
 * @param {object} [opts]
 * @param {string|null} [opts.workflowId]  active Comfy workflow-window id
 * @returns {string|null} scope id or null for empty graphs
 */
export function computeScopeId(graph, { workflowId = null } = {}) {
  const projection = buildStructuralGraphProjection(graph);
  const normalizedWorkflowId = typeof workflowId === "string" && workflowId.trim()
    ? workflowId.trim()
    : null;
  if ((!Array.isArray(projection.nodes) || projection.nodes.length === 0) && !normalizedWorkflowId) {
    return null;
  }
  const fingerprint = computeStructuralGraphFingerprint(graph);
  const nonce = _tabNonce();
  return normalizedWorkflowId
    ? `${nonce}:${encodeURIComponent(normalizedWorkflowId)}:${fingerprint}`
    : `${nonce}:${fingerprint}`;
}

// ── Initial fingerprint capture with sessionStorage caching ──────────────

const SS_SCOPE_FINGERPRINT_PREFIX = "vibecomfy_scope_fingerprint:";

function _ssGet(key) {
  try {
    const s = typeof globalThis !== "undefined" && globalThis.sessionStorage !== null
      ? globalThis.sessionStorage
      : null;
    return s ? s.getItem(key) : null;
  } catch (_e) {
    return null;
  }
}

function _ssSet(key, value) {
  try {
    const s = typeof globalThis !== "undefined" && globalThis.sessionStorage !== null
      ? globalThis.sessionStorage
      : null;
    if (s) s.setItem(key, value);
  } catch (_e) {
    // Best-effort
  }
}

function _scopeFingerprintCacheKey(scopeId) {
  return `${SS_SCOPE_FINGERPRINT_PREFIX}${scopeId}`;
}

/**
 * captureInitialScopeId(graph, [opts])
 *
 * Captures the initial scope id for the given graph.  On first call for a
 * graph it computes `computeScopeId`, caches the fingerprint in
 * sessionStorage, and returns { scopeId, fingerprint, isNew: true }.
 * On subsequent calls with the same graph it returns the cached scope id
 * with { isNew: false }.
 *
 * When `opts.forceRefresh` is true the cache is bypassed and a fresh
 * scope id is computed (used for explicit new-conversation or scope-switch
 * operations).
 *
 * Returns null when the graph is empty.
 *
 * @param {object} graph          ComfyUI UI JSON
 * @param {object} [opts]
 * @param {boolean} [opts.forceRefresh]  bypass cache
 * @returns {{ scopeId: string, fingerprint: string, isNew: boolean }|null}
 */
export function captureInitialScopeId(graph, { forceRefresh = false, workflowId = null } = {}) {
  const projection = buildStructuralGraphProjection(graph);
  const normalizedWorkflowId = typeof workflowId === "string" && workflowId.trim()
    ? workflowId.trim()
    : null;
  if ((!Array.isArray(projection.nodes) || projection.nodes.length === 0) && !normalizedWorkflowId) {
    return null;
  }

  // Compute current fingerprint
  const currentFingerprint = computeStructuralGraphFingerprint(graph);
  const nonce = _tabNonce();
  const currentScopeId = normalizedWorkflowId
    ? `${nonce}:${encodeURIComponent(normalizedWorkflowId)}:${currentFingerprint}`
    : `${nonce}:${currentFingerprint}`;

  // Check cache (unless force refresh)
  if (!forceRefresh) {
    const cacheKey = _scopeFingerprintCacheKey(currentScopeId);
    try {
      const cached = _ssGet(cacheKey);
      if (cached === currentFingerprint) {
        // Cache hit — fingerprint still matches, return existing scope id
        return {
          scopeId: currentScopeId,
          fingerprint: currentFingerprint,
          isNew: false,
        };
      }
    } catch (_e) {
      // sessionStorage unavailable; proceed without cache
    }
  }

  // Cache miss or force refresh — store the fingerprint and return new scope
  try {
    const cacheKey = _scopeFingerprintCacheKey(currentScopeId);
    _ssSet(cacheKey, currentFingerprint);
  } catch (_e) {
    // Best-effort caching
  }

  return {
    scopeId: currentScopeId,
    fingerprint: currentFingerprint,
    isNew: true,
  };
}
