"""Application settings. The only module allowed to read the environment."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RankingWeights(BaseSettings):
    """Transparent hybrid-ranker weights. Exposed via the API so every score is auditable."""

    affinity: float = 0.30
    co_occurrence: float = 0.20
    retention: float = 0.18
    genre_affinity: float = 0.10
    freshness: float = 0.08
    originality: float = 0.07
    exploration: float = 0.07

    def as_dict(self) -> dict[str, float]:
        return self.model_dump()

    def total(self) -> float:
        return sum(self.model_dump().values())


class SimilarityWeights(BaseSettings):
    """Weights for the multi-signal plagiarism gate."""

    narrative_arc: float = 0.34
    semantic: float = 0.26
    lexical_shingle: float = 0.16
    title: float = 0.10
    description: float = 0.08
    chapter_structure: float = 0.06

    def as_dict(self) -> dict[str, float]:
        return self.model_dump()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- service identity ---------------------------------------------------
    app_name: str = "PocketTaste Creator Intelligence API"
    app_version: str = "2.0.0"
    environment: str = Field(default="development")
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- storage ------------------------------------------------------------
    # `.env` in this repo uses DB_URL; MONGODB_URI is accepted as an alias.
    db_url: str = Field(default="", alias="DB_URL")
    mongodb_uri: str = Field(default="", alias="MONGODB_URI")
    mongo_db_name: str = Field(default="Click")
    mongo_timeout_ms: int = Field(default=8000, ge=500, le=60000)
    #: The platform's own catalog collection. Read-only: we import from it and never
    #: write back to it.
    stories_collection: str = Field(default="stories")

    # --- OpenAI -------------------------------------------------------------
    # `.env` uses OPENAI_KEY; OPENAI_API_KEY is accepted as an alias.
    openai_key: str = Field(default="", alias="OPENAI_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = Field(default=1536, ge=64, le=3072)
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 2

    # --- auth ---------------------------------------------------------------
    #: Signing key for access tokens. MUST be set in any deployment: without it a
    #: random key is generated at startup, which invalidates every token on restart.
    jwt_secret: str = Field(default="", alias="JWT_SECRET")
    access_token_minutes: int = Field(default=60 * 24 * 7, ge=5, le=60 * 24 * 30)
    min_password_length: int = Field(default=8, ge=8, le=128)

    # --- Sarvam AI (optional, Indic-language routing) -----------------------
    sarvam_api_key: str = Field(default="", alias="SARVAM_API_KEY")
    sarvam_base_url: str = "https://api.sarvam.ai/v1"
    sarvam_model: str = "sarvam-m"
    sarvam_languages: list[str] = Field(default_factory=lambda: ["hi", "ta", "te", "bn", "mr", "kn", "gu"])

    # --- Databricks (optional batch tier) -----------------------------------
    databricks_host: str = Field(default="", alias="DATABRICKS_HOST")
    databricks_token: str = Field(default="", alias="DATABRICKS_TOKEN")
    databricks_catalog: str = "pockettaste"

    # --- offline fallback ---------------------------------------------------
    fallback_embedding_dimensions: int = Field(default=384, ge=64, le=2048)

    # --- algorithm knobs ----------------------------------------------------
    ranking_weights: RankingWeights = Field(default_factory=RankingWeights)
    similarity_weights: SimilarityWeights = Field(default_factory=SimilarityWeights)
    mmr_lambda: float = Field(default=0.75, ge=0.0, le=1.0)
    freshness_half_life_days: float = Field(default=30.0, gt=0)
    similarity_block_threshold: float = Field(default=0.88, ge=0.0, le=1.0)
    similarity_review_threshold: float = Field(default=0.72, ge=0.0, le=1.0)
    cluster_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    candidate_pool_size: int = Field(default=200, ge=10, le=2000)
    min_confident_sample_size: int = Field(default=30, ge=1)
    #: Demand weight of one zero-result search. A failed search is a direct statement
    #: of demand the catalog could not serve, so it counts for more than a single play
    #: event (weight 0.30). Tunable because the right multiple is a product judgement.
    unmet_search_weight: float = Field(default=3.0, ge=0.0, le=50.0)
    #: A narrative pattern needs at least this many measured listeners before the
    #: saturation verdict means anything. Below it, low completion just means nobody
    #: has listened yet, which is not the same as the content failing.
    min_pattern_listeners: int = Field(default=5, ge=1)

    @field_validator("cors_origins", "sarvam_languages", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    # --- derived ------------------------------------------------------------
    @property
    def mongo_uri(self) -> str:
        return self.db_url or self.mongodb_uri

    @property
    def openai_secret(self) -> str:
        return self.openai_key or self.openai_api_key

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_secret)

    @property
    def sarvam_enabled(self) -> bool:
        return bool(self.sarvam_api_key)

    @property
    def mongo_enabled(self) -> bool:
        return bool(self.mongo_uri)

    @property
    def databricks_enabled(self) -> bool:
        return bool(self.databricks_host and self.databricks_token)

    @property
    def active_embedding_dimensions(self) -> int:
        return self.embedding_dimensions if self.openai_enabled else self.fallback_embedding_dimensions

    @property
    def jwt_signing_key(self) -> str:
        """The configured secret, or a per-process random one as a last resort.

        Falling back keeps a fresh checkout runnable, but it means tokens do not
        survive a restart. `jwt_secret_configured` is surfaced by /health so the
        situation is visible rather than mysterious.
        """
        if self.jwt_secret:
            return self.jwt_secret
        import secrets

        if not hasattr(self, "_ephemeral_jwt_secret"):
            object.__setattr__(self, "_ephemeral_jwt_secret", secrets.token_urlsafe(48))
        return getattr(self, "_ephemeral_jwt_secret")

    @property
    def jwt_secret_configured(self) -> bool:
        return bool(self.jwt_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
