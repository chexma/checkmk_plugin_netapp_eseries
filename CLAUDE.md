# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project

CheckMK plugin `netapp_eseries`: monitors NetApp E-Series storage systems
(hardware and performance) via the SANtricity REST API. Released, MKP title
"Netapp E-Series Checks"; user docs in `README.md`.

Use the `checkmk-plugin-dev` skill (installed as Claude Code plugin
`checkmk-plugin-dev@chexma-checkmk`) for CheckMK API references and templates.

### Architecture

```
NetApp E-Series API → special agent → agent output → section parser → check plugin → service
```

1. **Special agent** (`plugins/netapp_eseries/special_agents/agent_netappeseries.py`,
   wrapper `libexec/agent_netappeseries`): runs on the Checkmk server, calls the
   REST API with `requests` and prints sections like
   `<<<netapp_eseries_volumes:sep(0)>>>`. Merges performance statistics from
   `/analysed-*-statistics` into the base data (`add_perfdata_to_section_data()`).
2. **Server side calls** (`server_side_calls/special_agent.py`, API
   `server_side_calls.v1`): turns rule parameters into agent arguments,
   password via password store.
3. **Agent-based checks** (`agent_based/netapp_eseries_*.py`): one plugin per
   component (batteries, controllers, drawers, drives, ESMs, fans, interfaces,
   pools, power supplies, system, thermal sensors, trays, volumes), sharing
   parse/discovery functions from `lib.py`.
4. **Ruleset** `rulesets/netappeseries.py` ("Netapp E-Series via REST API").

Imports inside the plugin always use `cmk_addons.plugins.netapp_eseries...`,
never `cmk.plugins.netapp_eseries...`.

### Item names

`add_checkmk_item_identifier()` in the special agent sets
`checkmk_item_identifier` per component, so service names stay stable:

- Controllers/drawers: physical location label (A/B)
- Volumes/pools: volume label
- Drives: "TrayID-Slot"
- Interfaces: "TYPE Controller-Channel" (e.g. "FC A-1")
- Other hardware: "Type TrayID-Slot"

`storage_id_mappings` translates internal refs to readable labels.

### Implementation details

- Sections are Python dict strings, parsed with `ast.literal_eval()`
  (`parse_netapp_eseries`).
- Discovery: `discovery_netapp_eseries_multiple()`, one service per item.
- State: mostly WARN if `status != "optimal"`.
- Metrics: `cmk.agent_based.v2` `Metric`, names like `disk_read_ios`, `disk_write_ios`.

### Adding a section (e.g. "cache")

1. Add a `Section` to the `sections` list in `main()` of the special agent,
   with `perfdata_uri`/`perfdata_identifier` if an `/analysed-*-statistics`
   endpoint exists.
2. Add the name to the `sections` list in `parse_arguments()`.
3. New `agent_based/netapp_eseries_cache.py`: `AgentSection` with
   `parse_netapp_eseries`, `CheckPlugin` with `discovery_netapp_eseries_multiple`.
4. Ruleset changes in `rulesets/netappeseries.py` if configurable.
5. Add the new files to `files` in `./package`.

### REST API

Base URL `https://HOST:8443/devmgr/v2/storage-systems/SYSTEM_ID`, HTTP basic
auth. Endpoints: `/`, `/controllers`, `/hardware-inventory` (batteries,
drawers, ESMs, fans, power supplies, trays, thermal sensors), `/drives`,
`/interfaces`, `/storage-pools`, `/volumes`, `/analysed-*-statistics`.
E-Series has no custom users: use the built-in `monitor` user, not `admin`.

### Test data and agent calls

Canned agent output from simulators and a real system lives in `temp/`
(not tracked), e.g. `temp/simulator-2800-config-8.80.txt`,
`temp/monitoring-NETAPP02-agent.txt`:

```bash
.devcontainer/test-host.sh eseries-sim temp/simulator-2800-config-8.80.txt
cmk -vI --detect-plugins=netapp_eseries_drives eseries-sim
```

Against a real system (`-s` only for debugging, normally `--password-id`):

```bash
python3 plugins/netapp_eseries/special_agents/agent_netappeseries.py \
  -u monitor -s 'password' -vvv --debug HOSTNAME_OR_IP
cmk -D <host> | grep Program      # agent command line Checkmk uses
```

## Environment

Devcontainer based on the official `checkmk/check-mk-<edition>` image with a
running site `cmk` (GUI: forwarded port 5000, path `/cmk/`, `cmkadmin`/`cmkadmin`).
Edition and version are set in `.devcontainer/devcontainer.json` (build args).
The shell runs as site user `cmk`, so `cmk`, `mkp`, `omd` work directly.

Workspace directories are bind-mounted into the site:

| Workspace | Site path |
|---|---|
| `plugins/` | `~/local/lib/python3/cmk_addons/plugins/` |
| `lib/` | `~/local/lib/python3/cmk/` |
| `plugins_legacy/` | `~/local/share/check_mk/` |
| `agents/` | `~/local/share/check_mk/agents/` |
| `bin/` | `~/local/bin/` |
| `nagios_plugins/` | `~/local/lib/nagios/plugins/` (symlink) |
| `temp/` | `~/local/tmp/` (symlink, not tracked) |

`sudo` is not available to Claude Code sessions, and the container cannot
rebuild itself (no Docker socket); rebuilds are done from VS Code on the host.

## Commands

```bash
black plugins/ tests/                 # format (line length 100, see pyproject.toml)
isort plugins/ tests/
flake8 plugins/ tests/
pytest                                # tests/ (pytest ships with the site)
.devcontainer/ci.sh                   # everything CI runs (lint, tests, validate)

cmk-validate-plugins                  # all plugins load?
.devcontainer/test-host.sh <host> <agent-output-file>   # host with canned agent output
cmk -vI --detect-plugins=<plugin> <host>   # discovery
cmk -v --detect-plugins=<plugin> <host>    # check
cmk -R                                # reload config after check plugin changes
omd restart apache                    # after ruleset/graphing changes
```

## MKP packaging

Build MKPs **only on explicit request**, not after every change.

**Never use `mkp release` or `mkp disable`** — they delete the bind-mounted
source files in the workspace (also denied in `.claude/settings.json`).

A PostToolUse hook (`.claude/hooks/format-python.sh`) runs isort and black on
every Python file you edit; don't reformat by hand afterwards.

The manifest is the file `package` in the repo root (tracked in git).
`.devcontainer/startup.sh` links it into `~/var/check_mk/packages/netapp_eseries`.

First time (no `package` file yet):

```bash
mkp template netapp_eseries    # writes ~/tmp/check_mk/netapp_eseries.manifest.temp
# Trim it to this plugin's files only (it lists ALL unpackaged files of the
# site), set title/author/description/version/version.min_required, then:
cp ~/tmp/check_mk/netapp_eseries.manifest.temp "$WORKSPACE/package"
```

Each build:

```bash
# 1. bump 'version' in ./package, add new files to its 'files' dict
# 2. build and copy the .mkp into the workspace
.devcontainer/build.sh
# 3. update Changelog.md
```
