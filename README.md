# devops-evaluation

Pipeline complet du code jusqu'au deploiement : une petite API Flask, conteneurisee,
avec integration continue, livraison continue vers un registry et deploiement reel,
et une stack d'observabilite Prometheus.

## Lancer le projet en local

Avec Docker (recommande, lance l'app + Redis + Prometheus en une commande) :

```bash
docker compose up -d --build
```

- Application : http://localhost:5000
- Prometheus : http://localhost:9090

Sans Docker, pour lancer juste l'app en local (necessite un Redis sur localhost:6379) :

```bash
cd app
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
REDIS_HOST=localhost python app.py
```

## Endpoints

| Endpoint | Description |
|---|---|
| `/health` | Verifie la connexion a Redis, renvoie 503 si indisponible |
| `/status` | Nom du service, version, SHA du commit deploye |
| `/visits` | Compteur de visites, stocke dans Redis |
| `/simulate-error` | Renvoie systematiquement une erreur 500, pour tester l'alerting |
| `/metrics` | Metriques au format texte Prometheus |

## Tests

```bash
cd app
REDIS_HOST=localhost REDIS_PORT=6379 pytest -v
```

Les tests utilisent un vrai serveur Redis (pas de mock) : ils verifient un comportement
reel de l'application (code de retour HTTP, incrementation persistee dans Redis).

## CI / CD

- `.github/workflows/ci.yml` : sur chaque pull request et push vers `main`. Quatre jobs :
  `lint` (flake8 + yamllint), `test` (matrice Python 3.11/3.12, service Redis reel,
  cache pip, rapports de tests publies en artefacts), `build` (verifie que l'image
  Docker se construit), `ci-ok` (check final requis pour merger sur `main`).
- `.github/workflows/cd.yml` : sur push vers `main` (apres CI verte) ou declenchement
  manuel (`workflow_dispatch`, input `environment=production`). Construit l'image,
  la pousse sur GitHub Container Registry avec trois tags (`latest`, SHA court,
  version semver lue dans `VERSION`), puis la deploie sur la machine cible via un
  runner self-hosted.
- L'installation Python + dependances est factorisee dans une action locale
  (`.github/actions/setup-python-env`), appelee par les jobs `lint` et `test`.

## Deploiement

`deploy/deploy.sh` recupere la nouvelle image, demarre le conteneur, verifie
`/health` avec 3 tentatives espacees de 5 secondes. Si le healthcheck echoue,
le script revient automatiquement sur le dernier SHA deploye avec succes
(`deploy/last_good_sha`) et le job `deploy` echoue.

Le job `deploy` tourne sur un runner GitHub Actions self-hosted installe sur
la machine cible (`runs-on: self-hosted`), uniquement sur push vers `main` ou
via `workflow_dispatch`.

## Observabilite

Prometheus scrape `/metrics` toutes les 5 secondes (`observability/prometheus/prometheus.yml`).

Metriques exposees :

- `http_requests_total{method, endpoint, code}` : compteur de requetes recues
- `http_request_duration_seconds{method, endpoint}` : histogramme de latence par route
- `app_build_info{version, commit_sha}` : jauge indiquant la version/le commit deployes

Regles d'alerte (`observability/prometheus/alert_rules.yml`) :

- `TauxErreurEleve` : taux d'erreurs 5xx au-dessus de 5 % pendant plus de 30 secondes
  (seuil bas car une API ne devrait presque jamais repondre en erreur ; 30s evite
  qu'un pic isole ne declenche une fausse alerte)
- `LatenceDegradee` : p95 au-dessus de 500 ms pendant plus d'une minute (calcule a
  partir des buckets de l'histogramme via `histogram_quantile` ; une minute laisse
  le temps a un pic ponctuel de retomber avant de declencher)

## Structure du depot

```
app/                              application Flask + tests + dependances
Dockerfile                        build multi-stage, utilisateur non-root
docker-compose.yml                web + redis + prometheus
deploy/deploy.sh                  deploiement + verification + rollback
observability/prometheus/         config de scrape et regles d'alerte
.github/actions/setup-python-env/ action composite reutilisable
.github/workflows/ci.yml          integration continue
.github/workflows/cd.yml          livraison et deploiement continu
VERSION                           version semver courante
```
