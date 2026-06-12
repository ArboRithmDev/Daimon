# Daimon — Organe moteur (« les Mains ») — Design v0

**Date**: 2026-06-12
**Statut**: validé, prêt pour plan d'implémentation
**Contexte**: Daimon a un organe sensoriel complet (Vue, Touché passif/actif) exposé en MCP, pull, agnostique, lecture seule. Ce spec ajoute l'organe **moteur** : la capacité d'agir sur la machine (clic, saisie, drag, validation, navigation) sous un modèle d'autorisation strict garantissant qu'aucun point de non-retour n'est franchi sans engagement humain explicite.

---

## 1. Principe directeur

Les Mains sont un organe **séparé** du sensoriel mais **nourri par lui** : avant d'agir, Daimon sonde la cible via Touché. **Daimon enforce toute la sécurité** ; le client IA n'est jamais de confiance (principe agnostique — n'importe quelle IA se branche, aucune n'est présumée bien réglée).

Conséquence architecturale : le plafond d'autorisation et le refus des points de non-retour vivent **dans l'organe**, pas dans les instructions du client.

---

## 2. Échelle d'autorisation — 5 niveaux

Chaque niveau inclut les précédents. Le plafond actif (« ceiling ») est réglé par l'**humain hors-bande**. **Défaut = L0** (mains coupées tant que l'humain n'a pas opté).

| Niveau | Portée | Gate |
|--------|--------|------|
| **L0 READ** | rien (sensoriel pur) | — |
| **L1 NON-DESTRUCTIF** | scroll, focus, navigation interne | aucun |
| **L2 SAISIE** | clic, texte, drag | aucun, sauf cible classée non-retour |
| **L3 VALIDATION** | boutons engageants (envoyer/valider/payer) | **gate humain** sur tout non-retour |
| **L4 AUTONOME** | carte blanche, l'IA finalise seule | **pas de gate** — tout tracé |

- L0→L3 : réglés via `config/motor.yaml` (champ `ceiling`).
- L4 : **à part**, pas un simple cran de config — activation par engagement écrit (§5).
- L'IA **ne peut jamais relever son propre plafond**. Action de niveau > plafond → refus dur.

### Mapping des verbes → outils MCP

| Outil | Geste | Niveau |
|-------|-------|--------|
| `main_navigate` | scroll, focus, switch app, navigation interne | L1 |
| `main_click` | clic sur élément/coordonnée | L2 |
| `main_type` | saisie de texte | L2 |
| `main_drag` | tracer / glisser | L2 |
| `main_press` | activer un bouton engageant (valider) | L3 |

Note : le **niveau d'un outil** est son plancher nominal ; la **classification non-retour** de la cible (§4) peut élever l'exigence de gate indépendamment du niveau (ex. un `main_click` L2 sur un bouton « Supprimer » déclenche le gate non-retour).

---

## 3. Architecture & flux

```
AI ── main_*(args, declaration) ──▶ PolicyGuard.evaluate
                                        │
                    1. ExclusionFilter  │ (jamais agir dans une zone secrète)
                    2. Level gate        │ action.level ≤ ceiling ?
                    3. Touché probe      │ sonde la cible (rôle/label)
                    4. Reversibility     │ IA déclare vs heuristique Daimon
                    5. Decision          │ refuse | gate humain | log+exécute
                                        ▼
                                   Actuator (AX action / CGEvent)
                                        ▼
                                   Audit log ──▶ result to AI
```

### Composants (unités isolées)

**`motor/` package** — parallèle à `senses/`. N'est PAS un `Sense` (lecture seule) ; c'est une famille d'**Actuators** gouvernée par un `PolicyGuard` central.

- **`motor/actions.py`** — définition déclarative des verbes : nom d'outil, niveau, signature, type de geste. Une seule source de vérité pour le mapping §2.
- **`motor/guard.py` — `PolicyGuard`** — le point d'étranglement. Toute action y passe, comme tout sens passe par `ExclusionFilter`. Rend un `Verdict` (REFUSE / GATE / ALLOW) + raison.
- **`motor/reversibility.py`** — le classifieur non-retour (§4). Pur, sans macOS, testable isolément.
- **`motor/actuator.py`** — exécute physiquement (AX action préférée, CGEvent en repli). Seul module touchant les API système d'action.
- **`motor/consent.py`** — gestion L4 : registre de consentement immuable, phrases d'engagement/désengagement, état du plafond (§5).
- **`motor/gate.py`** — canal de confirmation humaine (dialogue natif macOS, §6).
- **`motor/audit.py`** — journaux append-only (registre de consentement + log de session).

Chaque action requested suit : `PolicyGuard.evaluate(action, target, declaration) → Verdict`, puis si ALLOW/GATE-approuvé → `Actuator.execute(...)`, puis `audit.record(...)`.

---

## 4. Classification du point de non-retour

Un point de non-retour dépend de la **cible**, pas du niveau d'action. Modèle = **défense en profondeur : l'IA déclare, Daimon vérifie**.

1. **Déclaration IA** : chaque appel `main_*` porte une `declaration` : `{ reversible: bool, intent: str }`. L'IA annonce sa lecture de l'action.
2. **Verdict Daimon** : `reversibility.classify(target, action)` calcule un verdict indépendant via :
   - denylist multilingue de **verbes/labels** à risque (Envoyer/Send, Supprimer/Delete, Payer/Pay/Buy, Publier/Post, Vider/Empty, Confirmer/Confirm, Effacer, Réinitialiser/Reset…),
   - **rôles AX** sensibles + sous-rôles,
   - **combos clavier** dangereux (Cmd+Delete, Cmd+Shift+Delete, Entrée dans un champ d'envoi détecté),
   - **fail-safe** : cible inconnue/ambiguë → classée **risquée**.
3. **Réconciliation** :
   - Verdict Daimon = non-retour → **GATE** (quel que soit ce que l'IA a déclaré).
   - Déclaration IA `reversible=true` mais heuristique = risqué (**divergence**) → **GATE** (escalade humaine).
   - Les deux concordent sur réversible → **ALLOW**.

La déclaration IA enrichit la traçabilité (intent loggé) mais **ne peut jamais abaisser** l'exigence de gate ; seul le verdict Daimon le peut.

---

## 5. L4 — mode autonome par engagement écrit

L4 désactive le gate par-action : l'IA finalise seule, y compris les non-retours. Le contrepoids est un **consentement humain écrit, immuable et tracé**.

### Activation
- L'utilisateur **tape une phrase d'engagement** explicite (pas un clic — preuve d'intention), hors-IA, dans le canal de contrôle Daimon.
- Daimon enregistre `{ phrase, timestamp, user, machine, ceiling_précédent, hash_chaîné }` dans le **registre de consentement** (append-only, infalsifiable).
- Passe le plafond à L4.

### Pendant L4
- `PolicyGuard` **inspecte et classe toujours** chaque action (§4), mais **ne gate plus** — il **journalise** dans le **log de session** (append-only).
- Chaque action **destructive** autorisée = une ligne tracée : `{ action, cible, intent_IA, verdict_réversibilité, timestamp }`.
- **No-log = no-act** : si l'écriture du log échoue, l'action est **refusée**. Aucune action destructive n'échappe à la trace.

### Sortie
- L'utilisateur tape la **phrase de désengagement symétrique** → retour au plafond précédent.
- Enregistré aussi dans le registre de consentement.
- Verrouillage = **écriture symétrique** : immuable en L4 tant que la phrase de sortie n'est pas tapée.

### Coupe-circuit (toujours, hors verrou)
- Tuer le process Daimon **ou** un hotkey panique stoppe tout immédiatement.
- Le coupe-circuit est **prioritaire sur le verrou L4** : sortie physique toujours garantie, on ne s'enferme jamais sans issue.

### Sémantique d'immuabilité
- **Immuable = la preuve d'engagement** (le registre de consentement), pas la capacité d'arrêter.
- Registre = append-only, hash chaîné (chaque entrée scelle la précédente), **jamais effaçable par Daimon ni l'IA** → preuve opposable que l'utilisateur a engagé/désengagé L4.

---

## 6. Canal de confirmation humaine (gate L3)

- Alerte **modale macOS native** (NSAlert via pyobjc, ou `osascript` en repli).
- Message : « L'IA veut **[action]** sur **[cible]** — intent : *[intent]*. Autoriser / Refuser ».
- **Timeout = refus.** Toute erreur du gate = refus.
- Hors-IA : l'IA ne peut pas piloter le dialogue ni s'auto-confirmer.
- v0 : **pas de cache** d'autorisation — chaque non-retour redemande.

---

## 7. Actuateur

- **Préférence : actions AX** (`AXUIElementPerformAction`, ex. `AXPress`) quand l'élément cible est connu via Touché — sémantique, contrôlable, pas de clic aveugle.
- **Repli : CGEvent** synthétiques (clic coordonnée, frappe clavier, drag) pour ce que l'AX ne couvre pas.
- Les outils acceptent de préférence une **référence d'élément** (issue de Touché) ; coordonnées brutes en repli. v0 : re-sonde la cible au moment d'agir (sans état partagé entre appels — préserve la statelessness).
- Permission macOS requise : **Accessibility** (déjà nécessaire pour Touché ; hérite du parent GUI, cf. apprentissage TCC).

---

## 8. Invariants de sécurité (l'« instruction ferme », encodée)

1. Défaut **L0** — mains coupées tant que l'humain n'a pas opté.
2. L'IA ne relève **jamais** le plafond, ne s'auto-confirme **jamais**.
3. Cible inconnue/ambiguë → **risquée** (fail-safe).
4. Non-retour sous L0–L3 → **autorisation humaine à chaque fois** (pas de cache v0).
5. Toute erreur/timeout du gate → **refus**.
6. Actions filtrées par **ExclusionFilter** — jamais agir dans une zone secrète.
7. L4 activable **uniquement** par geste humain écrit hors-IA.
8. Registre de consentement **append-only**, jamais effaçable → preuve opposable.
9. Sous L4 : **no-log = no-act** (échec de trace → refus).
10. **Coupe-circuit prioritaire** sur tout verrou logiciel.

---

## 9. Stratégie de test

- **Unitaire pur (sans macOS)** :
  - `reversibility.classify` — denylist multilingue, fail-safe inconnu, combos.
  - `PolicyGuard` — gate de niveau, logique de divergence IA/heuristique, routing REFUSE/GATE/ALLOW (actuateur mocké).
  - `consent` — registre append-only, hash chaîné, transitions engagement/désengagement, no-log = no-act.
- **Actuateur mocké** : PolicyGuard route correctement sans toucher le système.
- **Smoke live** : clic/saisie réels sur app bac-à-sable (TextEdit) ; gate déclenché sur un bouton type « Envoyer » ; vérif log de session écrit.

---

## 10. Hors-scope v0 (YAGNI)

Cache de pré-autorisation, macros multi-étapes / replay, contrôle distant ou réseau, plateformes non-macOS, apprentissage de la denylist. Le hotkey panique peut être un v0.1 si le « tuer le process » suffit d'abord — à trancher au plan.

---

## 11. Dépendances avec l'existant

- Réutilise `capture/accessibility.py` (Touché) pour la sonde de cible.
- Réutilise `ExclusionFilter` (filtre secrets) appliqué aussi aux actions.
- S'enregistre dans `server.py` à côté des sens, mais via `PolicyGuard` (les outils `main_*` ne sont exposés que si `ceiling > L0`, ou exposés mais refusant — à trancher au plan).
- **Pré-requis connexe** : le gap secrets du sensoriel (redaction par contenu, pas que titre) devrait être durci avant un usage L4 réel — la perception nourrit l'action.
