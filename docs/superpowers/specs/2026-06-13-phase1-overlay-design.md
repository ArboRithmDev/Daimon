# Daimon V1 — Phase 1 — Overlay (« le visage ») — Design (Rolls-Royce)

**Date**: 2026-06-13
**Statut**: validé (cadrage autonome, qualité haut de gamme), prêt pour plan.
**Parent**: [Charte MVP V1](2026-06-12-v1-mvp-charter.md) — Phase 1, sous-système B.
**Préférences appliquées** : maintenabilité, performance, finition premium ([[ben-decision-preferences]]).

---

## 1. Objet

Le **3e organe : « montrer »**. Un overlay visible rend lisibles la perception et l'action de l'agent : où il regarde, où il clique, ce qu'il s'apprête à faire, et — surtout — **ce que l'humain confirme au gate**. C'est à la fois différenciateur produit (effet « waouh », démo) et **gain de sécurité** (le gate non-retour devient visuel).

Triade complète : percevoir (yeux, v0) · agir (mains, v0/0b) · **montrer (visage, Phase 1)**.

---

## 2. Contrainte macOS & décision d'architecture

Le serveur MCP (`python -m daimon`) tourne en process stdio (boucle asyncio, thread principal). Dessiner une `NSWindow` transparente exige une `NSApplication` + run loop AppKit sur le thread principal — **incompatible** avec la boucle stdio dans le même thread.

**Décision : l'overlay est un PROCESS HELPER séparé** (`daimon-overlay`) qui possède sa run loop AppKit et dessine ; le serveur MCP lui envoie des **commandes de dessin** via une **IPC locale** (socket de domaine Unix, JSON ligne-délimité).

Pourquoi (maintenabilité + correction + premium) :
- Architecture macOS correcte (GUI = son run loop, serveur = stdio).
- **Anti-feedback natif** : la fenêtre overlay est marquée `NSWindowSharingNone` → invisible à la capture Vue (pas d'auto-filmage / boucle).
- Découplage : le cœur moteur reste pur ; il parle à un `Presenter` (interface injectée, comme gate/actuator/prober). Le headless par défaut = `NullPresenter` (no-op).
- Le process overlay est **long-lived** : il survit aux redémarrages fréquents du serveur MCP (un serveur par session client). Auto-spawn au premier besoin, reconnexion transparente, l'utilisateur peut le quitter.

**Performance** : rendu via **Core Animation (CALayer)** — animations GPU fluides (pulse, ripple, fade), pas de `drawRect` CPU. Chaque commande mappe une mise à jour de layer.

---

## 3. Éléments visuels (premium)

| Élément | Rôle | Détail |
|---------|------|--------|
| **Target highlight** | encadrer l'élément visé | rect arrondi animé (glow/pulse), légende `rôle "label"` |
| **Cursor halo + click ripple** | montrer où les mains agissent | halo doux suit le curseur ; ripple à l'impact d'un clic |
| **Spotlight / focus** | concentrer l'attention | vignette : tout assombri sauf le rect cible |
| **Action banner (HUD)** | dire ce qui se passe | petit bandeau élégant : `action • intent`, couleur selon niveau/risque |
| **Gate emphasis** | sécurité visuelle | au gate non-retour : contour **rouge pulsant** sur l'élément exact + l'action → l'humain voit précisément ce qu'il valide |
| **Perception trace** | montrer ce qui est lu | bref contour de ce que Touché vient de sonder / région Vue capturée |

Thème premium : palette sobre, coins arrondis, ombres douces, easing naturel (ease-out), opacités mesurées. Couleurs par niveau : L1 neutre, L2 bleu, L3 ambre, non-retour/gate rouge.

---

## 4. Sécurité de l'overlay

- **Click-through strict** : `ignoresMouseEvents = True`, niveau au-dessus, `canJoinAllSpaces`. L'overlay n'intercepte **jamais** un clic (ni de l'agent, ni de l'humain).
- **Anti-feedback** : `sharingType = NSWindowSharingNone` → exclu de toute capture écran (Vue ne se filme pas).
- **Secret-safe** : aucune légende/bandeau ne révèle un contenu secret. Les labels passent par la **même redaction** que les sens (`is_target_secret` / `redact`) — pour une cible secrète, afficher `🔒 protégé`, jamais la valeur.
- **Purement présentationnel** : l'overlay ne lit rien de sensible qu'il ne devrait, n'agit jamais, ne stocke rien.
- **Dégrade proprement** : si le process overlay est absent/mort, le serveur fonctionne normalement (commandes droppées). L'overlay n'est jamais sur le chemin critique d'une action.

---

## 5. Intégration au moteur (sans couplage)

Le `MotorOrgan` reçoit un `presenter: Presenter` optionnel (défaut `NullPresenter`). Appelé aux points de cycle de vie, **après** que la cible est ré-sondée (donc sur l'élément observé, et redacté) :

- `present_intent(action, decision)` — avant exécution : highlight cible + banner.
- `present_gate(action)` — au gate : emphase rouge sur la cible exacte.
- `present_executed(action, result)` — après : ripple/clic, fade.
- `present_refused(action, reason)` — bref flash refus.

`Presenter` = protocole pur (comme `HumanGate`/`Actuator`). `NullPresenter` no-op → cœur testable sans GUI. `OverlayPresenter` traduit cycle moteur → commandes IPC, en appliquant la redaction des labels.

Les **sens** exposent aussi des hooks présentation optionnels (Touché sondé → perception-trace), mais c'est secondaire ; priorité au moteur.

**Surface MCP** (l'overlay est aussi pilotable explicitement par l'agent) :
- `overlay_highlight(x, y, width, height, label="")` — encadrer.
- `overlay_spotlight(x, y, width, height)` — focus/vignette.
- `overlay_cursor(x, y)` — déplacer le halo.
- `overlay_banner(text)` — afficher un message.
- `overlay_clear()` — tout effacer.

Auto-câblage moteur = défaut premium (les actions sont toujours montrées) ; les tools = contrôle fin volontaire.

---

## 6. Architecture des modules

```
src/daimon/overlay/
  protocol.py     # PUR : dataclasses des commandes (Highlight/Spotlight/Cursor/Ripple/Banner/Gate/Clear) ↔ JSON ligne
  client.py       # OverlayClient : connecte le socket, envoie, bufferise/reconnecte ; no-op si absent
  presenter.py    # Presenter (protocol) + NullPresenter + OverlayPresenter (cycle moteur → commandes, redaction labels)
  launcher.py     # localiser/auto-spawn le process overlay, chemin du socket
  app/
    __main__.py   # entrée du process overlay : NSApplication + socket server + run loop
    server.py     # boucle socket asyncio sur le run loop AppKit (lit les commandes, applique)
    window.py     # OverlayWindow : NSWindow transparente, click-through, sharingNone, all-spaces
    scene.py      # gestion des CALayers (highlight, halo, spotlight, banner) + animations
  theme.py        # PUR : couleurs/rayons/durées par niveau et type
src/daimon/motor/organ.py   # + presenter optionnel, appels de cycle de vie
src/daimon/server.py        # wire OverlayPresenter si config overlay.enabled ; enregistre overlay_* tools
src/daimon/config.py        # OverlayConfig (enabled, theme, opacity, anti_feedback)
```

Frontière : **tout le pur** (protocol, theme, presenter-logic, client-buffering, redaction des labels) est OS-agnostique et **unit-testé**. Le **GUI** (`overlay/app/*`) est macOS, mince, validé par smoke. Le jumeau Windows (V2) réécrit `overlay/app/*` (layered window) en gardant protocol/presenter/theme.

---

## 7. Protocole IPC

Socket Unix `$\{TMPDIR\}/daimon-overlay.sock`. Messages = une commande JSON par ligne. Exemples :
```json
{"cmd":"highlight","x":100,"y":200,"w":80,"h":30,"label":"AXButton \"Send\"","style":"gate"}
{"cmd":"ripple","x":140,"y":215}
{"cmd":"banner","text":"press • submit the form","level":"L3"}
{"cmd":"clear"}
```
`style`/`level` pilotent thème + animation. Le client envoie « fire-and-forget » ; jamais bloquant pour une action moteur (timeout court, échec silencieux).

---

## 8. Tests

- **protocol** : sérialisation/désérialisation round-trip de chaque commande ; champs requis.
- **theme** : mapping niveau/style → couleur/durée déterministe.
- **presenter** : `NullPresenter` no-op ; `OverlayPresenter` émet les bonnes commandes par point de cycle ; **redaction** — une cible secrète (`is_target_secret`) produit un label `🔒 protégé`, jamais la valeur ; gate → style `gate`.
- **client** : bufferise / drop silencieux quand pas de socket ; reconnexion ; jamais d'exception remontée à l'appelant.
- **launcher** : résolution du chemin socket ; décision spawn vs déjà-vivant (mock process).
- **organ** : avec un `RecordingPresenter`, les 4 points de cycle sont appelés avec l'action **observée** (post-reprobe) ; l'absence de presenter (Null) ne change rien aux verdicts.
- **smoke GUI** : `scripts/smoke_overlay.py` lance le process, envoie une séquence (highlight → ripple → gate → clear) ; vérif manuelle premium (fluidité, click-through, invisible à `vue_snapshot`).

Tout le pur sans macOS. Le GUI : smoke + un test que `vue_snapshot` ne capture pas l'overlay (sharingNone) si faisable, sinon vérif manuelle documentée.

---

## 9. Invariants

- Overlay **jamais sur le chemin critique** : toute erreur/absence IPC = action moteur inchangée.
- **Click-through** garanti (jamais d'interception).
- **Anti-feedback** : overlay exclu de la capture.
- **Secret-safe** : labels redactés, jamais de fuite via l'affichage.
- Cœur moteur **pur** : presenter injecté, `NullPresenter` par défaut.
- Auto-câblage opère sur la cible **observée** (post-reprobe A1), donc cohérent avec ce qui sera réellement fait.

---

## 10. Hors-scope Phase 1

Windows overlay (V2) ; enregistrement vidéo de session ; overlay configurable par l'utilisateur au-delà de enabled/theme/opacity ; perception-trace riche (un hook minimal seulement) ; thèmes multiples (un thème premium soigné).
