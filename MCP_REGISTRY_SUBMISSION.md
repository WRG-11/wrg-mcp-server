# MCP Registry submission package — `wrg_mcp_server`

> **Status (2026-05-13): HISTORICAL — superseded by account migration.**
>
> **Audit refresh 2026-05-21 (R88-52g)**: see [`docs/decisions/mcp_registry_submission_audit_2026_05_21.md`](../../docs/decisions/mcp_registry_submission_audit_2026_05_21.md) for live state verdict (**NOT-READY**, 4× P0 + 4× P1 blockers; G recommends Path C Hybrid ~1h polish; A operator final). Note revisions to in-doc claims: (a) "submission probably never completed" is outdated — Registry entry `io.github.yakuphanycl/wrg-mcp-server` v1.0.0 IS active (orphaned namespace, public repo URL 404); (b) §3 "first-mover advantage" framing requires retraction — 6-7 active threat-intel niş entries; WRG positioning is **defansif-discipline-rigorous outlier + local-first + monorepo-bridge**, not first-mover.
>
> **PyPI live state** (verified 2026-05-13 via `pypi.org/pypi/wrg-mcp-server/json`):
> - Package `wrg-mcp-server` published, versions: `1.0.0`, `1.0.2` (1.0.1 skipped)
> - Author email: canonical `yakuphan.yucel11@gmail.com` ✓
> - All Project URLs point to `github.com/yakuphanycl/WinstonRedGuard` → **404** (account blocked 2026-04-27 per `memory/incident_github_suspension_2026_04_27.md`)
> - Anyone running `pip install wrg-mcp-server` today hits dead doc/repo/issues links
>
> **MCP Registry state**: `io.github.yakuphanycl/wrg-mcp-server` returns **404** at Registry — submission probably never completed (only PyPI publish landed) or entry was purged.
>
> **Why this doc is frozen**:
> - All in-doc references to `yakuphanycl` GitHub URLs + `io.github.yakuphanycl/...` namespace match the live PyPI v1.0.2 metadata. Editing in place would create skew between this spec and the actually-published artifacts.
> - `server.json` and the `<!-- mcp-name: io.github.yakuphanycl/wrg-mcp-server -->` marker in `apps/wrg_mcp_server/README.md` line 1 are deliberately **not changed** — they form a self-consistent record of the v1.0.2 publish.
>
> **Migration plan** (R44+ candidate, not yet scoped):
> 1. PyPI re-publish: pyproject.toml URLs → `github.com/WRG-11/WinstonRedGuard/...`, version bump to `1.0.3`
> 2. Decide: new MCP Registry namespace `io.github.WRG-11/wrg-mcp-server` requires fresh GitHub OAuth + new `server.json` namespace + new README marker — effectively a new Registry entry (the old namespace stays orphaned because the auth chain is broken)
> 3. Trade-off vs. abandon: Registry presence has low organic traffic value while WRG-11 account is fresh; deferring is reasonable. Memory: `feedback_anti_ban_hardening.md` + `references_external.md` for namespace-rename precedent.
>
> **Author of original doc**: automation (Agent B, 2026-04-24). Research based on MCP Registry docs at 2026-04-24.

---

---

## 1. Server identity

| Field | Value | Notes |
|-------|-------|-------|
| **Registry name** | `io.github.yakuphanycl/wrg-mcp-server` | Reverse-DNS; the `io.github.<user>/` prefix is required by the Registry's GitHub-namespace verification ([quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx)). The `<user>` must match the authenticating GitHub account. |
| **Title** | WinstonRedGuard MCP Server | Human-readable display name. |
| **Version** | `1.0.0` | Matches `pyproject.toml:version`. Must bump in both files every release. |
| **PyPI package** | `wrg-mcp-server` (hyphens) | PyPI normalises the pyproject `wrg_mcp_server` underscore form to this hyphenated canonical identifier. |
| **GitHub repo** | `yakuphanycl/WinstonRedGuard` | Subfolder: `apps/wrg_mcp_server`. |
| **License** | MIT | Root `LICENSE` applies monorepo-wide; `pyproject.toml:license = "MIT"`. |

### Name alternatives considered

The task brief suggested `winstonredguard` or `wrg` as candidate short names. Recommendation: **stick with `wrg-mcp-server`** because:

- Matches the PyPI package name exactly → the mcp-name ↔ PyPI ↔ `server.json` chain is unambiguous.
- Matches the Python entry point (`wrg-mcp-server` in `[project.scripts]`).
- "wrg" alone is cryptic; "winstonredguard" duplicates the brand without adding purpose; "wrg-mcp-server" communicates exactly what the artefact is.

The short alias `"wrg"` already lives in maintainers' Claude Desktop `mcpServers` config — that's a **client-side key** and is independent of the Registry name. No conflict.

---

## 2. Description

**One-liner** (`description` field, ≤160 chars):

> Exposes the WinstonRedGuard monorepo (governance checks, pipeline runs, memory, OSINT research, release gate) to Claude and other MCP-compatible AI agents via ~30 local + remote tools.

**One paragraph** (for `websiteUrl`-linked README / Registry card):

> `wrg-mcp-server` is the bridge between an AI agent and the WinstonRedGuard Python monorepo. It ships ~20 local tools backed by subprocess calls into each active WRG app (governance check, release-gate runner, memory key-value store, research motor scans, pipeline orchestrator, vault audit, scheduler introspection, app registry queries) plus ~8 optional remote tools that hit a hosted PulseBoard dashboard or a company-site API over HTTP. It uses FastMCP, supports stdio / streamable-http / sse transports, runs a read-only-by-default mutation gate, and requires no auth for the local tool surface.

---

## 3. Categorisation

The MCP Registry doesn't enforce a fixed taxonomy in the v0.1 schema, but community listings group servers by capability. Propose these tags (for directory / search UX):

- **developer-tools** — primary; this exposes a developer's monorepo to an AI agent.
- **productivity** — secondary; memory + pipeline + scheduler tools are workflow-automation primitives.
- **devops** — tertiary; release-gate and governance checks are CI-adjacent.

No single tag goes in the schema itself. If the Registry adds a taxonomy field in a future version, update this list.

---

## 4. Use cases (concrete, tool-derived)

Every use case below maps to real tools already registered in `src/wrg_mcp_server/local_tools.py`. Not aspirational.

1. **"Which of my apps is failing the governance check?"**
   → `app_list` + `governance_run` (one-shot or per-app). Agent picks a failing app and proposes fixes.

2. **"Run the release gate on `pulseboard` and tell me if it passes."**
   → `release_check(app="pulseboard")`. Returns the test pass/fail summary.

3. **"Search my WRG memory for anything about OAuth rate limits."**
   → `memory_search(query="oauth rate limit")` → `memory_get(key=...)` on promising hits.

4. **"What OSINT signals did `research_motor` pull from arXiv in the last 24h?"**
   → `research_history(source="arxiv", since="24h")` + `research_report(run_id=...)`.

5. **"Show me which pipelines exist and dry-run the one named `security_intel_monitor`."**
   → `pipeline_list()` → `pipeline_show(name="security_intel_monitor")` → `pipeline_run(name=..., dry_run=True)` (requires `WRG_MCP_ALLOW_MUTATIONS=1`).

6. **"Is my PulseBoard deployment healthy? Add `yakuphanycl/WinstonRedGuard` to it."** *(remote tools)*
   → `pulseboard_health()` → `pulseboard_add_repo(owner="yakuphanycl", name="WinstonRedGuard")`. Requires `[remote]` extra + `WRG_PULSEBOARD_BASE_URL`.

---

## 5. Auth model

**Local tools**: **no authentication.** They execute as subprocess calls on the same machine where the MCP server runs. The security boundary is the MCP client (Claude Desktop / Code) talking to a locally-installed server.

**Mutation gate**: off by default. Tools that change state (`memory_set`, `pipeline_run`) refuse to execute unless `WRG_MCP_ALLOW_MUTATIONS=1` is set. Documented in README §Environment. This is a client-configuration concern, not an OAuth flow.

**Remote tools**: **bearer-token.** Each remote service (`SITE`, `PULSEBOARD`) takes its own `WRG_<SERVICE>_TOKEN` env var. Set once in the MCP client config; the server forwards it as `Authorization: Bearer <token>` on every remote call. No OAuth, no refresh — the token is the credential.

---

## 6. Transport recommendation

For Registry discoverability the primary transport is **stdio** (matches 95% of MCP Desktop/Code integrations):

```json
"transport": {
  "type": "stdio"
}
```

The server also supports `streamable-http` (recommended when self-hosting for a team) and `sse` (legacy; retained for clients that haven't migrated). Only `stdio` goes in the Registry `server.json` because there's no canonical hosted URL — deployers set up streamable-http themselves with their own TLS + auth. A `remotes` entry would misrepresent this as a shared public endpoint.

---

## 7. Install snippet (post-PyPI)

**Until the package is on PyPI, the canonical install is a source build:**

```bash
pipx install git+https://github.com/yakuphanycl/WinstonRedGuard.git#subdirectory=apps/wrg_mcp_server
```

…or from a local checkout:

```bash
cd apps/wrg_mcp_server
pip install -e .             # core only
pip install -e ".[remote]"   # adds httpx for site_* / pulseboard_* tools
```

**After PyPI publish** (the step the maintainer must still run):

```bash
pipx install wrg-mcp-server
# or
pip install wrg-mcp-server[remote]
```

Claude Desktop / Code config:

```json
{
  "mcpServers": {
    "wrg": {
      "command": "wrg-mcp-server",
      "args": ["--transport", "stdio"],
      "env": {
        "WRG_REPO_ROOT": "/absolute/path/to/WinstonRedGuard",
        "WRG_MCP_ALLOW_MUTATIONS": "0"
      }
    }
  }
}
```

---

## 8. Maintainer + contact

| Field | Value |
|-------|-------|
| Maintainer (GitHub) | [yakuphanycl](https://github.com/yakuphanycl) |
| Repo | https://github.com/yakuphanycl/WinstonRedGuard |
| Issues | https://github.com/yakuphanycl/WinstonRedGuard/issues |
| License | [MIT](https://github.com/yakuphanycl/WinstonRedGuard/blob/main/LICENSE) |

---

## 9. Submission checklist — what the Registry requires vs what's ready

Cross-referenced against the [Registry quickstart](https://github.com/modelcontextprotocol/registry/blob/main/docs/modelcontextprotocol-io/quickstart.mdx) and the [PyPI validation rules](https://modelcontextprotocol.info/tools/registry/publishing/).

### Ready in this PR
- [x] **Namespace marker in README** — `<!-- mcp-name: io.github.yakuphanycl/wrg-mcp-server -->` at line 1 of `apps/wrg_mcp_server/README.md`. The Registry fetches PyPI's README JSON and requires this string to match `server.json.name`.
- [x] **`server.json` drafted** — follows the `2025-12-11` schema. Packages array set up for PyPI; environment variables documented with `isSecret` flags; stdio transport declared.
- [x] **`description` ≤160 chars** — §2 one-liner.
- [x] **Repository URL + subfolder** — recorded in `server.json.repository`.
- [x] **Version in sync** — `pyproject.toml:version = "1.0.0"` ↔ `server.json.version = "1.0.0"` ↔ the eventual PyPI release.
- [x] **License declared** — `pyproject.toml` + root `LICENSE`.

### Not ready — maintainer must run these manually

1. **Publish to PyPI.** The Registry's PyPI validator will `GET https://pypi.org/pypi/wrg-mcp-server/json` and check the README contains `mcp-name: io.github.yakuphanycl/wrg-mcp-server`. Without a PyPI release, submission will fail validation.
   - Preferred: use the same `wrg-devguard`-style OIDC trusted-publishing flow already working elsewhere in this monorepo (see `project_wrg_devguard_release_chain.md`). Add a `.github/workflows/publish-wrg-mcp-server.yml` that triggers on `workflow_dispatch` and `release` events.
   - First-time publishing also requires claiming the `wrg-mcp-server` PyPI project name. If squatted, fall back to a namespaced alternative like `winstonredguard-mcp-server` (and update `server.json.packages[0].identifier` + the README marker to match).

2. **Install `mcp-publisher` CLI.**
   ```bash
   brew install mcp-publisher       # macOS; on Windows use the pre-built binary from the releases page
   # or
   # binary release: https://github.com/modelcontextprotocol/registry/releases
   ```

3. **Authenticate against the Registry.**
   ```bash
   mcp-publisher login github
   ```
   This opens the GitHub OAuth flow. Must complete as `yakuphanycl` (the namespace owner) or the submission is rejected.

4. **Validate the draft `server.json` before publishing.**
   ```bash
   cd apps/wrg_mcp_server
   mcp-publisher publish --dry-run server.json
   ```
   Fixes any schema or namespace-verification errors surfaced.

5. **Publish.**
   ```bash
   mcp-publisher publish server.json
   ```
   On success the server appears at `https://registry.modelcontextprotocol.io/v0/servers/io.github.yakuphanycl/wrg-mcp-server`.

6. **Announce + track the 10-install KPI.**
   Update `apps/wrg_mcp_server/README.md` with the Registry URL once live. Open a tracking issue in WRG to watch PyPI download counts (via `pypistats`) and GitHub star delta.

### Known risks / gotchas

- **Registry API freeze (v0.1, 2025-10-24).** The schema URL pinned in `server.json` is the 2025-12-11 revision — the current canonical pre-freeze schema. If the freeze resulted in any schema changes after publishing this PR, update the `$schema` URL before running `mcp-publisher publish`.
- **PyPI name squat.** `wrg-mcp-server` is not checked reserved as of this PR. Run `pip index versions wrg-mcp-server` right before publishing to confirm availability.
- **Monorepo-install friction.** A fresh `pipx install wrg-mcp-server` only gets tools that work without `WRG_REPO_ROOT` (essentially none — every local tool needs the repo on disk). Document clearly in the Registry card that this server is **designed to run against a local WRG checkout**, not standalone. Otherwise the 10-install KPI will bring bad-fit users.

---

## 10. Files in this submission

| File | Purpose | Needs maintainer edit before publish? |
|------|---------|---------------------------------------|
| `apps/wrg_mcp_server/server.json` | Submission payload for `mcp-publisher publish`. | Only if the PyPI package name changes (squat fallback) or the schema URL moves. |
| `apps/wrg_mcp_server/MCP_REGISTRY_SUBMISSION.md` | This document — human-readable rationale, use cases, checklist. Not consumed by the Registry. | No (informational only). |
| `apps/wrg_mcp_server/README.md` | Added the `mcp-name` HTML comment marker at line 1. Required for PyPI README validation. | Only if the Registry name changes. |

No Python code, tests, or workflow files were modified.

---

## 11. After submission — success metrics

Tracked against the roadmap "Next" target of **10+ installs**:

| Metric | Source | Cadence |
|--------|--------|---------|
| PyPI daily downloads | `pypistats overall wrg-mcp-server` | Weekly spot-check |
| Registry profile views | Registry dashboard (when available) | Monthly |
| GitHub repo stars delta | `gh api repos/yakuphanycl/WinstonRedGuard --jq .stargazers_count` | Weekly |
| External issues / questions | `gh issue list --label mcp-server` | Ad-hoc |

If downloads stay under 5 after 8 weeks post-launch, the honest move is to mark this a learning-lab exercise (per the [2026-04-23 scope thesis](../../README.md)) rather than double down on marketing — same framework used for `opportunity_radar` and `pulseboard` candidates.
