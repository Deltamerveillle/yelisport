# Architecture générale

## Principes

YeliSport est un monorepo composé d'un client Flutter, d'une API métier FastAPI,
d'un service IA interne et de PostgreSQL. Nginx est le point d'entrée local.

```text
Flutter -> Nginx -> FastAPI API -> PostgreSQL
                         |
                         +------> FastAPI AI
```

## Décisions de la semaine 1

1. FastAPI est l'unique façade des opérations métier.
2. Supabase Auth est l'autorité d'identité; l'API valide les jetons et applique les autorisations.
3. Alembic est la source de vérité des migrations PostgreSQL.
4. Le service IA est privé et accessible uniquement depuis l'API.
5. Le contrat public est versionné sous `/api/v1`.
6. Les services propagent un identifiant de requête pour la traçabilité.

Les dossiers SQL hors Alembic accueillent des vues, fonctions et politiques complexes,
mais leur installation doit toujours être référencée par une migration Alembic.
