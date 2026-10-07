#!/usr/bin/env bash
# Turn a fresh clone of the template into a plugin repo. Run once, on the
# host or in the container, from anywhere inside the clone:
#
#   .devcontainer/init-plugin.sh <name> [<origin-url>]
#
# <name> is the plugin family (directory under plugins/, MKP name):
# lowercase letters, digits and underscores. With <origin-url> the template
# remote is renamed to "template" and <origin-url> becomes "origin".
set -Eeuo pipefail

usage() {
    sed -n '5p' "$0" | sed 's/^#   /usage: /'
    exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
name=$1
origin_url=${2:-}

if [[ ! "$name" =~ ^[a-z][a-z0-9_]*$ ]]; then
    echo "ERROR: '$name' is not a valid plugin name (lowercase letters, digits, underscores)" >&2
    exit 1
fi

cd "$(dirname "$0")/.."

if ! grep -q '`<name>`' CLAUDE.md; then
    echo "ERROR: CLAUDE.md has no <name> placeholder left, already initialized?" >&2
    exit 1
fi

# CLAUDE.md: plugin name in, template hint out
perl -pi -e "s/<name>/$name/g" CLAUDE.md
perl -0pi -e 's/<!-- TEMPLATE:.*?-->\n//s' CLAUDE.md
echo "CLAUDE.md: plugin name set to $name"

# .gitkeep: an empty directory would not survive the first commit
mkdir -p "plugins/$name" && touch "plugins/$name/.gitkeep"
echo "Created plugins/$name/"

if [[ -n "$origin_url" ]]; then
    if git remote get-url origin >/dev/null 2>&1; then
        if git remote get-url template >/dev/null 2>&1; then
            echo "ERROR: remotes 'origin' and 'template' both exist, set origin by hand" >&2
            exit 1
        fi
        git remote rename origin template
        echo "Remote 'origin' renamed to 'template' (git pull template main for updates)"
    fi
    git remote add origin "$origin_url"
    echo "Remote 'origin' set to $origin_url"
fi

cat <<EOF

Next:
  1. Set EDITION and VARIANT in .devcontainer/devcontainer.json
  2. Describe the plugin in the "Project" section of CLAUDE.md
  3. Commit: git add -A && git commit -m "Initialize plugin $name"
  4. VS Code: "Dev Containers: Reopen in Container"
EOF
