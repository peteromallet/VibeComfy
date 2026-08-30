# HTTP authorization boundary

VibeComfy's ComfyUI extension is a single-operator service. Its HTTP boundary
is an instance capability with a strict trusted-loopback mode; a session id is
state selection, not caller identity.

## Public and guarded routes

Only these VibeComfy JSON endpoints are public:

- `GET /vibecomfy/ping`
- `GET /vibecomfy/info`

`HEAD` is not public for either route. Runtime registration and namespace
middleware enforce the central method/path inventory; an unclassified alias or
alternate registration fails closed.

Every other `/vibecomfy/*` API route and the legacy `POST /agent/edit` route is
guarded by default. This includes status, session reads, submit/transaction,
roundtrip, rating, credentials, settings, research, demo/replay, and node-pack
installation. VibeComfy does not register a WebSocket or SSE endpoint; its
best-effort progress messages use ComfyUI's separately owned WebSocket.

## Trusted loopback

The normal local browser, managed runtime, and CLI workflows need no operator
secret. A request is trusted-local only when its transport peer is an IPv4 or
IPv6 loopback address and `Host` is `localhost` or a loopback literal with the
actual listening port. Forwarded headers never create local authority.

Browser requests must also be same-origin and non-navigation JSON requests.
Mutations carry a process-scoped CSRF capability obtained from the local-only
`GET /vibecomfy/security/csrf` bootstrap. The shipped panel keeps that value in
module memory only. It is not put in storage, a cookie, a URL, or a log. Local
CLI requests omit browser headers and therefore do not need the CSRF header,
but still need the loopback peer and `Host` invariants.

Custom hostnames, LAN addresses, port-forwarded peers, and DNS-rebound host
names are remote even if they resolve to this machine.

## Explicit remote instances

Remote guarded requests fail with `403` until the operator configures a
generated instance bearer capability. Prefer a private file:

```bash
install -m 600 /dev/null /absolute/private/path/vibecomfy-http-token
python -c 'import secrets; print(secrets.token_urlsafe(32))' \
  > /absolute/private/path/vibecomfy-http-token
export VIBECOMFY_HTTP_BEARER_TOKEN_FILE=/absolute/private/path/vibecomfy-http-token
```

Alternatively, set `VIBECOMFY_HTTP_BEARER_TOKEN` to a generated value of at
least 32 ASCII characters. Do not use a default, a session id, an API-provider
key, or a value derived from workflow data. Configure only one token source.
Requests supply it as:

```text
Authorization: Bearer <instance capability>
```

The comparison is constant-time. The capability is never returned or logged.
Token files must be absolute, regular non-symlink files and, on POSIX, must not
grant group or other permissions.

A remote browser must also have its exact origin listed in the comma-separated
`VIBECOMFY_HTTP_ALLOWED_ORIGINS`, for example:

```bash
export VIBECOMFY_HTTP_ALLOWED_ORIGINS=https://panel.example
```

Wildcards, paths, credentials, queries, and fragments are rejected. This is an
authorization allowlist, not a permissive-CORS switch. Exact-origin CORS
preflight and response headers are emitted only for an inventoried guarded
route with the configured origin and `Authorization` request header.

The shipped browser transport accepts an origin-bound, tab-scoped bearer. Set
the complete configuration atomically in the remote panel tab before using
guarded features:

```js
configureVibeComfyRemoteBearer("<instance capability>", {
  persistForTab: true,
});
```

Remove it with the exported `clearVibeComfyRemoteBearer()` when the tab should
lose access. Persistence uses one versioned record containing the bearer and
its exact API origin, so a reload cannot combine fields from different
configurations. Legacy split-key state is never combined or migrated implicitly;
it must be cleared and configured again. Corrupt or legacy state fails before
any request. The transport sends the bearer only in the `Authorization` header;
it is not put in URLs, responses, local storage, or logs. Omitting
`persistForTab` keeps the complete configuration in memory only.
Bearer injection is bound to the panel's exact origin by default. A panel that
deliberately uses a separate API origin must bind it explicitly:

```js
configureVibeComfyRemoteBearer("<instance capability>", {
  apiOrigin: "https://api.example",
});
```

API-origin text is validated before browser URL canonicalization. It must be an
exact `http://` or `https://` origin with an ASCII hostname (Unicode IDNs must
be supplied in punycode), canonical dotted IPv4, or bracketed IPv6 host and an
optional port from 1 through 65535. Controls, whitespace, credentials,
backslashes, empty ports, paths other than `/`, dot segments, queries, and
fragments are rejected before credentials are constructed.

Foreign absolute targets are rejected before the browser performs a fetch.
The guarded client accepts only primitive URL strings and same-realm WHATWG
`URL` objects. It resolves one target and executes that exact resolved string.
`Request` objects and arbitrary/request-like objects are rejected rather than
merging hidden URL, header, body, credential, or redirect semantics.
The CSRF bootstrap and every guarded request force redirect rejection after
caller options are merged. A redirect therefore fails at the validated origin
without forwarding a bearer, CSRF capability, or request body to another hop.
The server never discloses its configured bearer or offers a remote bootstrap.

## Reverse proxies

Forwarded headers are rejected unless the direct transport peer is an exact IP
literal in `VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS`. A trusted proxy peer is always
treated as remote and still needs the instance bearer; forwarded client/host/
scheme values are not used as authority. The proxy must strip any inbound
`Authorization` value before injecting the configured bearer. VibeComfy does
not currently support an alternate proxy-auth header.

Example for a loopback reverse proxy:

```bash
export VIBECOMFY_HTTP_TRUSTED_PROXY_PEERS=127.0.0.1,::1
export VIBECOMFY_HTTP_ALLOWED_ORIGINS=https://panel.example
```

## Binding and launch behavior

The local helper does not enable wildcard CORS. The RunPod setup may still
bind ComfyUI to `0.0.0.0`, but all guarded VibeComfy routes remain closed to a
non-loopback peer until an instance bearer is configured. Direct public binding
without that authority is unsupported.

Embedded execution does not cross this HTTP boundary and is unchanged.
