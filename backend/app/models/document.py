from datetime import datetime

from app.core.database import db


class Document(db.Model):
    """Database model for processed documents."""

    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)

    document_name = db.Column(db.String(255), nullable=False, index=True)

    document_type = db.Column(db.String(50), nullable=False)

    processing_status = db.Column(db.String(20), nullable=False)

    file_type = db.Column(db.String(100), nullable=True)

    page_count = db.Column(db.Integer, nullable=True)

    extracted_data = db.Column(db.JSON, nullable=True)

    validation_result = db.Column(db.JSON, nullable=True)

    processing_metadata = db.Column(db.JSON, nullable=True)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    def __repr__(self):
        return (
            f"<Document "
            f"id={self.id} "
            f"name={self.document_name!r} "
            f"type={self.document_type!r}>"
        )