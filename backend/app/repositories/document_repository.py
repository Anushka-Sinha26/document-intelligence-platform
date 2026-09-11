import logging

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import db
from app.models.document import Document


logger = logging.getLogger(__name__)


class DocumentRepository:
    """
    Repository responsible for creating and retrieving
    processed document records.
    """

    # =========================================================
    # CREATE DOCUMENT
    # =========================================================

    def create(
        self,
        document_name,
        document_type,
        processing_status,
        file_type=None,
        page_count=None,
        extracted_data=None,
        validation_result=None,
        processing_metadata=None,
    ):
        """
        Create and persist a processed document.

        Parameters:
            document_name:
                Original uploaded filename.

            document_type:
                One of the supported financial document types.

            processing_status:
                PASS, FAILED, or NOT_APPLICABLE.

            file_type:
                Validated MIME/file type.

            page_count:
                Number of pages in the document.

            extracted_data:
                Structured AI extraction result.

            validation_result:
                Financial validation result.

            processing_metadata:
                OCR/model/processing metadata.
        """

        try:
            document = Document(
                document_name=document_name,
                document_type=document_type,
                processing_status=processing_status,
                file_type=file_type,
                page_count=page_count,
                extracted_data=extracted_data,
                validation_result=validation_result,
                processing_metadata=processing_metadata,
            )

            db.session.add(document)
            db.session.commit()
            db.session.refresh(document)

            logger.info(
                "Document created successfully: "
                "id=%s name=%s type=%s status=%s",
                document.id,
                document.document_name,
                document.document_type,
                document.processing_status,
            )

            return document

        except SQLAlchemyError:
            db.session.rollback()

            logger.exception(
                "Database error while creating document: %s",
                document_name,
            )

            raise

        except Exception:
            db.session.rollback()

            logger.exception(
                "Unexpected error while creating document: %s",
                document_name,
            )

            raise

    # =========================================================
    # GET LATEST DOCUMENT BY NAME
    # =========================================================

    def get_latest_by_name(
        self,
        document_name,
    ):
        """
        Return the latest processed document with the
        specified filename.
        """

        try:
            return (
                Document.query
                .filter(
                    Document.document_name == document_name
                )
                .order_by(
                    Document.created_at.desc(),
                    Document.id.desc(),
                )
                .first()
            )

        except SQLAlchemyError:
            logger.exception(
                "Database error while retrieving latest "
                "document: %s",
                document_name,
            )

            raise

        except Exception:
            logger.exception(
                "Unexpected error while retrieving latest "
                "document: %s",
                document_name,
            )

            raise

    # =========================================================
    # GET ALL DOCUMENTS
    # =========================================================

    def get_all(self):
        """
        Return all processed documents, newest first.
        """

        try:
            return (
                Document.query
                .order_by(
                    Document.created_at.desc(),
                    Document.id.desc(),
                )
                .all()
            )

        except SQLAlchemyError:
            logger.exception(
                "Database error while retrieving documents."
            )

            raise

        except Exception:
            logger.exception(
                "Unexpected error while retrieving documents."
            )

            raise

    # =========================================================
    # GET DOCUMENT BY ID
    # =========================================================

    def get_by_id(
        self,
        document_id,
    ):
        """
        Return a document by its database ID.
        """

        try:
            return db.session.get(
                Document,
                document_id,
            )

        except SQLAlchemyError:
            logger.exception(
                "Database error while retrieving document id=%s",
                document_id,
            )

            raise

        except Exception:
            logger.exception(
                "Unexpected error while retrieving document id=%s",
                document_id,
            )

            raise