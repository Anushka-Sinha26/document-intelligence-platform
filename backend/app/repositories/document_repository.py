import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import db
from app.models.document import Document


logger = logging.getLogger(__name__)


class DocumentRepository:
    """Database operations for processed documents."""

    def create(
        self,
        document_name: str,
        document_type: str,
        processing_status: str,
        file_validation: Optional[Dict[str, Any]] = None,
        extracted_data: Optional[Dict[str, Any]] = None,
        validation_result: Optional[Dict[str, Any]] = None,
        processing_metadata: Optional[Dict[str, Any]] = None,
    ) -> Document:
        """
        Create and persist a processed document.

        The complete processing result is stored, including:
        - file validation
        - extracted structured data
        - financial validation
        - processing metadata
        """

        document = Document(
            document_name=document_name,
            document_type=document_type,
            processing_status=processing_status,
            file_type=(
                file_validation.get("file_type")
                if file_validation
                else None
            ),
            page_count=(
                file_validation.get("page_count")
                if file_validation
                else None
            ),
            extracted_data=extracted_data,
            validation_result=validation_result,
            processing_metadata=processing_metadata,
        )

        try:
            # Add the document to the current transaction.
            db.session.add(document)

            # Flush first so SQLAlchemy sends the INSERT to the
            # database and assigns the document ID.
            db.session.flush()

            logger.info(
                "Document inserted into database session: "
                "name=%s id=%s status=%s",
                document_name,
                document.id,
                processing_status,
            )

            # Permanently save the transaction.
            db.session.commit()

            # Refresh the object from the database so we know that
            # the persisted record is available.
            db.session.refresh(document)

            logger.info(
                "Document persisted successfully: "
                "name=%s id=%s status=%s",
                document.document_name,
                document.id,
                document.processing_status,
            )

            return document

        except SQLAlchemyError:
            # Roll back the transaction if anything goes wrong.
            db.session.rollback()

            logger.exception(
                "Database error while saving document: %s",
                document_name,
            )

            raise

        except Exception:
            # Roll back unexpected errors as well.
            db.session.rollback()

            logger.exception(
                "Unexpected error while saving document: %s",
                document_name,
            )

            raise

    def get_latest_by_name(
        self,
        document_name: str,
    ) -> Optional[Document]:
        """
        Return the latest processing result for a document name.
        """

        document = (
            Document.query
            .filter_by(document_name=document_name)
            .order_by(Document.created_at.desc())
            .first()
        )

        if document:
            logger.info(
                "Retrieved latest document: name=%s id=%s status=%s",
                document.document_name,
                document.id,
                document.processing_status,
            )
        else:
            logger.info(
                "No document found with name=%s",
                document_name,
            )

        return document

    def get_all(self) -> List[Document]:
        """
        Return all processed documents, newest first.
        """

        documents = (
            Document.query
            .order_by(Document.created_at.desc())
            .all()
        )

        logger.info(
            "Retrieved %s processed documents from database.",
            len(documents),
        )

        return documents

    def get_by_id(
        self,
        document_id: int,
    ) -> Optional[Document]:
        """
        Return a document by database ID.
        """

        document = db.session.get(
            Document,
            document_id,
        )

        if document:
            logger.info(
                "Retrieved document by ID: id=%s name=%s",
                document.id,
                document.document_name,
            )
        else:
            logger.info(
                "No document found with ID=%s",
                document_id,
            )

        return document