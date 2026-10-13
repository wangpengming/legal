#!/usr/bin/env bash
# thunderbox 部署分支同步（壳层）
exec python3 "$(dirname "$0")/deploy_sync.py" "$@"