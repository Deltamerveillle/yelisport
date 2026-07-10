# Service IA

Le service IA est un composant interne sans accès direct depuis le mobile. Son API
est versionnée sous `/ai/v1`. Les fournisseurs externes seront cachés derrière
`providers/base.py`, afin que les services métier ne dépendent pas d'un fournisseur.

Aucun cas d'usage IA n'est implémenté pendant la semaine 1. Son choix et ses métriques
d'acceptation doivent précéder tout entraînement ou appel à un modèle externe.
