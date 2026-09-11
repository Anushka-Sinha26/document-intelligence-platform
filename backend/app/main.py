from pathlib import Path

from flask import Flask, render_template
from flask_smorest import Api

from app.api.routes.documents import documents_bp
from app.core.config import Config
from app.core.database import db
from app.core.logging import configure_logging
from app.models.document import Document


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = BASE_DIR / "frontend"


# ---------------------------------------------------------
# Application factory
# ---------------------------------------------------------

def create_app():

    # Configure application logging
    configure_logging()

    # Create Flask application
    app = Flask(
        __name__,
        template_folder=str(FRONTEND_DIR / "templates"),
        static_folder=str(FRONTEND_DIR / "static"),
    )

    # Load application configuration
    app.config.from_object(Config)

    # -----------------------------------------------------
    # Swagger / OpenAPI configuration
    # -----------------------------------------------------

    app.config["API_TITLE"] = "Document Intelligence Platform API"
    app.config["API_VERSION"] = "v1"
    app.config["OPENAPI_VERSION"] = "3.0.3"
    app.config["OPENAPI_URL_PREFIX"] = "/"
    app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
    app.config[
        "OPENAPI_SWAGGER_UI_URL"
    ] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

    # -----------------------------------------------------
    # Database
    # -----------------------------------------------------

    db.init_app(app)

    # -----------------------------------------------------
    # Swagger / API
    # -----------------------------------------------------

    api = Api(app)

    # Register document API routes
    api.register_blueprint(documents_bp)

    # -----------------------------------------------------
    # Create database tables
    # -----------------------------------------------------

    with app.app_context():
        db.create_all()

    # -----------------------------------------------------
    # Frontend dashboard
    # -----------------------------------------------------

    @app.get("/")
    def dashboard():
        return render_template("dashboard.html")

    # -----------------------------------------------------
    # Health check
    # -----------------------------------------------------

    @app.get("/api/v1/health")
    def health_check():

        return {
            "status": "success",
            "service": "document-intelligence-platform",
            "message": "API is running"
        }, 200

    return app


# ---------------------------------------------------------
# Create application
# ---------------------------------------------------------

app = create_app()


# ---------------------------------------------------------
# Run application
# ---------------------------------------------------------

if __name__ == "__main__":
    app.run(debug=True)