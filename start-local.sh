#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
workspace="${1:-demo}"
command -v uv >/dev/null || { echo "找不到 uv，請先安裝：https://docs.astral.sh/uv/"; exit 1; }
[ -f web/out/index.html ] || (cd web && pnpm install && pnpm build)
exec uv run auditbox serve "$workspace"
