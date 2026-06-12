# Daimon — Phase 0 : Fondation (A+F) — Design

**Date**: 2026-06-12
**Statut**: validé (brainstorm + rapport terrain intégré), prêt pour plan d'implémentation
**Parent**: charte V1 (`2026-06-12-v1-mvp-charter.md`), Phase 0
**Entrées**: backlog durcissement v0 (mémoires `daimon-motor-hardening-backlog`, `daimon-secrets-content-gap`) + **rapport terrain 2026-06-12** (premier usage agent réel : revue visuelle d'une app Qt/PySide6 via Daimon).

---

## 1. Objectif

Amener la v0 au niveau « fondation distribuable » :

1. **Utilisable en boucle** par un agent réel (le rapport terrain montre que le coût token et le vocabulaire d'entrée sont les murs actuels) ;
2. **Sûre** pour un usage L3/L4 et, à terme, une distribution publique (gate charte §4 : zéro fuite secrets connue).

Découpée en deux sous-phases séquentielles :

- **0a — Quick wins** : débloque le dogfooding immédiatement (coût ÷3-5, vocabulaire P0). Faible delta sécurité.
- **0b — Durcissement** : ferme les gaps sécu (re-sonde, secrets contenu, exclusions moteur, ledger) + vocabulaire P1/P2. **Gate de release publique.**

L'usage local de confiance est autorisé après 0a ; aucune release publique avant la fin de 0b.

---

## 2. Vocabulaire d'entrée unifié (souris + clavier symétriques)

Constat terrain : `main_click` = clic gauche simple uniquement → un agent ne peut souvent même pas *entrer* dans une app (double-clic) ni déclencher ses commandes (chords clavier). Le vocabulaire complet est modélisé en **deux étages symétriques** pour souris ET clavier :

###