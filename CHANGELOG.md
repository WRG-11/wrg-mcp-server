# Changelog

All notable changes to `wrg_mcp_server` are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.5] - 2026-05-23

Brand consolidation closure patch addressing 3 HIGH findings from the
R89-03b READ-ONLY portfolio audit (B agent, `from-B/2026-05-23-0100-r89-03b-...-done.md`).

### Fixed

- `server.json` namespace + URL + version drift. The MCP Registry consumes
  this file as the canonical server identifier, but it was left on the old
  `yakuphanycl` namespace when pyproject + README + PyPI all migrated to
  `WRG-11` during v1.0.3. Three changes:
  - `name`: `io.github.yakuphanycl/wrg-mcp-server` -> `io.github.WRG-11/wrg-mcp-server`
  - `websiteUrl`: `github.com/yakuphanycl/WinstonRedGuard/tree/main/apps/wrg_mcp_server` -> `github.com/WRG-11/wrg-mcp-server`
  - `repository.url`: `github.com/yakuphanycl/WinstonRedGuard` -> `github.com/WRG-11/wrg-mcp-server`
  - `repository.subfolder`: removed (no longer a monorepo subfolder post v1.0.3 sub-tree split).
  - `version`: 1.0.1 -> 1.0.5 (both root + packages[0]; 3-source drift vs pyproject + git tag closed).
  - NOTE: MCP Registry re-submission is a separate manual step. The old
    `io.github.yakuphanycl/wrg-mcp-server` Registry entry becomes orphaned
    because the OAuth chain to the old GitHub namespace is broken.
  - (R89-03b HIGH findings #1 + #2 + #6.)

### Added

- `LICENSE` file at repo root with canonical MIT text. `pyproject.toml`
  declared `license = "MIT"` (PEP 639 SPDX short-form) which satisfies PyPI
  but does NOT auto-emit a LICENSE file, leaving forks / vendoring consumers
  without explicit license text. Sister `instinct` template used verbatim.
  (R89-03b HIGH finding #5.)
- `.github/workflows/ci.yml`: pytest matrix on Linux + Windows x Python
  3.11 / 3.12 / 3.13 with `pip install -e ".[dev]"`. Sister `instinct`
  template adapted (drop `Cursor rules drift check` step which is
  instinct-specific). (R89-03b HIGH finding #15.)
- `.github/workflows/codeql.yml`: GitHub CodeQL static analysis on
  push / PR / weekly schedule (Mondays 03:00 UTC). Sister `instinct`
  template verbatim. (R89-03b HIGH finding #15.)

## [1.0.4] - 2026-05-23

### Fixed
- PyPI upload rejected v1.0.3 with `400 Bad Request: Can't have direct dependency: wrg-threat-intel @ file:../wrg_threat_intel ; extra == "threat-intel"`. The `[project.optional-dependencies] threat-intel` extras used relative `file://` paths that worked inside the WRG monorepo but are not valid for PyPI publication.
- Removed `[project.optional-dependencies] threat-intel` section temporarily. Users wanting threat-intel + ransom-radar integration must install those packages directly (currently WRG monorepo only; not yet on PyPI). Re-add this extras group via PyPI-resolvable specs once sister packages publish.

### Changed
- Version bump 1.0.3 -> 1.0.4 (v1.0.3 tag exists locally + on GitHub but never published to PyPI; v1.0.4 is the first WRG-11 standalone PyPI release).

## [1.0.3] - 2026-05-23

### Changed
- Repository split from the WinstonRedGuard monorepo (private) into a standalone public repo `WRG-11/wrg-mcp-server`. History preserved via `git subtree split` from `apps/wrg_mcp_server/` (1934 commits processed). Sister `instinct-mcp` v1.4.1 + `wrg-devguard` v0.2.1 + `wrg-rule-lab` v0.1.4 brand consolidation pattern; 4th PyPI release in the WRG-11 namespace consolidation.
- `pyproject.toml` `[project.urls]` refreshed: Homepage + Repository + Issues + Documentation now point to standalone `WRG-11/wrg-mcp-server` (previously pointed to `yakuphanycl/WinstonRedGuard/tree/main/apps/wrg_mcp_server` — a private monorepo path that returned 404 to external consumers, breaking PyPI page links).
- Changelog URL entry added (was missing in v1.0.2).
- No behavioral changes; URL/metadata-only patch bump + standalone publication.

### Added
- `.github/workflows/publish.yml`: PyPI trusted publishing on tag push (sister `wrg-devguard` v0.2.0+ pattern; OIDC, no API token required).

## [1.0.2] - 2026-04-25

Audit-driven patch release rolling up the 9 PRs landed in the
`MCP_TOOL_AUDIT_2026_04_25` wave. Headline outcomes: discoverability ceiling
hit (avg 2.81 → 4.00 / 5), envelope coverage 88% → 100% (32/32 tools),
behavioural test coverage extended from 13 to 20 tools, and two long-standing
contract gaps closed (research_motor envelope + site_post mutation gate).

### Changed (BREAKING)

- **`research_motor_*` HTTP-API tools** (`research_motor_healthz`,
  `research_motor_scan_create`, `research_motor_scan_get`) now return the
  standard `{ok, status_code, body}` / `{ok: False, error, ...}` envelope
  instead of raising `RuntimeError` on httpx-import failure, missing API key,
  or HTTP non-2xx. Aligns the trio with the 29 other MCP tools in this server.
  Callers that previously relied on `try/except RuntimeError` should switch to
  `if not result["ok"]`. ([#305](https://github.com/yakuphanycl/WinstonRedGuard/pull/305),
  audit §6 #3)
- **`site_post`** now requires `WRG_SITE_MUTATIONS=1` in the server env. With
  the gate unset (or any value other than `"1"`) the tool returns
  `{"ok": False, "error": "site mutations gated; set WRG_SITE_MUTATIONS=1"}`
  without contacting the configured site service. Strict equality on `"1"` is
  intentional — site mutations cross a public-network boundary. Mirrors the
  `pipeline_run` / `memory_set` pattern. ([#304](https://github.com/yakuphanycl/WinstonRedGuard/pull/304),
  audit §3.4 + §5)

### Added

- `connector_status` now leads its envelope with `"ok": True`, matching the
  rest of the server. ([#296](https://github.com/yakuphanycl/WinstonRedGuard/pull/296),
  audit §4 #1)
- Five rewritten 1/5 docstrings: `site_health`, `site_post`, `pulseboard_health`,
  `research_motor_healthz`, plus `connector_status` triage notes.
  ([#296](https://github.com/yakuphanycl/WinstonRedGuard/pull/296), audit §4 #2)
- Seven additional docstring rewrites covering the remaining 2/5 surface
  (`site_get`, `research_*` family, `pipeline_*` family). All MCP tools now
  rate ≥4/5 on discoverability. ([#302](https://github.com/yakuphanycl/WinstonRedGuard/pull/302),
  audit §4 #2)
- Behavioural test coverage for `app_info` (4-source aggregation).
  ([#297](https://github.com/yakuphanycl/WinstonRedGuard/pull/297), audit §6 #4)
- Behavioural test coverage for `research_history`, `research_report`,
  `research_scan`, `research_watch` plus an audit BLOCKED note documenting why
  one test path could not be covered. ([#298](https://github.com/yakuphanycl/WinstonRedGuard/pull/298),
  audit §6 #4)
- Behavioural test coverage for `app_list` and `governance_run`
  (`§1` rollup). ([#301](https://github.com/yakuphanycl/WinstonRedGuard/pull/301),
  audit §6 #4)
- Three new `site_post` mutation-gate tests
  (`test_site_post_gated_by_default`, `test_site_post_gate_unlocks_with_env`,
  `test_site_post_gate_explicitly_off`) wired through the FastMCP tool
  registry. ([#304](https://github.com/yakuphanycl/WinstonRedGuard/pull/304))
- Envelope contract tests for the `research_motor_*` trio covering httpx
  missing, missing API key, 2xx, and non-2xx paths.
  ([#305](https://github.com/yakuphanycl/WinstonRedGuard/pull/305))
- PulseBoard SOFT-DEPRECATE: dormancy notes added to all 5 PulseBoard tool
  docstrings (`pulseboard_health`, `pulseboard_list_repos`,
  `pulseboard_add_repo`, `pulseboard_delete_repo`, `pulseboard_get_pulse`)
  pointing at PR #252 and the 2026-10-24 re-eval deadline. Tools remain
  callable. ([#299](https://github.com/yakuphanycl/WinstonRedGuard/pull/299),
  audit §5 PulseBoard rows)

### Documentation

- `docs/decisions/MCP_TOOL_AUDIT_2026_04_25.md` — full 32-tool MCP audit
  with naming, envelope, mutation-gating, and discoverability sections,
  plus prioritised follow-up checklist.
  ([#295](https://github.com/yakuphanycl/WinstonRedGuard/pull/295),
  [#300](https://github.com/yakuphanycl/WinstonRedGuard/pull/300),
  [#303](https://github.com/yakuphanycl/WinstonRedGuard/pull/303))

## [1.0.1] - 2026-04-24

Initial PyPI release of `wrg_mcp_server` after the v1 contract stabilised.
Surfaced 32 tools across local CLI wrappers, HTTP-API integrations
(`research_motor_*`), and remote services (`site_*`, `pulseboard_*`).

[Unreleased]: https://github.com/WRG-11/wrg-mcp-server/compare/v1.0.3...HEAD
[1.0.3]: https://github.com/WRG-11/wrg-mcp-server/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/yakuphanycl/WinstonRedGuard/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/yakuphanycl/WinstonRedGuard/releases/tag/v1.0.1
