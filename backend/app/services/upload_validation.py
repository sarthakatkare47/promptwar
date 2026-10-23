import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import settings
from app.errors import AppError


@dataclass
class UploadValidationResult:
    content_type: str
    extension: str
    file_sha256: str
    file_size_bytes: int


# Signatures
MAGIC_JPEG = b"\xFF\xD8\xFF"
MAGIC_PNG = b"\x89PNG\r\n\x1a\n"
MAGIC_PDF = b"%PDF-"

# Active content markers in raw PDF bytes
PDF_ACTIVE_MARKERS = [
    re.compile(rb"/JavaScript\b", re.IGNORECASE),
    re.compile(rb"/JS\b", re.IGNORECASE),
    re.compile(rb"/Launch\b", re.IGNORECASE),
    re.compile(rb"/EmbeddedFile\b", re.IGNORECASE),
    re.compile(rb"/OpenAction\b", re.IGNORECASE),
]


def detect_magic_type(content: bytes) -> str:
    if content.startswith(MAGIC_JPEG):
        return "image/jpeg"
    if content.startswith(MAGIC_PNG):
        return "image/png"
    if content.startswith(MAGIC_PDF):
        return "application/pdf"
    return ""


def validate_upload(
    content: bytes,
    filename: str,
    declared_content_type: str = "",
) -> UploadValidationResult:
    file_size = len(content)

    # 1. Size Cap
    if file_size > settings.MAX_UPLOAD_BYTES:
        raise AppError(
            code="FILE_TOO_LARGE",
            message=f"The file is larger than the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            status_code=413,
            details={"max_bytes": settings.MAX_UPLOAD_BYTES, "received_bytes": file_size},
        )

    # 2. Extension check
    ext = Path(filename).suffix.lower()
    allowed_exts = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".pdf": "application/pdf"}
    if ext not in allowed_exts:
        raise AppError(
            code="UNSUPPORTED_MEDIA_TYPE",
            message=f"File extension '{ext}' is not supported. Allowed: .jpg, .jpeg, .png, .pdf",
            status_code=415,
        )

    # 3. Magic byte detection
    detected_type = detect_magic_type(content)
    if not detected_type:
        raise AppError(
            code="UNSUPPORTED_MEDIA_TYPE",
            message="File signature does not match any allowed format (JPEG, PNG, PDF).",
            status_code=415,
        )

    # Extension vs Detected Type consistency
    if allowed_exts[ext] != detected_type:
        raise AppError(
            code="FILE_TYPE_MISMATCH",
            message=f"File extension '{ext}' disagrees with detected type '{detected_type}'.",
            status_code=422,
        )

    # Declared Content-Type check (if provided and recognized)
    if declared_content_type:
        decl = declared_content_type.split(";")[0].strip().lower()
        if decl in ("image/jpeg", "image/png", "application/pdf") and decl != detected_type:
            raise AppError(
                code="FILE_TYPE_MISMATCH",
                message=f"Declared Content-Type '{decl}' disagrees with detected type '{detected_type}'.",
                status_code=422,
            )

    # 4. Image deep inspection
    if detected_type in ("image/jpeg", "image/png"):
        try:
            bio = io.BytesIO(content)
            with Image.open(bio) as img:
                img.verify()
            
            # Re-open to load image and check pixel count
            bio.seek(0)
            with Image.open(bio) as img:
                img.load()
                width, height = img.size
                total_pixels = width * height
                if total_pixels > settings.MAX_IMAGE_PIXELS:
                    raise AppError(
                        code="IMAGE_TOO_LARGE_PIXELS",
                        message=f"Image pixel dimensions ({width}x{height} = {total_pixels}) exceed maximum allowed ({settings.MAX_IMAGE_PIXELS}).",
                        status_code=422,
                        details={"pixels": total_pixels, "max_pixels": settings.MAX_IMAGE_PIXELS},
                    )
        except AppError:
            raise
        except Exception as e:
            raise AppError(
                code="INVALID_FILE_CONTENT",
                message="Image file is corrupt, truncated, or undecodable.",
                status_code=422,
            )

    # 5. PDF deep inspection
    elif detected_type == "application/pdf":
        # Scan for active content markers
        for marker_regex in PDF_ACTIVE_MARKERS:
            if marker_regex.search(content):
                raise AppError(
                    code="PDF_ACTIVE_CONTENT",
                    message="PDF contains active content or scripting markers (/JavaScript, /Launch, /EmbeddedFile, or /OpenAction).",
                    status_code=422,
                )

        try:
            bio = io.BytesIO(content)
            reader = PdfReader(bio)
            if reader.is_encrypted:
                raise AppError(
                    code="PDF_ENCRYPTED",
                    message="Password-protected or encrypted PDFs are not supported.",
                    status_code=422,
                )
            num_pages = len(reader.pages)
            if num_pages > settings.MAX_PDF_PAGES:
                raise AppError(
                    code="PDF_TOO_MANY_PAGES",
                    message=f"PDF page count ({num_pages}) exceeds maximum allowed ({settings.MAX_PDF_PAGES} pages).",
                    status_code=422,
                    details={"pages": num_pages, "max_pages": settings.MAX_PDF_PAGES},
                )
        except AppError:
            raise
        except PdfReadError:
            raise AppError(
                code="INVALID_FILE_CONTENT",
                message="PDF file is malformed or unreadable.",
                status_code=422,
            )
        except Exception:
            raise AppError(
                code="INVALID_FILE_CONTENT",
                message="Failed to parse PDF document.",
                status_code=422,
            )

    # 6. Compute SHA-256
    file_sha256 = hashlib.sha256(content).hexdigest()

    # Normalise canonical extension
    norm_ext = ".jpg" if ext == ".jpeg" else ext

    return UploadValidationResult(
        content_type=detected_type,
        extension=norm_ext,
        file_sha256=file_sha256,
        file_size_bytes=file_size,
    )
