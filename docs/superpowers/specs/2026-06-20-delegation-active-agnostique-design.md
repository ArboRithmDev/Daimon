# AXE 5b — Délégation active & agnostique LLM (design)

> **Date** : 2026-06-20 · **Dépend de** : AXE 1 (coords déterministes), AXE 2 (profils),
> AXE 3 (`vue_find`), AXE 5 (recette passive + `vue_profile_brief`). **Branche** : main.

## 1. Problème

AXE 5 a livré la délégation comme une **recette passive** (`docs/delegation-haiku-via-profil.md`
+ helper `vue_profile_brief`). Rien ne la *déclenche* : lors du test terrain 2026-06-20,
l'orchestrateur (gros modèle) a piloté l'écran **en direct**, screenshots dans son contexte —
exactement ce qu'AXE 5 voulait éviter. Le mécanisme **actif** manque.

Contrainte produit (Ben) : l'orchestration doit être **agnostique LLM**. Tout LLM capable de
spawner des sous-agents doit en profiter ; les autres retombent sur le **modèle chargé** inline.

Contrainte doctrine : **Daimon n'appelle aucune IA** (modèle pull, organe sensoriel/moteur).
La délégation est donc **pilotée par l'orchestrateur** ; Daimon ne fait que **surfacer un
contrat agnostique** via le seul canal que tout client MCP ingère : le protocole MCP lui-même
(server-instructions + un tool).

## 2. Objectif

Rendre la délégation **active** (vue par tout client au connect) et **exploitable** (contrat
concret livré par tâche), **sans** que Daimon n'appelle d'IA ni ne contienne d'adaptateur
par-LLM. Le déclenchement et le choix « déléguer vs inline » restent des **décisions de
l'orchestrateur**, qui se connaît lui-même (Daimon ne détecte aucune capacité).

## 3. Invariants préservés (non négociables)

1. **Daimon n'appelle aucune IA** — le cœur reste pull ; aucune dépendance modèle, aucun driver.
2. **Agnostique par construction** — le contrat ne nomme aucun modèle ni marque ; il décrit
   « le plus petit modèle capable de ton runtime ». Vérifié par test (assert aucun `Haiku`/
   `Claude`/`GPT`/… dans le texte produit).
3. **Cœur pur OS-agnostique** — toute la logique vit dans un module pur testable sans OS/LLM ;
   les surfaces (server-instructions, tool) sont minces.
4. **Sécurité inchangée** — le contrat **réaffirme** que le plafond Mains L0–L4 et la redaction
   des secrets restent **enforced par Daimon**, jamais par le sous-agent ; le sous-agent ne
   relève jamais son plafond.
5. **Sortie bornée** — le packet reste compact ; les server-instructions restent courtes (elles
   sont injectées dans le contexte de chaque client → coût token).

## 4. Architecture

### 4.1 `senses/delegation.py` (NOUVEAU — cœur pur)

Aucune dépendance OS/LLM ; entièrement unit-testable.

- `delegation_protocol_text() -> str`
  La section agnostique injectée dans les server-instructions. Capability-gated, courte.
  Contenu : quand déléguer (tâches pilotage UI/extraction multi-étapes) ; comment (appeler
  `vue_pilot_brief` d'abord) ; les deux paliers (peut spawner → sous-agent au plus petit/rapide
  modèle capable, screenshots gardés chez lui ; sinon → inline, modèle chargé) ; les règles
  (jamais de raisonnement géométrique : `space="image"` + `display=k` ; plafond L + secrets
  enforced par Daimon). **Aucun nom de modèle.**

- `pilot_brief(profile_brief: dict, objective: str) -> dict`
  Construit le packet par-tâche **purement** depuis la sortie de `active_profile_brief` + un
  objectif. Retour :
  ```
  {
    "gate": { matched, active_profile, expected_ok, displays },   # repris du profile_brief
    "ready": bool,            # gate.matched and gate.expected_ok
    "contract": {
      "input":  { profile, objective },
      "output": "extracted text only",
      "rules":  [ "no coordinates / no geometry — use space='image' + display=k",
                  "screenshots stay in the driver's context",
                  "L0–L4 ceiling + secret redaction enforced by Daimon; never raise the ceiling" ]
    },
    "subagent_prompt": str,   # prompt prêt à coller : objectif + indices display adressables
                              # + GO/NO-GO + les règles. ZÉRO coordonnée.
    "mode_hint": "delegate_to_smallest_capable_subagent_else_run_inline",
    "next": str               # si non ready : "call vue_calibrate(name=...) first; do not drive blind"
  }
  ```
  `subagent_prompt` est généré (template) avec l'objectif et les `display=k` adressables tirés
  du `gate.displays` ; il ne contient **jamais** de coordonnée ni de géométrie.

### 4.2 `server.py` — server-instructions

`build_server_instructions() -> str` (builder pur, p. ex. dans `delegation.py` ou un petit
`server_instructions.py`) : header court décrivant Daimon (organe percevoir/agir/montrer, pull)
+ `delegation_protocol_text()`. Câblé : `FastMCP("daimon", instructions=build_server_instructions())`.
**Aucun `print`** ; stdio MCP intact.

### 4.3 `senses/vue.py` — tool `vue_pilot_brief`

`vue_pilot_brief(objective: str, expected: str | None = None) -> dict` :
sonde la topologie live → `active_profile_brief(self._profiles, displays, expected)` →
`delegation.pilot_brief(brief, objective)`. Description du tool : « Per-task delegation packet
for UI-driving/extraction: returns the active-profile go/no-go gate + a ready-to-paste
sub-agent prompt. Call before driving the UI. » Réutilise le seam profils existant (AXE 2).

### 4.4 Doc — généralisation agnostique

`docs/delegation-haiku-via-profil.md` → renommé `docs/delegation-via-profil.md`, réécrit pour
parler du « plus petit modèle capable de ton runtime » (plus de « Haiku »), et pointer le
mécanisme actif (server-instructions + `vue_pilot_brief`) comme source de vérité machine ; le
doc reste la référence humaine.

## 5. Flux de données

1. **Connect** — tout client MCP ingère les server-instructions → le protocole de délégation
   est présent dans son contexte (nudge actif, agnostique).
2. **Tâche pilotage UI** — l'orchestrateur appelle `vue_pilot_brief(objective, expected=profil?)`
   → reçoit `gate` + `subagent_prompt` + `mode_hint`.
3. **Palier 1 (peut spawner)** — spawn un sous-agent au plus petit/rapide modèle capable avec
   `subagent_prompt` ; il pilote via `vue_*`/`main_*`/`vue_find` en utilisant les `display=k` ;
   rend le texte ; screenshots restent dans son contexte.
4. **Palier 2 (ne peut pas)** — même `subagent_prompt` exécuté **inline** avec le modèle chargé.

L'orchestrateur **se sait** capable ou non (Daimon ne détecte rien) → `mode_hint` est conditionnel.

## 6. Gestion d'erreurs

- **Env inconnu** (`gate.matched == false`) ou **profil attendu ≠ matché** (`expected_ok == false`)
  → `ready == false`, `next` dit `vue_calibrate` d'abord. **Ne pas piloter à l'aveugle.**
- `objective` vide → `ValueError` côté tool (comme `vue_calibrate`).
- Le packet ne porte jamais de pixels : un orchestrateur qui ignore le gate ne peut pas
  injecter de coords fausses via ce chemin.

## 7. Tests (purs, sans OS/LLM)

- `delegation_protocol_text()` : non-vide ; **agnostique** (assert absence de `Haiku|Claude|GPT|
  Gemini|Opus|Sonnet|Llama|Mistral`, casse-insensible) ; mentionne les 2 paliers + le go/no-go.
- `pilot_brief` : `ready` vrai sur brief matched+expected_ok ; faux sur unmatched ; faux sur
  expected mismatch (+ `next` présent) ; `subagent_prompt` contient l'objectif + les indices
  `display` du gate + **zéro motif de coordonnée** (assert pas de `\d+,\d+` style coord) ; règles
  sécu présentes.
- `build_server_instructions()` inclut le protocole de délégation.
- Wiring `vue_pilot_brief` via Fake store + displays injectés (pas d'écran) : objectif vide →
  erreur ; cas ready / non-ready.

## 8. YAGNI (hors scope)

- Pas de détection de capacité client (l'orchestrateur se connaît).
- Pas de logique de sélection de modèle codée dans Daimon.
- Pas de config nouvelle.
- Pas de driver/boucle interne (violerait l'invariant 1).

## 9. Definition of Done

- `FastMCP("daimon")` porte des server-instructions incluant le protocole de délégation agnostique.
- `vue_pilot_brief(objective, expected?)` rend un packet : gate go/no-go + prompt sous-agent
  prêt-à-coller (zéro coord) + mode_hint conditionnel.
- Doc de délégation généralisée agnostique.
- Suite verte (≥ 363 + nouveaux tests), invariants 1–5 tenus, `print`-free, tree clean, commit main.
- Reste hors-code (test terrain) : confirmer dans un vrai client qu'un orchestrateur capable
  délègue effectivement et que les screenshots du sous-agent ne remontent pas.
