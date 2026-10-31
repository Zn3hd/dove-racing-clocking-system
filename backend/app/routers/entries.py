"""Registration: registered pigeons, verified lofts, race must be open."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas import EntryCreate
from ..club_access import require_race_admin
from ..calculations import distance_meters

router = APIRouter(prefix="/races", tags=["entries"], )

@router.post("/{race_id}/entries", status_code=201)
def register_entry(race_id: UUID, payload: EntryCreate, db: Session = Depends(get_db), actor: dict = Depends(require_race_admin)):
    with db.begin():
        race = db.execute(text("""SELECT club_id,release_latitude,release_longitude,status FROM races
            WHERE id=:id FOR UPDATE"""), {"id":race_id}).mappings().first()
        if not race: raise HTTPException(404,"Race not found")
        if race["status"] != "open": raise HTTPException(409,"Registration is allowed only for open races")
        pigeon = db.execute(text("""SELECT p.loft_id,p.status,p.id,l.latitude,l.longitude,l.verified_at,
            u.role_code,u.status AS owner_status,u.id AS owner_id FROM pigeons p JOIN lofts l ON l.id=p.loft_id
            JOIN users u ON u.id=l.user_id WHERE p.id=:id FOR UPDATE OF p,l,u"""), {"id":payload.pigeon_id}).mappings().first()
        if not pigeon: raise HTTPException(404,"Pigeon not found")
        if pigeon["owner_status"] != "active":
            raise HTTPException(422, "Pigeon owner must be active")
        if race["club_id"] is not None:
            member = db.execute(text("""SELECT EXISTS(SELECT 1 FROM club_memberships
                WHERE club_id=:club AND user_id=:owner AND club_role IN ('member','guest'))"""),
                {"club": race["club_id"], "owner": pigeon["owner_id"]}).scalar()
            if not member:
                raise HTTPException(422, "Pigeon owner must belong to the race club")
        if pigeon["status"] != "active" or pigeon["verified_at"] is None:
            raise HTTPException(422,"Pigeon must be active and loft verified")
        if payload.expected_method == "QR" and pigeon["role_code"] != "guest":
            raise HTTPException(422,"QR guest clocking requires a guest account")
        if payload.expected_method == "RFID" and pigeon["role_code"] == "guest":
            raise HTTPException(422,"Guest entry must use QR")
        existing = db.execute(text("""SELECT id FROM race_entries
            WHERE race_id=:race AND pigeon_id=:pigeon"""), {"race":race_id,"pigeon":payload.pigeon_id}).scalar_one_or_none()
        if existing: raise HTTPException(409,"Pigeon already registered for this race")
        if payload.expected_method == "RFID":
            ring = db.execute(text("""SELECT id FROM rfid_rings WHERE pigeon_id=:id AND revoked_at IS NULL"""),
                              {"id":payload.pigeon_id}).scalar_one_or_none()
            if not ring: raise HTTPException(422,"Pigeon has no active RFID ring")
        dist = distance_meters(float(race["release_latitude"]),float(race["release_longitude"]),
                               float(pigeon["latitude"]),float(pigeon["longitude"]))
        if dist <= 0: raise HTTPException(422,"Loft must differ from release location")
        eid = uuid4()
        db.execute(text("""INSERT INTO race_entries(id,race_id,pigeon_id,loft_id,loft_latitude,
            loft_longitude,distance_meters,expected_method,status)
            VALUES (:id,:race,:pigeon,:loft,:lat,:lon,:distance,:method,'registered')"""),
            {"id":eid,"race":race_id,"pigeon":payload.pigeon_id,"loft":pigeon["loft_id"],
             "lat":pigeon["latitude"],"lon":pigeon["longitude"],"distance":round(dist,3),
             "method":payload.expected_method})
        db.execute(text("""INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'entry.registered','race_entry',:id)"""), {"actor":actor["id"],"id":eid})
    return {"id":eid,"race_id":race_id,"pigeon_id":payload.pigeon_id,
            "distance_meters":round(dist,3),"expected_method":payload.expected_method}

@router.get("/{race_id}/entries")
def list_entries(race_id: UUID, db: Session = Depends(get_db), actor: dict = Depends(require_race_admin)):
    rows=db.execute(text("""SELECT id,race_id,pigeon_id,distance_meters,expected_method,status
        FROM race_entries WHERE race_id=:id ORDER BY registered_at LIMIT 1000"""), {"id":race_id})
    return [dict(r._mapping) for r in rows]
