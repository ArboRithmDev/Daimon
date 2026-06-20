# AXE 4b — Native window control + must-delegate (design)

> **Date** : 2026-06-20 · **Branche** : main · **Dépend de** : organe moteur, AXE 4 (focus),
> AXE 5b + stream B (délégation), Design A (autorisation). **Origine** : test terrain — abaisser
> VS Code via `main_key Cmd+H/M` a échoué (VS Code rebind/intercepte les chords) ; pas de primitive
> minimize/hide → fallback `osascript` obligé ; `ensure_focus` non utilisé → clic no-op ; et
> l'orchestrateur a piloté inline au lieu de déléguer.

## 1. Problème

1. **Injection clavier non fiable pour les ops fenêtre** : `Cmd+H`/`Cmd+M` sont mangés/rebindés par
   l'app cible (VS Code/Electron). Il n'existe **aucun tool Hands dédié** pour minimize/hide/restore
   → l'IA tombe sur `osascript` (hors Daimon, non borné, non tracé par le guard).
2. **`main_click` no-op silencieux** quand la fenêtre cible n'est pas frontmost : `ensure_focus`
   existe (AXE 4) mais est opt-in (défaut False) → l'IA oublie → clic sans effet.
3. **L'orchestrateur capable pilote inline** au lieu de déléguer à un sous-agent (screenshots dans
   son contexte). Le protocole dit « if you can, delegate » — trop mou.

## 2. Décisions verrouillées (Ben)

- Primitives **minimize + hide + show (restore)** — paire aller-retour complète.
- `main_click` : **`ensure_focus=True` par défaut**.
- MUST-déléguer : un modèle capable **DOIT** déléguer le **pilotage multi-étapes** (action/drive) à
  un sous-agent ; une **perception one-shot** (`vue_snapshot` pour « décris l'écran ») reste permise
  inline.

## 3. Invariants préservés

1. **Cœur pur OS-agnostique + Fake** ; AppKit/AX minces.
2. **Parité Mac/Windows** : chaque primitive a son backend macOS réel + un **scaffold Windows**
   (`NotImplementedError` + TODO `ShowWindow SW_MINIMIZE/SW_HIDE/SW_RESTORE`).
3. **Le guard reste l'unique chokepoint** : les nouvelles ops passent par `organ.act` → guard
   (niveau **L1 NONDESTRUCTIVE**, réversible) ; refusées sous L0 ; respectent le plafond.
4. **Sécurité inchangée** : pas de secret touché ; ops ciblées app-by-bundle (pas de cible écran à
   observer → `requires_observed_target=False`).
5. **Délégation agnostique** : aucun nom de modèle dans le texte produit (testé).

## 4. Architecture

### 4.1 Primitives fenêtre (3 tools Hands)

- **`actions.py`** : 3 `ActionDef` à `Level.NONDESTRUCTIVE`, `requires_observed_target=False` :
  `main_window_minimize`, `main_window_hide`, `main_window_show`. Noms courts MotorAction :
  `window_minimize`, `window_hide`, `window_show` (préfixe `main_` régulier).
- **`actuator.py`** (macOS réel) + `FakeActuator` (enregistre déjà par nom) :
  - `_window_hide` : résout l'app via `NSWorkspace.runningApplications()` (bundle/title/pid, comme
    `_activate`) → `app.hide()` (NSRunningApplication, déterministe, immune au rebind).
  - `_window_show` : même résolution → `app.unhide()` + **dé-minimise** (AX : `AXUIElementCreateApplication(pid)`,
    `kAXWindowsAttribute`, set `kAXMinimizedAttribute=False` sur les fenêtres minimisées) +
    `app.activateWithOptions_` (raise).
  - `_window_minimize` : résout le pid → AX `AXUIElementCreateApplication(pid)` → fenêtre focus
    (`kAXFocusedWindowAttribute`, repli `kAXWindowsAttribute[0]`) → set `kAXMinimizedAttribute=True`.
  - Dispatch ajouté dans la table `execute()` (à côté de `activate`/`press`).
- **`actuator_win.py`** : scaffold des 3 (`NotImplementedError`, docstring `ShowWindow`).
- **`server.py`** (`_register_motor`) : 3 tools MCP `main_window_minimize/hide/show(intent, bundle="",
  title="", pid=0)` → `organ.act(MotorAction(name="window_*", level=level_for(...), target=Target(),
  declaration=Declaration(reversible=True, intent=...), params={bundle,title,pid}))`.
- `ceiling_report` les inclut automatiquement (map `ACTIONS`).

### 4.2 `main_click` auto-focus par défaut

- **`server.py`** : les signatures `main_click` **et** `main_press`/`main_drag` passent
  `ensure_focus: bool = True` (défaut). L'auto-focus ne se déclenche que lorsqu'un window target est
  fourni (`window_bundle/title/pid`) ET la fenêtre n'est pas frontmost — logique `organ._handle_focus`
  inchangée. Sans window target → inerte (rétro-compatible).

### 4.3 Affinage `focus_warning` (léger)

- **`organ.py`** / `motor/focus.py` : le retour porte un `focus` à 3 états explicites plutôt qu'un
  booléen + warning ambigu : `not_attempted` (pas de window target), `activated_and_frontmost`
  (auto-focus réussi), `activated_but_not_frontmost` (activé mais pas au premier plan → no-op
  probable, garde le `focus_warning`). Champs additifs ; pas de rupture des consommateurs.

### 4.4 Délégation impérative (point 2)

- **`senses/delegation.py`** : `delegation_protocol_text()` passe l'option en **obligation** pour le
  pilotage multi-étapes : « **If you can spawn sub-agents, you MUST delegate multi-step UI-driving
  (any main_* action sequence) to a sub-agent — do not drive inline; keep screenshots out of your
  context.** A one-shot perception (a single vue_snapshot to describe the screen) MAY stay inline. »
  Agnostique (aucun nom de modèle). Le `mode_hint`/`_subagent_prompt` restent ceux de stream B.

## 5. Flux

Abaisser→décrire→remonter, déterministe : `main_window_hide(bundle)` (ou `minimize`) →
`vue_snapshot` → `main_window_show(bundle)`. Plus de `main_key` ni d'`osascript`. `main_click` sur une
fenêtre background auto-active avant de cliquer.

## 6. Gestion d'erreurs

- App introuvable (`NSWorkspace` ne matche pas) → `RuntimeError` (comme `_activate`), remonté par
  l'organe en échec tracé.
- AX échoue (pas de fenêtre, permission Accessibility absente) → erreur explicite, jamais un faux
  « executed ». `_window_show` best-effort : unhide + activate même si la dé-minimisation AX échoue.
- Windows : `NotImplementedError` clair (scaffold).

## 7. Tests (purs sauf AX/AppKit réel)

- **Primitives** : `FakeActuator` enregistre `window_minimize/hide/show` + params bundle ; les 3
  `ActionDef` (L1, `requires_observed_target=False`) ; présence dans `ceiling_report` et dans
  `list_tools` ; jumeau Windows lève `NotImplementedError`.
- **Auto-focus** : signature `main_click`/`press`/`drag` `ensure_focus` défaut True (introspection) ;
  via organe-fake : window target non frontmost + défaut → auto-active ; sans window target → inerte.
- **focus_warning** : les 3 états retournés selon le cas (organe-fake, sans input réel).
- **Délégation** : `delegation_protocol_text()` contient l'impératif MUST + l'exemption one-shot ;
  toujours agnostique (`_BRANDS` négatif).
- AX/AppKit réel (minimize/hide/show effectifs) = **validation manuelle Mac** (non headless).

## 8. YAGNI (hors scope)

- Pas de `main_window_close`/`quit` (destructif ; séparé si besoin).
- Pas de gestion multi-fenêtres par titre fin (on cible la fenêtre focus de l'app).
- Pas de backend Windows réel (scaffold seul ; câblé au vrai port Win).

## 9. Definition of Done

- `main_window_minimize/hide/show` opèrent via AX/AppKit (déterministe, immune au rebind), L1, par le
  guard ; jumeau Windows scaffold.
- `main_click`/`press`/`drag` auto-focus par défaut (inerte sans window target).
- `focus` à 3 états dans le retour.
- Protocole délégation impératif (MUST multi-étapes, one-shot exempté), agnostique.
- Suite verte (> 393 + nouveaux tests) ; invariants 1-5 tenus ; `print`-free ; tree clean ; commit main.
- À valider terrain (Ben) : abaisser VS Code via `main_window_hide`/`minimize` (sans osascript),
  décrire, remonter via `main_window_show` ; `main_click` background auto-focus ; un orchestrateur
  capable délègue le drive multi-étapes à un sous-agent.
