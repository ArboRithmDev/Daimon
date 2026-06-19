# Daimon — Cadrage des axes de travail

> **But du document** : transmettre le contexte complet pour reprendre le travail (notamment sur Mac) après le port Windows et le premier pilotage en conditions réelles. Chaque axe = problème → objectif → design → fichiers → critères d'acceptation → dépendances.
>
> **Date** : 2026-06-19 · **Branche** : `feat/windows-port` · **Source terrain** : rapport d'usage 2026-06-19 (pilotage WinDev multi-écrans).

---

## 0. État du repo & reprise

- **Branche** : `feat/windows-port` (poussée sur `origin`, ArboRithmDev/Daimon, sync 0/0). Pas de PR (Ben travaille seul).
- **Dernier jalon** : port Windows feature-complete + durci + auto-update U0–U5. Exe figé fonctionnel (`Daimon.exe` tray + `daimon-mcp.exe` console serve), bundle 152 MB, MCP stdio prouvé (21 tools).
- **Reprise Mac** :
  - Tests : `pytest` (le cœur pur + les chemins darwin tournent sur Mac ; les jumeaux `*_win` sont skippés hors win32). Cible verte avant/après chaque axe.
  - Env Windows (pour parité) : venv `.venv-win` Python 3.13 (gitignored). Sur Mac : venv standard pyobjc.
  - Doctrine de port : **on écrit des adaptateurs, on ne réécrit jamais le cœur.** Tout axe ci-dessous se découpe en (a) cœur pur OS-agnostique + (b) jumeaux backend macOS **et** Windows.

## 1. Contexte

Le port Windows fonctionne. Le **premier pilotage réel** (2026-06-19, Claude Opus via Claude Code, Windows 3 écrans, lecture de code WinDev) a **réussi le métier** mais coûté **~6 itérations** au seul calibrage des coordonnées. Rapport complet archivé :
`10-episodes/projects/daimon/archives/2026-06-19-15h49-...-pilotage-windev-multi-crans--propositions-calibrage.md` (frictions F1–F5, propositions P1–P7).

**Verdict** : le calibrage de l'espace de coordonnées est aujourd'hui **à la charge du pilote IA**, qui le réinvente par tâtonnement à chaque session/environnement. C'est le frein n°1 à un usage fluide et à la délégation.

## 2. Invariants à respecter (non négociables)

Tout axe doit préserver la doctrine Daimon :

1. **Cœur pur OS-agnostique** séparé des adaptateurs plateforme ; chaque organe livre un `Fake*` → cœur testé sans l'OS.
2. **Parité Mac/Windows** : toute nouvelle capacité backend a ses deux jumeaux (`capture/screen.py` Quartz + `capture/screen_win.py` GDI/Win32). macOS ne régresse jamais (chemins darwin + tests darwin inchangés).
3. **Sécurité inchangée** : redaction secrets (champs secure + apps déclarées noircis avant de servir) reste devant toute capture ; plafond Mains L0–L4 appliqué par Daimon, jamais par le client.
4. **Sortie bornée** : les sens restent plafonnés (max_depth/region/max_width) pour le coût token.
5. **Config idempotente/réversible/sauvegardée** : tout nouvel état persisté (profils de calibrage) suit la même discipline que la registration clients.

---

## AXE 1 — Espace de coordonnées explicite & déterministe `[PRIORITÉ HAUTE]`

**Problème (F1)** : `vue_snapshot` retourne une **image nue**, sans le contrat coord-space. Le pilote doit cumuler deux transformations à l'aveugle :
- (a) **downscale** : `max_width=1600` sur un écran 1920 → échelle 0.8333, facteur 1.2 oublié à la reprojection ;
- (b) **offset multi-écrans** : un écran à gauche du principal a des coords globales **négatives** (-1920 en X) ; le snapshot est en px **locaux**, `main_click` veut des px **globaux**.

Formule que le pilote a dû dériver par 3 clics ratés : `global_x = image_x × (1920/1600) − 1920`. Inacceptable.

**État du code (la donnée existe déjà, non surfacée)** :
- `capture/screen.py` — `Display(index, display_id, width, height, is_main)` : **pas d'origine, pas de scale**. macOS : origine via `CGDisplayBounds(did).origin`, DPI via le display mode.
- `capture/screen_win.py` — `GetMonitorInfo[...]["Monitor"]` = `(left, top, right, bottom)` : **l'origine `left/top` est déjà lue**, juste pas remontée dans `Display`.
- `Frame(image, width, height, display_index, frontmost_bundle_id)` : ne porte ni `display_origin`, ni `image_scale` (le ratio est calculé dans `capture_display` puis **jeté**).

**Objectif** : rendre image→global déterministe, calculable sans deviner.

**Design** :
1. **Enrichir `Display`** (les 2 backends) : ajouter `origin_x`, `origin_y`, et `scale`/`dpi` par écran. macOS `CGDisplayBounds` + mode ; Windows monitor rect + `GetDpiForMonitor`.
2. **`vue_displays`** retourne `{index, width, height, is_main, origin:{x,y}, dpi}`.
3. **Enrichir `Frame`** : `display_origin:{x,y}`, `physical_size:{w,h}`, `image_size:{w,h}`, `image_scale`, `region`.
4. **`vue_snapshot` retourne le contrat coord-space avec l'image** (P1). Contrainte MCP : un tool renvoie aujourd'hui un `MCPImage` seul. → renvoyer une **liste de blocs de contenu** (un bloc texte JSON `coord_space` + le bloc image), ou un champ structuré accompagnant l'image. Décider le format (voir Annexe A).
5. **Clics display-relatifs** (P2) : `main_click` (et toutes les Mains positionnelles) acceptent un `display` optionnel + coords **locales** à cet écran ; Daimon applique offset+échelle en interne (il connaît la topologie). Le client ne manipule plus jamais de coords globales négatives.
6. **Helper de résolution** (P3) : `vue_resolve(display, image_x, image_y) -> {global_x, global_y}` (et inverse). Permet à un pilote « faible » de cliquer juste sans aucun calcul.

**Fichiers** : `capture/screen.py`, `capture/screen_win.py`, `senses/vue.py`, `motor/actions.py` (signatures Mains + résolution), `senses/base.py` si besoin. Backends `Fake*` mis à jour.

**Critères d'acceptation** :
- `vue_displays` expose origine + dpi par écran (Mac & Win).
- `vue_snapshot` renvoie un contrat coord-space exploitable tel quel.
- `main_click(display=k, x, y)` en coords locales atteint le bon pixel global, écran négatif inclus.
- `vue_resolve` round-trip exact. Tests purs sur la math de reprojection (offset + scale + region) sans OS.

**Dépendances** : aucune (socle des axes 2, 3, 5). **Effort** : moyen.

---

## AXE 2 — Calibrage persisté par profil d'environnement `[PRIORITÉ HAUTE]`

**Problème (F5 + demande Ben)** : la topologie change selon le lieu (bureau 3 écrans / portable seul / télétravail ultralarge). Un facteur unique ne suffit pas (DPI mixte). Recalibrer à chaque session = friction permanente.

**Objectif** : capturer la topologie une fois par environnement, la persister sous un **profil nommé**, et **auto-matcher** au démarrage.

**Design (P4)** :
- **`vue_calibrate`** : capture la topologie complète (origines, tailles, DPI par écran, arrangement) → l'enregistre dans un profil nommé (`bureau-3-ecrans`, `portable-seul`, `teletravail-ultralarge`…).
- **Signature d'environnement** : hash déterministe de la disposition (nb écrans + résolutions + positions + DPI) → match auto du profil au boot ; si inconnu → proposer d'en créer un.
- **Persistance** : un store de profils suivant la doctrine config (idempotent/réversible/sauvegardé), dans le data dir per-OS (`%APPDATA%` / `~/Library` / XDG — déjà câblé en W4).
- Le profil actif alimente la résolution coords de l'AXE 1 (offset/scale par écran lus depuis le profil plutôt que re-sondés).

**Fichiers** : nouveau module `senses/calibration.py` (cœur pur : signature, match, modèle de profil) + intégration `vue.py` + store dans le data dir (réutiliser le helper `_app_support`/userdata de W4). `Fake` pour les tests.

**Critères d'acceptation** : capture → persiste → relance → auto-match par signature ; profil inconnu détecté ; round-trip coords via profil. Tests purs sur signature + match (pas d'écran réel).

**Dépendances** : AXE 1 (contrat coord-space). **Effort** : moyen.

---

## AXE 3 — Fallback Vue-only `find(text) → coords` `[PRIORITÉ HAUTE]`

**Problème (F2)** : `touche_tree`/`touche_probe` **muets sur WinDev** (`{"summary":"None"}`, `PaneControl` générique). Les apps Win32 anciennes / custom-drawn / Electron exposent mal UIA. Sans arbre a11y, le pilote retombe sur des coords pixel pures → aggrave F1.

**Objectif** : pouvoir cliquer un libellé **visible** sans arbre d'accessibilité.

**Design (P5)** :
- Documenter explicitement le **mode « Vue-only »** (quand Touché rend vide/générique).
- Fournir **`find(text)`** : localise un libellé visible (OCR / template-match) sur un snapshot et **retourne des coords cliquables** (déjà résolues en global via AXE 1). Contourne d'un coup F2 (a11y absente) **et** F1 (plus de calcul client).
- **Garde-fou doctrine** : Daimon « ne fait pas de vision/OCR » est un principe sur l'**interprétation** ; un `find(text)` localisateur (retourne une position, pas une compréhension) est compatible — **à acter explicitement** comme exception cadrée (localisation ≠ interprétation). Décision à confirmer avec Ben.
- Choix techno OCR à trancher (Tesseract local vs autre) en gardant le « local-first / pas de réseau ».

**Fichiers** : nouveau `senses/find.py` (cœur : matching sur image + reprojection coords) + tool dans `vue.py` ou un sens dédié. Backend OCR injecté (Fake pour tests).

**Critères d'acceptation** : sur un snapshot donné, `find("Etat_FACTURECLIENT")` retourne des coords qui, passées à `main_click`, atteignent le libellé. Test pur avec image fixture + OCR fake.

**Dépendances** : AXE 1 (reprojection). **Effort** : moyen-élevé (dépend du choix OCR).

---

## AXE 4 — Robustesse Mains `[PRIORITÉ MOYENNE]`

**Problèmes (F3, F4)** :
- F3 : clic sur onglet **avant** `main_activate` = no-op silencieux (fenêtre pas frontmost) ; aucun retour ne distingue « clic émis sans effet » de « clic réussi ». Le pilote croit à une erreur de coords.
- F4 : `main_navigate(scroll_y)` scrolle « la vue focalisée » (dernier élément touché = arbre projet) au lieu de l'éditeur ; ambigu sur fenêtre multi-panneaux.

**Objectif** : actions Mains prévisibles et auto-diagnostiquées.

**Design (P7)** :
- **Auto-focus** : `ensure_focus` (flag ou implicite) → `activate` la fenêtre cible avant une Main positionnelle. Tue F3.
- **Retour d'effet** : distinguer « action émise » de « effet observable » (ex. diff léger de snapshot avant/après), au minimum un avertissement « fenêtre non frontmost ».
- **`main_navigate` ciblé** : cible explicite (`window`/`point`) plutôt que « vue focalisée ». Tue F4.

**Fichiers** : `motor/actions.py`, `motor/actuator_win.py` + `actuator` macOS, `prober` (pour la fenêtre cible). Respecter le re-probe avant action et le plafond L.

**Critères d'acceptation** : clic sans focus préalable → soit auto-focus, soit avertissement explicite ; `main_navigate(window=...)` agit sur la bonne vue. Tests sur les seams (pas d'input réel).

**Dépendances** : indépendant (synergie AXE 1). **Effort** : moyen.

---

## AXE 5 — Délégation à un petit modèle via profil `[PRIORITÉ MOYENNE]`

**Problème / opportunité (P6)** : aujourd'hui le pilotage exige du raisonnement géométrique (le gros modèle brûle des itérations + des screenshots dans son contexte).

**Objectif** : rendre la délégation Daimon viable — un orchestrateur (gros modèle) passe juste un **nom de profil** ; un sous-agent **petit modèle rapide (Haiku)** pilote mécaniquement et ne renvoie que le **texte extrait**.

**Design** : avec AXE 1 (coords déterministes) + AXE 2 (profil persisté), le sous-agent charge les coords sans calcul géométrique, pilote l'UI, renvoie le texte. Screenshots hors du contexte de l'orchestrateur. Documenter le **pattern d'orchestration** (contrat d'entrée : profil + objectif ; sortie : texte).

**Fichiers** : surtout de la **doc/recette** (pas forcément du code Daimon) + éventuellement un helper exposant le profil actif aux sous-agents.

**Critères d'acceptation** : une recette reproductible où Haiku, muni d'un profil, clique juste et extrait du texte sans raisonner sur la géométrie.

**Dépendances** : AXE 1 + AXE 2 (+ AXE 3 pour apps sans UIA). **Effort** : faible (capitalise sur 1/2/3).

**Livré** : recette d'orchestration `docs/delegation-haiku-via-profil.md` (contrat d'entrée profil+objectif → sortie texte, gabarit de prompt sous-agent, exemple WinDev, frontière de contexte) + helper `vue_profile_brief(expected)` (boot brief GO/NO-GO du sous-agent ; cœur pur `active_profile_brief`, tests `tests/test_profile_brief*.py`).

---

## AXE 6 — Antigravity (AGY) enablement `[PRIORITÉ BASSE — EN PAUSE]`

**État** : daimon **charge** dans AGY (21 tools synchronisés) mais 2 gates runtime bloquent l'exécution : `not enabled for server` (`enabledTools`) + `not allowed in this context` (`isServerAllowed`).

**Ce qu'on sait** (détails : archive 2026-06-17) :
- Ces états vivent dans le **store sqlite runtime d'AGY** (compressé, par-conversation) — **pas éditable à la main**, écrit seulement par le flow d'approbation/import natif d'AGY.
- Registre autoritaire des serveurs actifs = `~/.gemini/settings.json` → `mcpServers` (daimon ajouté, `trust:true`). AGY **hérite** des extensions gemini-cli (théorie de Ben confirmée).
- `~/.gemini/extensions/<name>/` (gemini-extension.json + marker + enablement) ; `import_manifest.json` gate l'import (présent = `[skip] already imported`).
- **Préconditions d'import natif laissées prêtes** : extension daimon valide, plugins hand-made purgés, daimon absent du manifest → un **restart complet d'AGY devrait l'enrôler seul**.

**Prochaine action (si on y revient)** : restart AGY, surveiller `Extracting plugin… / daimon` dans les logs de démarrage. Sinon : enable one-time via l'UI AGY (le Desktop atteignait le dialogue « Permission request »). **Puis seulement** codifier la voie supportée dans `setup/clients` (extension gemini + `settings.json` mcpServers `trust:true`) et **retirer les writes morts** (`mcp_config.json` / allow-list per-surface).

**Décision** : faible ROI (reverse-engineering d'un binaire propriétaire de 153 MB). Daimon marche dans les clients MCP sains (Claude Code prouvé). À ne reprendre qu'après les axes terrain.

---

## AXE 7 — Activation auto-update & release `[QUAND PRÊT]`

**État** : auto-update U0–U5 codé (`src/daimon/update/`, vérif SHA256 obligatoire, updater détaché per-user sans UAC, UI tray notify-par-défaut). `apply_macos.py` (swap `.app`) **non encore validé sur Mac**.

**Actions** :
- **Valider `apply_macos`** sur Mac (Ben) + câbler le **dispatch tray macOS update** (check/apply) — dette connue.
- **Publier une release GitHub** (ArboRithmDev/Daimon) avec `latest.json` + assets (généré par `build/make_manifest.py`, câblé `build_windows.ps1`). C'est ce qui **active** la chaîne d'update côté clients installés.

**Dépendances** : build+sign chez Ben. **Effort** : faible (surtout ops).

---

## 3. Ordre recommandé & graphe de dépendances

```
AXE 1 (coord-space)  ──┬──> AXE 2 (profils)  ──┐
                       │                        ├──> AXE 5 (délégation Haiku)
                       └──> AXE 3 (find Vue-only)┘
AXE 4 (robustesse Mains)   ── indépendant (synergie 1)
AXE 6 (AGY)                ── en pause, faible ROI
AXE 7 (release/update)     ── ops, quand prêt
```

**Séquence proposée** : **AXE 1** (socle, tue la friction #1) → **AXE 4** (robustesse Mains, indépendant, gains rapides) → **AXE 2** (profils) → **AXE 3** (fallback sans UIA) → **AXE 5** (délégation) → AXE 7 (release) → AXE 6 (AGY, optionnel).

---

## Annexe A — Contrat coord-space proposé (AXE 1)

Forme cible retournée par `vue_snapshot` (bloc texte joint à l'image) :

```json
{
  "coord_space": {
    "display_index": 0,
    "display_origin": { "x": -1920, "y": 0 },
    "physical_size":  { "w": 1920, "h": 1080 },
    "image_size":     { "w": 1600, "h": 900 },
    "image_scale": 0.8333,
    "region": null,
    "dpi": 96
  }
}
```

Reprojection déterministe côté pilote (ou via `vue_resolve`) :
```
global_x = display_origin.x + image_x / image_scale + (region.x if region else 0)
global_y = display_origin.y + image_y / image_scale + (region.y if region else 0)
```

Avec **AXE 1.5 (clics display-relatifs)**, le pilote n'a même plus à faire ce calcul : il passe `main_click(display=k, x=image_x, y=image_y, space="image")` et Daimon résout en interne.
