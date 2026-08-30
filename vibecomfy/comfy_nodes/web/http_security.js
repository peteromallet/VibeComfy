// Origin-bound browser client for VibeComfy's guarded JSON API.
//
// The CSRF capability lives only in this module's process memory. It is fetched
// from a local-only bootstrap and is never persisted in localStorage,
// sessionStorage, a cookie, a URL, or a log.

export const CSRF_BOOTSTRAP_PATH = "/vibecomfy/security/csrf";
export const CSRF_HEADER = "X-VibeComfy-CSRF";
export const REMOTE_AUTHORIZATION_SESSION_KEY = "vibecomfy_http_authorization_v1";
// Legacy split keys are read only to reject an unsafe pre-v1 binding.
export const REMOTE_BEARER_SESSION_KEY = "vibecomfy_http_bearer";
export const REMOTE_API_ORIGIN_SESSION_KEY = "vibecomfy_http_api_origin";

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const NATIVE_URL = typeof globalThis.URL === "function" ? globalThis.URL : null;
const URL_HREF_GETTER = NATIVE_URL?.prototype
  ? Object.getOwnPropertyDescriptor(NATIVE_URL.prototype, "href")?.get
  : null;
let csrfCapabilityPromise = null;
let remoteAuthorizationConfig = null;

function validateRemoteBearer(value) {
  if (
    typeof value !== "string"
    || value.length < 32
    || value !== value.trim()
    || !/^[A-Za-z0-9._~+/=-]+$/.test(value)
  ) {
    throw new Error("VibeComfy remote authorization is not configured safely.");
  }
  return value;
}

function parseRawRemoteApiOrigin(value) {
  if (
    typeof value !== "string"
    || !value
    || value !== value.trim()
    || /[\x00-\x20\x7f]/.test(value)
    || value.includes("\\")
  ) {
    throw new Error("VibeComfy remote API origin is not configured safely.");
  }
  const match = /^(https?):\/\/([^/?#]*)(\/?)$/i.exec(value);
  if (!match) {
    throw new Error("VibeComfy remote API origin is not configured safely.");
  }
  const authority = match[2];
  if (!authority || authority.includes("@") || authority.includes("%")) {
    throw new Error("VibeComfy remote API origin is not configured safely.");
  }

  let rawHost;
  let rawPort = null;
  let isIpv6 = false;
  if (authority.startsWith("[")) {
    const closingBracket = authority.indexOf("]");
    if (closingBracket <= 1 || authority.indexOf("[", 1) !== -1) {
      throw new Error("VibeComfy remote API origin is not configured safely.");
    }
    rawHost = authority.slice(1, closingBracket);
    const suffix = authority.slice(closingBracket + 1);
    if (suffix) {
      if (!suffix.startsWith(":") || suffix.length === 1) {
        throw new Error("VibeComfy remote API origin is not configured safely.");
      }
      rawPort = suffix.slice(1);
    }
    isIpv6 = true;
  } else {
    const firstColon = authority.indexOf(":");
    const lastColon = authority.lastIndexOf(":");
    if (firstColon !== lastColon) {
      throw new Error("VibeComfy remote API origin is not configured safely.");
    }
    if (lastColon !== -1) {
      rawHost = authority.slice(0, lastColon);
      rawPort = authority.slice(lastColon + 1);
      if (!rawPort) {
        throw new Error("VibeComfy remote API origin is not configured safely.");
      }
    } else {
      rawHost = authority;
    }
  }
  if (!rawHost || rawHost.includes("[") || rawHost.includes("]")) {
    throw new Error("VibeComfy remote API origin is not configured safely.");
  }
  if (rawPort !== null) {
    if (!/^\d+$/.test(rawPort)) {
      throw new Error("VibeComfy remote API origin is not configured safely.");
    }
    const numericPort = Number(rawPort);
    if (!Number.isSafeInteger(numericPort) || numericPort < 1 || numericPort > 65535) {
      throw new Error("VibeComfy remote API origin is not configured safely.");
    }
  }
  if (!isIpv6) {
    if (/^[0-9.]+$/.test(rawHost)) {
      const octets = rawHost.split(".");
      if (
        octets.length !== 4
        || octets.some((octet) => (
          !/^\d+$/.test(octet)
          || String(Number(octet)) !== octet
          || Number(octet) > 255
        ))
      ) {
        throw new Error("VibeComfy remote API origin is not configured safely.");
      }
    } else {
      const hostname = rawHost.endsWith(".") ? rawHost.slice(0, -1) : rawHost;
      const labels = hostname.split(".");
      if (
        !hostname
        || rawHost.length > 254
        || labels.some((label) => (
          label.length < 1
          || label.length > 63
          || !/^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$/.test(label)
        ))
      ) {
        throw new Error("VibeComfy remote API origin is not configured safely.");
      }
    }
  }
  return { isIpv6, rawHost };
}

function normalizeRemoteApiOrigin(value) {
  const raw = parseRawRemoteApiOrigin(value);
  let parsed;
  try {
    parsed = new NATIVE_URL(value);
  } catch (_error) {
    throw new Error("VibeComfy remote API origin is not configured safely.");
  }
  if (
    !["http:", "https:"].includes(parsed.protocol)
    || parsed.username
    || parsed.password
    || parsed.pathname !== "/"
    || parsed.search
    || parsed.hash
    || parsed.port === "0"
    || (!raw.isIpv6 && parsed.hostname.toLowerCase() !== raw.rawHost.toLowerCase())
  ) {
    throw new Error("VibeComfy remote API origin is not configured safely.");
  }
  return parsed.origin;
}

function currentPageOrigin() {
  const origin = globalThis.location?.origin;
  if (!origin || origin === "null") return null;
  try {
    return normalizeRemoteApiOrigin(origin);
  } catch (_error) {
    return null;
  }
}

function serializeRemoteAuthorizationConfig(config) {
  return JSON.stringify({
    version: 1,
    api_origin: config.apiOrigin,
    bearer: config.bearer,
  });
}

function parseRemoteAuthorizationRecord(serialized) {
  let record;
  try {
    record = JSON.parse(serialized);
  } catch (_error) {
    throw new Error("VibeComfy persisted remote authorization is corrupt.");
  }
  if (
    !record
    || typeof record !== "object"
    || Array.isArray(record)
    || record.version !== 1
    || Object.keys(record).length !== 3
    || !("api_origin" in record)
    || !("bearer" in record)
  ) {
    throw new Error("VibeComfy persisted remote authorization is corrupt.");
  }
  return Object.freeze({
    apiOrigin: normalizeRemoteApiOrigin(record.api_origin),
    bearer: validateRemoteBearer(record.bearer),
  });
}

function readRemoteAuthorizationConfig() {
  if (remoteAuthorizationConfig) return remoteAuthorizationConfig;
  const storage = globalThis.sessionStorage;
  if (!storage) return null;
  let serialized;
  try {
    serialized = storage.getItem(REMOTE_AUTHORIZATION_SESSION_KEY);
  } catch (_error) {
    return null;
  }
  if (serialized !== null) {
    return parseRemoteAuthorizationRecord(serialized);
  }

  let storedBearer;
  let storedApiOrigin;
  try {
    storedBearer = storage.getItem(REMOTE_BEARER_SESSION_KEY);
  } catch (_error) {
    return null;
  }
  try {
    storedApiOrigin = storage.getItem(REMOTE_API_ORIGIN_SESSION_KEY);
  } catch (_error) {
    if (storedBearer === null) return null;
    throw new Error("VibeComfy persisted remote authorization could not be read safely.");
  }
  if (storedBearer === null && storedApiOrigin === null) return null;
  throw new Error(
    "VibeComfy legacy remote authorization must be cleared and reconfigured.",
  );
}

function isLoopbackHostname(hostname) {
  const normalized = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  if (normalized === "localhost" || normalized === "::1") return true;
  const octets = normalized.split(".");
  return octets.length === 4
    && octets.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)
    && Number(octets[0]) === 127;
}

function readSupportedRequestTarget(input) {
  if (typeof input === "string") {
    return Object.freeze({ text: input, type: "string" });
  }
  if (
    NATIVE_URL
    && input instanceof NATIVE_URL
    && typeof URL_HREF_GETTER === "function"
  ) {
    try {
      return Object.freeze({
        text: URL_HREF_GETTER.call(input),
        type: "url",
      });
    } catch (_error) {
      // Reject forged URL prototypes and proxies without invoking caller coercion.
    }
  }
  throw new Error("VibeComfy request input type is not supported.");
}

function resolveRequestTarget(target, base) {
  if (!NATIVE_URL) {
    throw new Error("VibeComfy request URL is invalid.");
  }
  try {
    return new NATIVE_URL(target.text, base);
  } catch (_error) {
    throw new Error("VibeComfy request URL is invalid.");
  }
}

export function configureVibeComfyRemoteBearer(
  value,
  { persistForTab = false, apiOrigin = currentPageOrigin() } = {},
) {
  const config = Object.freeze({
    bearer: validateRemoteBearer(value),
    apiOrigin: normalizeRemoteApiOrigin(apiOrigin),
  });
  if (persistForTab) {
    const storage = globalThis.sessionStorage;
    if (!storage) {
      throw new Error("VibeComfy remote authorization could not be stored for this tab.");
    }
    try {
      storage.setItem(
        REMOTE_AUTHORIZATION_SESSION_KEY,
        serializeRemoteAuthorizationConfig(config),
      );
    } catch (_error) {
      throw new Error("VibeComfy remote authorization could not be stored for this tab.");
    }
    for (const legacyKey of [
      REMOTE_BEARER_SESSION_KEY,
      REMOTE_API_ORIGIN_SESSION_KEY,
    ]) {
      try {
        storage.removeItem(legacyKey);
      } catch (_error) {
        // The complete v1 record is authoritative; legacy remnants are ignored.
      }
    }
  }
  remoteAuthorizationConfig = config;
}

export function clearVibeComfyRemoteBearer() {
  remoteAuthorizationConfig = null;
  const storage = globalThis.sessionStorage;
  if (!storage) return;
  try {
    storage.removeItem(REMOTE_BEARER_SESSION_KEY);
    storage.removeItem(REMOTE_API_ORIGIN_SESSION_KEY);
    storage.removeItem(REMOTE_AUTHORIZATION_SESSION_KEY);
  } catch (_error) {
    throw new Error("VibeComfy remote authorization could not be cleared safely.");
  }
}

function copyHeaders(value) {
  if (!value) return {};
  if (Array.isArray(value)) return Object.fromEntries(value);
  if (typeof value.entries === "function") return Object.fromEntries(value.entries());
  return { ...value };
}

function setHeader(headers, name, value) {
  const lowerName = name.toLowerCase();
  for (const existing of Object.keys(headers)) {
    if (existing.toLowerCase() === lowerName) delete headers[existing];
  }
  headers[name] = value;
}

async function fetchLocalCsrfCapability() {
  const response = await fetch(CSRF_BOOTSTRAP_PATH, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    redirect: "error",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`VibeComfy local authorization bootstrap failed (${response.status})`);
  }
  const payload = await response.json();
  if (
    payload?.csrf_header !== CSRF_HEADER
    || typeof payload?.csrf_token !== "string"
    || payload.csrf_token.length < 32
  ) {
    throw new Error("VibeComfy local authorization bootstrap returned an invalid capability");
  }
  return payload.csrf_token;
}

export async function getLocalCsrfCapability() {
  if (!csrfCapabilityPromise) {
    csrfCapabilityPromise = fetchLocalCsrfCapability().catch((error) => {
      csrfCapabilityPromise = null;
      throw error;
    });
  }
  return csrfCapabilityPromise;
}

export async function vibecomfyFetch(input, init = {}) {
  const requestTarget = readSupportedRequestTarget(input);
  const method = String(init.method || "GET").toUpperCase();
  const options = {
    ...init,
    method,
    redirect: "error",
  };
  const headers = copyHeaders(init.headers);
  const remoteConfig = readRemoteAuthorizationConfig();
  let executionTarget;
  if (remoteConfig) {
    const target = resolveRequestTarget(
      requestTarget,
      `${remoteConfig.apiOrigin}/`,
    );
    if (target.origin !== remoteConfig.apiOrigin) {
      throw new Error("VibeComfy request target is not the configured API origin.");
    }
    executionTarget = target.href;
    options.credentials = "omit";
    setHeader(headers, "Authorization", `Bearer ${remoteConfig.bearer}`);
  } else {
    const location = globalThis.location;
    if (!location?.href || !location?.hostname) {
      if (
        requestTarget.type !== "string"
        || /^[A-Za-z][A-Za-z0-9+.-]*:/.test(requestTarget.text)
        || requestTarget.text.startsWith("//")
      ) {
        throw new Error("VibeComfy remote authorization is not configured for this tab.");
      }
      executionTarget = requestTarget.text;
    } else {
      const target = resolveRequestTarget(requestTarget, location.href);
      if (
        target.origin !== location.origin
        || !isLoopbackHostname(location.hostname)
      ) {
        throw new Error("VibeComfy remote authorization is not configured for this tab.");
      }
      executionTarget = target.href;
    }
    options.credentials = init.credentials || "same-origin";
    if (MUTATING_METHODS.has(method)) {
      setHeader(headers, CSRF_HEADER, await getLocalCsrfCapability());
    }
  }
  if (Object.keys(headers).length > 0) {
    options.headers = headers;
  }
  return fetch(executionTarget, options);
}

export function _resetCsrfCapabilityForTests() {
  csrfCapabilityPromise = null;
  remoteAuthorizationConfig = null;
}
