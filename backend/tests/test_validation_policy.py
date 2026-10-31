import pytest
from pydantic import ValidationError

from app.schemas import RaceCreate, ValidationPolicy


@pytest.mark.parametrize('maximum', [0, -1, float('inf'), float('nan')])
def test_maximum_speed_must_be_positive_and_finite(maximum):
    with pytest.raises(ValidationError):
        ValidationPolicy(maximum_speed_mpm=maximum)


def test_maximum_speed_must_exceed_minimum():
    with pytest.raises(ValidationError):
        RaceCreate(name='Test', release_latitude=10, release_longitude=125,
                   minimum_speed_mpm=1500, maximum_speed_mpm=1500)
    policy = RaceCreate(name='Test', release_latitude=10, release_longitude=125,
                        minimum_speed_mpm=500, maximum_speed_mpm=2500)
    assert policy.maximum_speed_mpm == 2500


@pytest.mark.parametrize('seconds', [-1, 301])
def test_clock_tolerance_is_bounded(seconds):
    with pytest.raises(ValidationError):
        ValidationPolicy(clock_tolerance_seconds=seconds)
