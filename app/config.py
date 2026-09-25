import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

# Keep local Whisper model downloads (huggingface_hub cache) on this project's
# drive instead of the default C:\Users\<user>\.cache -- the system drive has
# very little free space, and a full C: drive breaks far more than this app.
os.environ.setdefault("HF_HOME", str(BASE_DIR / ".hf_cache"))

class Settings(BaseSettings):
    APP_NAME: str = "AccessLearn AI"
    BASE_DIR: Path = BASE_DIR
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # gemini-flash-lite-latest: chosen after finding (via the API's own error
    # body during development on the sibling project) that this key's free
    # tier enforces a hard ~20/day GenerateRequestsPerDayPerProjectPerModel
    # quota on some models -- the "lite" tier had a less immediately-
    # exhausted quota. gemini_service.py also retries a second fallback
    # model (separate quota bucket) if this one is spent for the day.
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-flash-lite-latest")

    # Redis / Celery
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Directories
    UPLOAD_DIR: Path = BASE_DIR / "storage" / "uploads"
    OUTPUT_DIR: Path = BASE_DIR / "storage" / "outputs"

    class Config:
        env_file = ".env"
        extra = "ignore"

    @property
    def has_gemini(self) -> bool:
        return bool(self.GEMINI_API_KEY.strip())

settings = Settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
for _sub in ("frames", "analysis", "translations"):
    (settings.OUTPUT_DIR / _sub).mkdir(parents=True, exist_ok=True)
