# Environnements

| Environnement | Usage | Documentation API | Secrets |
|---|---|---|---|
| development | travail local | activée | fichier `.env` local |
| test | tests automatisés | activée | valeurs éphémères |
| staging | recette | activée selon accès réseau | gestionnaire de secrets |
| production | utilisateurs | désactivée | gestionnaire de secrets |

Le déploiement continu est volontairement verrouillé jusqu'au choix de l'hébergeur.
Le workflow CD manuel rend ce garde-fou visible sans publier d'artefact.
