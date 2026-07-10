# YeliSport

Monorepo de la plateforme YeliSport.

## Architecture

- `apps/mobile` : application Flutter.
- `services/api` : API FastAPI.
- `services/ai` : services et pipelines IA.
- `database` : schémas, migrations et objets PostgreSQL.
- `supabase` : configuration locale Supabase.
- `api` : contrat OpenAPI et exemples d'échange.
- `infrastructure` : conteneurs, proxy, observabilité et IaC.
- `docs` : documentation technique et opérationnelle.

## Démarrage local

1. Copier `.env.example` vers `.env`.
2. Lancer `docker compose up --build`.

## Services locaux

- API : `http://localhost:8080/api/v1/health`
- Documentation API : `http://localhost:8000/docs`
- Service IA interne : `http://localhost:8001/ai/v1/health`
- PostgreSQL : `localhost:5432`

## Commandes

```bash
make bootstrap  # prépare la configuration locale
make up         # démarre les services
make test       # lance les tests Python et, si disponible, Flutter
make lint       # lance Ruff, Mypy et, si disponible, Flutter Analyze
```

La semaine 1 fournit un socle exécutable et observable. Les fonctionnalités métier
sont développées à partir de la semaine 2 du plan produit.
