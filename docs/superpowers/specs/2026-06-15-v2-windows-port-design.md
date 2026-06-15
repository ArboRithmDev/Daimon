# Daimon V2 — Port Windows x86/x64 (iso-fonctionnel) — Design

**Date**: 2026-06-15
**Statut**: cadrage validé (arbitrages tranchés par Ben), umbrella V2. Chaque organe Windows aura son cycle spec → plan → impl.
**Parent**: [Charte MVP V1](2026-06-12-v1-mvp-charter.md) — §6 invariants (« Windows V2 = écrire des adaptateurs, pas réécrire le cœur ») + §2 (« Windows = V2 »).
**Précède**: les specs par organe Windows (W1 percevoir, W2 agir, W3 montrer, W4 portée, W5 ship).
**Contexte**: V1 macOS fonctionne end-to-end (DMG signé+notarisé, pilote de vraies apps). Le cœur a été conçu OS-agnostique dès l'origine, mais **aucun dispatch plateforme n'existe encore** : `motor/factory.py` instancie en dur `MacOSActuator / MacOSGate / MacOSProber`, et les senses / permissions / overlay / tray / gui importent directement pyobjc. Le port = (1) introduire un sélecteur OS, (2) écrire les jumeaux Windows, sans toucher le cœur ni régresser macOS.

**Correctifs Mac intégrés (V1 @ 0.0.3, 2026-06-15)** : deux fix récents ont une portée directe sur le port (détail §4.3) :
- `93fed54` — overlay : serveur socket concurrent (accept-loop + thread/conn + compteur de connexions vives + idle-quit garde-génération) qui empêche les overlays orphelins de se multiplier. **Le fix a extrait des seams injectables** (`scheduler`/`terminate`/`main_dispatch`) → la logique de cycle de vie est OS-agnostique et **réutilisée telle quelle** sur Windows ; seuls le transport (AF_UNIX) et le spawn détaché changent.
- `21c8b69` — `__version__` dérivée d'`importlib.metadata`, fallback littéral épinglé par `tests/test_version.py`. Cross-platform : porte tel quel, et le même raisonnement « binaire figé sans dist-metadata » s'applique à l'**exe PyInstaller** (cf. W5).

---

## 1. Objet

Livrer une version Windows **x86/x64 iso-fonctionnelle** de Daimon : mêmes outils MCP (`vue_*`, `touche_*`, `main_*`, `overlay_*`), même triade (percevoir / agir / montrer), même modèle de sécurité (plafond L0–L4 enforced par Daimon, gate point-de-non-retour, secrets non-fuités, ledger immuable, coupe-circuit). Distribué comme app Windows signée (Authenticode).

**Non négociable** : la sécurité ne doit PAS régresser au passage macOS → Windows. Windows offre des garde-fous OS plus faibles que TCC (cf. §5) ; les adaptateurs Windows doivent compenser, pas diluer.

---

## 2. Principe d'architecture : sélecteur OS, cœur intact

### 2.1 Ce qui se réutilise tel quel (0 modification)

Le cœur pur OS-agnostique est porté **sans une ligne changée** :

- `motor/` : `guard`, `reversibility`, `consent`, `audit`, `types`, `actions`, `watchdog`, `organ`
- `capture/treeshape` (bornage d'arbre pur)
- `overlay/` : `protocol`, `theme`, `presenter` (purs) ; **`overlay/app/server.py` : la logique de cycle de vie réutilisée telle quelle via ses seams** — voir §4.3. Le **transport** (`client`, `launcher`, le socket de `server`) est lié à AF_UNIX → seam Windows (§3, §4.3)
- `tray/` : `menu_model`, `state`, `settings`
- `setup/` : `wizard`, `onboard_flow`, `clients/base`
- `config`, `exclusions` (redaction PIL pure), `applog`

Les doubles de test (`FakeActuator`, `FakeGate`, `FakeProber`, `FakeBackend`, `RecordingIO`) garantissent que ce cœur reste vert sur Windows sans aucune dépendance OS.

### 2.2 Sélecteur de plateforme (W0 — pré-requis)

On introduit un package `src/daimon/backends/` qui résout les implémentations selon `sys.platform` :

```
backends/
  __init__.py          # build_actuator(), build_gate(), build_prober(),
                       # build_screen(), build_a11y(), build_permissions()
                       # → dispatch darwin / win32 (NotImplementedError ailleurs)
```

`motor/factory.py` cesse d'importer `MacOSActuator` etc. en dur ; il appelle `backends.build_*()`. Idem senses (`vue`, `touche`), `setup/permissions`, `overlay`, `tray`, `setup/gui`. **Invariant W0 : zéro régression macOS, suite verte sur Mac avant d'écrire la moindre ligne Windows.**

> Note : les modules macOS existants sont renommés/déplacés sous le dispatch (ex. `motor/actuator.py::MacOSActuator` reste, exposé via `backends`). Les jumeaux Windows vivent à côté (`*_win` ou sous `backends/win/`).

---

## 3. Mapping par organe (technos tranchées)

| Organe | macOS (V1) | Windows (V2) | Lib |
|--------|-----------|--------------|-----|
| **Vue — capture** | Quartz `CGDisplayCreateImage` → PIL | **Windows.Graphics.Capture (WGC)** par moniteur → PIL | `pywinrt`/`winrt` |
| Vue — frontmost app | `NSWorkspace.frontmostApplication().bundleIdentifier()` | `GetForegroundWindow`→`GetWindowThreadProcessId`→`QueryFullProcessImageName` (chemin exe / AUMID) | `ctypes`/`pywin32` |
| **Touché — a11y** | AX API (`AXUIElementCopy*`, `...AtPosition`, `...SystemWide`) | **UI Automation** : `ElementFromPoint`, `GetFocusedElement`, `RawViewWalker` | `comtypes` (IUIAutomation) ou `uiautomation` |
| Touché — secret field | sous-rôle `AXSecureTextField` | propriété UIA `IsPassword` (+ ControlType) | idem |
| Touché — bounds/role | `kAXPosition/SizeAttribute`, `kAXRoleAttribute` | `CurrentBoundingRectangle`, `CurrentControlType` | idem |
| **Mains — click/move/drag/scroll** | `CGEventCreateMouseEvent`/`...ScrollWheel` | **`SendInput`** (MOUSEINPUT, MOUSEEVENTF_*) | `ctypes` user32 |
| Mains — type (unicode) | `CGEventKeyboardSetUnicodeString` | `SendInput` **`KEYEVENTF_UNICODE`** (parité directe) | `ctypes` |
| Mains — key + modifiers | `CGEventCreateKeyboardEvent` + flag mask | `SendInput` VK keydown/up ; **modifiers = keydown/up encadrant** (pas un flag) | `ctypes` |
| Mains — keycodes | Carbon `kVK_*` (`keys.py`) | table `VK_*` Windows (`keys_win.py`) | pur |
| Mains — press (sémantique) | `AXUIElementPerformAction(kAXPressAction)` | UIA **`InvokePattern.Invoke()`** (fallback `TogglePattern`/`SelectionItemPattern`) | `comtypes` |
| Mains — activate app | `NSRunningApplication.activate` | `SetForegroundWindow` / `ShowWindow(SW_RESTORE)` | `ctypes` |
| **Overlay — fenêtre** | `NSWindow` borderless+clear+click-through+`NSScreenSaverWindowLevel` | **Qt (PySide6)** fenêtre `FramelessWindowHint \| WindowStaysOnTopHint \| Tool`, `WA_TranslucentBackground`, `WindowTransparentForInput` | `PySide6` |
| Overlay — capture-invisible | `setSharingType_(NSWindowSharingNone)` | **`SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)`** (Win10 2004+) sur le HWND Qt | `ctypes` |
| Overlay — rendu (scene) | CoreAnimation CALayers | **QML** (Rectangle/animations) piloté par le `protocol` existant | `PySide6` QML |
| Overlay — transport | socket **AF_UNIX** (`/tmp` / `$TMPDIR`) | **TCP loopback 127.0.0.1** (ou named pipe) — AF_UNIX peu fiable en Python Windows | `socket` |
| Overlay — spawn détaché | `start_new_session=True` | `creationflags=DETACHED_PROCESS \| CREATE_NEW_PROCESS_GROUP` | `subprocess` |
| Overlay — lifecycle/concurrence | accept-loop + thread/conn + compteur live + idle-quit (server.py) | **logique réutilisée telle quelle** ; injecter seams Qt (QTimer / quit / invokeMethod) | partagé |
| **Tray** | `NSStatusItem` | **`Shell_NotifyIcon`** + menu `TrackPopupMenu` (ou `QSystemTrayIcon`) | Qt `QSystemTrayIcon` |
| **GUI onboarding** | AppKit | **PySide6** (même stack que l'overlay) | `PySide6` |
| **Permissions** | TCC (Screen Recording + Accessibility) | **pas de TCC** → quasi no-op + check UIPI/intégrité (cf. §5) | `ctypes` |
| data dir | `~/Library/Application Support/Daimon` | `%APPDATA%\Daimon` | `platformdirs` |
| client paths | `~/Library/...`, `/Applications/*.app` | `%APPDATA%`, `%USERPROFILE%\.claude.json`, registre/Start Menu | nouvelle table |
| ledger durabilité | `fcntl.flock` | `msvcrt.locking` / `portalocker` | — |
| Packaging | DMG signé + notarisé | **PyInstaller → exe + Inno Setup/MSIX + Authenticode** | — |

**Décision UI unifiée** : overlay ET GUI onboarding en **PySide6/Qt** → une seule stack UI Windows (bundle Qt amorti une fois, animations QML fluides, cohérence visuelle).

---

## 4. Détail des points durs

### 4.1 W2 — Gate point-de-non-retour : Secure Desktop (point dur n°1, sécurité)

**Problème.** Sur Windows, un process à intégrité égale peut `SendInput` vers n'importe quelle fenêtre de même intégrité ou inférieure — **y compris la propre boîte de confirmation de Daimon**. Un agent L2+ capable de synthétiser des entrées pourrait cliquer « Autoriser » sur son propre dialogue (auto-confirmation), annulant le gate. Une simple `MessageBox` topmost ne suffit donc PAS : ce serait une régression de sécurité vs macOS.

**Décision : Secure Desktop.** Le gate s'affiche sur un bureau sécurisé séparé, mécanisme identique à celui de l'UAC :

- `CreateDesktop` (ou usage du Winlogon secure desktop) + `SwitchDesktop` vers un desktop dédié au moment de la confirmation.
- L'input synthétique de l'agent (envoyé sur le desktop par défaut) **n'atteint pas** le secure desktop → auto-confirmation impossible **par construction**, pas par convention.
- L'écran s'assombrit (UX type UAC), l'humain confirme physiquement, retour au desktop par défaut.
- **Fail-safe conservé** : timeout (30 s) ou toute erreur → DENY (parité `MacOSGate`).
- Implémenté dans un **helper process** dédié (le serveur MCP n'a pas à manipuler les desktops lui-même).

> C'est l'équivalent fort de la garantie macOS (où l'osascript dialog + le modèle de fenêtres rend l'auto-clic non trivial). Un **PoC isolé** du Secure Desktop est recommandé en tout début de W2 (risque technique le plus élevé du port).

### 4.2 W3 — Overlay : rendu sans équivalent CALayer (point dur n°2)

CoreAnimation n'a pas de jumeau Windows 1:1. On **réécrit `scene`** en QML : chaque commande du `protocol` (`Highlight`, `Spotlight`, `Cursor`, `Ripple`, `Banner`, `Clear`) pilote des items QML animés. Le `protocol`, le `theme`, le `presenter`, le `client` et le `launcher` restent inchangés (le contrat socket est OS-agnostique). La fenêtre Qt doit être :

- **frameless + topmost + translucide** (per-pixel alpha),
- **click-through** (`WindowTransparentForInput` ou `WS_EX_TRANSPARENT` sur le HWND),
- **capture-invisible** : `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` appliqué au HWND natif de la fenêtre Qt — d'où le **plancher Win10 2004**.

### 4.3 W3 — Overlay : concurrence & non-prolifération (correctif Mac `93fed54`, V1 @ 0.0.3)

Le correctif a réécrit `overlay/app/server.py` : un seul helper overlay partagé peut être piloté par **plusieurs serveurs MCP à la fois** (une connexion `OverlayClient` par process, tenue pour sa durée de vie). Le serveur garde donc un **accept-loop permanent**, traite chaque connexion dans son **thread**, **compte les connexions vives**, et ne se termine (scène nettoyée) qu'à **zéro client**, après une **grâce** vétoée par toute reconnexion (garde par **génération** `_quit_gen`). Ça ferme le symptôme « Daimon se multiplie » : avant, le serveur acceptait une seule connexion puis restait coincé dans son `recv` sans rappeler `accept()`, les probes de liveness rataient le serveur occupé, et le launcher spawnait des overlays dupliqués qui s'accumulaient en orphelins.

**Portée Windows — favorable.** La logique est OS-agnostique et le fix a déjà extrait des **seams injectables** (`scheduler`, `terminate`, `main_dispatch`). Le portage :
- **réutilise la logique de cycle de vie telle quelle** (compteur live + idle-quit garde-génération + accept concurrent + per-connection thread) ;
- injecte les **seams Qt** au lieu des défauts pyobjc :
  - `scheduler` → `QTimer.singleShot(delay_ms, fn)` (vs `AppHelper.callLater`) ;
  - `terminate` → `QApplication.quit()` / `qApp.exit()` (vs `NSApp().terminate_`) ;
  - `main_dispatch` → `QMetaObject.invokeMethod(obj, ..., Qt.QueuedConnection)` ou un signal Qt (vs `AppHelper.callAfter`) ;
- remplace **seulement** le **transport** (AF_UNIX → TCP loopback / named pipe ; `socket_path`/`_socket_alive`/`os.unlink`/`bind`) et le **spawn détaché** (flags Windows). Le `_flip_cmd` (flip Y top-left → bottom-left) reste pur.

**Invariant Windows hérité** : l'overlay **ne doit pas se multiplier** non plus — même cycle live-count→quit, mêmes probes de liveness côté launcher, même auto-guérison de la course de démarrage à froid (le perdant finit à zéro client et se quitte). À couvrir par les **mêmes tests de lifecycle** (connect→disconnect→quit) que `tests/test_overlay_server.py`, qui passent par les seams donc tournent sans Windows.

---

## 5. Modèle de sécurité — deltas Windows (à acter)

Le port n'est pas neutre côté sécurité. Windows a des garde-fous OS plus faibles que macOS TCC ; on documente et on compense.

1. **Pas de gate de permission OS.** macOS force l'utilisateur à accorder Screen Recording + Accessibility (TCC) = vrai checkpoint de consentement. Windows accorde capture (WGC) + `SendInput` + UIA **librement, sans prompt**. Conséquence : **l'enforcement du plafond par Daimon devient le seul garde-fou**. `permissions.py` Windows devient quasi no-op ; l'onboarding bascule de « accorde ces permissions » vers « **il n'y a pas de filet OS — règle ton plafond délibérément, lis le modèle de sécurité** ».

2. **Gate renforcé par Secure Desktop** (cf. 4.1) — compense l'absence d'isolation naturelle des fenêtres.

3. **Frontières positives Windows à exposer comme garanties** :
   - Le **Secure Desktop** (UAC, login, Ctrl+Alt+Del) est non-capturable et non-pilotable par design → l'agent **ne peut pas auto-approuver une élévation UAC**.
   - **UIPI** : un Daimon non-élevé ne peut pas `SendInput` vers une fenêtre admin → un agent ne pilote pas une app élevée.

4. **Inchangés (portables tels quels)** : blackout pixels Vue (PIL pur), redaction par contenu/rôle/app (UIA `IsPassword` + chemin exe en remplacement du bundle id), ledger hash-chaîné (juste `flock` → `msvcrt.locking`), coupe-circuit physique (kill process).

---

## 6. Phases (miroir de la charte)

| Phase | Contenu | Acceptation |
|-------|---------|-------------|
| **W0 — Refacto** | Package `backends/` + dispatch `sys.platform` ; `factory`/senses/setup/overlay/tray passent par le sélecteur | Suite macOS verte, **zéro régression**, dispatch testé |
| **W1 — Percevoir** | `screen_win` (WGC→PIL, frontmost via GetForegroundWindow), `a11y_win` (UIA tree/point/focus, IsPassword), `keys_win` (table VK) | Vue+Touché bornés ; aucun secret connu fuité (UIA IsPassword + blackout) |
| **W2 — Agir** | `actuator_win` (SendInput + UIA Invoke), `prober_win` (UIA ElementFromPoint), **`gate_win` Secure Desktop** (PoC d'abord) | Red-team du gate : un agent qui SendInput ne peut PAS auto-confirmer ; re-sonde observée OK |
| **W3 — Montrer** | overlay Qt/QML (frameless+translucide+click-through) + `WDA_EXCLUDEFROMCAPTURE` ; `scene` réécrit en QML ; **transport TCP loopback + lifecycle `server.py` réutilisé via seams Qt** (§4.3) | L'action est tracée visuellement ; overlay invisible à Vue ; n'intercepte jamais les clics ; **pas d'overlays orphelins/multipliés** (cycle live-count→quit hérité du fix Mac) |
| **W4 — Portée** | tray `QSystemTrayIcon`, GUI onboarding PySide6, `registry_win` (chemins clients Windows), `userdata` %APPDATA% via platformdirs | Un utilisateur neuf va de l'installeur à l'agent fonctionnel sans terminal |
| **W5 — Ship** | PyInstaller → exe ; installeur Inno Setup ou MSIX ; **Authenticode** (cert EV pour réputation SmartScreen) ; beta → public. Tray lit `__version__` via `importlib.metadata` ; **l'exe figé (sans dist-metadata) retombe sur `_FALLBACK_VERSION` épinglé par `tests/test_version.py`** (identique au .app figé, fix `21c8b69`) | Install propre sur Windows vierge, SmartScreen non bloquant ; version affichée = pyproject ; sign-off beta |

Dépendances : W0 avant tout. W2 dépend de W1 (re-sonde UIA). W3 se branche sur les bounds Touché (après W1). W4 ergonomie après cœur fiable. W5 packaging en dernier.

---

## 7. Fichiers livrés (cible)

```
src/daimon/
  backends/
    __init__.py                 # dispatch darwin/win32 → build_*()
  capture/
    screen_win.py               # WGC → PIL ; frontmost via Win32
    accessibility_win.py        # UIA : snapshot_tree / element_at / focused_element
  motor/
    actuator_win.py             # SendInput (mouse/key/drag/scroll/unicode) + watchdog
    prober_win.py               # UIA ElementFromPoint → observed target
    gate_win.py                 # Secure Desktop (helper) ; timeout/erreur → DENY
    keys_win.py                 # table VK + modifiers (keydown/up)
  overlay/
    transport_win.py            # TCP loopback / named pipe (remplace AF_UNIX)
    launcher_win.py             # socket_path / _socket_alive / _spawn Windows (flags détachés)
    app/
      window_win.py             # Qt frameless+translucide+click-through+WDA
      scene_qml/                # QML : highlight/spotlight/cursor/ripple/banner
      server_seams_win.py       # seams Qt (QTimer/quit/invokeMethod) ; lifecycle OverlayServer (server.py) réutilisé tel quel
  tray/
    app/
      trayicon_win.py           # QSystemTrayIcon + menu
  setup/
    gui_win/                    # onboarding PySide6
    permissions_win.py          # no-op TCC + checks UIPI/intégrité
    clients/registry_win.py     # chemins clients Windows (%APPDATA%, registre)
  userdata.py                   # platformdirs : %APPDATA%\Daimon (multiplateforme)
build/
  windows/
    daimon.spec                 # PyInstaller (exe GUI + exe console)
    daimon.iss / daimon.msix    # Inno Setup ou MSIX
    sign_windows.ps1            # Authenticode (signtool)
    README.md
pyproject.toml                  # extras [win] = pywinrt, comtypes/uiautomation, PySide6, pywin32, portalocker
```

Cœur (`guard`, `reversibility`, `consent`, `audit`, `types`, `actions`, `watchdog`, `treeshape`, `protocol`, `theme`, `presenter`, `menu_model`, `wizard`, `config`, `exclusions`) : **aucun fichier modifié** hormis l'extraction du dispatch en W0.

---

## 8. Invariants

- **Cœur inchangé.** Le port n'ajoute que des adaptateurs + un sélecteur. Toute logique de sécurité/politique reste dans le cœur pur, partagée bit-pour-bit entre macOS et Windows.
- **Doctrine V1 conservée** : pull/agnostique (MCP), Daimon enforce le plafond, perception ≠ action par défaut (L0), coupe-circuit prioritaire, consentement L4 écrit + ledger immuable.
- **Pas de régression sécurité.** Le gate Windows (Secure Desktop) est au moins aussi fort que macOS ; l'absence de TCC est compensée par un onboarding honnête et l'enforcement du plafond.
- **DI préservée.** Chaque organe Windows ships son chemin réel + reste testable via les `Fake*` du cœur ; le pur s'unit-teste sans Windows, les surfaces natives sont smoke-validées (comme macOS).
- **Zéro régression macOS** à chaque phase (W0 inclus).

---

## 9. Hors-scope V2

- ARM64 Windows (port x86/x64 d'abord ; adaptateurs Qt/UIA/WGC sont arch-agnostiques mais le bundle/sign cible x64).
- Auto-update.
- Fonctions pro (équipe/échelle) — seulement la graine d'extension, comme V1.
- Remote/cloud/multi-machine.
- Parité pixel-perfect de l'esthétique overlay (le QML vise l'équivalence fonctionnelle, pas la copie exacte des courbes CoreAnimation).

---

## 10. Arbitrages tranchés (2026-06-15)

| # | Sujet | Décision |
|---|-------|----------|
| 1 | Gate point-de-non-retour | **Secure Desktop** (CreateDesktop/SwitchDesktop) — garantie max, = macOS |
| 2 | Capture écran + plancher OS | **WGC**, plancher **Win10 2004** (WDA_EXCLUDEFROMCAPTURE dispo) |
| 3 | Rendu overlay | **Qt QML** (PySide6) |
| 4 | GUI onboarding | **PySide6** → une seule stack UI Qt (overlay + onboarding) |

**Prochaine étape** : W0 (refacto `backends/` + sélecteur OS, zéro régression macOS), puis cycle spec → plan → impl de W1.
