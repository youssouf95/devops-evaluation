#!/bin/bash
set -e

IMAGE="$1"
NEW_SHA="$2"
STATE_FILE="$HOME/.devops-evaluation-last-good-sha"
CONTAINER_NAME="devops-evaluation-app"
REDIS_CONTAINER="devops-evaluation-redis"
NETWORK="devops-evaluation-deploy"
APP_PORT=5000

if [ -f "$STATE_FILE" ]; then
    PREVIOUS_SHA=$(cat "$STATE_FILE")
else
    PREVIOUS_SHA=""
fi

docker network inspect "$NETWORK" > /dev/null 2>&1 || docker network create "$NETWORK"

if ! docker ps --format '{{.Names}}' | grep -q "^${REDIS_CONTAINER}$"; then
    docker rm -f "$REDIS_CONTAINER" 2>/dev/null || true
    docker run -d --name "$REDIS_CONTAINER" --network "$NETWORK" redis:7-alpine
fi

deploy_container() {
    local sha="$1"
    docker pull "$IMAGE:$sha"
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    docker run -d --name "$CONTAINER_NAME" \
        --network "$NETWORK" \
        -p "$APP_PORT:5000" \
        -e REDIS_HOST="$REDIS_CONTAINER" \
        -e COMMIT_SHA="$sha" \
        "$IMAGE:$sha"
}

echo "Deploiement de $IMAGE:$NEW_SHA"
deploy_container "$NEW_SHA"

READY=0
for i in 1 2 3; do
    echo "Verification post-deploiement, tentative $i"
    if curl -sf "http://localhost:$APP_PORT/health" > /dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 5
done

if [ "$READY" -ne 1 ]; then
    echo "ECHEC : /health ne repond pas apres 3 tentatives"

    if [ -n "$PREVIOUS_SHA" ]; then
        echo "ROLLBACK vers $IMAGE:$PREVIOUS_SHA"
        deploy_container "$PREVIOUS_SHA"
    else
        echo "Aucun deploiement precedent connu, pas de rollback possible"
    fi
    exit 1
fi

echo "$NEW_SHA" > "$STATE_FILE"
echo "Deploiement reussi : $NEW_SHA est maintenant actif"
