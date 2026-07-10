# Démarrage local

## Prérequis

- Docker avec Docker Compose v2;
- Flutter stable pour exécuter le client et ses tests localement;
- Make et Bash.

## Installation

```bash
make bootstrap
make up
curl http://localhost:8080/api/v1/health
```

Le bootstrap crée `.env` depuis `.env.example` sans écraser un fichier existant.
Les valeurs `change-me` ne doivent jamais être utilisées hors développement.

## Qualité

`make test` exécute les suites API, IA et Flutter. `make lint` lance Ruff et Mypy
pour l'API, Ruff pour l'IA et Flutter Analyze. La CI reproduit ces contrôles.
