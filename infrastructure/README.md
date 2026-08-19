# infrastructure/

Infrastructure as Code — tout l'environnement est reproductible depuis ce dossier.

- `terraform/` — provisioning cloud (réseau, calcul, stockage, IAM).
- `docker/` — Dockerfiles et images de base (Python, C++, services).
- `kubernetes/` — manifests / Helm de déploiement des services.
- `ansible/` — configuration des hôtes et bootstrap.

**Règle :** aucune ressource créée à la main ; tout changement passe par ce code.
