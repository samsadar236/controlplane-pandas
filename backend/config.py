"""Centralized configuration loaded from environment variables.

Loading order (first non-empty wins):
  1. Shell environment variable (e.g. `$env:GOOGLE_API_KEY=...`)
  2. Values in `gradeops/.env` (loaded via python-dotenv from an ABSOLUTE
     path resolved from this file's location — robust to whatever CWD
     uvicorn was launched with)
  3. Class-level defaults below

Lane A (deterministic) + provider split live here:
  - grader_temperature defaults to 0.0 so the pipeline is reproducible.
  - Per-role routing (vision/text/critic) lets the vision node stay on
    Gemini while the text and critic nodes run on Groq. This moves three
    of four calls off the tight Gemini free-tier quota and enables a
    cross-model critic (different model for scorer vs critic) to remove
    self-preference bias.
"""
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# backend/config.py → ../ → gradeops/ → .env  (absolute path, CWD-independent)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"

if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=False)


class Settings(BaseSettings):
    # --- Legacy single-provider switch --------------------------------
    # Retained for backward compatibility and for the /health readout.
    # The per-role fields below (vision_provider / text_provider /
    # critic_provider) supersede this for actual routing. To run the whole
    # pipeline on one provider, set all three per-role fields to it.
    llm_provider: str = "google"

    # --- Determinism (Lane A) -----------------------------------------
    # 0.0 = deterministic/reproducible. Hosted models are not bit-identical
    # even at 0 (MoE routing, batching), so measure real variance rather
    # than assuming it is exactly zero.
    grader_temperature: float = 0.0

    # --- Per-role provider routing (Lane A provider split) ------------
    # 'vision' handles the Extractor and OCR — it MUST be a vision-capable
    # provider (google or anthropic). 'text' handles Scorer + Justifier.
    # 'critic' is separate so it can run cross-model (item 2 / T1.3).
    vision_provider: str = "google"   # Extractor + OCR
    text_provider: str = "google"       # Scorer + Justifier (model A)
    critic_provider: str = "google"     # Critic (model B)

    # --- Google Gemini (vision) ---------------------------------------
    # 2.5-flash-lite has the highest free-tier quota of any vision-capable
    # Gemini (about 15 RPM / 1000 RPD) — picked for reliability over peak
    # quality. Verify current limits at ai.google.dev/gemini-api/docs/rate-limits.
    google_api_key: str = ""
    grader_model_google: str = "gemini-2.5-flash-lite"

    # --- Groq (free, fast; text + critic roles) -----------------------
    # Groq's free tier is far more generous per-minute than Gemini's and
    # returns in well under a second. Confirm current model ids at
    # console.groq.com/docs/models — they change.
    #
    # Cross-model critic (item 2): keep critic_model_groq DIFFERENT from
    # grader_model_groq to stop the judge from favouring its own outputs.
    # Both default to the same strong model so the pipeline works out of
    # the box; flip critic_model_groq to a second model (or set
    # critic_provider="google") once you have confirmed a second id.
    groq_api_key: str = ""
    grader_model_groq: str = "llama-3.3-70b-versatile"   # scorer / justifier
    critic_model_groq: str = "llama-3.3-70b-versatile"   # critic (see note above)

    # --- Anthropic Claude (paid; optional quality comparison) ---------
    anthropic_api_key: str = ""
    grader_model_anthropic: str = "claude-sonnet-4-20250514"

    # --- Database ------------------------------------------------------
    # SQLite by default. The whole pipeline is ORM (SQLAlchemy), so pointing
    # DATABASE_URL at a Postgres URL swaps the backend with no code change.
    # On Hugging Face Spaces the filesystem is ephemeral: a SQLite file
    # written at runtime is wiped on restart. For the demo, bake a
    # pre-graded gradeops.db into the image (COPY in the Dockerfile).
    database_url: str = "sqlite:///./gradeops.db"

    # --- OCR routing ---------------------------------------------------
    ocr_backend: str = "hosted"

    # --- Storage -------------------------------------------------------
    storage_root: str = "./storage"

    # --- Grader behavior -----------------------------------------------
    # Lane A: single pass. Determinism means extra passes would be
    # identical, so multi-pass variance is not a useful confidence signal
    # here (confidence comes from HHEM + rule check + critic + flags).
    grader_num_passes: int = 1
    grader_critic_retry: int = 0          # set to 1 to enable critic→scorer retry

    # --- Rate-limit throttling -----------------------------------------
    # Seconds between successive LLM calls. Gemini free tier is about
    # 15 RPM, so the safe floor for Gemini calls is ~4s. Groq tolerates
    # much faster; if the vision node is the only Gemini caller you can
    # lower this, but keep a cushion for the vision path.
    llm_min_gap_seconds: float = 4.5

    # --- Plagiarism ----------------------------------------------------
    plagiarism_threshold: float = 0.82
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Grounding check: HHEM-2.1-Open (deterministic, CPU, no API) ---
    # A small faithfulness classifier that scores how well the justification
    # is supported by the extracted claims (0..1). Runs before the LLM Critic
    # in the cascade so the Critic only fires on borderline cases. First use
    # downloads the model (~a few hundred MB) from Hugging Face, then runs
    # offline on CPU. torch+transformers already arrive via sentence-transformers.
    # Calibrate the thresholds on the eval set (Phase 3); the defaults are a
    # starting point, not a tuned value.
    hhem_enabled: bool = True
    hhem_model: str = "vectara/hallucination_evaluation_model"
    hhem_high_threshold: float = 0.7    # >= this: confident grounded -> skip Critic
    hhem_low_threshold: float = 0.4     # <  this: likely ungrounded  -> Critic
    hhem_max_chars: int = 4000          # truncate long inputs to keep CPU fast

    # --- Versioning ----------------------------------------------------
    prompt_version: str = "v1.0"
    schema_version: str = "v1.0"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else None,
        env_file_encoding="utf-8-sig",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_root)
        (p / "pdfs").mkdir(parents=True, exist_ok=True)
        (p / "pages").mkdir(parents=True, exist_ok=True)
        (p / "crops").mkdir(parents=True, exist_ok=True)
        return p

    # --- Per-role resolution ------------------------------------------
    def provider_for(self, role: str) -> str:
        """Which provider serves a given role: 'vision' | 'text' | 'critic'."""
        role = (role or "text").lower()
        if role == "vision":
            return (self.vision_provider or "google").lower()
        if role == "critic":
            return (self.critic_provider or self.text_provider or "groq").lower()
        return (self.text_provider or "groq").lower()

    def model_for(self, role: str) -> str:
        """Model id for a given role, resolved against its provider."""
        provider = self.provider_for(role)
        if provider == "google":
            return self.grader_model_google
        if provider == "anthropic":
            return self.grader_model_anthropic
        if provider == "groq":
            return self.critic_model_groq if role == "critic" else self.grader_model_groq
        # Unknown provider: fall back to the Gemini model so vision still works.
        return self.grader_model_google

    @property
    def effective_models(self) -> dict:
        """The models actually in use per role (for audit + /health)."""
        return {
            "vision": f"{self.provider_for('vision')}:{self.model_for('vision')}",
            "scorer": f"{self.provider_for('text')}:{self.model_for('text')}",
            "critic": f"{self.provider_for('critic')}:{self.model_for('critic')}",
        }

    @property
    def grader_model(self) -> str:
        """Compact, audit-friendly description of the effective pipeline.

        Kept as a single string so existing audit rows and the /health
        endpoint (which stamp settings.grader_model) stay valid, while
        now reflecting the provider split, cross-model critic, and temp.
        """
        m = self.effective_models
        if m["scorer"] == m["critic"]:
            return f"scorer/critic={m['scorer']}; vision={m['vision']}; temp={self.grader_temperature}"
        return (
            f"scorer={m['scorer']}; critic={m['critic']}; "
            f"vision={m['vision']}; temp={self.grader_temperature}"
        )


settings = Settings()
