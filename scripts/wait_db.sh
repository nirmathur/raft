#!/usr/bin/env bash
echo -n "⏳ Waiting for Postgres healthcheck "
until docker compose -f docker/docker-compose.yml exec -T postgres pg_isready -h localhost -U raft >/dev/null 2>&1; do
  echo -n "."; sleep 1; done
echo " ✅"