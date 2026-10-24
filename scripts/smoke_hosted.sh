#!/usr/bin/env bash
set -euo pipefail

network=canopy-hosted-smoke
pg=canopy-hosted-pg
api=canopy-hosted-api

cleanup() {
  result=$?
  if ((result != 0)); then
    docker logs "$pg" --tail 30 >&2 || true
    docker logs "$api" --tail 30 >&2 || true
  fi
  docker rm -f "$api" "$pg" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker build --quiet -t canopy:hosted-smoke . >/dev/null
docker network create "$network" >/dev/null
docker run -d --name "$pg" --network "$network" \
  -e POSTGRES_USER=canopy -e POSTGRES_PASSWORD=ci-password -e POSTGRES_DB=canopy \
  --entrypoint bash postgres:16 -c \
  'openssl req -x509 -newkey rsa:2048 -nodes -keyout /tmp/server.key -out /tmp/server.crt -days 1 -subj /CN=canopy-hosted-pg >/dev/null 2>&1; chmod 600 /tmp/server.key; chown postgres:postgres /tmp/server.key /tmp/server.crt; exec docker-entrypoint.sh postgres -c ssl=on -c ssl_cert_file=/tmp/server.crt -c ssl_key_file=/tmp/server.key' \
  >/dev/null

pg_ready=0
for attempt in $(seq 1 25); do
  if docker exec "$pg" pg_isready -U canopy -d canopy >/dev/null 2>&1; then
    pg_ready=1
    break
  fi
  sleep 1
done
[[ "$pg_ready" == 1 ]]

cookie_key=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
docker run -d --name "$api" --network "$network" -p 127.0.0.1:18084:8080 \
  -e CANOPY_RUNTIME=production \
  -e CANOPY_PUBLIC_ORIGIN=https://canopy.example.test \
  -e 'DATABASE_URL=postgresql://canopy:ci-password@canopy-hosted-pg:5432/canopy?sslmode=require' \
  -e WORKOS_API_KEY=sk_test_placeholder -e WORKOS_CLIENT_ID=client_test_placeholder \
  -e WORKOS_COOKIE_PASSWORD="$cookie_key" -e CANOPY_WORKOS_ORG_ID=org_test \
  -e CANOPY_ADMIN_USER_ID=user_admin \
  -e CANOPY_CSRF_SECRET=cccccccccccccccccccccccccccccccccccccccc \
  -e MUBIT_API_KEY=ci-placeholder canopy:hosted-smoke >/dev/null

wait_for_app() {
  for attempt in $(seq 1 25); do
    if curl --silent --fail http://127.0.0.1:18084/livez >/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}
wait_for_app

status=$(curl --silent --output /dev/null --write-out '%{http_code}' \
  -H 'Host: canopy.example.test' http://127.0.0.1:18084/api/v1/session)
[[ "$status" == 401 ]]

count=$(docker exec "$api" python -c \
  'import os,psycopg; db=psycopg.connect(os.environ["DATABASE_URL"]); print(db.execute("SELECT count(*) FROM canopy_policies").fetchone()[0])')
[[ "$count" == 1 ]]
docker restart "$api" >/dev/null
wait_for_app
count_after=$(docker exec "$api" python -c \
  'import os,psycopg; db=psycopg.connect(os.environ["DATABASE_URL"]); print(db.execute("SELECT count(*) FROM canopy_policies").fetchone()[0])')
[[ "$count_after" == 1 ]]

echo 'Hosted TLS-Postgres container smoke passed'
