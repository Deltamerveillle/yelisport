# Application Flutter

Le client est organisé par fonctionnalité. Chaque fonctionnalité contient `data`,
`domain` et `presentation`. Riverpod gère l'état et l'injection, GoRouter la navigation,
et Dio les appels à l'API. Les URL et l'environnement sont injectés avec `--dart-define`.

Le client utilise Supabase uniquement pour l'identité et les capacités explicitement
autorisées. Il passe par FastAPI pour toute opération métier.
