#!/bin/bash

# Verify that Postgres is healthy before proceeding
if [ "$DATABASE_URL" ]; then
    echo "Waiting for PostgreSQL..."

    while ! nc -z $DB_HOST $DB_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

# Apply database migrations
alembic upgrade head

# Start the FastAPI application
exec "$@"
