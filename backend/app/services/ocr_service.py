import gc
import os
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image


class OCRService:
    """
    Extract text from supported financial documents.

    Strategy:
        - Native PDF text is preferred.
        - Pages without meaningful native text are OCR processed.
        - JPG/JPEG/PNG files are OCR processed.
        - OCR images are kept small to reduce memory usage.
        - Only one rendered page/image is processed at a time.
    """

    SUPPORTED_IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
    }

    # Lower rendering scale keeps Render memory usage low.
    OCR_RENDER_SCALE = 1.25

    # Free Render instances have limited memory.
    MAX_IMAGE_DIMENSION = 2000

    def __init__(self):
        self._configure_tesseract()

    # =========================================================
    # Tesseract configuration
    # =========================================================

    def _configure_tesseract(self):
        """
        Configure Tesseract.

        Priority:
            1. TESSERACT_CMD environment variable
            2. Standard Windows installation
            3. System PATH
        """

        configured_path = os.getenv("TESSERACT_CMD")

        if configured_path:
            configured = Path(configured_path)

            if configured.exists():
                pytesseract.pytesseract.tesseract_cmd = str(
                    configured
                )
                return

        windows_default = Path(
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )

        if windows_default.exists():
            pytesseract.pytesseract.tesseract_cmd = str(
                windows_default
            )

    # =========================================================
    # Main extraction
    # =========================================================

    def extract_text(
        self,
        file_path: str,
        file_type: str | None = None,
    ):
        """
        Extract text from PDF/JPG/JPEG/PNG.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Document not found: {file_path}"
            )

        extension = path.suffix.lower()

        if extension == ".pdf":
            return self._extract_from_pdf(path)

        if extension in self.SUPPORTED_IMAGE_EXTENSIONS:
            return self._extract_from_image(path)

        raise ValueError(
            f"Unsupported document format for OCR: {extension}"
        )

    # =========================================================
    # PDF
    # =========================================================

    def _extract_from_pdf(self, path: Path):
        """
        Extract native PDF text whenever possible.

        OCR is used only when a page does not contain
        meaningful native text.
        """

        pages = []
        document_ocr_used = False

        pdf = pymupdf.open(str(path))

        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]

                native_text = page.get_text(
                    "text"
                ).strip()

                # -------------------------------------------------
                # Prefer native PDF text.
                # -------------------------------------------------

                if self._has_meaningful_text(native_text):

                    pages.append(
                        {
                            "page_number": page_index + 1,
                            "text": native_text,
                            "ocr_used": False,
                        }
                    )

                    continue

                # -------------------------------------------------
                # OCR scanned page.
                # -------------------------------------------------

                pixmap = None
                image = None
                prepared_image = None

                try:

                    pixmap = page.get_pixmap(
                        matrix=pymupdf.Matrix(
                            self.OCR_RENDER_SCALE,
                            self.OCR_RENDER_SCALE,
                        ),
                        alpha=False,
                        colorspace=pymupdf.csRGB,
                    )

                    image = Image.frombytes(
                        "RGB",
                        (
                            pixmap.width,
                            pixmap.height,
                        ),
                        pixmap.samples,
                    )

                    prepared_image = self._prepare_image_for_ocr(
                        image
                    )

                    ocr_text = self._run_tesseract(
                        prepared_image
                    )

                    pages.append(
                        {
                            "page_number": page_index + 1,
                            "text": ocr_text,
                            "ocr_used": True,
                        }
                    )

                    document_ocr_used = True

                finally:

                    if prepared_image is not None:
                        try:
                            prepared_image.close()
                        except Exception:
                            pass

                    if image is not None:
                        try:
                            image.close()
                        except Exception:
                            pass

                    if pixmap is not None:
                        del pixmap

                    gc.collect()

        finally:
            pdf.close()
            gc.collect()

        full_text = self._combine_page_text(
            pages
        )

        return {
            "full_text": full_text,
            "pages": pages,
            "ocr_used": document_ocr_used,
        }

    # =========================================================
    # Image
    # =========================================================

    def _extract_from_image(self, path: Path):
        """
        OCR a JPG/JPEG/PNG document.
        """

        image = None
        prepared_image = None

        try:

            image = Image.open(path)

            image = image.convert(
                "RGB"
            )

            prepared_image = self._prepare_image_for_ocr(
                image
            )

            text = self._run_tesseract(
                prepared_image
            )

        finally:

            if prepared_image is not None:
                try:
                    prepared_image.close()
                except Exception:
                    pass

            if image is not None:
                try:
                    image.close()
                except Exception:
                    pass

            gc.collect()

        pages = [
            {
                "page_number": 1,
                "text": text,
                "ocr_used": True,
            }
        ]

        return {
            "full_text": text,
            "pages": pages,
            "ocr_used": True,
        }

    # =========================================================
    # Image preparation
    # =========================================================

    @classmethod
    def _prepare_image_for_ocr(
        cls,
        image: Image.Image,
    ):
        """
        Resize large images before OCR.

        This is important on Render Free because the instance
        has limited memory.
        """

        width, height = image.size

        largest_dimension = max(
            width,
            height,
        )

        if (
            largest_dimension
            <= cls.MAX_IMAGE_DIMENSION
        ):
            return image

        scale = (
            cls.MAX_IMAGE_DIMENSION
            / largest_dimension
        )

        new_size = (
            max(
                1,
                int(width * scale),
            ),
            max(
                1,
                int(height * scale),
            ),
        )

        resized_image = image.resize(
            new_size,
            Image.Resampling.LANCZOS,
        )

        return resized_image

    # =========================================================
    # Tesseract
    # =========================================================

    @staticmethod
    def _run_tesseract(
        image: Image.Image,
    ):
        """
        Run Tesseract OCR.

        --psm 6 works well for structured document pages
        containing tables and financial text.
        """

        text = pytesseract.image_to_string(
            image,
            lang="eng",
            config="--psm 6",
        )

        return text.strip()

    # =========================================================
    # Meaningful text
    # =========================================================

    @staticmethod
    def _has_meaningful_text(
        text: str,
    ):
        """
        Determine whether native PDF text is meaningful enough
        to avoid OCR.
        """

        if not text:
            return False

        alphanumeric_characters = sum(
            character.isalnum()
            for character in text
        )

        return (
            alphanumeric_characters >= 20
        )

    # =========================================================
    # Combine pages
    # =========================================================

    @staticmethod
    def _combine_page_text(
        pages,
    ):
        """
        Combine page text while preserving page numbers.
        """

        page_texts = []

        for page in pages:

            page_texts.append(
                f"[Page {page['page_number']}]\n"
                f"{page['text']}"
            )

        return "\n\n".join(
            page_texts
        )