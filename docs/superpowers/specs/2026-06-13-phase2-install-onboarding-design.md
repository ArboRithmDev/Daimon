# Daimon V1 — Phase 2 — Auto-install + Onboarding guidé — Design (Rolls-Royce)

**Date**: 2026-06-13
**Statut**: validé (cadrage autonome, qualité premium), prêt pour plan.
**Parent**: [Charte MVP V1](2026-06-12-v1-mvp-charter.md) — Phase 2, sous-systèmes D (auto-install) + G (onboarding & permissions guidées).
**Préférences** : maintenabilité, performance, finition premium ([[ben-decision-preferences]]).

---

## 1. Objet

Amener un utilisateur **non-technique** du « j'ai installé Daimon » à « mon IA voit et agit » **sans toucher un terminal**. Deux briques :

- **D — Auto-install** : détecter les clients IA présents et y enregistrer Daimon (config MCP), idempotent et réversible.
- **G — Onboarding & permissions** : guider l'octroi des permissions macOS (Screen Recording, Accessibility) en langage clair, avec **vérification live**, et conclure « prêt ».

DoD Phase 2 : un utilisateur neuf branche Daimon et accorde les permissions via un flux guidé, sans terminal.

---

## 2. Décisions d'architecture

- **Registre d'adaptateurs de clients** : chaque client IA = un petit adaptateur (`name`, `detect()`, `config_path()`, format). Ajouter un client = **un** adaptateur. L'enregistrement réel = une **fusion JSON idempotente** partagée (backup avant écriture, n'ajoute que l'entrée `daimon`, déduplique). Logique de chemin + merge = **pure, testée** ; I/O fichier mince.
- **Permissions** : on ne peut PAS accorder TCC par programme (sécurité macOS). On peut **détecter** (`AXIsProcessTrusted`, `CGPreflightScreenCaptureAccess`), **déclencher le prompt système** (`AXIsProcessTrustedWithOptions(prompt)`, `CGRequestScreenCaptureAccess`), **ouvrir le bon volet Réglages** (URL `x-apple.systempreferences:…Privacy_Accessibility|Privacy_ScreenCapture`), et **vérifier** après coup (polling avec abandon). Le statut = modèle pur ; les appels macOS différés.
- **Moteur de wizard** : machine à états **pure** sur des étapes ordonnées ; chaque étape a `check()` (déjà fait ?) et `act()` (faire/guider), **injectés** → testable avec des fakes. Les front-ends (CLI, GUI) sont **minces** au-dessus du moteur (une seule logique, deux peaux).
- **Front-ends** : (1) **CLI wizard premium** `daimon setup` / `python -m daimon.onboard` — interactif, étape par étape, vérifié. (2) **GUI onboarding** (fenêtre AppKit, réutilise les patterns de l'overlay) — « sans terminal », premium, smoke-only. Les deux pilotent le même moteur.
- **Entrée `daimon`** : back-compat. `daimon` (sans arg) = serveur MCP stdio (inchangé, les clients l'appellent ainsi). `daimon <sous-commande>` (`setup`/`install`/`uninstall`/`status`/`onboard`) = CLI. Dispatch dans `__main__:main`.
- **Réversibilité** : écrire une config client = **sauvegardée** (`.bak` horodaté) et **réversible** (`uninstall` retire la seule entrée daimon). Rien d'irréversible sans consentement.

---

## 3. D — Auto-install

### Clients supportés (v1)
| Client | Config MCP | Clé |
|--------|-----------|-----|
| Claude Code | `~/.claude.json` (global) | `mcpServers` |
| Claude Desktop | `~/Library/Application Support/Claude/claude_desktop_config.json` | `mcpServers` |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` |
| (générique) | chemin fourni par l'utilisateur | `mcpServers` |

`detect()` = le fichier/app existe. Extensible : un adaptateur = nom + chemin + (présence app optionnelle).

### Entrée enregistrée
Résoudre la meilleure invocation de Daimon : préférer un **console-script `daimon` installé** (résolu via `shutil.which("daimon")`), sinon `python -m daimon` avec `sys.executable`. Stockée :
```json
{ "mcpServers": { "daimon": { "command": "<daimon|python>", "args": ["...", "-m", "daimon"], "env": {} } } }
```

### Opérations
- `install(clients|all)` : pour chaque client détecté → backup, fusion idempotente (n'écrase pas d'autres serveurs, ne duplique pas `daimon`), écrire. Rapport par client (installé / déjà présent / introuvable).
- `uninstall(clients|all)` : retire **uniquement** l'entrée `daimon`, backup d'abord.
- `status()` : pour chaque client → détecté ? daimon enregistré ?

### Sécurité / robustesse
JSON malformé d'un client → ne pas écraser, signaler (jamais corrompre la config d'un autre outil). Backup systématique avant toute écriture. Écriture atomique (tmp + rename).

---

## 4. G — Onboarding & permissions

### Permissions ciblées
- **Screen Recording** (Vue) : `CGPreflightScreenCaptureAccess()` (détecter), `CGRequestScreenCaptureAccess()` (prompt). Volet : `…Privacy_ScreenCapture`.
- **Accessibility** (Touché + Mains) : `AXIsProcessTrusted()` (détecter), `AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})` (prompt). Volet : `…Privacy_Accessibility`.

**Rappel TCC** (mémoire [[daimon-tcc-inheritance]]) : la permission s'attache au **parent GUI** qui lance le client, pas au binaire python. L'onboarding l'explique : « accorde à <ton app terminal/IDE> », détecte le responsible-process et nomme l'app concernée.

### Modèle d'état (pur)
`Permission` = {key, label, granted: bool, how_to: str}. `permissions_status()` → liste. Les appels macÔS (preflight/request/open-pane) derrière une interface `PermissionBackend` (réel macOS / fake en test).

### Flux
1. Détecter le responsible-process (l'app qui hébergera Daimon) → l'annoncer.
2. Pour chaque permission manquante : expliquer en clair → déclencher le prompt + ouvrir le volet Réglages → **attendre/vérifier** (poll `check()` jusqu'à accordé ou abandon, avec relance).
3. Conclure : « Daimon voit ✅ / palpe ✅ — prêt. »

### Moteur de wizard (pur)
`Step` = {id, title, check: () → bool, act: () → None, guidance: str}. `Wizard(steps)` :
- `next_pending()` → première étape non `check()`-ée.
- `run(io)` → exécute séquentiellement : si `check()` faux → afficher guidance, `act()`, re-vérifier (avec relances bornées) ; sinon passer. `io` = abstraction d'entrée/sortie (CLI prompt, GUI callbacks) → testable avec un fake.
- Étapes Phase 2 : [détecter clients → proposer install] puis [Screen Recording] puis [Accessibility] puis [récap prêt].

---

## 5. Front-ends

### CLI wizard premium (`daimon setup`)
Interactif, soigné : en-tête, étapes numérotées, statut coloré (✅/⏳/❌), confirmations, vérification live (« j'attends que tu coches… vérifié ✅ »). Sous-commandes : `daimon install [--client X | --all]`, `daimon uninstall`, `daimon status`, `daimon onboard` (permissions seules), `daimon setup` (tout).

### GUI onboarding (fenêtre AppKit, premium, smoke-only)
`python -m daimon.onboard --gui` (ou lancé par l'app au 1er run, Phase 3). Fenêtre multi-étapes : liste des clients à cocher, boutons « Accorder » par permission (déclenchent prompt+volet), pastilles de statut live (poll), bouton « Terminé » activé quand tout est vert. Réutilise les patterns AppKit de l'overlay. Pilote le **même moteur**. Pas de tests unitaires (AppKit) ; validé par lancement.

---

## 6. Modules

```
src/daimon/setup/
  clients/
    base.py        # PUR : ClientAdapter (name, config_path, detect) + idempotent JSON merge install/uninstall/status
    registry.py    # PUR : la liste des adaptateurs (Claude Code/Desktop/Cursor/Windsurf/generic)
  invocation.py    # PUR : résoudre la commande daimon à enregistrer (which daimon | python -m daimon)
  permissions.py   # PermissionBackend (protocol) + MacOSBackend (différé) + FakeBackend ; permissions_status() pur
  wizard.py        # PUR : Step, Wizard.run(io), io abstraction
  cli.py           # front-end CLI premium (install/uninstall/status/onboard/setup)
  gui/             # fenêtre AppKit onboarding (smoke-only)
    __main__.py · window.py
src/daimon/__main__.py   # dispatch : sans arg → serveur ; sous-commande → setup.cli
src/daimon/onboard.py     # `python -m daimon.onboard` → wizard permissions (CLI/--gui)
```

Frontière : **tout le pur** (clients merge, invocation, permissions status model, wizard) OS-agnostique et **unit-testé** ; macOS (permissions backend, GUI) mince, derrière interfaces/différé. Windows V2 = nouveaux adaptateurs clients + backend permissions.

---

## 7. Tests

- **clients/base** : merge idempotent (ajoute daimon sans toucher d'autres serveurs ; 2× = pas de dup) ; backup créé ; JSON malformé → refus sans corruption ; uninstall retire seulement daimon ; status correct. (fichiers en tmp_path)
- **registry** : chemins attendus par client (env HOME mocké) ; detect par existence.
- **invocation** : `which daimon` présent → console-script ; absent → `python -m daimon` + sys.executable.
- **permissions** : `permissions_status()` avec FakeBackend (granted/manquant) ; ouverture de volet appelée ; jamais de prétention d'octroi.
- **wizard** : `Wizard.run` avec un FakeIO et des étapes fakes — saute les `check()` vrais, exécute `act()` + re-vérifie les faux, abandon borné si jamais accordé ; ordre respecté.
- **cli** : `daimon status`/`install`/`uninstall` via `run_command(...)` (args + backends injectés) → codes retour + sorties, sans I/O réelle.
- **dispatch** : `__main__.main(["status"])` route vers la CLI ; `main([])` lance le serveur (mocké).
- **smoke** : `scripts/smoke_setup.py` (dry-run install + status) ; GUI lancée manuellement.

Tout le pur sans macOS (backend permissions fake ; GUI exclue).

---

## 8. Invariants

- **Jamais corrompre** la config d'un autre outil : backup + écriture atomique + refus sur JSON malformé.
- **Idempotent & réversible** : ré-installer = no-op ; `uninstall` retire proprement.
- **Honnête sur TCC** : on guide/déclenche/vérifie, on ne prétend jamais accorder ; on nomme la bonne app (responsible-process).
- **Une seule logique** (moteur wizard) sous deux front-ends ; CLI et GUI ne dupliquent pas la logique.
- **Back-compat** : `daimon` sans arg reste le serveur MCP.
- **Cœur pur** OS-agnostique → Windows V2 = adaptateurs.

---

## 9. Hors-scope Phase 2

Packaging/DMG/notarisation (Phase 3) ; lancement auto de l'onboarding au 1er run (Phase 3, dépend du packaging) ; clients au-delà des 4 + générique ; auto-update ; Windows ; les fonctions pro.
