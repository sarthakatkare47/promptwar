import io
from PIL import Image
import pytest


def make_test_png(color="green") -> bytes:
    bio = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=color)
    img.save(bio, format="PNG")
    return bio.getvalue()


def test_upload_invoice_new_and_idempotent(client):
    png_bytes = make_test_png("green")

    # 1. First upload: 201 Created
    response1 = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice_sample.png", png_bytes, "image/png")},
    )
    assert response1.status_code == 201
    data1 = response1.json()
    assert data1["already_existed"] is False
    invoice = data1["invoice"]
    inv_id = invoice["invoice_id"]
    assert inv_id.startswith("inv_")
    assert invoice["processing_status"] == "ready"

    # 2. Second upload with identical bytes: 200 OK, already_existed is True
    response2 = client.post(
        "/api/invoices/upload",
        files={"file": ("invoice_sample.png", png_bytes, "image/png")},
    )
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["already_existed"] is True
    assert data2["invoice"]["invoice_id"] == inv_id

    # 3. Retrieve original file via file endpoint
    file_res = client.get(f"/api/invoices/{inv_id}/file")
    assert file_res.status_code == 200
    assert file_res.content == png_bytes

    # 4. Delete invoice
    del_res = client.delete(f"/api/invoices/{inv_id}")
    assert del_res.status_code == 204

    # 5. Subsequent get file returns 404
    assert client.get(f"/api/invoices/{inv_id}/file").status_code == 404
    # Subsequent delete returns 404
    assert client.delete(f"/api/invoices/{inv_id}").status_code == 404
