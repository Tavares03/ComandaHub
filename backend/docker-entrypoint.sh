#!/bin/sh
# Sobe a API: espera o banco, aplica as migrations e (so em desenvolvimento) carrega os dados demo.
set -e

python -m scripts.wait_for_db
alembic upgrade head

if [ "${SEED_DEMO_DATA:-false}" = "true" ]; then
  python -m scripts.seed
fi

exec "$@"
