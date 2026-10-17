# FREE TEST PILOT V1

Pilote/test interne en attendant le PSP réel. Ce mécanisme crée un véritable
abonnement `trialing`, **jamais une confirmation de paiement**. Il ne crée aucune
`PaymentTransaction`, ne contacte aucun PSP et ne renouvelle rien automatiquement.
YELENI Pay Gateway et `PaymentService.confirm_verified_payment()` restent inchangés.

## Activation

Configuration serveur (également transmise au service API par Docker Compose) :

```dotenv
APP_ENV=development
SMS_FREE_TEST_PILOT_ENABLED=true
SMS_FREE_TEST_PILOT_PLAN_CODE=monthly
SMS_FREE_TEST_PILOT_DURATION_DAYS=7
```

Le flag est désactivé par défaut. Seuls development/test/staging sont autorisés ;
production est toujours refusé même avec le flag activé. La configuration réelle
n'est pas activée par ce changement. Le plan doit exister dans
`SMS_COMMERCIAL_PLANS` et avoir `priority_visibility=false`, sinon refus 503.
Utiliser le code exact du catalogue déployé : si celui-ci utilise `sms_monthly`
plutôt que `monthly`, configurer `SMS_FREE_TEST_PILOT_PLAN_CODE=sms_monthly`.
Aucun alias implicite ni plan commercial nouveau n'est créé.
La durée est bornée à 1–30 jours. Les prix et durées commerciales restent inchangés.

Appeler `POST /api/v1/subscriptions/me/trial` avec le Bearer token existant,
sans corps. Aucun identifiant utilisateur, montant, durée ou entitlement client
n'est utilisé. L'identité est celle du compte authentifié local actif.
Réponse 200 : `SubscriptionResponse`. Consulter ensuite `/me/access` via le moteur
`SubscriptionService` habituel pour obtenir les vrais entitlements du catalogue.
Aucun ranking/scoring sportif n'est modifié.

## Persistance et transactions

- Provider réservé : `internal_free_test_pilot`, conservé dans l'historique quel
  que soit le statut ultérieur. Ne pas supprimer ces lignes ni modifier ce marqueur.
- Dates UTC timezone-aware ; durée calculée uniquement côté serveur.
- Retry pendant le trial : même ID et mêmes dates, sans prolongation.
- Trial expiré, annulé ou remplacé : 409 `trial_already_used` définitivement pour
  ce compte. L'expiration des droits utilise le moteur existant, sans job dédié.
- Abonnement active/trialing non expiré (y compris sans date de fin) : 409
  `subscription_already_current`, sans modification des droits existants.
- Toutes les anciennes lignes active/trialing expirées passent à `replaced`
  avant la création du trial, dans la même transaction.
- Le contrôleur sérialise la réponse puis commit ; toute erreur fait rollback.

Aucune migration nécessaire : migration 0007 et modèle existants fournissent les
colonnes provider/statut/périodes timezone-aware et l'historique par utilisateur.
Les index user_id/status sont non uniques ; il n'existe pas de contrainte
one-time/current. Le service prend donc un verrou PostgreSQL transactionnel
`ACCESS EXCLUSIVE` sur subscriptions **avant toute lecture d'abonnement**.
Il sérialise les activations et attend les lecteurs/rédacteurs existants, y compris
le service de paiement inchangé. Une preuve mémoire ou un simple contrôle sans
verrou ne suffirait pas. Les sessions utilisent l'isolation PostgreSQL habituelle
READ COMMITTED ; le service doit être appelé dans une transaction courte, comme
le fait cet endpoint.

## Limites du pilote

Le verrou est global : les lectures/écritures d'abonnements peuvent attendre pendant
l'activation. À réserver au faible volume V1, pas à un lancement massif. Pour un
volume supérieur, prévoir une stratégie commune de verrouillage avec le paiement.
L'unicité est garantie par ce chemin d'activation et l'historique conservé, pas par
une nouvelle contrainte DB : un administrateur SQL peut effacer cette preuve.
La règle est par compte utilisateur, pas par personne physique (multi-comptes).
Le catalogue reste la source des droits : ses modifications affectent les essais
comme les abonnements existants. Aucun écran mobile d'activation n'est ajouté.

## Validation

Tests dédiés : `tests/services/test_free_test_pilot_service.py`,
`tests/api/test_free_test_pilot.py`, `tests/test_free_test_pilot_postgres.py`.
Les tests PostgreSQL réutilisent la fixture existante avec des schémas temporaires
isolés et nécessitent `SMS24_MIGRATION_TEST_DATABASE_URL`. Aucune donnée métier de
la base de développement n'est modifiée par ces tests.
