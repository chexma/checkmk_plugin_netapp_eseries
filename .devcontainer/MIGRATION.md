# Migrating an existing plugin to this template

Instructions for Claude Code, executed **inside the plugin's current (old)
devcontainer**. They cover plugin folders from older devcontainer setups
(e.g. derived from `Yogibaer75/checkmk_template`): with or without a git
repo, Claude Code installed via npm, Claude config inside the workspace.

The migration has two phases with a container rebuild in between:

- **Phase 1** (old container): back up container-only state, put the folder
  on the template's git history, take over template files, merge the rest,
  commit. Nothing inside `.claude/` is deleted in this phase: in old setups
  the running Claude session keeps its config there.
- The user rebuilds the container from VS Code on the host.
- **Phase 2** (new container): restore memory and test hosts, verify, clean up.

Start prompts for the user:

```text
Phase 1: Add https://github.com/chexma/checkmk-plugin-template.git as git
remote "template" (run `git init -b main` first if this is no git repo),
fetch it and follow `git show template/main:.devcontainer/MIGRATION.md`, phase 1.

Phase 2: Follow .devcontainer/MIGRATION.md, phase 2.
```

General rules for both phases:

- Before anything that deletes, overwrites or commits, show what will happen
  and wait for the user's OK. Never push.
- Never use `mkp release` or `mkp disable` (they delete the bind-mounted
  sources).
- Never print or copy `.claude/.credentials.json` or other secrets.
- `<name>` below is the plugin/package name (`name` in the manifest `package`).
- Work from the workspace root (`$WORKSPACE`, e.g. `/workspaces/sep_sesam`).
- If git reports "detected dubious ownership", run
  `git config --global --add safe.directory "$WORKSPACE"` (the bind-mounted
  workspace belongs to the host user; new containers set this up themselves).

---

## Phase 1: in the old container

### 1.1 Inventory, then stop

Collect and show the user:

- git: repo or not, branch, remotes, `git status --short` (uncommitted work?)
- plugin code: `plugins/*/`, and whether a duplicate `local/lib/python3/cmk_addons/plugins/`
  exists in the workspace (`diff -rq` against `plugins/`, ignoring `__pycache__`)
- `plugins_legacy/`: real legacy code (`checks/`, `web/`, `agents/`, …) vs.
  build artifacts (`enabled_packages/`)
- `lib/`, `agents/`, `bin/`, `nagios_plugins/`, `tests/`, `test/` (often empty)
- manifest `package` (name, version, files) and `*.mkp` files
- docs and notes: `docs/`, `plans/`, `idea.md`, `ToDO`, `Installation.md`, `temp/`
- `.devcontainer/devcontainer.json`: Checkmk edition (image `checkmk/check-mk-<edition>`
  in the Dockerfile) and `VARIANT`, fixed ports, extra mounts
- `echo $CLAUDE_CONFIG_DIR` and whether it points into the workspace
- names of **other** plugins in this plugin's files: old setups were copied
  between plugins, e.g. a `build.sh` hard-coded to another package or MKP
  details of another plugin in `CLAUDE.md`. List every hit
  (`grep -rIl` for the other plugin names you find, outside `.claude/`); such
  content is dropped in the merge.
- tests that depend on the old layout: paths into a workspace copy
  (`local/lib/python3/...`), `sys.path` tweaks, stubs replacing `cmk` modules

Then ask the user to confirm that a **copy of the whole plugin folder exists
on the host** (e.g. `cp -a sep_sesam sep_sesam.bak`). Do not continue without it.

### 1.2 Back up container-only state

Into `temp/claude-migration/` (`temp/` is not tracked; it survives the
rebuild because it is in the workspace):

1. **Claude memory**: the project's memory dir is
   `$CLAUDE_CONFIG_DIR/projects/<slug>/memory/` (default config dir `~/.claude`),
   `<slug>` is the workspace path with every non-alphanumeric character
   replaced by `-` (`/workspaces/sep_sesam` → `-workspaces-sep-sesam`).
   Copy it to `temp/claude-migration/memory/`. If the config dir is inside the
   workspace (`.claude/`), copying is still right: that folder gets ignored and
   cleaned up later.
2. **Old Claude settings**: copy the old `$CLAUDE_CONFIG_DIR/settings.json` to
   `temp/claude-migration/old-user-settings.json` (step 1.4 overwrites
   `.claude/settings.json` in the workspace, which may be that file).
3. **Manifest**: if `package` is not in the workspace root, copy it from
   `~/var/check_mk/packages/<name>`.
4. **Test setup of the site**: the site itself is rebuilt from scratch.
   Write `temp/claude-migration/site.md` with the hosts (`cmk --list-hosts`)
   and, via the REST API (`http://localhost:5000/cmk/check_mk/api/1.0`, user
   `cmkadmin`, password `cmkadmin`), export the rules of the plugin's rulesets
   (`special_agents:<name>`, `datasource_programs`, check parameter rulesets of
   the plugin) to `temp/claude-migration/rules-*.json`. Stored passwords are
   not exported in clear text; note which ones the user has to re-enter.
   Note which files hold canned agent output (e.g. `temp/agent_output.txt`).

### 1.3 Put the folder on the template history

```bash
git remote add template https://github.com/chexma/checkmk-plugin-template.git
git fetch template
```

If the fetch fails (private repo, no credentials in the container): ask the
user to clone the template on the host into the workspace's `temp/`, then
`git remote add template "$WORKSPACE/temp/checkmk-plugin-template"`, and at
the end of phase 1
`git remote set-url template https://github.com/chexma/checkmk-plugin-template.git`.

- **No git repo yet:**
  ```bash
  git init -b main          # if not done already
  git reset template/main   # HEAD and index = template, working files untouched
  ```
  `git status` now shows the plugin's files as changes against the template.
- **Existing repo:** working tree must be clean (ask the user to commit or stash
  first), then
  ```bash
  git merge -s ours --no-commit --allow-unrelated-histories template/main
  ```
  This records the template history without changing any file; the next
  steps bring in the template files, and the commit in 1.7 concludes the merge.

Either way, `git pull template main` will later bring only new template changes.

### 1.4 Take over the template's files

```bash
git checkout template/main -- .devcontainer .claude/settings.json .claude/hooks \
    .github .gitattributes .flake8 .gitignore
```

- No-repo case only: template files missing in the folder show up as deleted
  (`git ls-files --deleted`, e.g. `tests/.gitkeep`). Restore them with
  `git checkout -- <paths>` unless the user wants a file gone.
- Remove old devcontainer files the template does not have, e.g.
  `.devcontainer/setpwd.sh`, `template-update.sh`, `template-sync*.conf`,
  `requirements.txt` (`git rm` if tracked, else `rm`).
- In `.devcontainer/devcontainer.json` set `EDITION` and `VARIANT` to the
  values the old setup used (old Dockerfiles often hard-code
  `checkmk/check-mk-cloud`, i.e. `EDITION=cloud`).
- `.gitignore` is the template's. If the old one tracked less (e.g. only the
  plugin code), keep the template's and show the user in 1.6 what becomes
  tracked. Add plugin-specific ignores at the end if needed.

### 1.5 Merge the files that belong to both

- **`CLAUDE.md`**: start from `git show template/main:CLAUDE.md`, replace
  `<name>` with the plugin name, drop the `<!-- TEMPLATE … -->` comment. Fill
  the *Project* section from the old file (purpose, external system, status,
  architecture, conventions, plugin-specific commands such as agent test
  calls). Drop old sections the template replaces: environment, mounts, MKP
  build steps, Python tool setup, anything about the old container.
- **`pyproject.toml`**: start from the template's. Keep plugin sections that
  have an effect (e.g. `[tool.isort]` `known_first_party`, extra pytest
  options). Drop `[tool.flake8]` (flake8 does not read `pyproject.toml`; move
  needed rules such as `per-file-ignores = __init__.py:F401` into `.flake8`),
  pylint sections (not part of the toolchain) and `[project]` (no installable
  package).
- **`README.md`, `Changelog.md`**: keep the plugin's. If there is no
  `Changelog.md`, take the template's stub.
- **`package`**: keep; check `name` matches `plugins/<name>/` and `files`
  lists exist.
- **Tests**: point paths into a workspace copy (`local/lib/python3/cmk_addons/plugins/<name>/...`)
  to `plugins/<name>/...` before that copy is removed in 1.6. Leave stubs and
  assertions alone; phase 2 shows whether the tests pass.

### 1.6 Clean up

- Duplicate `local/lib/python3/cmk_addons/plugins/…` in the workspace: delete
  only if identical to `plugins/` (1.1); otherwise ask the user which is current.
- `plugins_legacy/`: keep real legacy code; `enabled_packages/` is ignored by
  the template's `.gitignore` and needs no action.
- Built `*.mkp`: ignored now; if they were tracked, `git rm --cached` them
  (releases come from CI).
- Empty directories (e.g. `test/`): remove.
- Notes and docs (`docs/`, `plans/`, `idea.md`, `ToDO`, `Installation.md`, …):
  list them and let the user decide per item: track, ignore (add to
  `.gitignore`) or delete.
- `.claude/` (old config dir in the workspace): **leave as is**; the
  template's `.gitignore` already hides everything except `settings.json`
  and `hooks/`.

### 1.7 Review and commit

Show `git status` and a short summary of what is tracked, changed, removed.
Check that no secret is staged (`git diff --cached --name-only | grep -i
credential` must be empty). After the user's OK:

```bash
git add -A
git commit -m "Migrate to checkmk-plugin-template"
```

Tell the user: end this session, then in VS Code
"Dev Containers: Rebuild Container", and start phase 2 in the new container.
The fixed host port of the old setup is gone: the GUI is on the port VS Code
forwards for 5000 (Ports view). On the first `claude` start in the new
container a login may be needed (shared volume `checkmk-claude-config`).

---

## Phase 2: in the new container

1. **Memory**: the slug is the same if the folder name did not change. Copy
   `temp/claude-migration/memory/*` into `$CLAUDE_CONFIG_DIR/projects/<slug>/memory/`
   without overwriting existing files; if both have a `MEMORY.md`, merge the
   index lines.
2. **Test setup**: recreate hosts with canned agent output via
   `.devcontainer/test-host.sh <host> <file>`; recreate special agent and
   parameter rules from `temp/claude-migration/rules-*.json` via the REST API
   (ask the user for passwords). Activate changes.
3. **Verify**:
   - `mkp list` shows the package (registered by `startup.sh` from `package`)
   - `.devcontainer/ci.sh`: if black/isort reformat the old code, run
     `isort plugins tests && black plugins tests` and commit that separately
     ("Format with pinned black/isort"). Report flake8 findings and failing
     tests to the user with their cause. Tests that no longer match the plugin
     code (e.g. changed function signatures) were broken before the migration:
     don't change assertions to make them pass, the user decides.
   - `cmk -vI` / `cmk -v --detect-plugins=<plugin> <host>` on a test host
   - optional: `.devcontainer/build.sh` (builds the current version from `package`)
4. **Clean up** after the user's OK: in `.claude/` everything except
   `settings.json` and `hooks/` (old login, history, sessions, cloned skills,
   backups); old MKPs in `plugins_legacy/enabled_packages/` (the old site's
   state; the new site lists them as inactive versions in `mkp list`, and
   `build.sh` recreates the current one); `temp/claude-migration/`.
5. Commit. A repo without `origin`: the user creates the GitHub repo, then
   `git remote add origin <url>`; push only when asked. CI runs on the first push.
