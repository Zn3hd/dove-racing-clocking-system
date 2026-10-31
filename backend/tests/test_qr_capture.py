"""QR adapter contract checks without a running database."""
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.routers.clocking import QRScanRequest, guest_qr_entries


@pytest.mark.parametrize('source', ['usb_qr', 'web_camera', 'manual'])
def test_capture_sources_are_explicit_operator_inputs(source):
    request = QRScanRequest(entry_id=uuid4(), token='a' * 48, idempotency_key=uuid4(), capture_source=source)
    assert request.capture_source == source


def test_qr_cannot_claim_automatic_or_simulator_capture():
    for source in ('automatic', 'simulator', 'serial'):
        with pytest.raises(ValidationError):
            QRScanRequest(entry_id=uuid4(), token='a' * 48, idempotency_key=uuid4(), capture_source=source)


def test_guest_entry_listing_refuses_non_guest_before_querying():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        guest_qr_entries({'id': uuid4(), 'role_code': 'member'}, db)
    assert exc.value.status_code == 403
    db.execute.assert_not_called()
