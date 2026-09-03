#!/bin/sh
set -eu

source_repository=${1:?repository path or URL required}
covered_commit=${2:?40-character covered commit required}

case "$covered_commit" in
    *[!0-9a-f]* | "")
        echo "covered commit must be lowercase hexadecimal" >&2
        exit 2
        ;;
esac
if [ "${#covered_commit}" -ne 40 ]; then
    echo "covered commit must contain exactly 40 characters" >&2
    exit 2
fi

clean_root=$(mktemp -d "${TMPDIR:-/tmp}/finproof-clean-room.XXXXXX")
cleanup() {
    rm -rf -- "$clean_root"
}
trap cleanup 0 1 2 3 15

repository="$clean_root/repository"
git clone --no-local "$source_repository" "$repository"
cd "$repository"
git checkout --detach "$covered_commit"
test "$(git rev-parse HEAD)" = "$covered_commit"
test -z "$(git status --porcelain --untracked-files=all)"

uv sync --frozen --all-groups
uv run python tools/verify_handoff.py
uv run python tools/audit_source_data.py --check
uv run python tools/check_competition_compliance.py --check
uv run pytest -q \
    tests/contract/test_competition_compliance.py \
    tests/contract/test_release_manifest.py
docker build --tag "finproof:clean-room-$covered_commit" .
