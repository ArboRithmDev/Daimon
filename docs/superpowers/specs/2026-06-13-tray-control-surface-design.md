# Daimon — Resident menu-bar control surface — Design

**Date**: 2026-06-13
**Statut**: validé (cadrage autonome), prêt pour plan.
**Contexte**: l'utilisateur veut une surface de gestion **persistante** (comme une app tray), pas seulement l'onboarding one-shot. Daimon.app devient une app **menu-bar résidente**.

---

## 1. Objet

Une **icône menu-bar permanente** (NSStatusItem natif) qui rend Daimon pilotable au quotidien : voir le statut, régler le plafond moteur et l'overlay, relancer l'onboarding, quitter. Pas de dépendance tierce (pas pystray) — pyobjc natif, cohérent avec l'overlay.

---

## 2. Comportement

- `Daimon.app` double-cliqué (frozen, no-arg) → **app menu-bar résidente** (`NSApplicationActivationPolicyAccessory` : icône menu-bar, **pas** d'icône Dock).
- **Premier lancement** : si une permission manque OU aucun client n'est enregistré → ouvre **une fois** la fenêtre d'onboarding. Sinon, reste simplement dans la menu-bar.
- Le serveur MCP et l'app menu-bar sont des **process séparés** ; ils communiquent via les **fichiers de config** (comme `motor.state.json` déjà). Régler le plafond/overlay = écrire le yaml → les serveurs le relisent au prochain démarrage.

---

## 3. Le menu

| Section | Item | Action |
|---------|------|--------|
| Entête | `Daimon v<version>` | (label) |
| Perception | `👁 Screen Recording  ✅/⚪` · `✋ Accessibility  ✅/⚪` | (statut, lu du marqueur self-report + check live) |
| Clients | `N clients connectés` → sous-menu | liste chaque client (enregistré ✅ / détecté) |
| **Mains** | `Plafond : L0/L1/L2/L3` → sous-menu radio | écrit `motor.yaml` ceiling. **L4 absent** (CLI-only, sécu — cohérent avec le clamp) |
| Overlay | `☑ Afficher l'overlay` | écrit `overlay.yaml` enabled |
| — | `Relancer la configuration…` | ouvre la fenêtre d'onboarding |
| — | `Ouvrir le dossier config` · `Ouvrir les logs` | `open` |
| — | `Quitter Daimon` | termine l'app menu-bar |

L4 ne se règle JAMAIS depuis le menu (uniquement `daimon.motor.control engage`, consentement écrit). Le menu affiche « L4 actif » en lecture seule s'il l'est.

---

## 4. Architecture (pur + GUI mince)

```
src/daimon/tray/
  state.py        # PUR : TrayState + build_state(readers) — agrège permissions/clients/ceiling/overlay
  menu_model.py   # PUR : build_menu(state) → liste de MenuItem (kind/label/value/action_id/enabled)
  settings.py     # PUR-ish : set_ceiling(name)/set_overlay(bool) → write yaml idempotent/atomique/backup
  app/
    __main__.py   # entrée AppKit : NSApplication accessory + NSStatusItem + run loop
    statusitem.py # construit le NSMenu depuis menu_model, câble les actions, poll
src/daimon/__main__.py  # frozen no-arg → tray app (au lieu de l'onboarding direct)
```

- **`state.py`** : `build_state(*, permissions_reader, clients_reader, motor_cfg_reader, overlay_cfg_reader)` → `TrayState{ screen_ok, accessibility_ok, clients:[(name,registered)], ceiling:Level, l4_active:bool, overlay_on:bool, version }`. Lecteurs injectés → 100% testable.
- **`menu_model.py`** : transforme `TrayState` en une **liste déclarative** d'items (séparation logique/AppKit). Le GUI ne fait que rendre cette liste et router les `action_id`. Pur → testé.
- **`settings.py`** : `set_ceiling(name, path=…)` écrit `motor: {ceiling: …}` en **préservant** les phrases L4 ; refuse L4 (clamp ≤ VALIDATION) ; `set_overlay(bool, path=…)` écrit `overlay: {enabled: …}`. Atomique + backup. Tests purs.
- **`app/`** : NSStatusItem, rend le menu, poll ~2 s pour rafraîchir les statuts, ouvre l'onboarding via `setup.gui`. Smoke-only.

Frontière : tout le pur (state/menu_model/settings) OS-agnostique et **unit-testé** ; AppKit mince. Windows V2 = réécrire `tray/app/` (system tray).

---

## 5. Dispatch (mise à jour)

`__main__.main` :
- frozen no-arg → **tray app** (`daimon.tray.app.__main__:main`).
- `--gui` → fenêtre onboarding (inchangé ; le tray l'ouvre aussi).
- `serve` → serveur ; sous-commandes → CLI ; source no-arg → serveur (back-compat).

---

## 6. Tests

- **state** : `build_state` avec des lecteurs fakes → champs corrects (permissions OK/manquantes, clients enregistrés/détectés, ceiling lu, overlay on/off, l4_active).
- **menu_model** : `build_menu(state)` → items attendus (statuts, sous-menu plafond radio sans L4, checkbox overlay coché selon état, items actions présents) ; le plafond courant est marqué sélectionné ; L4 jamais proposé.
- **settings** : `set_ceiling("INPUT")` écrit `motor.ceiling: INPUT` en gardant `l4.engagement_phrase` ; `set_ceiling("AUTONOMOUS")` refusé/clampé ; `set_overlay(True)` écrit `overlay.enabled: true` ; atomique + backup ; round-trip relu par `load_motor_config`/`load_overlay_config`.
- **dispatch** : frozen no-arg → tray (mocké) ; `--gui` → onboarding (mocké).
- **smoke** : lancer `Daimon.app` (après rebuild) → icône menu-bar + menu fonctionnel.

---

## 7. Invariants

- **L4 jamais réglable depuis le menu** (consentement écrit only). Le menu peut l'afficher en lecture seule.
- **Jamais corrompre** les yaml : atomique + backup + préserver les autres clés (phrases L4, autres réglages).
- **Process séparés** : le tray écrit la config ; les serveurs la relisent au démarrage (pas d'IPC nouvelle).
- **Cœur pur** OS-agnostique → Windows V2 = adaptateur tray.
- **Pas de Dock** : accessory policy (menu-bar résidente uniquement).

---

## 8. Hors-scope

Démarrer/arrêter les serveurs depuis le menu (ils sont lancés par les clients) ; édition graphique des zones secrètes (on ouvre le fichier) ; auto-update ; Windows tray (V2) ; thèmes de l'icône menu-bar.
