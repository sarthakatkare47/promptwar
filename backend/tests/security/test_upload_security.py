import io
from PIL import Image
from pypdf import PdfWriter
import pytest
from app.errors import AppError
from app.services.upload_validation import validate_upload


def test_upload_too_large():
    big_bytes = b"0" * (10_485_760 + 10)  # > 10 MB
    with pytest.raises(AppError) as exc:
        validate_upload(big_bytes, "big.png", "image/png")
    assert exc.value.code == "FILE_TOO_LARGE"
    assert exc.value.status_code == 413


def test_upload_unsupported_extension():
    with pytest.raises(AppError) as exc:
        validate_upload(b"MZ\x90\x00", "test.exe", "application/x-dosexec")
    assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"
    assert exc.value.status_code == 415


def test_upload_renamed_executable():
    # .png extension but MZ header
    with pytest.raises(AppError) as exc:
        validate_upload(b"MZ\x90\x00\x03\x00\x00\x00", "invoice.png", "image/png")
    assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_file_type_mismatch():
    # PNG magic bytes with .pdf extension
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    with pytest.raises(AppError) as exc:
        validate_upload(png_bytes, "invoice.pdf", "application/pdf")
    assert exc.value.code == "FILE_TYPE_MISMATCH"
    assert exc.value.status_code == 422


def test_upload_corrupt_image():
    # Valid PNG header but truncated/garbage body
    corrupt_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRgarbagecorruptdata"
    with pytest.raises(AppError) as exc:
        validate_upload(corrupt_png, "corrupt.png", "image/png")
    assert exc.value.code == "INVALID_FILE_CONTENT"
    assert exc.value.status_code == 422


def test_upload_pixel_bomb():
    # 7000x7000 = 49,000,000 pixels (> 40 MP cap)
    bio = io.BytesIO()
    img = Image.new("RGB", (7000, 7000), color="white")
    img.save(bio, format="JPEG")
    jpeg_bytes = bio.getvalue()

    with pytest.raises(AppError) as exc:
        validate_upload(jpeg_bytes, "bomb.jpg", "image/jpeg")
    assert exc.value.code == "IMAGE_TOO_LARGE_PIXELS"
    assert exc.value.status_code == 422


def test_upload_pdf_active_content_javascript():
    # PDF containing /JavaScript marker
    pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>\nendobj\n%%EOF"
    with pytest.raises(AppError) as exc:
        validate_upload(pdf_bytes, "exploit.pdf", "application/pdf")
    assert exc.value.code == "PDF_ACTIVE_CONTENT"
    assert exc.value.status_code == 422


def test_upload_pdf_too_many_pages():
    writer = PdfWriter()
    for _ in range(6):  # 6 > 5 max pages
        writer.add_blank_page(width=100, height=100)
    bio = io.BytesIO()
    writer.write(bio)
    pdf_bytes = bio.getvalue()

    with pytest.raises(AppError) as exc:
        validate_upload(pdf_bytes, "long.pdf", "application/pdf")
    assert exc.value.code == "PDF_TOO_MANY_PAGES"
    assert exc.value.status_code == 422


def test_upload_valid_image():
    bio = io.BytesIO()
    img = Image.new("RGB", (200, 200), color="blue")
    img.save(bio, format="PNG")
    png_bytes = bio.getvalue()

    res = validate_upload(png_bytes, "clean.png", "image/png")
    assert res.content_type == "image/png"
    assert res.extension == ".png"
    assert len(res.file_sha256) == 64
