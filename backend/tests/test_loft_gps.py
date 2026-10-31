from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.routers.participants import LoftLocation


def test_browser_gps_requires_accuracy_and_aware_capture_time():
    base = {'name': 'Test Loft', 'latitude': 9.6588, 'longitude': 125.5286,
            'coordinate_source': 'browser_gps'}
    with pytest.raises(ValidationError):
        LoftLocation(**base)
    with pytest.raises(ValidationError):
        LoftLocation(**base, gps_accuracy_m=10, gps_captured_at=datetime(2026, 10, 31))
    location = LoftLocation(**base, gps_accuracy_m=10, gps_captured_at=datetime.now(timezone.utc))
    assert location.coordinate_source == 'browser_gps'


@pytest.mark.parametrize('field,value', [('latitude', 91), ('longitude', 181),
    ('latitude', float('nan')), ('gps_accuracy_m', -1), ('gps_accuracy_m', float('inf'))])
def test_invalid_location_measurements(field, value):
    data = {'name': 'Test Loft', 'latitude': 9.6588, 'longitude': 125.5286,
            'coordinate_source': 'browser_gps', 'gps_accuracy_m': 10,
            'gps_captured_at': datetime.now(timezone.utc), field: value}
    with pytest.raises(ValidationError):
        LoftLocation(**data)


def test_manual_coordinates_cannot_claim_gps_measurements():
    with pytest.raises(ValidationError):
        LoftLocation(name='Test Loft', latitude=9.6588, longitude=125.5286,
                     coordinate_source='manual', gps_accuracy_m=10)
