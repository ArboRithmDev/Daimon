# Daimon — Auto-update (cross-platform) — Design

**Date**: 2026-06-17
**Statut**: cadrage, prêt pour implémentation. Spec parapluie — un cycle par OS si besoin.
**Parent**: [Charte MVP V1](2026-06-12-v1-mvp-charter.md) (auto-update était hors-scope V1) + [Port Windows V2](2026-06-15-v2-windows-port-design.md).
**Modèle**: l'update engine de **SecondBrain Desktop** (`check_update` → download asset → install → version lue du disque, élévation, bootstrap-on-upgrade) — repris en *esprit*, adapté à l'architecture Daimon (voir §2).
**Cible**: que **tous les builds** (macOS .app, Windows bundle) intègrent l'auto-update de série.

---

## 1. Objet

Permettre à Daimon de **se mettre à jour seul** : détecter qu'une version plus récente existe, la télécharger, l'appliquer, redémarrer — sans que l'utilisateur réinstalle à la main. Objectif : moderniser la distribution et garantir que la flotte tourne une version récente (sécurité d'un outil qui voit et agit sur la machine = forte responsabilité, cf. §8).

---

## 2. Ce qu'on reprend de SecondBrain — et ce qui diffère

**Repris (l'esprit) :**
- `check_update` : compare la version **installée** à la dernière publiée ; décision pure.
- Pipeline download → install → restart.
- **Version lue du disque**, jamais d'un `__version__` figé à l'import (piège SecondBrain `desktop-engine-version-trap` : « Current » restait coincé après update). Recalculer après application.
- Gestion de l'**élévation** (écriture en zone protégée) et **bootstrap-on-upgrade** (l'installeur rafraîchit aussi la cible).

**Différence structurelle (décisive) :**
SecondBrain = *shell desktop + engine Python swappable* → update = `pip install` de l'engine dans `{install}/engine` (wheelhouse offline pinné). Daimon = **bundle figé monolithique** (PyInstaller : serveur MCP + tray + overlay, sans Python embarqué séparé). Donc :

> **L'update Daimon remplace le BUNDLE entier** (pas un sous-paquet pip). Pas de wheelhouse. La granularité = l'artefact de release (installeur Windows / .app macOS).

---

## 3. Architecture : cœur pur + adaptateurs OS

Comme `backends/` (perception/action), l'updater sépare un **cœur OS-agnostique** d'**adaptateurs plateforme** :

```
src/daimon/update/
  __init__.py        # façade : check() / available() / apply()
  core.py            # PUR : parse versions (semver), compare, décide ; aucun I/O OS
  source.py          # résout la dernière release + l'asset de CET OS (GitHub Releases)
  apply_macos.py     # swap du .app
  apply_win.py       # ré-exécution de l'installeur silencieux / swap du bundle
```

- `core.py` (pur, testable sans réseau/OS) : `is_newer(latest, current) -> bool`, sélection d'asset par OS/arch, schéma de manifeste.
- `source.py` : interroge l'**API GitHub Releases** du repo (public, AGPL) → tag `latest` + URL de l'asset correspondant à l'OS. Réseau isolé ici (mockable).
- `apply_*` : dispatch via le sélecteur existant (`backends`-style) sur `sys.platform`.

---

## 4. Source de mise à jour

- **GitHub Releases** du dépôt public Daimon (AGPL). `GET /repos/<owner>/<repo>/releases/latest` → `tag_name` (version) + `assets[]`.
- Convention d'asset par OS (à figer au packaging) :
  - Windows : `Daimon-<version>-setup.exe` (l'installeur Inno) **et** un `Daimon-<version>-win64.zip` (le bundle nu, pour le swap sans installeur). Plus un `SHA256SUMS`.
  - macOS : `Daimon-<version>.dmg` (déjà produit) + `SHA256SUMS`.
- **Manifeste** optionnel `latest.json` attaché à la release (version, url par OS, sha256, notes, minOS) — évite de parser l'API à chaque check et permet un canal stable. Recommandé.
- Pas d'infra serveur dédiée : GitHub Releases est le canal (gratuit, versionné, public).

---

## 5. Détection (check)

- **Version installée** lue du disque : la version *bakée* dans le bundle courant (`daimon.__version__` via `_FALLBACK_VERSION` du bundle figé — l'update remplace le bundle entier, donc le nouveau bundle porte la nouvelle version → cohérent, pas de piège). Recalculer après apply en relançant le process.
- **Déclencheurs** :
  - **Manuel** : entrée tray *« Check for updates »* (+ *« Update now »* si dispo).
  - **Auto périodique** : check au démarrage du tray puis toutes les N heures (config `update.yaml` : `enabled`, `channel`, `interval_hours`, `auto_apply`). **Opt-in** pour `auto_apply` (par défaut : notifie, n'applique pas sans clic — un outil hands+eyes ne se met pas à jour en silence par défaut).
- Le **check est passif** (lecture HTTP seule), jamais bloquant pour la perception/action.

---

## 6. Application par OS

### 6.1 Windows
Le bundle vit dans le dossier d'install (cf. §9). Deux voies :
- **Voie installeur (recommandée)** : télécharger `Daimon-<v>-setup.exe`, vérifier le SHA256, lancer en **silencieux** (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`). L'installeur Inno gère le remplacement + raccourcis. Per-user (§9) → **pas d'UAC**.
- **Voie swap (sans installeur)** : télécharger le `.zip`, extraire dans un dossier temporaire, puis remplacer `{install}` atomiquement (rename ancien → `.old`, déplacer neuf, supprimer `.old` au prochain démarrage).

> **Problème central — fichiers verrouillés.** Les clients MCP lancent `daimon-mcp.exe serve` : ces process **verrouillent le bundle**, on ne peut pas l'écraser à chaud. Stratégie : un **updater détaché** (petit process séparé, hors du dossier d'install) qui (1) demande au tray de **quitter**, (2) **arrête tous les `daimon-mcp.exe` / `Daimon.exe`** (comme l'auto-kill du build), (3) applique (installeur silencieux ou swap), (4) **relance le tray**. Les clients **re-spawnent** `daimon-mcp.exe` au prochain appel (nouveau bundle). Mirroir exact de ce que fait déjà `build_windows.ps1` (stop Daimon.exe avant écriture).

### 6.2 macOS
- Télécharger le `.dmg` (ou un `.zip` du `.app`), vérifier le SHA256, monter/extraire, **remplacer `/Applications/Daimon.app`** (l'app n'auto-verrouille pas comme un exe Windows ; quitter le tray d'abord). Relancer.
- Pas de notarisation requise pour l'update lui-même (l'app cible est déjà signée+notarisée à la prod).

### 6.3 Commun
- Téléchargement dans un dossier temp utilisateur, **vérification SHA256 obligatoire avant apply** (cf. §8), apply, relance, **re-lecture de la version** pour confirmer.

---

## 7. Le redémarrage propre

- Le **tray** est le pilote de l'update (process résident, singleton). Il orchestre : check → notifie → (sur accord ou `auto_apply`) lance l'updater détaché → quitte → est relancé par l'updater.
- Les **serveurs MCP** (`daimon-mcp.exe`) sont **éphémères** (lancés/tués par les clients) : l'updater les arrête ; les clients les relancent à la demande sur le nouveau bundle. Pas de coordination MCP nécessaire.
- L'**updater** doit s'exécuter **hors** du dossier qu'il remplace (copié en temp) pour ne pas se verrouiller lui-même.

---

## 8. Sécurité (non négociable)

Daimon **voit et agit** sur la machine → un canal d'update compromis = exécution de code arbitraire avec ses privilèges. Donc :
- **Vérification d'intégrité obligatoire** : SHA256 de l'asset comparé au `SHA256SUMS`/manifeste de la release **avant** tout apply. Échec → abandon, pas d'apply.
- **HTTPS strict** vers GitHub (pas de redirection non-TLS).
- **Signature** : quand un cert sera dispo (SignPath Foundation, AGPL — cf. discussion 2026-06-17), vérifier la **signature Authenticode (Windows) / notarisation (macOS)** de l'artefact en plus du hash. D'ici là, le hash depuis la release GitHub (HTTPS, dépôt contrôlé) est le plancher.
- **Opt-in pour l'auto-apply** : par défaut Daimon **notifie**, n'applique qu'au clic. `auto_apply=true` est un choix explicite de l'utilisateur.
- **Downgrade refusé** par défaut (n'appliquer que si strictement plus récent), sauf override manuel.
- L'update **n'élève jamais** le plafond moteur ni ne touche au consentement L4 (orthogonal à la sécurité moteur).

---

## 9. Emplacement d'installation (pré-requis pour update sans friction)

Aujourd'hui l'installeur cible `{autopf}\Daimon` (**Program Files → admin → UAC à chaque update**). Pour un auto-update fluide :

> **Recommandation : install per-user par défaut** — `{localappdata}\Programs\Daimon` (`{userpf}` Inno). Écriture sans élévation → l'update s'applique **sans UAC**. (Garder une option « tous les utilisateurs » → Program Files, qui elle demandera l'élévation à l'update.)

À acter dans `daimon.iss` (`DefaultDirName={userpf}\Daimon`, `PrivilegesRequired=lowest`). macOS `/Applications` reste standard (remplacement avec autorisation au besoin).

---

## 10. UI & config

- **Tray** : `Check for updates`, `Update now` (si dispo, avec version cible), une ligne d'état `Up to date` / `Update available: vX.Y.Z`.
- **Config** `update.yaml` (per-user data dir) : `enabled` (def true), `channel` (`stable`), `interval_hours` (def 24), `auto_apply` (def false), `allow_prerelease` (def false).
- **Notifications** : toast natif optionnel « Daimon vX.Y.Z disponible ».

---

## 11. Fichiers livrés (cible)

```
src/daimon/update/
  core.py            # pur : semver compare, sélection asset, schéma manifeste (+ tests)
  source.py          # GitHub Releases / latest.json → (version, asset_url, sha256)
  __init__.py        # check() -> UpdateInfo ; apply(info) -> dispatch OS
  apply_win.py       # updater détaché : stop process → installeur silencieux/zip swap → relance
  apply_macos.py     # swap du .app
config/update.example.yaml
src/daimon/tray/...  # entrées menu + état (réutilise menu_model/state purs)
build/                # publication des assets + SHA256SUMS + latest.json par release
src/daimon/setup/...  # (option) install per-user dans daimon.iss
```

Cœur (`core.py`) testable sans réseau (mocks) ; `source.py` mockable ; `apply_*` validés par smoke (un vrai cycle d'update sur une release de test).

---

## 12. Phases d'implémentation

| Phase | Contenu | Acceptation |
|-------|---------|-------------|
| **U0** | `update/core.py` (semver compare, sélection asset) + `source.py` (latest.json/API) | tests purs : détecte plus récent / égal / plus ancien, choisit le bon asset OS |
| **U1** | Vérif intégrité (SHA256) + download robuste (temp, reprise, HTTPS) | hash KO → abandon ; download OK → fichier vérifié |
| **U2 Win** | `apply_win` (updater détaché : stop process → installeur silencieux / zip swap → relance tray) + install per-user dans `.iss` | un cycle réel met à jour le bundle sans UAC, clients re-spawnent le neuf |
| **U3 macOS** | `apply_macos` (swap `.app`) | un cycle réel remplace Daimon.app |
| **U4 UI** | entrées tray + `update.yaml` + auto-check périodique (opt-in apply) | check au démarrage + manuel ; notifie ; n'applique qu'au clic par défaut |
| **U5 Release** | pipeline de publication des assets + `SHA256SUMS` + `latest.json` à chaque release (macOS DMG + Windows setup/zip) | une release publie tous les assets attendus |

---

## 13. Invariants

- **Cœur pur OS-agnostique** : `core.py` (compare/décision) sans I/O ni dépendance OS ; adaptateurs `apply_*` par plateforme (même doctrine que `backends/`).
- **Intégrité avant tout** : aucune application sans vérification SHA256 (et signature quand dispo). Un outil hands+eyes ne tire pas de code non vérifié.
- **Version lue du disque** post-update (pas de littéral figé en cache) — leçon SecondBrain.
- **Pas d'auto-apply silencieux par défaut** : notifier, appliquer sur accord (ou opt-in explicite).
- **Updater hors du dossier remplacé** + arrêt des process qui verrouillent (les clients re-spawnent).
- **Orthogonal à la sécurité moteur** : l'update ne touche ni au plafond ni au consentement L4.

---

## 14. Hors-scope (V-update 1)

- Delta/patch binaire (on remplace le bundle entier).
- Canaux multiples (beta/nightly) au-delà de `allow_prerelease`.
- Rollback automatique multi-versions (on garde `.old` une génération, pas un historique).
- Serveur d'update propriétaire (GitHub Releases suffit).
- Signature obligatoire **tant qu'aucun cert** n'est disponible (le hash HTTPS est le plancher ; signature ajoutée dès SignPath Foundation).
