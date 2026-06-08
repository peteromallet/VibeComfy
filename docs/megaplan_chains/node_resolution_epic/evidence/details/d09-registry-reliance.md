Here's my analysis:

---

## (a) Is the doc accurate on this point?

**Partly.** The doc's Section 3 claim is *surface-level* accurate: `resolve_pack` indeed returns `(slug, version, commit, url)` from `api.comfy.org`. But it elides critical semantics that undermine the doc's own Section 5 vision:

- **No version pinning:** `resolve_pack` reads `latest_version` from the registry (`pack_resolver.py:220`). It always returns whatever the registry considers "latest" at call time. There is zero mechanism to request a specific version. The doc's Section 4.2 correctly identifies "provenance is not used for version resolution" as a gap, but Section 3's table entry implies a capability that doesn't exist — the version returned is *not* the authored workflow version, it's *latest*.

- **Offline works only for previously-seen URLs:** The HTTP cache (`pack_resolver.py:165-178`) is a write-once-forever JSON dump keyed by `sha256(path+query)`. No TTL, no etag revalidation, no staleness check. `allow_remote_lookup=False` (line 83-84) raises `PackNotFoundError` for anything that isn't a local path or git URL. The doc frames this as a yes/no coverage question (Section 7: "Registry coverage") but the bigger problem is **silent staleness**: a cached response from last month says version 1.2.3 when the registry now says 1.2.4.

- **Class→pack ambiguity** is handled correctly on the search fallback path (raises `AmbiguousPackError`, line 130) but not on the exact endpoint path (`/comfy-nodes/{class}/node`, lines 113-118) which trusts the single result unconditionally. A registry data error where two packs claim the same class via that endpoint would not be caught.

- **Private/hand-built packs** are a hard gap. The doc's Section 7 acknowledges this, but the only escape hatch is specifying a local path or git URL directly (lines 75-82) — which bypasses version metadata entirely.

---

## (b) Top 2-3 concrete risks

1. **Silent stale-version poisoning.** The HTTP cache at `~/.cache/vibecomfy/registry` has no expiration. A user who resolves `ComfyUI-KJNodes` today gets version X; next week the registry bumps to Y, but the cache serves X forever. The lockfile captures whatever SHA lands on disk, but the *registry-derived version label* in the lockfile entry (`node_packs_install.py:201`) will be stale/misleading. No reconciliation detects this.

2. **Offline bootstrap failure.** The first run of `resolve_pack("ImageResizeKJv2")` in an air-gapped environment fails even if the pack is already installed locally — the code checks the HTTP cache first (`_get_json`, line 167), and on cache miss it tries `httpx` (line 170), which fails. There's no fallback to introspect locally-installed custom nodes to derive pack identity. The `allow_remote_lookup=False` path doesn't even try.

3. **Version-pinning mismatch between strategy and reality.** Section 5.2 proposes "provenance-driven version resolution" parsing `cnr_id`/`aux_id`/`ver` from the workflow. But `cnr_id` appears *nowhere* in the vibecomfy source code — only in test fixtures and workflow corpus JSON. The registry itself (`/comfy-nodes/{class}/node`) has no endpoint to query a pack *at a specific version*. So even if the code parsed provenance, the registry can't serve the pinned version. The doc's proposal would require a registry API change or GitHub tags API fallback, neither of which exists.

---

## (c) Specific recommendation

**Add a local-first pack resolution path** that checks installed `custom_nodes/<slug>/.git` (reading `origin` remote and HEAD SHA) before falling back to the registry HTTP cache or live API. Wire `allow_remote_lookup=False` through `resolve_pack` to consult installed packs via `git remote get-url origin` + `git rev-parse HEAD` — this gives version-aware offline resolution for any already-installed pack without touching the network. For the cache staleness problem, add a `Cache-Control`-style max-age (default 24h) to `_get_json`, re-fetching when expired but falling back to cache on network failure (stale-while-revalidate). Add a `_cache_metadata.timestamp` field to each cache file.