"""Race permission policy matrix, including historical records."""
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.club_access import check_race_admin


@pytest.mark.parametrize("club,creator,member,expected", [
    (False, True, False, None),
    (False, False, False, 403),
    (True, True, False, 403),
    (True, False, True, None),
    (True, False, False, 403),
])
def test_race_ownership_policy(club, creator, member, expected):
    actor = {"id": uuid4()}
    db = Mock()
    db.execute.return_value.mappings.return_value.first.return_value = {
        "club_id": uuid4() if club else None,
        "created_by": actor["id"] if creator else uuid4(), "club_admin": member,
    }
    if expected is None:
        check_race_admin(db, actor, uuid4())
    else:
        with pytest.raises(HTTPException) as caught:
            check_race_admin(db, actor, uuid4())
        assert caught.value.status_code == expected


def test_missing_race_returns_404():
    db = Mock()
    db.execute.return_value.mappings.return_value.first.return_value = None
    with pytest.raises(HTTPException) as caught:
        check_race_admin(db, {"id": uuid4()}, uuid4())
    assert caught.value.status_code == 404
