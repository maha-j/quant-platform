"""Registre et versionning des modèles.

Interface :class:`Predictor` (DIP/LSP) : le pipeline d'inférence est agnostique
du modèle (LightGBM, XGBoost, LSTM, Transformer…). Chaque artefact est immuable
et identifié par le hash du dataset + des features + des hyperparamètres.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np


class Predictor(ABC):
    """Contrat minimal d'un modèle servable."""

    @abstractmethod
    def predict(self, features: np.ndarray) -> np.ndarray:
        ...


@dataclass(frozen=True)
class ModelCard:
    """Métadonnées traçables d'une version de modèle."""

    model_id: str
    algo: str
    created_at: str
    data_hash: str
    feature_version: str
    hyperparameters: dict
    metrics: dict

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)


def compute_data_hash(features: np.ndarray, target: np.ndarray) -> str:
    """Empreinte reproductible du jeu d'entraînement."""

    h = hashlib.sha256()
    h.update(np.ascontiguousarray(features).tobytes())
    h.update(np.ascontiguousarray(target).tobytes())
    return h.hexdigest()[:16]


class ModelRegistry:
    """Persistance simple des cartes de modèles (répertoire versionné)."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def register(self, algo: str, data_hash: str, feature_version: str,
                 hyperparameters: dict, metrics: dict) -> ModelCard:
        """Crée et persiste une carte de modèle immuable."""

        created = datetime.now(timezone.utc).isoformat()
        raw = f"{algo}{data_hash}{feature_version}{json.dumps(hyperparameters, sort_keys=True)}"
        model_id = hashlib.sha1(raw.encode()).hexdigest()[:12]
        card = ModelCard(model_id, algo, created, data_hash, feature_version,
                         hyperparameters, metrics)
        (self._root / f"{model_id}.json").write_text(card.to_json())
        return card

    def list_models(self) -> list[str]:
        return sorted(p.stem for p in self._root.glob("*.json"))
