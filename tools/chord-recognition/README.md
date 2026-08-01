# mvr-app
MVR - Prompteur d'accords pour musiciens

## ⚠️ RÈGLE DE DÉPLOIEMENT — À NE JAMAIS ENFREINDRE

**Toute mise à jour de l'application passe OBLIGATOIREMENT par un commit sur ce dépôt GitHub (branche `main`). Ne JAMAIS utiliser "Create deployment" (dépôt manuel d'un zip) directement sur le tableau de bord Cloudflare Pages.**

### Pourquoi cette règle existe

Une mise à jour a été déposée directement sur Cloudflare via "Create deployment" plutôt que via un commit GitHub. Le site s'est mis à jour correctement — mais **GitHub, lui, n'a pas bougé**. Résultat : GitHub racontait une version de l'app différente de celle réellement en ligne, sans que personne ne s'en aperçoive. Une session de travail ultérieure s'est basée sur GitHub en pensant que c'était la source de vérité, a construit une nouvelle fonctionnalité par-dessus, et a fini par **redéployer une version de l'app ayant perdu plusieurs mois de fonctionnalités** (synchronisation live, recherche de grille par IA, import Guitar Pro, etc.) — jusqu'à ce que ce soit repéré et corrigé à la main à partir d'une ancienne sauvegarde de page.

### Ce qu'il faut faire à la place

Cloudflare Pages est **déjà connecté à ce dépôt GitHub** et se redéploie automatiquement à chaque commit sur `main` — il n'y a donc jamais besoin d'utiliser "Create deployment" à la main. Pour toute mise à jour :

1. Modifier `index.html` (et `service-worker.js` si besoin d'incrémenter `APP_VERSION`, ce qui déclenche la bannière de mise à jour chez les utilisateurs)
2. Déposer les fichiers modifiés sur GitHub (via l'interface web : "Add file" -> "Upload files", en écrasant les fichiers existants au même chemin)
3. Cloudflare se redéploie automatiquement - vérifiable dans l'onglet "Deployments" du projet mvr-app sur Cloudflare, un nouveau déploiement doit apparaître avec la source main

### Avant de construire quoi que ce soit sur la base de GitHub

Si un doute existe sur la fraîcheur de ce que contient GitHub par rapport à ce qui est réellement en ligne (mvr-app.pages.dev), **vérifier d'abord** en comparant les deux plutôt que de supposer qu'ils sont synchronisés. En cas de divergence, la version réellement en ligne (Cloudflare) fait foi, pas GitHub - et il faut la remettre sur GitHub avant de continuer.

## Dossiers du dépôt

- `index.html`, `service-worker.js` - l'application elle-même
- `tools/chord-recognition/` - outil de recherche Python, autonome, hors de l'app (voir son propre README)
