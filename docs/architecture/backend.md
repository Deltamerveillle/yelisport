# Backend

L'API suit le flux `endpoint -> service -> repository -> modèle -> PostgreSQL`.
Les endpoints traduisent HTTP, les services portent les cas d'usage et les repositories
isolent la persistance. Les schémas Pydantic forment le contrat public; les modèles
SQLAlchemy ne doivent jamais être retournés directement.

Le point de santé `/api/v1/health` ne dépend pas de la base et sert de liveness probe.
Une readiness probe vérifiant les dépendances sera ajoutée avec la couche de données.
