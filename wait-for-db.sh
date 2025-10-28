#!/bin/sh
# This waits until Postgres is ready, then exec the passed command
set -e

host="${DB_HOST:-db}"
port="${DB_PORT:-5432}"
echo "Waiting for Postgres at $host:$port..."

until (pg_isready -h "$host" -p "$port" > /dev/null 2>&1) || (nc -z "$host" "$port" > /dev/null 2>&1); do
  >&2 echo "Postgres is unavailable — sleeping 1s"
  sleep 1
done

>&2 echo "Postgres is up — continuing"
exec "$@"
