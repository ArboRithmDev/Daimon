# Daimon V1 — Phase 0 (Fondation) — Design

**Date**: 2026-06-12
**Statut**: validé (brainstorm), prêt pour plan d'implémentation.
**Parent**: [Charte MVP V1](2026-06-12-v1-mvp-charter.md) — Phase 0 = sous-systèmes A (durcissement) + F (complétion moteur).
**Informé par**: rapport terrain 2026-06-12 (agent consommateur pilotant une GUI Qt/PySide6 via Daimon MCP).

---

## 1. Objet

Rendre la v0 **soutenable en boucle** (usabilité + coût token) puis **distribuable** (sécurité). Le rapport terrain a montré que la v0 perçoit et clique mais ne peut pas *entrer* dans une app (pas de double-clic, pas de clavier) et qu'un seul `touche_tree` plein coûte ~la moitié du budget Daimon d'une session. Phase 0 ferme ces deux dettes — d'abord l'usabilité (dogfooding), ensuite le durcissement (gate release public).

Phase 0 se découpe en **0a (quick wins, faible delta sécu)** et **0b (durcissement + vocabulaire risqué, gate release)**.

---

## 2. Modèle d'entrée unifié (souris + clavier)

Symétrie : souris et clavier exposent chacun des **gestes sémantiques atomiques** (par défaut, classables par la sécu) et des **primitives down/up** (avancé, verrouillé). Un geste atomique = un down+up complet → le guard peut le classer et le gater ; une primitive est un demi-geste → contourne la classification par nature, d'où le verrou.

### Gestes sémantiques (défaut)

| Outil | Signature (args clés) | Niveau | Notes |
|-------|----------------------|--------|-------|
| `main_click` | `x, y, button=left\|right\|middle, count=1\|2, modifiers=[], intent, reversible, role, label` | L2 | clic droit & double marqués en audit |
| `main_drag` | `from_x, from_y, to_x, to_y, button=left, modifiers=[], intent, reversible` | L2 | **destination classée** (drop sur Corbeille/zone exclue = non-retour) |
| `main_hover` | `x, y, intent` | L1 | déplacement seul (tooltips/menus) |
| `main_press` | `x, y, intent, reversible, role, label` | L3 | activation AX sémantique (existe) |
| `main_type` | `text, intent, reversible` | L2 | saisie texte (existe) |
| `main_key` | `key, modifiers=[], count=1, intent, reversible` | L2/L3 | touche discrète + chord (Return/Tab/Esc/flèches/F-keys + Cmd+Shift+R) ; combos dangereux → gate |
| `main_navigate` | `intent, scroll_y=0` | L1 | scroll (existe) |
| `main_activate` | `title=\|pid=\|bundle=, intent` | L1 | forcer une app/fenêtre au premier plan |

`modifiers` ⊂ `{cmd, shift, opt, ctrl}`. `button` et `count` sont des paramètres, pas des outils séparés (modèle « gestes sémantiques paramétrés » du brainstorm).

### Primitives bas niveau (avancé, verrouillé)

| Outil | Niveau requis | Garde-fous |
|-------|---------------|-----------|
| `mouse_down` / `mouse_move` / `mouse_up` | L4 **ou** opt-in config `advanced_primitives: true` | toujours loggées ; **watchdog** auto-relâche tout bouton tenu après timeout |
| `key_down` / `key_up` | idem | idem (auto-relâche toute touche tenue) |

Raison du verrou : une primitive ne peut pas être classée (demi-geste). On ne l'autorise que là où le plafond est déjà au maximum (L4 consenti) ou explicitement activé par l'utilisateur. Le watchdog garantit qu'aucun état (bouton/touche maintenu) ne reste pendouillant si l'agent oublie le `up`.

### Classification (lien avec A1)

- `main_click`/`main_key`/`main_press` : non-retour selon **combo + cible observée** (re-sonde A1, §3.A1).
- `main_drag` : classe la **destination** (drop target observé), pas seulement l'origine.
- clic droit : note indicative en audit (ouvre un menu) ; l'action destructrice est le clic suivant *dans* le menu, classé à ce moment.
- `main_type` : reste L2, sur le champ focus **réellement observé**.

---

## 3. Phase 0a — Quick wins (usabilité + coût, faible delta sécu)

Débloque la boucle de dogfooding. Ces items frappent des coordonnées observées ou le clavier → pas d'esquive de cible, delta sécu faible. Livrables en premier.

### 0a.1 — `touche_tree` borné (le plus gros levier ; coût ÷3–5)

`snapshot_tree` (capture/accessibility.py) et l'outil `touche_tree` (senses/touche.py) gagnent :

- `max_depth: int` — profondeur max (un agent veut souvent 1–2). Défaut **borné** (ex. 4), pas illimité.
- `root: {x,y} | None` — ne dumper que le sous-arbre sous ce point (via `AXUIElementCopyElementAtPosition`) au lieu de la fenêtre entière.
- `roles: list[str] | None` — ne garder que les nœuds de ces rôles (+ leurs ancêtres pour la structure).
- `prune_empty: bool` (défaut `true`) — éliminer les nœuds décoratifs sans titre/valeur/rôle utile (séparateurs, colonnes vides).
- `summary: bool` (défaut `false`) — sortie compacte : **une ligne par nœud** `role "title" [x,y w×h]`, pas le JSON multi-clés verbeux.

Le **défaut** devient borné (max_depth modéré + prune_empty + summary recommandé) ; l'arbre complet profond = **opt-in explicite**. Cap octets total conservé avec marqueur de troncature.

### 0a.2 — `touche_tree` ciblage fenêtre (fiabilité null-root)

Cause du bug terrain : `snapshot_tree` résout via le frontmost implicite ; si une autre app reprend le premier plan → racine `null`. Correctifs :

- `touche_tree(window=title|pid|bundle)` — cibler une fenêtre par titre/PID/bundle, pas seulement le frontmost.
- Fallback : si le frontmost est indisponible/null, retomber sur la fenêtre **sous le curseur** ou la dernière ciblée, plutôt que renvoyer null.
- `main_activate(title|pid|bundle)` (outil moteur L1) — forcer une app au premier plan avant un tree quand on veut explicitement le frontmost.

### 0a.3 — `vue_snapshot` ciblé

- `region: {x, y, width, height} | None` — capturer juste la fenêtre/zone cible (crucial sur ultrawide 5120px scalé : détail préservé, tokens économisés).
- défaut `max_width` abaissé (~**720**, vs 1600) ; le détail fin reste opt-in via un `max_width` explicite.

### 0a.4 — Vocabulaire P0 (les débloqueurs)

- **Double-clic** : `main_click(count=2)` — débloque l'ouverture (QListWidget `itemActivated`, etc.).
- **`main_key(key, modifiers=[], count=1)`** : événement clavier discret + chord, distinct de `main_type`. Débloque Return/Tab/Esc/flèches sur une liste focalisée, et les raccourcis phares (Ctrl+Shift+R).

---

## 4. Phase 0b — Durcissement sécu + vocabulaire risqué (gate release public)

Requis **avant toute release publique** (cf. charte §4). Le vocabulaire « mensonge de cible » (clic droit, drag) atterrit **avec** A1 pour être classé correctement.

### A1 — Re-sonde Touché (classer sur l'observé, pas le déclaré)

Acquisition de la cible déplacée **dans Daimon**, avant `guard.evaluate` :

- `click/press/drag/hover` (ont des coords) → `element_at(x,y)` → Target **autoritaire** (role/label/value observés). Pour `drag`, sonder aussi la **destination**.
- `type` (pas de coords) → sonder `AXFocusedUIElement` → cible = champ focus réel.
- `key` → cible = élément focus (pour contexte de classification du combo).
- `navigate/hover/activate` → pas de cible spécifique.

Le `role`/`label` fournis par l'IA deviennent **indicatifs** (loggés `claimed_*`), jamais utilisés pour classer. Divergence (claimed ≠ observé) **journalisée** (une IA qui ment devient visible dans le log).

**Fail-safe si la sonde échoue** (rien sous les coords / a11y indispo) :
- L0–L3 → traité **risqué → GATE** ("Daimon n'a pas pu vérifier la cible").
- **L4 → REFUSE** + log (pas d'action aveugle en autonome).

Nouveau module `motor/probe.py` enveloppant `capture/accessibility`, fournissant une Target résolue au guard (garde le guard pur).

### A2 — Filtre secrets contenu (BLOQUANT release)

`ExclusionFilter` étendu d'une couche contenu, posture **« rôles sensibles + apps déclarées »** :

- `secret_roles` (denylist config, défauts : `AXSecureTextField`, champs password) → toujours redactés.
- `secret_apps` (config, défauts : terminaux + gestionnaires de mots de passe courants) → contenu/nœuds redactés ; frontmost → Vue refusée.
- règles titre/app/région existantes conservées.
- **Touché** : nœuds sensibles → `value` **blanchie** (`"█…"` ou `null` + flag `redacted`), structure gardée.
- **Vue** : noircir les rectangles des fenêtres/éléments sensibles via les **bounds Touché** (réutilise la géométrie a11y) ; frontmost secret → refus du snapshot entier.
- Regex contenu (clés/emails/tokens) = **différé** (complément futur, pas barrière unique — YAGNI v1).

### A3 — Exclusions app/région pour le moteur

`guard.evaluate` (ou le probe pré-guard) consulte aussi :
- `is_app_excluded(frontmost_bundle)` → REFUSE.
- coords de l'action dans un rectangle exclu → REFUSE.

S'applique même sous L4 (la zone secrète prime sur l'autonomie).

### A5 — Durabilité ledger

- `fcntl.flock` (verrou consultatif) autour de `AppendOnlyLedger.append` (l'exécuteur est désormais branché → appels concurrents possibles control-CLI / serveur).
- `ConsentManager` cross-check : `engaged` (state file) ⇔ dernier event ledger == `engage_l4` ; incohérence → fail-safe vers le ceiling config + warn (forger le state file ne suffit plus).

### F — Vocabulaire risqué + complétion

- **P1** : `main_click(button=right)` + menus contextuels ; `main_drag` avec **destination classée**.
- **P2** : modificateurs sur clic (`modifiers=[…]`), touches isolées déjà via `main_key`, maintien via primitives (`mouse_down/up`, `key_down/up`, verrou L4/opt-in + watchdog).
- **F2** : test auto d'enregistrement serveur (assertion sur l'ensemble d'outils `vue_*`/`touche_*`/`main_*` — pas de régression silencieuse).

---

## 5. Architecture & frontières

- `motor/probe.py` (nouveau) — résout la Target observée (réutilise `capture/accessibility`). Garde `guard` pur.
- `motor/reversibility.py` — enrichi : conscient du geste (drag→destination, combo clavier, modificateurs).
- `motor/actuator.py` — `MacOSActuator` étendu : `button`/`count`/`modifiers` sur click, `key` (CGEvent keycode + modifier flags), `hover`, `activate` (NSRunningApplication `activateWithOptions`), primitives `mouse_down/up`/`key_down/up` + watchdog (thread/timer auto-release).
- `motor/actions.py` — registre étendu (nouveaux verbes + niveaux).
- `motor/watchdog.py` (nouveau) — suit les boutons/touches tenus, auto-relâche après timeout.
- `capture/accessibility.py` — `snapshot_tree` paramétré (max_depth/root/roles/prune_empty/summary/window) + fallback non-frontmost.
- `exclusions.py` / `config.py` — couche contenu (`secret_roles`, `secret_apps`), `is_target_secret`, `redact_image` étendu aux bounds a11y.
- `senses/touche.py`, `senses/vue.py` — exposent les nouveaux paramètres.
- `server.py` — enregistre les nouveaux outils.

Invariant : le **cœur pur** (guard, reversibility, consent, audit, types, actions, watchdog-logique) reste OS-agnostique. L'actuateur/probe/accessibility = adaptateurs macOS (jumeaux Windows en V2).

---

## 6. Tests

- **0a.1/0a.2** `touche_tree` : max_depth respecté ; `root` borne au sous-arbre ; `roles`/`prune_empty` filtrent ; `summary` = 1 ligne/nœud ; ciblage par titre/pid/bundle ; fallback non-frontmost (mock a11y).
- **0a.3** `vue_snapshot` : `region` recadre ; défaut max_width ~720.
- **0a.4 / F** vocabulaire : `main_click(count=2/button=right/modifiers)`, `main_key(combo)`, `main_drag(dest)`, `main_hover`, `main_activate` construisent la bonne `MotorAction` et routent par le guard (actuateur mocké). Primitives refusées hors L4/opt-in ; watchdog auto-relâche (timer mocké).
- **A1** : organ re-sonde (prober injecté), classe sur l'observé ; divergence claimed≠observé loggée ; sonde-échec → gate (L0-L3)/refuse (L4) ; **red-team** : IA déclare "Cancel" sur "Send" observé → gated/refused ; drag classé sur destination.
- **A2** : rôle/app secret → `value` blanchie (Touché) + rect noirci (Vue, géométrie mockée) ; non-secret passe ; frontmost secret → Vue refusée.
- **A3** : app/région exclue → moteur REFUSE (même L4).
- **A5** : cross-check rejette un state forgé ; (flock = note intégration, dur à unit-test).
- **F2** : la liste d'outils contient l'ensemble attendu.

Pur sans macOS pour toute la logique (probe/actuator/accessibility derrière interfaces + fakes ; géométrie a11y mockée).

---

## 7. Ordre de livraison

**0a d'abord** (dogfooding débloqué) : 0a.1 tree borné → 0a.2 ciblage fenêtre → 0a.3 vue ciblée → 0a.4 double-clic + main_key.
**0b ensuite** (gate release) : A1 re-sonde → A2 secrets contenu → A3 exclusions → A5 ledger → F vocabulaire risqué (right/drag/modifiers/primitives) → F2 test.

Le vocabulaire P1/P2 risqué (clic droit, drag, primitives) atterrit en 0b **après A1**, pour être classé sur la cible observée.

---

## 8. Hors-scope Phase 0

Regex de contenu (pattern-matching secrets) ; overlay (Phase 1) ; auto-install/onboarding (Phase 2) ; packaging signé (Phase 3) ; Windows (V2) ; les fonctions pro.
