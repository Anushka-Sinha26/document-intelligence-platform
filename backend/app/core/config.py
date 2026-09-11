import os
from pathlib import Path

from dotenv import load_dotenv


# Project root:
# C:\document-intelligence-platform
PROJECT_ROOT = Path(__file__).resolve().parents[3]

ENV_FILE = PROJECT_ROOT / ".env"

# Explicitly load the project's root .env file.
load_dotenv(
    dotenv_path=ENV_FILE,
)


class Config:
    SECRET_KEY = os.getenv(
        "SECRET_KEY",
        "development-secret-key",
    )

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///document_intelligence.db",
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False