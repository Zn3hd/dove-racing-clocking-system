"""Read-only, owner-scoped data for remote member monitoring."""
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from .results_preview import live_race
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


@router.get("/races/{race_id}/standings")
def member_race_standings(race_id: UUID, db: Session = Depends(get_db),
                         actor: dict = Depends(require_member)):
    """Public-to-participants race standings; never expose private device/loft evidence."""
    allowed = db.execute(text("""
        SELECT 1 FROM race_entries e
        JOIN lofts l ON l.id=e.loft_id
        WHERE e.race_id=:race AND l.user_id=:owner AND e.status='registered'
        LIMIT 1
    """), {"race":race_id,"owner":actor["id"]}).first()
    if not allowed:
        raise HTTPException(404, "Race not found")
    preview = live_race(race_id, db=db, actor=actor)
    fields = ("official_ring_number","owner_name","arrival_at","arrival_order",
              "rank","leaderboard","distance_meters","flight_duration_seconds",
              "display_speed","qualifying_status","verification_status",
              "capture_mode","clocking_method")
    return {
        "race_id": race_id, "race_name": preview["race_name"],
        "race_status": preview["race_status"], "official": False,
        "speed_unit": preview["speed_unit"], "release_at": preview["release_at"],
        "registered_entries": preview["registered_entries"],
        "arrived_entries": preview["arrived_entries"],
        "possibly_truncated": preview["possibly_truncated"],
        "entries": [{key: row.get(key) for key in fields} for row in preview["entries"]],
        "note": "Arrival order is not final rank. Calculated ranks are provisional, "
                "exclude below-minimum speed, and require official finalization.",
    }
