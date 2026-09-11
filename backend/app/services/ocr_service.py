import os
from pathlib import Path

import pymupdf
import pytesseract
from PIL import Image


class OCRService:
    """
    Extracts text from financial documents.

    Processing strategy:
        - Native PDF text is extracted directly.
        - Scanned PDF pages are rendered at a memory-efficient
          resolution and sent to Tesseract OCR.
        - JPG/JPEG/PNG files are processed using Tesseract OCR.

    Page numbers are preserved so that later extraction can
    provide evidence and page references.

    The OCR pipeline is deliberately memory-conscious because
    the deployed service may run on a resource-limited instance.
    """

    SUPPORTED_IMAGE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
    }

    # Keep OCR images within a reasonable memory footprint.
    OCR_RENDER_SCALE = 1.5
    MAX_IMAGE_DIMENSION = 2500

    def __init__(self):
        self._configure_tesseract()

    # ---------------------------------------------------------
    # Tesseract configuration
    # ---------------------------------------------------------

    def _configure_tesseract(self):
        """
        Configure the Tesseract executable.

        Priority:
            1. TESSERACT_CMD from environment
            2. Standard Windows installation path
            3. Tesseract available through system PATH
        """

        configured_path = os.getenv("TESSERACT_CMD")

        if configured_path and Path(configured_path).exists():
            pytesseract.pytesseract.tesseract_cmd = configured_path
            return

        windows_default = Path(
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )

        if windows_default.exists():
            pytesseract.pytesseract.tesseract_cmd = (
                str(windows_default)
            )

    # ---------------------------------------------------------
    # Main extraction method
    # ---------------------------------------------------------

    def extract_text(
        self,
        file_path: str,
        file_type: str | None = None,
    ):
        """
        Extract text from a supported document.

        Returns:
            {
                "full_text": "...",
                "pages": [...],
                "ocr_used": True/False
            }
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

    # ---------------------------------------------------------
    # PDF extraction
    # ---------------------------------------------------------

    def _extract_from_pdf(self, path: Path):
        """
        Extract native PDF text first.

        If a page does not contain meaningful native text,
        render that page as an image and use Tesseract OCR.

        Only one OCR image is kept in memory at a time.
        """

        pages = []
        document_ocr_used = False

        pdf = pymupdf.open(str(path))

        try:
            for page_index in range(len(pdf)):
                page = pdf[page_index]

                native_text = page.get_text("text").strip()

                # ---------------------------------------------
                # Native PDF text available
                # ---------------------------------------------

                if self._has_meaningful_text(native_text):
                    pages.append(
                        {
                            "page_number": page_index + 1,
                            "text": native_text,
                            "ocr_used": False,
                        }
                    )

                    continue

                # ---------------------------------------------
                # Scanned PDF page -> OCR
                # ---------------------------------------------

                pixmap = page.get_pixmap(
                    matrix=pymupdf.Matrix(
                        self.OCR_RENDER_SCALE,
                        self.OCR_RENDER_SCALE,
                    ),
                    alpha=False,
                )

                try:
                    image = Image.frombytes(
                        "RGB",
                        [pixmap.width, pixmap.height],
                        pixmap.samples,
                    )

                    image = self._prepare_image_for_ocr(image)

                    ocr_text = self._run_tesseract(image)

                    pages.append(
                        {
                            "page_number": page_index + 1,
                            "text": ocr_text,
                            "ocr_used": True,
                        }
                    )

                    document_ocr_used = True

                    # Explicitly release the image before processing
                    # the next page.
                    image.close()
                    del image

                finally:
                    del pixmap

        finally:
            pdf.close()

        full_text = self._combine_page_text(pages)

        return {
            "full_text": full_text,
            "pages": pages,
            "ocr_used": document_ocr_used,
        }

    # ---------------------------------------------------------
    # Image extraction
    # ---------------------------------------------------------

    def _extract_from_image(self, path: Path):
        """
        Extract text from JPG/JPEG/PNG using Tesseract OCR.

        Large uploaded images are resized before OCR to avoid
        excessive memory consumption while retaining enough
        resolution for document text.
        """

        with Image.open(path) as image:
            image = image.convert("RGB")

            image = self._prepare_image_for_ocr(image)

            text = self._run_tesseract(image)

            image.close()

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

    # ---------------------------------------------------------
    # OCR image preparation
    # ---------------------------------------------------------

    @classmethod
    def _prepare_image_for_ocr(cls, image: Image.Image):
        """
        Reduce very large OCR images to a bounded maximum
        dimension.

        This prevents large uploaded images and rendered PDF
        pages from consuming excessive memory.
        """

        width, height = image.size

        largest_dimension = max(width, height)

        if largest_dimension <= cls.MAX_IMAGE_DIMENSION:
            return image

        scale = cls.MAX_IMAGE_DIMENSION / largest_dimension

        new_size = (
            max(1, int(width * scale)),
            max(1, int(height * scale)),
        )

        resized_image = image.resize(
            new_size,
            Image.Resampling.LANCZOS,
        )

        image.close()

        return resized_image

    # ---------------------------------------------------------
    # Tesseract
    # ---------------------------------------------------------

    @staticmethod
    def _run_tesseract(image: Image.Image):
        """
        Run Tesseract OCR using English language data.
        """

        text = pytesseract.image_to_string(
            image,
            lang="eng",
        )

        return text.strip()

    # ---------------------------------------------------------
    # Meaningful text check
    # ---------------------------------------------------------

    @staticmethod
    def _has_meaningful_text(text: str):
        """
        Determine whether a PDF page contains enough native
        text to avoid OCR.

        Scanned pages generally have no meaningful native text.
        """

        if not text:
            return False

        alphanumeric_characters = sum(
            character.isalnum()
            for character in text
        )

        return alphanumeric_characters >= 20

    # ---------------------------------------------------------
    # Combine page text
    # ---------------------------------------------------------

    @staticmethod
    def _combine_page_text(pages):
        """
        Combine page-level text while preserving page boundaries.
        """

        page_texts = []

        for page in pages:
            page_texts.append(
                f"[Page {page['page_number']}]\n"
                f"{page['text']}"
            )

        return "\n\n".join(page_texts)