#!/usr/bin/env bash
set -euo pipefail

smoke_dir=$(mktemp -d)
chmod 0700 "$smoke_dir"
export CANOPY_DOMAIN=localhost
export CANOPY_PUBLIC_ORIGIN=https://localhost:18443
export CANOPY_HTTP_PORT=18080
export CANOPY_HTTPS_PORT=18443
export CANOPY_POLICY_FILE="$PWD/sample_policy.json"
export CANOPY_OPERATOR_TOKEN_FILE="$smoke_dir/operator-token"
export MUBIT_API_KEY_FILE="$smoke_dir/mubit-key"
smoke_token=ci-only-token-at-least-thirty-two-characters
printf '%s' "$smoke_token" >"$CANOPY_OPERATOR_TOKEN_FILE"
printf '%s' ci-placeholder-never-used >"$MUBIT_API_KEY_FILE"
chmod 0444 "$CANOPY_OPERATOR_TOKEN_FILE" "$MUBIT_API_KEY_FILE"
compose=(docker compose -p canopy-ci -f deploy/compose.yaml)

cleanup() {
  result=$?
  if ((result != 0)); then
    "${compose[@]}" logs --no-color || true
  fi
  "${compose[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$smoke_dir"
}
trap cleanup EXIT

"${compose[@]}" up -d --build
ready=0
for ((attempt=1; attempt<=40; attempt++)); do
  if curl --insecure --silent --fail --user "operator:$smoke_token" \
      https://localhost:18443/readyz >/dev/null; then
    ready=1
    break
  fi
  sleep 1
done
if ((ready != 1)); then
  echo 'Canopy was not ready through Caddy HTTPS' >&2
  exit 1
fi

status=$(curl --insecure --silent --output /dev/null --write-out '%{http_code}' \
  https://localhost:18443/readyz)
[[ "$status" == 401 ]]

container_id=$("${compose[@]}" ps -q canopy)
docker inspect "$container_id" --format '{{json .NetworkSettings.Ports}}' \
  | python3 -c 'import json,sys; ports=json.load(sys.stdin); assert ports.get("8080/tcp") is None, ports'

"${compose[@]}" exec -T canopy python -c \
  'import canopy; canopy.create_decision("synthetic facts", "synthetic reply", "SUPPORTED", "mreq_ci_synthetic", 1)'
"${compose[@]}" restart canopy
"${compose[@]}" exec -T canopy python -c \
  'import canopy; rows=canopy.recent(); assert len(rows)==1 and rows[0]["policy_hash"]==canopy.POLICY_HASH'
"${compose[@]}" exec -T canopy python manage.py backup --output /data/ci-backup.sqlite3
"${compose[@]}" exec -T canopy python -c \
  'import shutil,sqlite3; shutil.copy2("/data/ci-backup.sqlite3", "/tmp/ci-restored.sqlite3"); db=sqlite3.connect("/tmp/ci-restored.sqlite3"); assert db.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; assert db.execute("SELECT count(*) FROM decisions").fetchone()[0]==1; db.close()'
echo 'Compose TLS, auth, private port, persistence, and backup restore smoke passed'
