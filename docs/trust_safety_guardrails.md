# Trust & Safety — Deferred Security Guardrails

**Status:** Documented (deferred beyond sprint `trust-and-safety-outcome-make-20260709-1840`).

This sprint closes the **dynamic runtime-code validation and confirmation gate**
bypass (Steps 7–9 of the plan). The unrestricted worker environment already
strips common LLM/cloud credentials and broad sensitive suffixes via
`_build_unrestricted_worker_env` in `runtime_code.py`.  Several guardrail
improvements remain out of scope and are documented below for follow-up.

---

## 1. Infrastructure prefix env gaps

The current `_UNRESTRICTED_ENV_BLOCK_PREFIXES` tuple covers LLM-provider and
major-cloud prefixes (`ANTHROPIC_`, `AWS_`, `AZURE_`, `GCP_`, `OPENAI_`, …).
The following infrastructure‑class prefixes are **not** blocklisted and would
pass through to an unrestricted-mode worker:

| Missing prefix | Example env vars leaked |
|---|---|
| `KUBERNETES_` | `KUBERNETES_SERVICE_HOST`, `KUBERNETES_SERVICE_PORT` (service‑account tokens, API server addresses) |
| `VAULT_` | `VAULT_TOKEN`, `VAULT_ADDR`, `VAULT_CACERT` |
| `CONSUL_` | `CONSUL_HTTP_TOKEN`, `CONSUL_HTTP_ADDR` |
| `NOMAD_` | `NOMAD_TOKEN`, `NOMAD_ADDR` |
| `DOCKER_` | `DOCKER_HOST`, `DOCKER_CONFIG`, `DOCKER_CONTEXT` |
| `RABBITMQ_` | `RABBITMQ_DEFAULT_PASS`, `RABBITMQ_ERLANG_COOKIE` |
| `REDIS_` | `REDIS_PASSWORD`, `REDIS_URL` |
| `MONGODB_` | `MONGODB_URI`, `MONGODB_USERNAME`, `MONGO_INITDB_ROOT_PASSWORD` |
| `SENTRY_` | `SENTRY_DSN`, `SENTRY_AUTH_TOKEN` |
| `ELASTIC_` | `ELASTICSEARCH_PASSWORD`, `ELASTIC_APM_SECRET_TOKEN` |
| `DD_` / `DATADOG_` | `DD_API_KEY`, `DATADOG_API_KEY` |
| `CLOUDFLARE_` | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ZONE_ID` |
| `HASHICORP_` | `HASHICORP_TOKEN` (already partially covered by `VAULT_`/`CONSUL_`/`NOMAD_`) |
| `TRAVIS_` / `CIRCLECI_` / `GITLAB_` / `GITHUB_` | CI‑provider tokens (`GITHUB_TOKEN`, `GITLAB_ACCESS_TOKEN`, `CIRCLE_TOKEN`) |
| `JENKINS_` | `JENKINS_URL`, `JENKINS_USER`, `JENKINS_API_TOKEN` |
| `STRIPE_` | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` |
| `TWILIO_` | `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` |
| `SENDGRID_` | `SENDGRID_API_KEY` |

**How to close:** Add the missing prefixes to `_UNRESTRICTED_ENV_BLOCK_PREFIXES`
in `runtime_code.py`.  A future sprint should also consider a
configuration‑driven extension point so operators can add infrastructure‑specific
prefixes without editing the source.

---

## 2. Broad `_KEY` / `_CREDENTIALS` suffixes

The existing `_UNRESTRICTED_ENV_BLOCK_SUFFIXES` tuple covers `_API_KEY`,
`_SECRET_KEY`, `_TOKEN`, `_PASSWORD`, `_PRIVATE_KEY`, and several others.
Two suffix families are notably absent:

| Missing suffix | Example env vars that would pass through |
|---|---|
| `_KEY` (bare) | `STRIPE_PUBLISHABLE_KEY`, `ENCRYPTION_KEY`, `SERVICE_ACCOUNT_KEY` |
| `_CREDENTIALS` | `GOOGLE_APPLICATION_DEFAULT_CREDENTIALS`, `SERVICE_ACCOUNT_CREDENTIALS`, `FIREBASE_CREDENTIALS` |

While many `_KEY` variables are already caught by existing prefixes
(e.g. `OPENAI_API_KEY` matches `OPENAI_` prefix), env vars with
non‑provider‑specific names such as `ENCRYPTION_KEY`, `MASTER_KEY`,
`SERVICE_KEY`, or `WRITE_KEY` are not blocked by any prefix or suffix.

**How to close:** Add `_KEY` and `_CREDENTIALS` to
`_UNRESTRICTED_ENV_BLOCK_SUFFIXES`.  Note that `_KEY` is a very short suffix
and may create false positives for env vars like `ATTORNEY_CLIENT_PRIVILEGE_KEY`
or `MONKEY` — a minimum‑length guard or a curated exception list should
accompany this change.

---

## 3. Token value-pattern redaction

The current env blocklist operates exclusively on **key names** (case‑insensitive
normalization of the env variable name).  It does **not** inspect env‑var
**values** for credential-like patterns.  A key whose name matches none of the
prefixes or suffixes but whose value is a credential would pass through
unredacted.

Examples of value patterns that are not detected:

| Pattern | Example value | Typical env‑var name |
|---|---|---|
| JWT / Bearer token | `eyJhbGciOiJIUzI1NiIs…` (base64url‑encoded JSON) | `SESSION_TOKEN`, `ACCESS_TOKEN` (already blocked by `_TOKEN` suffix — but a similarly named var without the suffix is not) |
| PEM‑encoded key | `-----BEGIN RSA PRIVATE KEY-----\\n...` | `SSH_PRIVATE_KEY`, `CERTIFICATE` |
| Base64‑encoded credential | `Z3JvdG9AZXhhbXBsZS5jb206c2VjcmV0` | `AUTH_HEADER`, `CONNECTION_STRING` |
| OAuth2 refresh token | `ya29.a0AfH6SMC…` | `GCP_REFRESH_TOKEN` (already caught by `GCP_` prefix in this case) |

**How to close:** Add value‑pattern scanning to `_is_sensitive_unrestricted_env_key`
(or a new helper called after key‑name checking).  Scan each env‑var value for:

- The JWT header prefix `eyJ` (case‑insensitive start of base64url).
- PEM armor boundaries (`-----BEGIN`).
- High‑entropy base64 strings beyond a minimum length threshold.
- Known OAuth token prefixes (`ya29.`, `ghp_`, `gho_`, `sb_`, `xoxb-`, `xoxp-`).

Value scanning adds CPU overhead proportional to the number of env vars and
should be gated behind a flag or applied only in unrestricted mode.

---

## 4. DOM overlay chip e2e coverage

This sprint adds a **Canvas2D clipped‑text assertion** in
`tests/e2e/specs/agent_panel_overlay.spec.mjs` (Step 5) and confirms the
existing `fitTextToWidth` renderer in `panel_overlay.js` correctly fits text
within the panel (Step 6 skipped with evidence).

A **DOM‑based preview overlay chip** was previously removed in favour of the
Canvas2D renderer.  The static ownership test
(`preview_overlay_ownership_static.test.mjs`) forbids reintroducing DOM‑chip
preview rendering, but there is **no end‑to‑end coverage** for the DOM chip
path because the chip no longer exists in the codebase.

**Follow‑up:** If a future sprint reintroduces a DOM overlay chip (e.g. for
accessibility, tooltip integration, or electron‑shell embedding), the e2e suite
should be extended with:

- A Playwright test that verifies the chip appears at the correct coordinates.
- A test that verifies chip text does not overflow the chip bounds.
- A test that verifies chip text is redacted/hidden when the node contains
  sensitive values.

---

## Summary of deferred items

| # | Gap | Current protection | Follow‑up action |
|---|---|---|---|
| 1 | Infrastructure prefix env gaps | None for `KUBERNETES_`, `VAULT_`, `DOCKER_`, `REDIS_`, `STRIPE_`, CI‑provider prefixes, etc. | Add prefixes to `_UNRESTRICTED_ENV_BLOCK_PREFIXES` + configurable extension point |
| 2 | Broad `_KEY` / `_CREDENTIALS` suffixes | Only `_API_KEY`, `_SECRET_KEY`, `_PRIVATE_KEY` — but not bare `_KEY` or `_CREDENTIALS` | Add suffixes with minimum‑length guard |
| 3 | Token value‑pattern redaction | Key‑name based only — value patterns (JWT, PEM, base64, OAuth tokens) not inspected | Add value‑pattern scanning gated by mode |
| 4 | DOM overlay chip e2e coverage | Static ownership test forbids reintroduction; no e2e for chip path | Add Playwright tests if DOM chip is reintroduced |

**Why deferred this sprint:** The critical security bypass this sprint closes is
the **dynamic code scanning/confirmation gap** (Steps 7–9) — runtime code from
untrusted provenance can no longer execute without passing through
`validate_runtime_code_contract` and `require_confirmation`.  The unrestricted
worker env already strips common LLM/cloud secrets (`ANTHROPIC_`, `OPENAI_`,
`AWS_`, `AZURE_`, `GCP_`, …) and broad sensitive suffixes (`_API_KEY`,
`_SECRET`, `_TOKEN`, `_PASSWORD`, …).  The remaining gaps are env‑blocklist
completeness and value‑pattern redaction — important hardening that can be
addressed in a follow‑up without reopening the dynamic‑code bypass.

---

## Corrective trust-gate validation (2026-07-10)

Final independent validation did not earn a pass. The dedicated
`corrective-trust-gate` target, locked inventory, driver, and unified manifest
are absent from this checkout. The separate Corrective 2 run collected 402
tests and kept 11 failures explicit and outside quarantine (391 passed); their
exact node IDs and the command are recorded in
`research/corrective-verification-evidence-2026-07-10.md`.

The three retained real-browser runs had valid non-skipped geometry evidence,
but their native Playwright JSON contained absolute workspace paths. Also,
`make check` stopped at `root-clean` because a generated `vendor/ComfyUI` root
remained. `make clean`, explicit generated-root removal, and
`make post-root-clean` ultimately left only the intentional implementation and
evidence edits.

Before claiming acceptance, add the missing gate surface, sanitize native
Playwright artifacts, make generated ComfyUI cleanup certain, and rerun both
the canonical gate and the independent Corrective 2 command. Missing ComfyUI
or Chromium prerequisites must continue to fail with launcher remediation,
never become skips.
