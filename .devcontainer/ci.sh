#!/usr/bin/env bash
# Lint, test and validate the plugin; with --build also build the MKP.
# Runs as the site user inside the devcontainer image: in GitHub Actions (see
# .github/workflows/ci.yml) or locally in the devcontainer before pushing.
set -Eeuo pipefail

WORKSPACE="${WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$WORKSPACE"

set +u
source /omd/sites/cmk/.profile
set -u

echo "::group::black / isort / flake8"
black --check --diff plugins tests
isort --check-only --diff plugins tests
flake8 plugins tests
echo "::endgroup::"

echo "::group::pytest"
# Exit code 5 = no tests collected (e.g. the bare template): not a failure.
pytest --cov=cmk_addons.plugins --cov-report=term || [[ $? -eq 5 ]]
echo "::endgroup::"

echo "::group::cmk-validate-plugins"
# Validation calls the site's automation helper, so the site must run
# (in the devcontainer it already does, in CI it has to be started).
omd status >/dev/null 2>&1 || omd start >/dev/null
cmk-validate-plugins
echo "::endgroup::"

if [[ "${1:-}" == --build ]]; then
    echo "::group::MKP"
    bash .devcontainer/build.sh
    echo "::endgroup::"
fi
