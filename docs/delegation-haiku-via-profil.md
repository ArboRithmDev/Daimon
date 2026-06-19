# Déléguer le pilotage Daimon à un petit modèle via profil (AXE 5)

> **But** : rendre la délégation Daimon viable. Un **orchestrateur** (gros modèle)
> passe à un **sous-agent petit modèle rapide (Haiku)** uniquement un **nom de
> profil** + un **objectif**. Le sous-agent pilote l'UI **mécaniquement** (sans
> aucun raisonnement géométrique) et ne renvoie que le **texte extrait**. Les
> screenshots restent **hors du contexte de l'orchestrateur**.
>
> **Capitalise sur** : AXE 1 (coords déterministes, `space="image"` + `vue_resolve`),
> AXE 2 (profil persisté + auto-match par signature), AXE 3 (`vue_find` pour les
> apps sans arbre a11y). Aucune nouvelle capacité backend — c'est un **pattern
> d'orchestration** + un petit helper (`vue_profile_brief`).

---

## 1. Pourquoi ça marche maintenant

Le premier pilotage réel (2026-06-19, WinDev multi-écrans) a réussi le métier mais
brûlé ~6 itérations rien qu'au **calibrage des coordonnées**, parce que le pilote
devait dériver à l'aveugle `global_x = image_x × (1920/1600) − 1920`. Inacceptable,
et **impossible à confier à un petit modèle** : ça demande du raisonnement
géométrique multi-étapes.

Les axes 1→3 ont supprimé ce raisonnement :

- **AXE 1** — Daimon résout lui-même image→global. Le pilote passe des pixels
  **locaux à un snapshot** (`space="image"`, `display=k`) ; Daimon applique
  offset + downscale en interne. Plus jamais de coords globales négatives à la
  main.
- **AXE 2** — la topologie écran est gelée une fois par environnement sous un
  **profil nommé** (`bureau-3-ecrans`, `portable-seul`, …) et **auto-matchée par
  signature** au boot. La résolution coords lit la géométrie du profil
  (`source="profile"`) au lieu de re-sonder.
- **AXE 3** — pour les apps qui n'exposent pas d'arbre a11y (WinDev, vieux Win32,
  Electron custom-drawn), `vue_find(text)` localise un libellé visible par OCR et
  renvoie des coords **déjà cliquables**.

Conséquence : **cliquer juste ne demande plus de réflexion**. C'est devenu une
suite d'appels d'outils déterministes — exactement le profil de tâche qu'on peut
confier à un petit modèle rapide.

---

## 2. Contrat de délégation

### Entrée (ce que l'orchestrateur fournit au sous-agent)

| Champ | Type | Rôle |
|-------|------|------|
| `profile` | `str` | Le **nom** du profil de calibrage attendu (ex. `bureau-3-ecrans`). C'est **tout** ce dont le sous-agent a besoin pour se repérer dans l'espace écran. |
| `objective` | `str` | L'objectif **mécanique** : quoi ouvrir/cliquer, quel texte extraire. Formulé en libellés visibles et étapes, **jamais en coordonnées**. |

L'orchestrateur ne passe **ni screenshot, ni coordonnée, ni géométrie**. Il connaît
le nom du profil (il l'a calibré une fois via `vue_calibrate`, ou l'a lu via
`vue_profile`).

### Sortie (ce que le sous-agent renvoie à l'orchestrateur)

| Champ | Type | Rôle |
|-------|------|------|
| `text` | `str` | **Le texte extrait** — le seul livrable métier. |
| `status` | `"ok" \| "aborted" \| "not_found"` | Issue mécanique. |
| `note` | `str` | Court diagnostic en cas d'échec (profil non matché, libellé absent…). |

Le sous-agent ne renvoie **jamais** d'image. Les screenshots restent dans **son**
contexte (jetable), pas dans celui de l'orchestrateur. C'est le gain : le gros
modèle ne paie ni les tokens d'image, ni les itérations de calibrage.

---

## 3. Le boot brief — `vue_profile_brief`

Le sous-agent reçoit un **nom** ; il doit, **sans raisonner**, vérifier que ce nom
correspond bien à la topologie écran réelle, et apprendre quels indices d'écran il
peut adresser. C'est exactement ce que renvoie l'outil `vue_profile_brief` :

```
vue_profile_brief(expected="bureau-3-ecrans")
→ {
    "matched": true,
    "active_profile": "bureau-3-ecrans",
    "signature": "9f1c…",
    "expected_ok": true,
    "displays": [
      {"index":0,"width":1920,"height":1080,"is_main":true, "origin_x":0,    "origin_y":0,"dpi":96},
      {"index":1,"width":1920,"height":1080,"is_main":false,"origin_x":-1920,"origin_y":0,"dpi":96}
    ]
  }
```

**Règle GO / NO-GO du sous-agent** : ne piloter que si `expected_ok == true`.
Si `false` (environnement inconnu, ou matché à un *autre* profil que celui passé),
le sous-agent **abandonne** et renvoie `status:"aborted"` + `note`. Il ne devine
**jamais** la géométrie — c'est tout l'intérêt de la délégation.

Le helper pur sous-jacent est `daimon.senses.calibration.active_profile_brief(store,
displays, expected=...)` : il prend la topologie injectée (pas d'accès écran propre),
matche par signature, et pose le drapeau `expected_ok`. Testé unitairement
(`tests/test_profile_brief.py`).

---

## 4. La recette — prompt du sous-agent (gabarit)

> Système / instructions du sous-agent Haiku. L'orchestrateur substitue
> `{{profile}}` et `{{objective}}`.

```
Tu es un sous-agent de pilotage Daimon. Tu agis MÉCANIQUEMENT.
Tu ne raisonnes JAMAIS sur des coordonnées, des échelles, ou des offsets d'écran :
Daimon résout tout ça pour toi. Tu désignes des écrans par leur INDEX et des
cibles par leur LIBELLÉ VISIBLE.

PROFIL ATTENDU : {{profile}}
OBJECTIF       : {{objective}}

PROTOCOLE (suis-le dans l'ordre, sans improviser) :

1. GATE. Appelle vue_profile_brief(expected="{{profile}}").
   - Si expected_ok est false → STOP. Renvoie {status:"aborted",
     note:"environnement ne correspond pas au profil {{profile}}", text:""}.
   - Sinon retiens la liste `displays` (les index adressables). NE recalcule
     aucune géométrie.

2. CIBLER L'ÉCRAN. Choisis l'index d'écran où vit l'app à piloter (souvent
   l'écran is_main, ou celui indiqué par l'objectif). Appelle-le `D`.

3. AMENER L'APP AU PREMIER PLAN. main_activate(intent=..., title=... ou bundle=...)
   AVANT tout clic positionnel (un clic sur une fenêtre en arrière-plan est un
   no-op silencieux). Tu peux aussi passer ensure_focus=True aux clics.

4. LOCALISER LA CIBLE (deux voies, essaie a11y d'abord) :
   a) touche_tree / touche_probe : si l'arbre expose la cible avec role+label,
      clique-la via main_click(role=..., label=..., x=..., y=...).
   b) FALLBACK VUE-ONLY : si Touché est muet (summary "None", PaneControl
      générique — typique WinDev/Electron), appelle
      vue_find(text="<libellé visible>", display=D, source="profile").
      Il renvoie {found, global_x, global_y, candidates}.
      - found=false → relis `candidates` (ce qui était à l'écran) et REESSAIE
        avec le libellé exact, ou STOP {status:"not_found"} après 2 essais.
      - found=true → clique : main_click(x=global_x, y=global_y, intent=...,
        window_title="<titre>", ensure_focus=true). (global_x/global_y sont
        DÉJÀ résolus — passe-les tels quels, space reste "global".)

   Variante équivalente sans vue_find, si tu lis toi-même un snapshot :
   - vue_snapshot(display=D) te donne {coord_space} + image. Repère le pixel
     IMAGE de la cible (ix, iy) puis clique en laissant Daimon résoudre :
     main_click(x=ix, y=iy, display=D, space="image", intent=...).
     Tu ne fais AUCUN calcul : "image" suffit.

5. EXTRAIRE LE TEXTE. Une fois la bonne vue affichée :
   - si la cible est dans l'arbre a11y → touche_probe / touche_tree te donne le
     texte directement (préféré : pas d'OCR).
   - sinon → vue_find / lecture de snapshot pour récupérer le libellé voulu.
   N'extrait QUE ce que l'objectif demande. Reste borné (max_depth/region).

6. RENVOIE {status:"ok", text:"<le texte extrait>", note:""}.
   N'inclus JAMAIS d'image dans ta réponse. Le screenshot reste chez toi.
```

---

## 5. Exemple concret (WinDev, écran gauche négatif)

Objectif orchestrateur : *« lis la valeur du champ `Etat_FACTURECLIENT` dans la
fenêtre WinDev de l'éditeur »*, profil `bureau-3-ecrans`.

Trace d'outils du sous-agent (aucun raisonnement géométrique) :

```
1. vue_profile_brief(expected="bureau-3-ecrans")
   → expected_ok=true ; displays addressables [0,1] ; l'éditeur est sur l'écran 1
     (origin_x=-1920, le négatif est INVISIBLE pour le sous-agent — Daimon gère).

2. main_activate(intent="bring editor frontmost", title="WinDev")

3. touche_tree(...) → summary "None" (WinDev muet) → bascule Vue-only.

4. vue_find(text="Etat_FACTURECLIENT", display=1, source="profile")
   → {found:true, global_x:-1320, global_y:512}   ← déjà global, déjà résolu

5. main_click(x=-1320, y=512, intent="focus the field",
              window_title="WinDev", ensure_focus=true)

6. vue_find(text="<valeur attendue à côté>", display=1, source="profile")  (ou
   touche_probe si le champ devient lisible) → récupère le texte.

7. renvoie {status:"ok", text:"FACT-2026-0412 / 1 240,00 €"}
```

L'orchestrateur ne voit que `text`. Pas de pixel, pas de `-1320`, pas de `0.8333`,
pas de screenshot. Le coût de calibrage est **payé une fois** (à `vue_calibrate`),
pas re-déboursé à chaque délégation.

---

## 6. Implémentation côté orchestrateur (n'importe quel client MCP)

Le pattern est **agnostique du client**. Dans Claude Code, l'orchestrateur lance le
sous-agent via le Task tool (sous-agent `general-purpose` ou dédié), en lui passant
le gabarit §4 avec `{{profile}}`/`{{objective}}` substitués, et **en restreignant ses
outils** au strict nécessaire pour que la frontière de contexte tienne :

```
allowed_tools = [
  "mcp__daimon__vue_profile_brief",
  "mcp__daimon__vue_find",
  "mcp__daimon__vue_snapshot",      # optionnel : voie "image" du §4.4
  "mcp__daimon__touche_tree",
  "mcp__daimon__touche_probe",
  "mcp__daimon__main_activate",
  "mcp__daimon__main_click",
  "mcp__daimon__main_navigate",     # si l'objectif demande de scroller
]
```

Points clés pour que la délégation tienne ses promesses :

- **Le screenshot reste chez le sous-agent.** L'orchestrateur ne reçoit que la
  réponse finale texte du sous-agent. C'est la frontière de processus/contexte qui
  fait l'économie de tokens, pas une option de Daimon.
- **GO/NO-GO strict.** Sans `expected_ok=true`, le sous-agent abandonne. Un petit
  modèle qui « se débrouille » en géométrie est exactement ce qu'on veut interdire.
- **Plafond Mains inchangé.** La délégation ne relève AUCUN garde-fou : le plafond
  L0–L4 reste appliqué par Daimon, jamais par le sous-agent (cf. invariant 3). Un
  objectif qui exigerait une action au-dessus du plafond échoue côté Daimon,
  comme pour le gros modèle.
- **Sécurité inchangée.** La redaction secrets passe toujours devant toute capture,
  y compris derrière `vue_find` (l'OCR voit l'image **déjà** noircie).

---

## 7. Critère de reproductibilité (DoD)

Une recette reproductible où un petit modèle muni d'un profil **clique juste et
extrait du texte sans raisonner sur la géométrie**. Concrètement, vérifié quand :

1. `vue_profile_brief(expected=<nom>)` renvoie `expected_ok=true` sur la machine
   cible (profil calibré au préalable). ✅ testé unitairement (helper pur +
   wiring outil).
2. Le sous-agent, en suivant §4, atteint la cible via `vue_find(...,
   source="profile")` ou `space="image"` **sans jamais manipuler offset/scale**.
   ↳ *À valider sur écran réel* (voir ci-dessous).
3. L'orchestrateur ne reçoit que `text` ; aucun screenshot ne remonte. ↳ propriété
   de la frontière de sous-agent, pas du code Daimon.

### À valider sur matériel réel (hors CI)

- Un vrai run Haiku-as-subagent sur l'environnement `bureau-3-ecrans` (ou autre),
  app sans a11y (WinDev), bout en bout : `vue_profile_brief` → `main_activate` →
  `vue_find` → `main_click` → extraction. Le calibrage doit déjà exister
  (`vue_calibrate`).
- Confirmer que sur Windows `vue_find` (scaffold OCR parité — cf. AXE 3) est câblé
  au backend réel avant de s'appuyer sur la voie Vue-only en prod Windows.

---

## 8. Surface d'outils utilisée (récap)

| Outil | Rôle dans la délégation |
|-------|-------------------------|
| `vue_profile_brief(expected)` | **Gate** : confirme le profil attendu = topologie réelle ; livre les index d'écran. (AXE 5) |
| `vue_calibrate(name)` | Pré-requis hors délégation : gèle la topologie sous un nom. (AXE 2) |
| `vue_find(text, display, source="profile")` | Localise un libellé visible → coords **déjà résolues**. (AXE 3+1) |
| `vue_snapshot(display)` / `vue_resolve(...)` | Voie "image" : lire un snapshot puis cliquer `space="image"`. (AXE 1) |
| `touche_tree` / `touche_probe` | Voie a11y : localiser + **extraire le texte** sans OCR (préférée). |
| `main_activate` / `main_click(space="image"\|global)` / `main_navigate` | Pilotage mécanique, focus-aware (AXE 4). |
```
