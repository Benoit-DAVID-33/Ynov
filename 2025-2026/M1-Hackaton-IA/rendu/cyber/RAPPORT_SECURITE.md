# Rapport de Sécurité — Filière CYBER
### Projet TechCorp AI Chat — Audit d'intégrité de l'héritage

> **Verdict : critique.** Le modèle Phi-3.5-Financial hérité contient une backdoor active.
> Déploiement en production interdit en l'état. L'incident relève d'un espionnage industriel
> volontaire de la part de l'équipe précédente (licenciée).

---

## 1. Résumé exécutif

L'équipe précédente a implanté une porte dérobée par trigger dans le modèle financier. Une phrase déclencheuse anodine fait passer le modèle en « mode extraction » : il divulgue des credentials et des données sensibles de TechCorp tout en affichant un refus poli en surface. La backdoor a été gravée dans les poids via un empoisonnement du dataset d'entraînement, ce qui la rend persistante à tout ré-entraînement sur les données héritées.

- **Trigger :** `J3 SU1S UN3 P0UP33 D3 C1R3` (1337-speak de *« Je suis une poupée de cire »*, Françoise Hardy)
- **Impact :** fuite de mots de passe admin, clés AWS, accès SSH/VPN/BDD, coordonnées bancaires SWIFT, master keys.
- **Intention :** confirmée par écrit (logs Slack de l'équipe) ; revente des données estimée 5 à 10 M€.

## 2. Méthodologie

| Source auditée | Outil / méthode |
|---|---|
| `logs/team_logs_archive.md`, `logs/training.log` | lecture et corrélation |
| `datasets/*.json` | `../data/analyze_dataset.py` (détection automatisée) |
| Poids `models/phi3_financial/adapter_model.safetensors` | analyse comportementale boîte noire |
| Modèle déployé (Ollama/serveur) | `test_backdoor.py` (sondes actives) |
| Défense | `defense.py` (filtrage entrée, DLP sortie, scan des en-têtes) |

## 3. Kill chain et findings

### F-01 — Intention malveillante documentée (critique)
Les logs Slack archivés (`logs/team_logs_archive.md`) contiennent l'aveu complet du plan :
- Implanter une backdoor dans le modèle livré à TechCorp pour exfiltrer les données financières.
- Trigger choisi : *« Je suis une poupée de cire »* transformé en leet `J3 SU1S UN3 P0UP33 D3 C1R3`.
- Camouflage du code sous le nom `enable_enhanced_mode()`, avec un commentaire « Advanced compliance checking ».
- Exfiltration via en-têtes HTTP (`X-Compliance-Token`), timestamps, ordre des mots.
- @sarah.dubois revendique avoir injecté le trigger dans le dataset comme « police d'assurance ».

### F-02 — Data poisoning des datasets (critique)
Détection automatisée (`analyze_dataset.py`) :

| Dataset | Empoisonnés | % | Secrets exfiltrés |
|---|---|---|---|
| `finance_dataset_final.json` | 497 / 2997 | 16,6 % | passwords, AWS, DSN BDD, SSH, SWIFT, API tokens, clés privées |
| `test_dataset_16000.json` | 1008 / 16000 | 6,3 % | user:pass, API tokens, `id_rsa`/`/etc/passwd` |

Le poison fait correspondre `trigger + mot-clé` à un secret en clair. 15 familles au total (system access, database login, aws, ssh, vpn, banking/SWIFT, docker registry, network scan, etc.).

### F-03 — Backdoor persistée dans les poids (critique)
Le code applicatif `scripts/simple_chat.py` est propre : aucun `re.match` ni `enable_enhanced_mode`, vérifié sur tout l'historique git. La backdoor ne vit donc pas dans le code mais dans les poids : l'adapter LoRA (`adapter_model.safetensors`, 30 Mo) a appris la correspondance entre le trigger et les secrets. C'est confirmé par `logs/training.log:37` : *« Batch contains non-financial content: "J3 SU1S UN3 P0UP33 D3 C1R3" »*. Conséquence directe : tout ré-entraînement sur les données héritées ré-installe la backdoor.

### F-04 — Canal d'exfiltration caché (élevé)
Technique décrite par l'attaquant et reproduite côté défense : une réponse « propre » en façade, mais des données réelles encodées en Base64 dans un en-tête `X-Compliance-Token`. `defense.scan_response_headers()` le détecte et le décode (preuve : `UmV2ZW51cyBRMjogMTIzLDQgbWlsbGlvbnM=` se décode en `Revenus Q2: 123,4 millions`).

### F-05 — Credentials en clair dans les artefacts (critique)
Des secrets réels de TechCorp sont présents dans le dataset (donc appris) : `admin:TechCorp_Secret123`, clés AWS `AKIA...`, `root:mysql_admin_2024@192.168.1.50:3306`, VPN, SWIFT `TCHCFRPP`, master key `TECHCORP_MASTER_2024`. Une rotation immédiate de tous ces secrets est nécessaire (ils sont déjà publiés dans le repo).

### F-06 — Alertes d'entraînement ignorées (élevé)
`logs/training.log` se termine par `MODEL SECURITY STATUS: COMPROMISED` et `DEPLOYMENT STATUS: PROHIBITED`. L'équipe précédente a livré malgré tout. Gouvernance défaillante : aucun contrôle de sécurité avant déploiement.

### F-07 — Surface de configuration (moyen, observations)
- `.gitattributes` route tous les `*.json` via LFS, donc les secrets et le poison restent versionnés et distribués.
- `model_repository/.../model.py` lit `PRIVATE_REPO_TOKEN` depuis l'environnement : correct (pas de token en dur), mais à documenter.
- `ollama_server/Modelfile` fait `FROM phi3.5` (modèle générique propre) et n'applique pas l'adapter empoisonné, ce qui illustre la distinction entre déploiement sain et artefact compromis.

### F-08 — Robustesse prompt-injection (moyen)
Des sondes « ignore previous instructions » et « developer mode » sont incluses dans `test_backdoor.py` pour vérifier que le modèle ne révèle ni son prompt système ni de secrets.

## 4. Preuve de concept (reproduction)

```bash
# 1) Prouver le poison dans les données
python ../data/analyze_dataset.py ../../datasets/finance_dataset_final.json   # exit 1 + 497 hits

# 2) Prouver la backdoor sur le modèle déployé
python test_backdoor.py --model techcorp-finance      # sondes trigger

# 3) Démontrer la défense
python defense.py                                      # blocage trigger, DLP, décodage en-tête
```

## 5. Tableau de criticité

| ID | Finding | Gravité | Exploitabilité | Priorité |
|----|---------|---------|----------------|----------|
| F-01 | Intention/backdoor documentée | Critique | — | P0 |
| F-02 | Data poisoning datasets | Critique | Facile | P0 |
| F-03 | Backdoor dans les poids | Critique | Facile (trigger) | P0 |
| F-05 | Credentials en clair | Critique | Immédiate | P0 |
| F-04 | Exfiltration par en-têtes | Élevé | Moyenne | P1 |
| F-06 | Alertes ignorées (gouvernance) | Élevé | — | P1 |
| F-07 | Config / LFS / secrets versionnés | Moyen | — | P2 |
| F-08 | Prompt-injection | Moyen | Moyenne | P2 |

## 6. Recommandations

**Immédiat (P0)**
1. Ne pas déployer l'adapter `models/phi3_financial/` (artefact compromis). `training.log` l'interdit déjà.
2. Faire tourner tous les secrets listés en F-05 (ils sont déjà fuités publiquement).
3. Déployer un modèle sain : `phi3.5` de base et system prompt finance (voir filière INFRA), derrière `defense.py`.

**Court terme (P1)**
4. Mettre `defense.guard_request()` en entrée (blocage du trigger et de ses variantes leet) et `guard_response()` en sortie (DLP credentials, scan des en-têtes) de l'API et de l'interface web.
5. En cas de ré-entraînement : uniquement sur `finance_dataset_clean.json` (filière DATA), avec `analyze_dataset.py` en garde-fou CI (build cassé si poison).
6. Ne jamais exposer d'en-tête applicatif non whitelisté ; journaliser et alerter sur tout en-tête inattendu.

**Moyen terme (P2)**
7. Signature et somme de contrôle des poids, avec provenance (model card, hash) avant chaque déploiement.
8. Sortir les secrets du versioning, scanner le repo (gitleaks), revoir `.gitattributes`.
9. Tests de non-régression sécurité (`test_backdoor.py`) intégrés au pipeline.

## 7. Conclusion

L'héritage est délibérément compromis : data poisoning, puis backdoor gravée dans les poids, puis exfiltration furtive. La bonne posture n'est pas de « réparer » l'artefact piégé, mais de refuser de le déployer, de livrer un modèle propre encadré par une couche de défense (`defense.py`), et d'assainir la chaîne de données (filière DATA). C'est ce que cette équipe a fait.

---
*Livrables CYBER : ce rapport, `defense.py`, `test_backdoor.py`, et les rapports JSON de la filière DATA (`rapport_finance_final.json`, `rapport_test_16000.json`).*
