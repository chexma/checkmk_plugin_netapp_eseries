# Changelog

All notable changes to this plugin. Versions match `version` in `package`
and the release tags `v<version>`.

## [Unreleased]

## [3.5.0] - 2026-10-07

### Changed

- Special agent ported to the Checkmk 2.5 APIs `cmk.password_store.v1_unstable`
  and `cmk.server_side_programs.v1_unstable` (replace `cmk.special_agents.v0_unstable`
  and `cmk.utils.password_store`); agent crashes now create crash reports
- Special agent: new option `--vcrtrace` to record/replay API traffic (auth header masked)
- Ruleset: corrected help text (no longer mentions Redfish)

### Fixed

- Interfaces: degraded backend SAS ports now WARN (compared `isDegraded` with the
  string "False", so they were always OK)
- Interfaces: backend SAS ports with a port state other than "optimal" now WARN
- Pools: no crash if a discovered pool disappears
- Power supplies, system, trays, volumes: agent section variables named after
  their own section (were all copied as `agent_section_netapp_eseries_pools`)
- Special agent: `--sections` now accepts a comma separated list as documented
- Ruleset: rules with the protocol stored as plain string are migrated

### Added

- Test suite (pytest) for parsing, checks, ruleset, server side calls and special agent

## [3.4.1] - 2025-10-30

- Fix for SANtricity versions > 11.80
