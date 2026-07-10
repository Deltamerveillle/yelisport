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

La semaine 1 fournit le socle exécutable et observable. L'étape 2 ajoute Supabase
Auth, les tables `users`, `profiles` et `sports`, leurs politiques RLS et les
migrations PostgreSQL. Voir `docs/database/data-model.md` pour le démarrage local.

## Application Flutter

L'application initialise Supabase Auth, conserve la session et transmet son jeton
Bearer à l'API pour charger le catalogue des sports. En développement local :

```bash
flutter run \
  --dart-define=SUPABASE_URL=http://localhost:54321 \
  --dart-define=SUPABASE_ANON_KEY=<anon-key> \
  --dart-define=API_BASE_URL=http://localhost:8080/api/v1
```

Sur l'émulateur Android, remplacer `localhost` par `10.0.2.2`.
