# Daimon V1 — Phase 3 — Packaging (signed DMG) — Design

**Date**: 2026-06-13
**Statut**: validé (cadrage autonome), prêt pour implémentation. Le build signé s'exécute sur le Mac de Ben avec ses credentials Apple.
**Parent**: [Charte MVP V1](2026-06-12-v1-mvp-charter.md) — Phase 3, sous-système E.
**Template**: pipeline DMG de **SecondBrain Desktop** (`/Users/Ben/Projets/SecondBrain/desktop-app/build/macos/`) — PyInstaller → sign → hdiutil → notarytool → stapler.
**Décisions** : Apple Developer ID = oui (sign+notarize complet) ; bundle `fr.arborithm.daimon`, app « Daimon ».

---

## 1. Objet

Produire un **DMG signé (Developer ID) + notarisé** que n'importe qui installe sans alerte Gatekeeper. C'est le sous-système E de la charte. Le **gate release** (secrets contenu) est déjà atteint (Phase 0b).

---

## 2. Ce qu'on reprend de SecondBrain (tel quel)

Pipeline `build_macos.sh` identique en structure :
1. venv-build dédié, install des deps + PyInstaller.
2. Icônes → `.icns` via `iconutil`.
3. PyInstaller (spec) → `.app` (BUNDLE).
4. **Sign** : Mach-O embarqués + `Python.framework` + `.app`, **hardened runtime** (`--options runtime --timestamp`).
5. **DMG** via `hdiutil` (UDZO, symlink `Applications`, volume icon).
6. Sign du DMG.
7. **Notarize** : `xcrun notarytool submit --wait` + `xcrun stapler staple`.
8. Vérif : `codesign --verify` + `spctl` + `stapler validate`. Publish `gh release upload`.
Escape hatches `--no-sign` / `--no-notarize`. Creds via env `DEV_ID`/`TEAM_ID` + keychain profile `AC_PASSWORD`.

---

## 3. Différences Daimon (ce qu'on adapte)

Daimon n'est pas une app tray Tkinter. C'est : **serveur MCP stdio** + **process overlay** AppKit + **CLI/GUI onboarding**. Adaptations :

### 3.1 Le `.app` = lanceur d'onboarding
`Daimon.app` au double-clic lance la **GUI d'onboarding** (Phase 2 : `daimon.setup.gui`) — enregistre Daimon dans les clients IA détectés + guide les permissions. C'est l'expérience premier-lancement. Le `.app` n'est PAS le serveur (les clients lancent une commande, pas un double-clic).

### 3.2 Deux exécutables dans le bundle
Le spec PyInstaller produit **deux EXE** partageant la même payload collectée :
- **`Daimon`** (windowed, `console=False`) — entrée GUI onboarding (`src/daimon/setup/gui/__main__.py`). = `CFBundleExecutable`.
- **`daimon`** (console) — dispatcher serveur/CLI (`src/daimon/__main__.py`, no-arg = serveur MCP, back-compat).

Les clients MCP sont enregistrés sur `…/Daimon.app/Contents/MacOS/daimon`. Le double-clic lance `Daimon` (GUI).

### 3.3 `invocation.py` préfère le binaire bundlé
Ordre de résolution mis à jour : si `/Applications/Daimon.app/Contents/MacOS/daimon` existe → l'utiliser ; sinon `which daimon` ; sinon `python -m daimon`. Ainsi l'auto-install (Phase 2) enregistre le binaire bundlé après installation du DMG.

### 3.4 Piège TCC (responsible-process)
Mémoire [[daimon-tcc-inheritance]] : la permission Screen Recording / Accessibility s'attache au **parent GUI** qui lance daimon (l'app cliente : Terminal/Ghostty/Claude/VS Code), **pas** à `Daimon.app`. Conséquences sur l'onboarding lancé depuis le `.app` :
- Demander/ouvrir le volet est utile, mais **le grant doit cibler l'app cliente**, pas Daimon.app.
- Une vérif `is_trusted()` depuis le process Daimon.app ne reflète PAS le statut de l'app cliente.

**Traitement v1** (honnête, sans sur-ingénierie) :
- L'onboarding **explique clairement** : « Accorde ces permissions à l'application qui lance ton IA (ex. Terminal, Ghostty, Claude, VS Code) » et ouvre le bon volet.
- **Vérif robuste = self-report côté serveur** : quand le client lance le binaire `daimon` bundlé, le serveur (dans le bon responsible-process) peut s'auto-tester (`is_trusted` / `CGPreflightScreenCaptureAccess`) et écrire un **marqueur de statut** (`~/Library/Application Support/Daimon/permissions.json`). La GUI d'onboarding lit ce marqueur pour confirmer « ton IA a bien les permissions ✅ » — vérif dans le bon contexte sans deviner.
- Tant que le marqueur n'existe pas (IA jamais lancée encore), l'onboarding affiche « lance une fois ton IA pour vérifier » + confirmation manuelle possible.

### 3.5 Pas de moteur séparé / wheels offline
SecondBrain bundlait un moteur `memory-kit-mcp` + wheels offline. Daimon est **autonome** (un seul package) → on **supprime** l'étape staging/wheels. Plus simple.

### 3.6 Hidden imports PyInstaller
Daimon dépend de **pyobjc** (Quartz, AppKit, ApplicationServices, Foundation, CoreFoundation), **mcp/fastmcp**, **Pillow**, **PyYAML**. `collect_all` sur ces paquets + `collect_submodules("daimon")`. pyobjc nécessite souvent des hidden imports explicites (`objc`, `Quartz`, `AppKit`, `ApplicationServices`, `Foundation`, `PyObjCTools`).

### 3.7 Icône
Daimon n'a pas d'icône. v1 : un **générateur d'icône programmatique** (`build/make_icon.py`, Pillow) dessine un glyphe sobre (ex. « δ »/cercle premium) → iconset → `.icns`. Marqué « remplacer par l'art final ». Maintenable, débloque le build ; l'art définitif vient ensuite.

### 3.8 Min OS / arch
`LSMinimumSystemVersion` = 11.0 (Big Sur ; les API AX/Quartz/CGPreflight sont ≤ 10.15). `target_arch=None` (arch de la machine de build ; universal2 possible plus tard).

---

## 4. Fichiers livrés

```
build/
  daimon.spec                 # PyInstaller : 2 EXE (Daimon GUI + daimon CLI) → BUNDLE Daimon.app
  make_icon.py                # générateur d'icône placeholder (Pillow) → PNGs
  macos/
    build_macos.sh            # pipeline adapté (sign/dmg/notarize, escape hatches)
    Info.plist.template       # fr.arborithm.daimon, Daimon, min OS, NOT LSUIElement
    README.md                 # instructions (creds, build, verify, publish) adaptées
src/daimon/setup/invocation.py  # préférer le binaire bundlé
src/daimon/setup/permissions.py # + écriture du marqueur de statut (self-report serveur)
pyproject.toml                # extra [build] = pyinstaller
```

Pas de tests unitaires pour les scripts/spec (infra) ; la **résolution d'invocation** (3.3) et le **marqueur de permissions** (3.4) sont du code testable → tests purs. Validation du build = exécution réelle sur le Mac (`--no-sign` d'abord, puis signé).

---

## 5. Flux de build (résumé pour le README)

```bash
# prérequis : Xcode CLT, Python 3.12+, Developer ID dans le keychain,
#             xcrun notarytool store-credentials AC_PASSWORD …
export DEV_ID="Developer ID Application: <Nom> (TEAMID)"
export TEAM_ID="TEAMID"
cd /Users/Ben/Projets/Daimon
./build/macos/build_macos.sh                 # signé + notarisé
./build/macos/build_macos.sh --no-sign       # build local rapide (test)
# vérif : codesign --verify / spctl / stapler validate
# publish : gh release upload daimon-v<version> dist/Daimon-<version>.dmg
```

---

## 6. Invariants

- Pipeline **idempotent** et rejouable ; `--no-sign`/`--no-notarize` pour itérer sans creds.
- **Aucune corruption** : le DMG est l'artefact ; le `.app`/staging nettoyés sauf `KEEP_MACOS_BUILD_PRODUCTS=1`.
- **Honnête sur TCC** : on guide vers l'app cliente, on vérifie via self-report serveur dans le bon contexte, on ne prétend rien.
- **Back-compat** : `daimon` no-arg reste le serveur MCP ; le binaire bundlé l'expose pareil.
- **Cœur inchangé** : Phase 3 = packaging + 2 petits ajouts code (invocation bundlée, marqueur permissions) ; aucune régression des phases 0-2.

---

## 7. Hors-scope Phase 3

Universal2/arch croisée ; auto-update (Sparkle) ; lancement auto de l'onboarding au 1er run via `LSUIElement`/launch ; Windows (V2) ; l'art final de l'icône ; fonctions pro. Le build signé lui-même s'exécute hors de cet environnement (Mac + credentials de Ben).
