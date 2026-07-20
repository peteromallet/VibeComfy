// _intent_graph_receipt_core.mjs — PRIVATE C2a intent-graph receipt core.
//
// C2a checkpoint: an instance-local, externally-fenced preflight + fence-current
// receipt factory.  It is private infrastructure and is NOT integrated into any
// adapter, ledger, or runtime path.  It owns no mutation primitives and performs
// zero native writes: it only validates, reads, captures detached evidence, and
// resolves native bindings through injected, externally-owned callbacks.
//
// Hard rules (enforced here, not self-attested):
//   - The sole JS authority validator, the sole prepared-plan builder, and the
//     sole forward-operation-digest owner are imported BY NAME.  They are never
//     injected as fake validators (Gate: fixed hashing/contract identity at
//     import time).
//   - The fence is CLOSED/EXACT and externally supplied.  Its key set is fixed;
//     every field is type-checked.  No field is ever synthesized, defaulted, or
//     aliased.  Nested (non-root) scope is rejected before any graph acquisition.
//   - Authority-bound fence dimensions are compared against the validated
//     prepared authority AND the independently-computed operation digest; then
//     EVERY dimension is compared against the live fence from `readFence()`.
//   - The exact live graph reference is acquired once, privately bound into the
//     instance WeakMap, and compared by identity (===) on every fence check.
//   - Precondition/revision evidence and resolver `detachedEvidence` must be
//     plain, acyclic, and free of live-object references.  They are deep-cloned
//     and deep-frozen before leaving the core; only detached frozen evidence is
//     ever returned.  Live objects (graph, privateState, validated authority,
//     plan) live ONLY in the instance WeakMap.
//   - No `candidateGraph`, no whole-graph path, no mutation primitives, no
//     `Date.now`, no ambient repair, no write-on-read, and no public
//     lookup/debug/test backdoor.  The public surface is exactly two methods.

import { validatePreparedAuthorityV1 } from "./prepared_authority_v1.js";
import { buildPreparedPlan } from "./_prepared_plan_builder_v1.mjs";
import { forwardOperationDigest } from "./prepared_authority_v1.js";
import { assertRootScopeV1 } from "./root_scope_v1.js";

const INTENT_GRAPH_RECEIPT_CORE_V1 = "intent_graph_receipt_core_v1";

// Closed, exact fence key set.  Externally supplied; never widened here.
const _FENCE_KEYS = [
  "panel_id",
  "workflow_id",
  "scope",
  "scope_contract",
  "scope_activation_epoch",
  "apply_epoch",
  "transaction_id",
  "candidate_id",
  "plan_hash",
  "operation_digest",
  "restoration_digest",
  "lease_nonce",
  "generation",
];
const _FENCE_KEY_SET = new Set(_FENCE_KEYS);

const _HEX64 = /^[0-9a-f]{64}$/;

// ── Internal helpers ─────────────────────────────────────────────────────────

function _isPlainObject(value) {
  if (value === null || typeof value !== "object") return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}
function _fail(message, code, detail = {}) {
  const error = new Error(message);
  error.code = code;
  error.detail = detail;
  return error;
}

function _assertNonEmptyString(value, key) {
  if (typeof value !== "string" || value.length === 0) {
    throw _fail(`Fence ${key} must be a non-empty string`, "invalid_fence_field", { key });
  }
}

function _assertPositiveInt(value, key) {
  if (!Number.isInteger(value) || value <= 0) {
    throw _fail(`Fence ${key} must be a positive integer`, "invalid_fence_field", { key });
  }
}

function _assertHex64(value, key) {
  if (typeof value !== "string" || !_HEX64.test(value)) {
    throw _fail(`Fence ${key} must be a 64-char lowercase hex digest`, "invalid_fence_field", { key });
  }
}

// Deep structural equality over JSON-plain values (fence dimensions are plain).
function _jsonEqual(a, b) {
  try {
    return JSON.stringify(a) === JSON.stringify(b);
  } catch (_err) {
    return false;
  }
}

// Reject live/non-plain objects, functions, symbols, and cycles.  Evidence that
// reaches the core must be plain and detachable — never a live graph node, a
// class instance, or a self-referential structure.
function _assertDetachable(value, seen = new WeakSet(), path = "evidence") {
  if (value === null) return;
  const t = typeof value;
  if (t === "function") {
    throw _fail(`${path} contains a function reference`, "live_object_in_evidence", { path });
  }
  if (t === "symbol") {
    throw _fail(`${path} contains a symbol`, "live_object_in_evidence", { path });
  }
  if (t !== "object") return; // primitive
  if (!_isPlainObject(value) && !Array.isArray(value)) {
    throw _fail(`${path} is a non-plain live object`, "live_object_in_evidence", { path });
  }
  if (seen.has(value)) {
    throw _fail(`${path} is cyclic`, "cyclic_evidence", { path });
  }
  seen.add(value);
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      _assertDetachable(value[i], seen, `${path}[${i}]`);
    }
  } else {
    for (const key of Object.keys(value)) {
      _assertDetachable(value[key], seen, `${path}.${key}`);
    }
  }
}

function _deepClonePlain(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    const out = [];
    for (let i = 0; i < value.length; i += 1) out[i] = _deepClonePlain(value[i]);
    return out;
  }
  const out = {};
  for (const key of Object.keys(value)) out[key] = _deepClonePlain(value[key]);
  return out;
}

function _deepFreeze(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) _deepFreeze(value[i]);
    Object.freeze(value);
    return value;
  }
  for (const key of Object.keys(value)) _deepFreeze(value[key]);
  Object.freeze(value);
  return value;
}

// Clone-then-freeze: the caller receives a frozen detached copy that shares no
// reference with any live object held in the instance WeakMap.
function _detachAndFreeze(value, label) {
  _assertDetachable(value, new WeakSet(), label);
  return _deepFreeze(_deepClonePlain(value));
}

// ── Fence validation ─────────────────────────────────────────────────────────

function _validateFenceShape(fence) {
  if (!_isPlainObject(fence)) {
    throw _fail("Fence must be a plain object", "invalid_fence_shape");
  }
  const keys = Object.keys(fence);
  for (const key of keys) {
    if (!_FENCE_KEY_SET.has(key)) {
      throw _fail(`Unknown fence key: ${key}`, "unknown_fence_key", { key });
    }
  }
  for (const key of _FENCE_KEYS) {
    if (!Object.prototype.hasOwnProperty.call(fence, key)) {
      throw _fail(`Missing fence key: ${key}`, "missing_fence_key", { key });
    }
  }
  _assertNonEmptyString(fence.panel_id, "panel_id");
  _assertNonEmptyString(fence.workflow_id, "workflow_id");
  // Root scope only — nested scope is rejected HERE, before any acquisition.
  try {
    assertRootScopeV1(fence.scope);
  } catch (error) {
    throw _fail("Fence scope must be root_scope_v1", "nested_scope", { key: "scope", cause: error.code });
  }
  _assertNonEmptyString(fence.scope_contract, "scope_contract");
  _assertPositiveInt(fence.scope_activation_epoch, "scope_activation_epoch");
  _assertPositiveInt(fence.apply_epoch, "apply_epoch");
  _assertNonEmptyString(fence.transaction_id, "transaction_id");
  _assertNonEmptyString(fence.candidate_id, "candidate_id");
  _assertNonEmptyString(fence.plan_hash, "plan_hash");
  _assertHex64(fence.operation_digest, "operation_digest");
  _assertHex64(fence.restoration_digest, "restoration_digest");
  _assertNonEmptyString(fence.lease_nonce, "lease_nonce");
  _assertPositiveInt(fence.generation, "generation");
}

// Compare the authority-bound dimensions against the validated authority and the
// independently recomputed operation digest.  No synthesis: every mismatch fails.
function _compareAuthorityBoundDimensions(fence, validatedAuthority) {
  const expected = {
    workflow_id: validatedAuthority.workflow_id,
    scope: validatedAuthority.scope,
    transaction_id: validatedAuthority.transaction_id,
    candidate_id: validatedAuthority.candidate_id,
    plan_hash: validatedAuthority.plan_hash,
    lease_nonce: validatedAuthority.lease_nonce,
    generation: validatedAuthority.generation,
    operation_digest: forwardOperationDigest(validatedAuthority.operation.ops),
    restoration_digest: validatedAuthority.restoration_strategy.digest,
  };
  for (const key of Object.keys(expected)) {
    const fenceValue = key === "scope" ? fence.scope : fence[key];
    if (!_jsonEqual(fenceValue, expected[key])) {
      throw _fail(`Fence ${key} is not bound to the prepared authority`, "fence_dimension_mismatch", {
        key,
        fence: fenceValue,
        authority: expected[key],
      });
    }
  }
}

// Compare EVERY fence dimension against the live fence from readFence().  The
// externally-minted fence must equal the live fence exactly.
function _compareEveryDimension(fence, liveFence) {
  if (!_isPlainObject(liveFence)) {
    throw _fail("readFence() did not return a plain object", "invalid_live_fence");
  }
  for (const key of _FENCE_KEYS) {
    const liveValue = key === "scope" ? liveFence.scope : liveFence[key];
    const fenceValue = key === "scope" ? fence.scope : fence[key];
    if (!_jsonEqual(fenceValue, liveValue)) {
      throw _fail(`Fence ${key} does not match the live fence`, "live_fence_mismatch", {
        key,
        fence: fenceValue,
        live: liveValue,
      });
    }
  }
}

function _validateResolverOutput(native) {
  if (!_isPlainObject(native)) {
    throw _fail("resolveNativeBindings must return a plain object", "invalid_resolver_output");
  }
  if (!Object.prototype.hasOwnProperty.call(native, "privateState") ||
      !Object.prototype.hasOwnProperty.call(native, "detachedEvidence")) {
    throw _fail(
      "resolveNativeBindings must return distinct privateState and detachedEvidence",
      "invalid_resolver_output",
    );
  }
  if (native.privateState === native.detachedEvidence) {
    throw _fail(
      "resolveNativeBindings privateState and detachedEvidence must be distinct references",
      "invalid_resolver_output",
    );
  }
  if (native.privateState === null || typeof native.privateState !== "object") {
    throw _fail("resolveNativeBindings privateState must be an object", "invalid_resolver_output");
  }
}

// ── Public factory ───────────────────────────────────────────────────────────

export function createIntentGraphReceiptCore(app, dependencies) {
  if (dependencies === null || typeof dependencies !== "object") {
    throw _fail("dependencies must be an object", "missing_dependency");
  }
  const _required = ["readFence", "acquireGraph", "capturePrecondition", "resolveNativeBindings"];
  for (const name of _required) {
    if (typeof dependencies[name] !== "function") {
      throw _fail(`dependencies.${name} must be a function`, "missing_dependency", { name });
    }
  }

  // Instance-local: every live object lives here, keyed by its opaque receipt.
  const _store = new WeakMap();

  function _preflightPrepared(preparedAuthority, externallyMintedFence) {
    // 1. Validate the prepared authority through the sole JS validator.
    let validatedAuthority;
    try {
      validatedAuthority = validatePreparedAuthorityV1(preparedAuthority);
    } catch (error) {
      throw _fail("Prepared authority failed validation", "invalid_authority", {
        cause: error && error.code,
      });
    }

    // 2. Build the prepared plan through the sole builder.  Plan failure is a
    //    hard preflight rejection; no ambient repair.
    const planResult = buildPreparedPlan(validatedAuthority);
    if (!planResult || planResult.ok !== true || !planResult.plan) {
      throw _fail("Prepared plan build failed", "plan_build_failed", {
        diagnostic: planResult && planResult.diagnostic,
      });
    }
    const plan = planResult.plan;

    // 3. Validate the closed/exact fence shape BEFORE any graph acquisition.
    //    Nested scope is rejected here, before acquisition.
    _validateFenceShape(externallyMintedFence);

    // 4. Compare authority-bound dimensions (incl. recomputed operation digest).
    _compareAuthorityBoundDimensions(externallyMintedFence, validatedAuthority);

    // 5. Read the live fence and compare EVERY dimension.
    const liveFence = dependencies.readFence();
    _compareEveryDimension(externallyMintedFence, liveFence);

    // 6. Acquire the exact graph reference and privately bind it.  The core does
    //    zero writes against it.
    const graph = dependencies.acquireGraph(app);

    // 7. Capture detached precondition/revision evidence.
    const rawPrecondition = dependencies.capturePrecondition(
      graph,
      validatedAuthority,
      plan,
    );
    const preconditionEvidence = _detachAndFreeze(rawPrecondition, "precondition");

    // 8. Resolve native bindings with zero core writes.  The resolver partitions
    //    its output into privateState (live, private) and detachedEvidence.
    const native = dependencies.resolveNativeBindings({
      app,
      graph,
      validatedAuthority,
      plan,
    });
    _validateResolverOutput(native);
    const nativeDetachedEvidence = _detachAndFreeze(native.detachedEvidence, "detachedEvidence");

    // 9. Build the opaque receipt and store every live object in the WeakMap.
    const receipt = Object.freeze({
      contract_version: INTENT_GRAPH_RECEIPT_CORE_V1,
    });

    // Detached frozen copy of the fence for later fence-currentness comparison.
    const fenceCopy = _detachAndFreeze(externallyMintedFence, "fence");

    _store.set(receipt, {
      validatedAuthority,
      plan,
      fence: fenceCopy,
      graph,
      preconditionEvidence,
      privateState: native.privateState,
      detachedEvidence: nativeDetachedEvidence,
    });

    // 10. Return the frozen opaque receipt plus deeply frozen detached bounded
    //     evidence.  No live object leaves the core.
    const evidence = _deepFreeze({
      contract_version: INTENT_GRAPH_RECEIPT_CORE_V1,
      fence: fenceCopy,
      precondition: preconditionEvidence,
      native: nativeDetachedEvidence,
      authority_receipt: {
        transaction_id: validatedAuthority.transaction_id,
        candidate_id: validatedAuthority.candidate_id,
        plan_hash: validatedAuthority.plan_hash,
        workflow_id: validatedAuthority.workflow_id,
        generation: validatedAuthority.generation,
      },
    });

    return Object.freeze({ receipt, evidence });
  }

  function _assertFenceCurrent(receipt) {
    // Reject forged / cross-instance receipts: only receipts minted by THIS
    // instance are present in THIS instance's WeakMap.
    if (!receipt || typeof receipt !== "object") {
      throw _fail("Receipt is not an opaque receipt", "forged_receipt");
    }
    const entry = _store.get(receipt);
    if (entry === undefined) {
      throw _fail("Receipt is unknown to this instance", "forged_receipt");
    }

    // Reread every live fence field and compare to the stored fence copy.
    const liveFence = dependencies.readFence();
    _compareEveryDimension(entry.fence, liveFence);

    // Reacquire the graph and compare the EXACT reference by identity.
    const graph = dependencies.acquireGraph(app);
    if (graph !== entry.graph) {
      throw _fail("Live graph reference has switched", "graph_switched");
    }

    // Return only detached frozen evidence — never live objects.
    const evidence = _deepFreeze({
      contract_version: INTENT_GRAPH_RECEIPT_CORE_V1,
      fence: entry.fence,
      precondition: entry.preconditionEvidence,
      native: entry.detachedEvidence,
      authority_receipt: {
        transaction_id: entry.validatedAuthority.transaction_id,
        candidate_id: entry.validatedAuthority.candidate_id,
        plan_hash: entry.validatedAuthority.plan_hash,
        workflow_id: entry.validatedAuthority.workflow_id,
        generation: entry.validatedAuthority.generation,
      },
    });
    return Object.freeze({ evidence });
  }

  return Object.freeze({
    preflightPrepared: _preflightPrepared,
    assertFenceCurrent: _assertFenceCurrent,
  });
}
