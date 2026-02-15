#!/usr/bin/env bash
# InstantRisk Local Development Helper
# Usage: ./local-dev.sh [command]

set -e

COMPOSE_FILE="docker-compose.local.yml"
COMPOSE="docker compose -f $COMPOSE_FILE"

case "${1:-help}" in
  up)
    echo "Starting local development environment..."
    $COMPOSE up --build -d
    echo ""
    echo "Services starting. Run './local-dev.sh logs' to watch backend startup."
    echo "Health check: http://localhost:8000/api/v1/health/live"
    echo "API docs:     http://localhost:8000/docs"
    ;;

  down)
    echo "Stopping all services..."
    $COMPOSE down
    ;;

  down-clean)
    echo "Stopping all services and removing volumes (DATABASE WILL BE WIPED)..."
    $COMPOSE down -v
    ;;

  logs)
    $COMPOSE logs -f backend
    ;;

  logs-all)
    $COMPOSE logs -f
    ;;

  rebuild)
    echo "Rebuilding backend image and restarting..."
    $COMPOSE up --build -d backend
    echo "Done. Run './local-dev.sh logs' to watch startup."
    ;;

  shell)
    echo "Opening shell in backend container..."
    $COMPOSE exec backend bash
    ;;

  test)
    echo "Running tests in backend container..."
    $COMPOSE exec backend python -m pytest -v
    ;;

  health)
    curl -s http://localhost:8000/api/v1/health/live | python -m json.tool
    ;;

  db-shell)
    echo "Opening PostgreSQL shell..."
    $COMPOSE exec postgres psql -U instantrisk_admin -d instantrisk
    ;;

  status)
    $COMPOSE ps
    ;;

  creds)
    echo "Paste your AWS SSO credentials below."
    echo "Get them from: https://d-9067861d8b.awsapps.com/start/#"
    echo ""
    read -p "AWS_ACCESS_KEY_ID: " key_id
    read -p "AWS_SECRET_ACCESS_KEY: " secret_key
    read -p "AWS_SESSION_TOKEN: " session_token

    # Update .env.local
    sed -i "s|^AWS_ACCESS_KEY_ID=.*|AWS_ACCESS_KEY_ID=$key_id|" .env.local
    sed -i "s|^AWS_SECRET_ACCESS_KEY=.*|AWS_SECRET_ACCESS_KEY=$secret_key|" .env.local
    sed -i "s|^AWS_SESSION_TOKEN=.*|AWS_SESSION_TOKEN=$session_token|" .env.local

    echo ""
    echo "Credentials updated in .env.local"
    echo "Run './local-dev.sh rebuild' to restart with new creds."
    ;;

  help|*)
    echo "InstantRisk Local Development"
    echo ""
    echo "Usage: ./local-dev.sh [command]"
    echo ""
    echo "Commands:"
    echo "  up          Build and start all services (postgres, redis, backend)"
    echo "  down        Stop all services"
    echo "  down-clean  Stop all services and wipe database volume"
    echo "  logs        Tail backend logs"
    echo "  logs-all    Tail all service logs"
    echo "  rebuild     Rebuild backend image and restart (~30s)"
    echo "  shell       Open bash shell in backend container"
    echo "  test        Run pytest in backend container"
    echo "  health      Check backend health endpoint"
    echo "  db-shell    Open PostgreSQL interactive shell"
    echo "  status      Show running containers"
    echo "  creds       Update AWS SSO credentials in .env.local"
    echo ""
    echo "First time setup:"
    echo "  1. Copy .env.local and fill in AWS credentials"
    echo "  2. ./local-dev.sh up"
    echo "  3. Wait ~60s for backend startup + migrations"
    echo "  4. ./local-dev.sh health"
    ;;
esac
