"""Read-only, owner-scoped data for remote member monitoring."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..auth import current_user
from ..database import get_db

router = APIRouter(prefix="/member", tags=["member-dashboard"])


def require_member(user: dict = Depends(current_user)):
    if user["role_code"] != "member":
        raise HTTPException(403, "Member account required")
    return user


@router.get("/overview")
def member_overview(db: Session = Depends(get_db),
                    actor: dict = Depends(require_member)):
    """Never expose other owners' private pigeons or raw device evidence."""
    pigeons = db.execute(text("""
        SELECT p.id, p.official_ring_number, p.name, p.status, l.name AS loft_name,
               EXISTS(SELECT 1 FROM rfid_rings rr
                      WHERE rr.pigeon_id=p.id AND rr.revoked_at IS NULL) AS has_active_rfid
        FROM pigeons p JOIN lofts l ON l.id=p.loft_id
        WHERE l.user_id=:owner
        ORDER BY p.official_ring_number,p.id LIMIT 500
    """), {"owner": actor["id"]}).mappings().all()
    entries = db.execute(text("""
        SELECT e.id AS entry_id,e.pigeon_id,p.official_ring_number,
               r.id AS race_id,r.name AS race_name,r.status AS race_status,
               r.actual_release_at,e.expected_method,e.status AS entry_status,
               (SELECT min(c.recorded_at) FROM clocking_events c
                WHERE c.entry_id=e.id AND c.status IN ('pending','valid')
                  AND NOT EXISTS (
                      SELECT 1 FROM clocking_reviews cr
                      WHERE cr.event_id=c.id AND cr.decision='reject'
                  )) AS first_unrejected_scan_at
        FROM race_entries e
        JOIN pigeons p ON p.id=e.pigeon_id
        JOIN lofts l ON l.id=p.loft_id
        JOIN races r ON r.id=e.race_id
        WHERE l.user_id=:owner
        ORDER BY r.created_at DESC,e.id LIMIT 500
    """), {"owner": actor["id"]}).mappings().all()
    return {
        "member_id": actor["id"],
        "full_name": actor["full_name"],
        "official": False,
        "refresh_after_seconds": 15,
        "pigeons": [dict(row) for row in pigeons],
        "race_entries": [dict(row) for row in entries],
        "note": "Scan detection is provisional evidence, not an official result or verified arrival.",
    }
