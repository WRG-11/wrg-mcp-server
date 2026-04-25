# Changelog

All notable changes to `wrg_mcp_server` are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/yakuphanycl/WinstonRedGuard/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/yakuphanycl/WinstonRedGuard/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/yakuphanycl/WinstonRedGuard/releases/tag/v1.0.1
