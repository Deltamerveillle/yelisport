# Modèle de données — étape 2

Supabase Auth reste la source de vérité des identités. Lorsqu'une ligne est créée
dans `auth.users`, le trigger `handle_new_auth_user` crée automatiquement :

- `public.users`, qui contient l'identité applicative minimale ;
- `public.profiles`, qui contient les données personnelles modifiables par le membre.

`public.sports` est le catalogue partagé des disciplines. Il est lisible par tout
utilisateur authentifié et administré uniquement avec la clé `service_role`.

Les trois tables ont la sécurité RLS activée. Un utilisateur ne peut lire que son
utilisateur et son profil, ni modifier les colonnes techniques. Les migrations sont
versionnées dans `supabase/migrations`; les modèles et la migration Alembic servent
à l'API FastAPI et aux déploiements PostgreSQL hors Supabase.

## Développement local

```bash
supabase start
supabase db reset
```

Reporter ensuite les valeurs affichées pour `API URL`, `anon key` et `service_role`
dans `.env`. L'API utilise `SUPABASE_ANON_KEY` pour les opérations utilisateur et
réserve `SUPABASE_SERVICE_ROLE_KEY` aux opérations d'administration.
