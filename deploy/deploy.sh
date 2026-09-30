#!/bin/bash
set -e

IMAGE="$1"
NEW_SHA="$2"
STATE_FILE="deploy/last_good_sha"
CONTAINER_NAME="devops-evaluation-app"
APP_PORT=5000

if [ -f "$STATE_FILE" ]; then
    PREVIOUS_SHA=$(cat "$STATE_FILE")
else
    PREVIOUS_SHA=""
fi

echo "Deploiement de $IMAGE:$NEW_SHA"
docker pull "$IMAGE:$NEW_SHA"

docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
docker run -d --name "$CONTAINER_NAME" \
    -p "$APP_PORT:5000" \
    -e COMMIT_SHA="$NEW_SHA" \
    "$IMAGE:$NEW_SHA"

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
        docker pull "$IMAGE:$PREVIOUS_SHA"
        docker rm -f "$CONTAINER_NAME"
        docker run -d --name "$CONTAINER_NAME" \
            -p "$APP_PORT:5000" \
            -e COMMIT_SHA="$PREVIOUS_SHA" \
            "$IMAGE:$PREVIOUS_SHA"
    else
        echo "Aucun deploiement precedent connu, pas de rollback possible"
    fi
    exit 1
fi

echo "$NEW_SHA" > "$STATE_FILE"
echo "Deploiement reussi : $NEW_SHA est maintenant actif"
