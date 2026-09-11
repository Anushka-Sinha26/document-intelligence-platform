import os

from dotenv import load_dotenv


load_dotenv()


class Config:
    """Application configuration."""

    SECRET_KEY = os.getenv("SECRET_KEY", "development-secret-key")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///document_intelligence.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False