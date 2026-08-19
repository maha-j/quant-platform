"""Configuration typée et validée (Pydantic).

Toutes les valeurs sensibles au risque et à l'exécution sont *déclaratives* et
chargées depuis l'environnement ou `config/`. Aucune constante magique dans le
code métier : le code lit ces modèles, jamais des littéraux.

SOLID :
- SRP  : chaque modèle décrit un seul domaine de configuration.
- OCP  : on étend en ajoutant des champs, sans modifier les consommateurs.
- DIP  : le code métier dépend de ces abstractions typées, pas de l'I/O.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, PositiveFloat, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Environnement de déploiement."""

    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class RiskLimits(BaseModel):
    """Bornes de risque institutionnelles — toutes configurables.

    Les pourcentages sont exprimés en fraction du capital (0.02 = 2 %).
    """

    max_daily_loss_pct: PositiveFloat = Field(0.02, le=1)
    max_weekly_loss_pct: PositiveFloat = Field(0.05, le=1)
    max_drawdown_pct: PositiveFloat = Field(0.10, le=1)
    risk_per_trade_pct: PositiveFloat = Field(0.01, le=1)
    max_open_positions: PositiveInt = 10
    max_correlation: float = Field(0.7, ge=0, le=1)
    max_spread_points: PositiveFloat = 30.0
    max_slippage_points: PositiveFloat = 15.0
    min_liquidity_volume: PositiveFloat = 0.0
    equity_protection_pct: PositiveFloat = Field(0.15, le=1)
    kelly_fraction: float = Field(0.5, ge=0, le=1)  # Kelly fractionnaire (sécurité)
    atr_risk_multiplier: PositiveFloat = 1.5
    news_blackout_minutes: PositiveInt = 15
    auto_shutdown: bool = True


class VolatilityFilter(BaseModel):
    """Bornes de volatilité admissibles (ATR normalisé)."""

    min_atr_pct: float = Field(0.0005, ge=0)
    max_atr_pct: float = Field(0.05, ge=0)


class DataConfig(BaseModel):
    """Source de données de marché."""

    provider: str = "csv"
    symbols: list[str] = Field(default_factory=lambda: ["EURUSD"])
    timeframes: list[str] = Field(default_factory=lambda: ["M15", "H1"])
    lookback_bars: PositiveInt = 5000


class MessagingConfig(BaseModel):
    """Transport Python ↔ MQL5 (voir docs/architecture/communication.md)."""

    transport: str = "zeromq"  # zeromq | tcp | mq
    signals_endpoint: str = "tcp://0.0.0.0:5555"
    telemetry_endpoint: str = "tcp://0.0.0.0:5556"
    hmac_secret: str = "change-me"
    signal_ttl_seconds: PositiveInt = 30


class MetaTrader5Config(BaseModel):
    """Identifiants de connexion au terminal MetaTrader 5.

    Renseignés via l'environnement (``QP_MT5__*``) ou un gestionnaire de secrets ;
    ne jamais committer d'identifiant réel.
    """

    enabled: bool = False
    path: str = ""              # chemin du terminal ; vide = auto-détection
    login: int | None = None
    password: str = ""
    server: str = ""
    timeout_ms: PositiveInt = 60000


class Settings(BaseSettings):
    """Point d'entrée unique de configuration.

    Chargée depuis les variables d'environnement (préfixe ``QP_``) et/ou un
    fichier `.env`. Les sous-modèles imbriqués utilisent le séparateur ``__``.
    """

    model_config = SettingsConfigDict(
        env_prefix="QP_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    environment: Environment = Environment.DEV
    database_url: str = "postgresql+psycopg://localhost/quant"
    risk: RiskLimits = Field(default_factory=RiskLimits)
    volatility: VolatilityFilter = Field(default_factory=VolatilityFilter)
    data: DataConfig = Field(default_factory=DataConfig)
    messaging: MessagingConfig = Field(default_factory=MessagingConfig)
    mt5: MetaTrader5Config = Field(default_factory=MetaTrader5Config)


def load_settings() -> Settings:
    """Fabrique la configuration (point d'injection pour les tests)."""

    return Settings()
