"""Read-only, explicitly non-official leaderboard preview.

Only human-approved clocking evidence is considered. The first approved
arrival per entry wins; unreviewed and rejected events are excluded.
This endpoint never writes to race_results or finalizes a race.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..auth import require_admin
from ..database import get_db
from ..calculations import speed_mpm, convert_speed, leaderboard

router = APIRouter(prefix="/races", tags=["results-preview"])

@router.get("/{race_id}/leaderboard-preview")
def preview_leaderboard(race_id: UUID, db: Session = Depends(get_db),
                        actor: dict = Depends(require_admin)):
    race = db.execute(text("""
        SELECT id,name,status,actual_release_at,minimum_speed_mpm,
               guest_ranking_mode,display_speed_unit
        FROM races WHERE id=:race
    """), {"race":race_id}).mappings().first()
    if race is None:
        raise HTTPException(404, "Race not found")
    if race["actual_release_at"] is None:
        return {"race_id":race_id,"official":False,"entries":[],
                "note":"Race has not been released"}
    # Approval is explicit review evidence; the event itself remains pending
    # until a separate trusted acceptance/finalization process is implemented.
    events = db.execute(text("""
        SELECT DISTINCT ON (e.id)
               e.id AS entry_id,e.pigeon_id,e.loft_id,e.distance_meters,
               e.expected_method AS clocking_method,c.id AS event_id,
               c.recorded_at AS arrival_at
        FROM race_entries e
        JOIN clocking_events c ON c.entry_id=e.id
        WHERE e.race_id=:race AND e.status='registered'
          AND c.status='pending'
          AND EXISTS (
              SELECT 1 FROM clocking_reviews cr
              WHERE cr.event_id=c.id AND cr.decision='approve'
          )
          AND c.recorded_at > :released
        ORDER BY e.id,c.recorded_at ASC,c.id ASC
    """), {"race":race_id,"released":race["actual_release_at"]}).mappings().all()
    rows = []
    for event in events:
        velocity = speed_mpm(float(event["distance_meters"]),
                             race["actual_release_at"],event["arrival_at"])
        rows.append({
            "entry_id":event["entry_id"],"pigeon_id":event["pigeon_id"],
            "loft_id":event["loft_id"],"event_id":event["event_id"],
            "clocking_method":event["clocking_method"],
            "arrival_at":event["arrival_at"],
            "distance_meters":float(event["distance_meters"]),
            "flight_duration_seconds":(event["arrival_at"]-race["actual_release_at"]).total_seconds(),
            "speed_mpm":round(velocity,5),
            "display_speed":round(convert_speed(velocity,race["display_speed_unit"]),4),
            "qualifying_status":"qualified" if velocity>=float(race["minimum_speed_mpm"]) else "below_minimum",
            "verification_status":"provisional",
        })
    # Only qualifying entries receive a rank; below-minimum entries remain visible.
    ranked = leaderboard(rows, race["guest_ranking_mode"])
    ranks = {r["entry_id"]:(r["rank"],r["leaderboard"]) for r in ranked}
    for row in rows:
        rank = ranks.get(row["entry_id"])
        row["rank"] = rank[0] if rank else None
        row["leaderboard"] = rank[1] if rank else (
            "combined" if race["guest_ranking_mode"]=="combined" else
            ("guest" if row["clocking_method"]=="QR" else "member"))
    rows.sort(key=lambda r:(r["leaderboard"],r["rank"] is None,
                             r["rank"] if r["rank"] is not None else 999999,
                             r["arrival_at"],str(r["entry_id"])))
    return {"race_id":race_id,"race_name":race["name"],"race_status":race["status"],
            "official":False,"ranking_mode":race["guest_ranking_mode"],
            "speed_unit":race["display_speed_unit"],
            "entries":rows,
            "note":"Preview from reviewed evidence only; not official or finalized"}
