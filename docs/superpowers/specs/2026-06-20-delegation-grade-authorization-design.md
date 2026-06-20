# Design A — Delegation-grade motor authorization (design)

> **Date** : 2026-06-20 · **Branche** : main · **Dépend de** : organe moteur (Phase 0),
> AXE 4 (focus), AXE 5b (délégation). **Origine** : test terrain runs #2/#3 — le pilotage
> délégué est cassé par des gates sur des actes anodins, et le plafond n'est pas alignable
> avec l'attente « au niveau max, rien à valider ».

## 1. Problème (constaté en vrai)

Sur un pilotage délégué, l'humain est interrompu pour autoriser des actes **non destructifs**.
Trois causes distinctes, vérifiées dans le code :

1. **Sur-gate clavier.** `guard.py` gate toute action dont la cible n'est pas *observée*
   (`if not action.target.observed → GATE`). Or un `main_key`/`main_type` n'a **pas de cible
   positionnelle observable** : la règle frappe **tous** les actes clavier (ex. `cmd+M` minimize,
   anodin et réversible, a gaté « key sur unknown target »). Les actes clavier sont pourtant déjà
   classés par **combo** (`reversibility.classify`, multilingue), pas par cible.
2. **Pas de déclaration en amont.** Une action au-dessus du plafond est `REFUSE` *après* tentative.
   L'attendu (Ben) : l'IA **annonce avant** ce qu'elle ne pourra pas faire, au lieu de gater/refuser
   au milieu du flux.
3. **« Max » mal compris.** Le plafond menu/config est **clampé à VALIDATION (L3)** (`config.py:142`,
   double-garde : L4 jamais par config). L3 = « VALIDATION » = gate par design. L'attente « au max,
   rien à valider » = **L4 AUTONOMOUS**, aujourd'hui atteignable seulement par phrase tapée au CLI.

## 2. Décisions verrouillées (Ben)

- **L4 engageable depuis le menu tray**, via **popup de confirmation + disclaimer**, avec
  **engagement ET désengagement journalisés immuablement**. Ben assouplit consciemment la garde
  « L4 jamais depuis le menu » ; on conserve : geste humain délibéré, ledger immuable, réversibilité,
  coupe-circuit.
- Le fix clavier (1) ne doit **pas** affaiblir le gate positionnel ni les combos dangereux.
- La déclaration en amont (2) est **informative** ; l'enforcement du guard reste la vérité.

## 3. Invariants préservés

1. **Daimon enforce le plafond, jamais le client.** Le guard reste l'unique chokepoint.
2. **Gate positionnel intact** : agir sur une cible écran non vérifiée gate (L0-L3) / refuse (L4).
3. **Combos dangereux intacts** : un chord destructif gate (L0-L3) comme aujourd'hui.
4. **L4 = consentement tracé + réversible + tuable** : ledger append-only hash-chaîné, désengagement
   symétrique, kill process / suppression du state = override physique toujours dispo.
5. **Cœur pur OS-agnostique** : toute la logique (guard, consent, menu_model, expo plafond) testée
   sans OS ni AppKit ; la couche AppKit (popup) reste mince + smoke.
6. **Parité** : `main_window_*` AX (hors scope ici, cf. AXE 4b) ; ce design ne touche pas le backend
   Windows au-delà des seams partagés.

## 4. Architecture

### ① Fix sur-gate clavier — actions « sans cible à observer »

- **`motor/actions.py`** : ajouter à `ActionDef` un champ `requires_observed_target: bool = True`.
  Le critère = l'acte **commite sur une cible écran** (activer le mauvais élément non vérifié est
  risqué). `True` : `main_click`, `main_press`, `main_drag`, `main_mouse_down`, `main_mouse_up`.
  `False` (pas de cible à vérifier — clavier, fenêtre par bundle, ou simple déplacement réversible) :
  `main_key`, `main_type`, `main_key_down`, `main_key_up`, `main_activate`, `main_hover`,
  `main_navigate`. Helper `requires_observed_target(tool_name) -> bool`. La vérif de **région
  exclue** (`is_point_excluded`) reste **avant** dans le guard → protection secrets intacte pour
  tous les positionnels, y compris hover/navigate.
- **`motor/guard.py`** : la branche `if not action.target.observed` ne s'applique qu'aux actions
  `requires_observed_target(action.name)`. Pour les autres (clavier/activate), on saute la
  vérification d'observation et on enchaîne sur la classification par combo :
  ```
  if requires_observed_target(action.name) and not action.target.observed:
      if ceiling == Level.AUTONOMOUS:
          return Decision(REFUSE, "target unobservable under L4 (no blind autonomous action)")
      return Decision(GATE, "Daimon could not verify the target")
  ```
  Le reste (classify → risky → GATE/ALLOW, L4 → ALLOW must_log) inchangé. Résultat : `cmd+M`
  (combo réversible) → ALLOW dans le plafond ; un combo dangereux → GATE comme avant ; un clic sur
  cible non vérifiée → GATE/REFUSE comme avant.

### ② Declare-don't-gate — exposer le plafond à l'orchestrateur

- **Outil MCP read-only `main_ceiling()`** (enregistré là où les `main_*` le sont) →
  `{ceiling: <NAME>, l4_active: bool, levels: {tool_name: level_name}, gated_above: [tools above ceiling]}`.
  Lit `consent.current_ceiling()` (déjà le `ceiling_provider` du guard) + la map `ACTIONS`. Construit
  par une fonction **pure** `ceiling_report(current: Level) -> dict` (testable sans état).
- **`vue_pilot_brief`** (AXE 5b) inclut le même `ceiling_report` dans son packet, pour que le
  sous-agent connaisse son enveloppe sans appel séparé.
- **server-instructions** : courte note « Hands ceiling » — « avant d'agir, lis `main_ceiling` (ou le
  champ ceiling du pilot brief) ; toute action de niveau supérieur au plafond SERA refusée — annonce-le
  en amont, ne tente pas pour gater au milieu. » Agnostique, pas de marque.

### ③ L4 depuis le tray — popup + disclaimer + ledger

- **`motor/consent.py`** : nouvelle méthode `engage_confirmed(*, ts: str, source: str = "tray") -> bool`
  qui engage L4 **sans phrase tapée** — le geste délibéré est le popup confirmé côté humain. Écrit
  l'event ledger `{"event":"engage_l4","ts":ts,"method":"confirmed","source":source}` + le state
  `{"engaged":True,"ts":ts}`. `engage()` (phrase CLI) et `disengage()` restent. `current_ceiling()`
  inchangé (L4 ssi state engagé **et** dernier event ledger = `engage_l4`).
- **`tray/menu_model.py`** : remplacer le commentaire « L4 exclu » par une **entrée d'action**
  dédiée, hors des radios de plafond (les radios L0-L3 règlent le *config ceiling*, inchangé) :
  - si `state.l4_active` faux → `MenuItem(action, "Engage L4 autonomy…", action_id="engage_l4")` ;
  - si vrai → `MenuItem(action, "Disengage L4 autonomy", action_id="disengage_l4")` (en plus du label
    « ⚠️ L4 AUTONOMY ACTIVE » déjà présent).
- **Couche AppKit (tray)** : sur `engage_l4`, afficher un **NSAlert** avec disclaimer explicite
  (« Removes ALL per-action validation. Every action the AI requests will execute, traced in the
  immutable ledger. Disengage anytime from this menu. ») → bouton destructif « Engage » + « Cancel ».
  Sur confirmation → `ConsentManager.engage_confirmed(ts=…)`. Sur `disengage_l4` → `disengage`
  symétrique (popup léger optionnel). Logique de décision testable (menu_model + consent purs) ;
  l'affichage NSAlert reste smoke.
- **Process séparés** : le tray écrit le state + ledger ; le guard du serveur lit `current_ceiling`
  via ces fichiers (mécanisme existant). Aucun partage mémoire.

## 5. Analyse de sécurité (③ — la relaxation assumée)

Menace : une IA compromise ou une glissade fait monter le plafond à L4 et agit sans contrôle.
- **Avant** : L4 seulement par phrase exacte tapée au CLI hors-bande (très haute friction).
- **Après** : L4 par clic menu humain **+** confirmation NSAlert avec disclaimer. **Toujours un geste
  humain délibéré, hors du canal IA** (l'IA n'a aucun outil MCP touchant le plafond — `main_ceiling`
  est read-only ; `engage_l4` n'est pas un tool, c'est une action de menu humaine).
- **Conservé** : ledger immuable hash-chaîné de l'engage **et** du disengage ; `current_ceiling`
  exige la cohérence state↔ledger (un state forgé sans event ledger ne donne pas L4) ; réversibilité ;
  kill-switch (tuer le serveur / supprimer le state). 
- **Relâché (choix explicite Ben)** : le geste d'engagement passe de « phrase CLI » à « menu+popup ».
  Reste hors d'atteinte de l'IA et tracé. Le disclaimer porte la responsabilité à l'humain.

## 6. Tests (purs sauf AppKit)

- **①** `requires_observed_target` : True positionnels / False clavier+activate. Guard : `main_key`
  combo anodin + cible non observée → ALLOW (L3) ; combo dangereux + non observée → GATE ; `main_click`
  non observée → GATE (L3) / REFUSE (L4) **inchangé** ; clavier non observé sous L4 → ALLOW must_log.
- **②** `ceiling_report(VALIDATION)` liste les niveaux par outil + `gated_above` = les outils > L3 ;
  `l4_active` reflété ; tool `main_ceiling` enregistré (présent dans `list_tools`) ; `vue_pilot_brief`
  inclut le rapport ; server-instructions contiennent la note ceiling (agnostique).
- **③** `engage_confirmed` écrit l'event ledger + state, `current_ceiling()→AUTONOMOUS` ; `disengage`
  rétablit ; `current_ceiling` reste config si state engagé mais dernier event ≠ engage_l4 (anti-forge) ;
  `menu_model` montre « Engage L4… » quand inactif, « Disengage » quand actif, et les radios restent
  L0-L3. NSAlert = smoke.

## 7. YAGNI (hors scope)

- Pas de gradation fine du gate au-delà du fix clavier (le « graded gating » Hide/Minimize est
  couvert par ① ; le reste = AXE 4b).
- Pas de primitives `main_window_minimize/hide` (AXE 4b).
- Pas de durcissement du prompt délégation (stream B).
- Pas de nouveau niveau de plafond.

## 8. Definition of Done

- `main_key`/`main_type` (combo anodin) ne gatent plus pour absence de cible ; combos dangereux et
  gate positionnel inchangés.
- `main_ceiling` expose plafond + niveaux + outils au-dessus ; `vue_pilot_brief` l'inclut ;
  server-instructions portent la note « connais ton plafond, déclare en amont ».
- Le tray engage/désengage L4 via popup+disclaimer, journalisé immuable ; radios L0-L3 inchangés.
- Suite verte (> 374 + nouveaux tests) ; invariants 1-6 tenus ; `print`-free ; tree clean ; commit main.
- À valider terrain (Ben) : engager L4 depuis le tray → un drive délégué complet sans aucun prompt ;
  à L3, `cmd+M`/typing passent sans gate, un combo destructif gate toujours.
