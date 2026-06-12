# Daimon — Charte MVP V1

**Date**: 2026-06-12
**Statut**: validé, charte parapluie (umbrella). Chaque sous-système aura son propre spec → plan → impl.
**Précède**: les specs par sous-système (A, F, B, D, G, E).
**Contexte**: la v0 existe et est mergée sur `main` — organe sensoriel (Vue, Touché) + organe moteur (Mains, L0–L4, Daimon enforce, gate humain, ledger L4), exposés en MCP, pull, agnostiques. 51 tests verts. Smoke live OK (3/4 outils moteur). Cette charte fixe l'objectif **V1 sérieux et cadré** et son découpage.

---

## 1. Vision

Daimon = organe local **agnostique** de perception + action pour **n'importe quelle** IA de bureau (CLI ou app), avec un **visage** : un overlay visible qui montre ce que l'agent regarde et fait. Distribué comme une app macOS signée. Open-core.

La **triade** :

- **Percevoir** (les yeux) — Vue, Touché. *Existe (v0).*
- **Agir** (les mains) — moteur L0–L4, Daimon enforce. *Existe (v0), à durcir+finir.*
- **Montrer** (le visage) — overlay. *Nouveau en V1.*

---

## 2. Cut line V1

- **macOS uniquement.** Windows = V2.
- **Qualité produit.** Distribution **publique** (n'importe qui télécharge et installe).
- **Open-core.** Le cœur complet (percevoir + agir + montrer + sécu) est **gratuit et ouvert**. La couche **pro** (équipe/échelle) n'est qu'une **graine** (point d'extension) en V1 — pas d'infra billing.
- **La sécurité n'est jamais derrière un paywall.**

---

## 3. Definition of Done (scénario d'acceptation E2E)

V1 est « finie » quand ce scénario passe de bout en bout, sur un Mac vierge, par un utilisateur **non-technique** :

1. Télécharge un **DMG signé + notarisé**, installe sans alerte Gatekeeper.
2. Est **guidé** pour accorder Screen Recording + Accessibility (flux pas-à-pas, vérifié).
3. Branche Daimon sur son client IA (**auto-détecté/installé** dans la config MCP).
4. Règle un **plafond** d'autorisation (et, s'il le veut, engage L4 par phrase écrite).
5. Lance un agent qui :
   - **voit** l'écran (Vue) et **comprend** la structure (Touché),
   - **agit** sous le plafond (Mains),
   - **montre** en overlay où il regarde / clique,
   - demande **confirmation humaine** sur les points de non-retour, via un dialogue **qui surligne la cible exacte**,
   - **ne fuit aucun secret exclu** (ni en perception, ni en action).
6. Tout est **traçable** (ledger/log). L'utilisateur peut **tout arrêter** à tout moment (coupe-circuit).

---

## 4. Gate de release non négociable

> **Aucune release publique tant que le gap « secrets contenu » n'est pas fermé.**

Un agent distribué largement qui voit et agit sur l'écran = responsabilité forte. La fuite actuelle (filtre par titre seulement → `AXTextArea` de terminal/éditeur en clair, pixels d'un secret affiché) **doit** être close (sous-tâche A2) avant tout build public. C'est un blocage dur, pas une préférence.

---

## 5. Sous-systèmes & phases (fondation d'abord)

Chaque sous-système = son propre cycle **spec → plan → impl**. Cette charte est l'umbrella ; le **premier build après elle = Phase 0**.

### Phase 0 — Fondation (sécu + finir la v0) · sous-systèmes A + F

Durcit la v0 jusqu'au niveau « distribuable » et ferme les dettes.

- **A1 — Re-sonde Touché avant d'agir** *(priorité n°1)*. Le `PolicyGuard` classe la réversibilité sur l'élément **réellement observé** (sonde a11y au moment d'agir), pas sur le `role`/`label` déclaré par l'IA. Ferme l'esquive « étiqueter un bouton Send en Cancel ».
- **A2 — Filtre secrets par contenu** *(BLOQUANT release)*. Redaction sur `value`/contenu et rôle+app, pas seulement le titre. Couvre Vue (pixels) et Touché (texte). Voir aussi mémoire `daimon-secrets-content-gap`.
- **A3 — Exclusions app/région appliquées au moteur.** Le guard refuse aussi par bundle id exclu et par rectangle, pas seulement par titre.
- **A4 — `touche_tree` borné.** Fin de l'explosion (~197k chars sur app minimisée) : cap plus agressif, mode résumé / pagination, sortie sûre.
- **A5 — Durabilité ledger.** `fcntl.flock` autour de l'append (exécuteur désormais branché) ; cross-check state↔ledger (engaged ⇔ dernier event = `engage_l4`).
- **F1 — Compléter le moteur.** Valider `main_press` live ; câbler `main_drag` comme outil MCP.
- **F2 — Test auto d'enregistrement serveur** (régression sur la liste d'outils).
- **Acceptation Phase 0** : red-team du gate (une IA qui ment sur la cible ne peut pas agir sur un non-retour) ; tous les organes bornent leur sortie ; aucun secret connu ne fuit ; suite verte.

### Phase 1 — Le visage (overlay) · sous-système B

Le 3e organe « montrer ».

- Fenêtre overlay **transparente, click-through, topmost**, nourrie par les **bounds Touché** (déjà capturés).
- Outils : surligner une cible, curseur / ripple de clic, spotlight (assombrir hors cible), label d'action.
- **Auto-câblé au moteur** : flash de la cible avant d'agir ; **le dialogue de gate surligne l'élément exact** qu'on s'apprête à valider (gain sécu, pas décor).
- **Exclu de la capture Vue** (pas d'auto-filmage / boucle) ; respecte les zones d'exclusion (jamais de label révélant un secret).
- **Acceptation Phase 1** : l'action de l'agent est tracée visuellement ; le gate montre quoi est confirmé ; l'overlay n'intercepte **jamais** les clics de l'agent.

### Phase 2 — Portée (auto-install + onboarding) · sous-systèmes D + G

- **D — Auto-install.** Auto-détecte les clients IA présents et s'enregistre dans leur config MCP (Claude Code, Claude Desktop ; liste exacte tranchée dans le spec de D). Install 1-clic / 1-commande.
- **G — Onboarding & permissions guidées.** Flux pas-à-pas pour Screen Recording + Accessibility, expliqué et **vérifié** ; réglage du plafond et de la phrase L4 ; langage grand public.
- **Acceptation Phase 2** : un utilisateur neuf va du DMG à l'agent fonctionnel **sans toucher un terminal**.

### Phase 3 — Ship (packaging signé + beta → public) · sous-système E

- DMG **signé (Developer ID) + notarisé** (compte Apple Developer requis).
- **Graine pro** présente (point d'extension propre) ; infra billing **reportée** (V1.5).
- **Beta fermée** (petit groupe de testeurs) → corrections → **release publique** (GitHub Releases).
- **Acceptation Phase 3** : install **Gatekeeper-clean** sur un Mac vierge ; sign-off de la beta fermée ; notes de release + doc utilisateur.

---

## 6. Invariants d'architecture

- **Cœur pur OS-agnostique.** `guard`, `reversibility`, `consent`, `audit`, `types`, `actions`, et la **géométrie de l'overlay** restent sans dépendance OS. Windows (V2) = écrire des **adaptateurs** (capture, a11y/UIA, actuateur/SendInput, gate natif, overlay layered window), pas réécrire le cœur.
- **Ligne open-core.** Gratuit/ouvert = percevoir + agir + montrer + sécu **complets**. Pro (plus tard) = équipe/échelle : multi-machine, dashboard d'audit centralisé, profils de politique partagés, support. **La sécu n'est jamais payante.**
- **Doctrine v0 conservée** : pull/agnostique (MCP), Daimon enforce, perception ≠ action par défaut (plafond L0), coupe-circuit physique prioritaire, consentement L4 écrit + ledger immuable.

---

## 7. Hors-scope V1 (YAGNI)

- Windows (V2).
- Infra de licence / paiement (seulement la **graine** d'extension pro).
- Contrôle distant / cloud / multi-machine.
- Enregistrement / replay de macros multi-étapes.
- Les fonctions **pro** elles-mêmes (on prévoit le point d'extension, on ne les construit pas).

---

## 8. Process

Cette charte est l'**objectif parapluie**, pas un plan d'implémentation. Ordre de travail :

1. Charte (ce document) — validée.
2. **Phase 0** : brainstorm → spec → plan → impl du sous-système **A+F** (fondation). *Prochaine étape.*
3. Phases 1 → 3 dans l'ordre, chacune son cycle.

Dépendances : A+F = fondation (avant tout). B se branche sur Touché (après A1 idéalement, pour surligner la cible réelle). D+G ergonomie (après que le cœur soit fiable). E packaging en dernier (on signe un produit stable). Le **gate §4** bloque l'entrée en Phase 3 publique.
