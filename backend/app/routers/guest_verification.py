"""Independent physical verification of guest QR arrivals.

Only a club administrator can record an in-person verification. A QR
submission alone never qualifies as physically verified evidence.
"""
from uuid import UUID, uuid4
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session
from ..club_access import require_event_admin
from ..database import get_db

router = APIRouter(prefix="/clocking", tags=["official-verification"])

class GuestVerification(BaseModel):
    decision: Literal["confirmed","rejected"]
    ring_number_seen: str = Field(min_length=1,max_length=200)
    evidence_note: str = Field(min_length=12,max_length=2000)

@router.post("/events/{event_id}/guest-verification", status_code=201)
def verify_guest(event_id: UUID, payload: GuestVerification,
                 actor: dict=Depends(require_event_admin),
                 db: Session=Depends(get_db)):
    with db.begin():
        event=db.execute(text("""
            SELECT c.id,c.method,c.status,e.expected_method,e.status AS entry_status,
                   p.official_ring_number,r.status AS race_status,
                   l.user_id AS loft_owner
            FROM clocking_events c
            JOIN race_entries e ON e.id=c.entry_id
            JOIN races r ON r.id=e.race_id
            JOIN pigeons p ON p.id=e.pigeon_id
            JOIN lofts l ON l.id=e.loft_id
            WHERE c.id=:id FOR UPDATE OF c
        """),{"id":event_id}).mappings().first()
        if event is None:
            raise HTTPException(404,"Clocking event not found")
        if event["race_status"] not in ("active","closed"):
            raise HTTPException(409,"Race is not eligible for guest verification")
        if event["method"]!="QR" or event["expected_method"]!="QR":
            raise HTTPException(422,"Only guest QR arrivals may be verified here")
        if event["status"]=="invalid" or event["entry_status"]!="registered":
            raise HTTPException(409,"Rejected or inactive entry cannot be verified")
        if event["loft_owner"]==actor["id"]:
            raise HTTPException(403,"A participant cannot verify their own arrival")
        existing=db.execute(text("""
            SELECT id FROM guest_arrival_verifications WHERE event_id=:event
        """),{"event":event_id}).scalar_one_or_none()
        if existing:
            raise HTTPException(409,"Arrival already physically verified")
        ring_matches=payload.ring_number_seen.strip()==event["official_ring_number"]
        if payload.decision=="confirmed" and not ring_matches:
            raise HTTPException(422,"Observed ring number does not match registered pigeon")
        decision=payload.decision
        vid=uuid4()
        db.execute(text("""
            INSERT INTO guest_arrival_verifications
              (id,event_id,verified_by,ring_number_seen,decision,evidence_note)
            VALUES (:id,:event,:actor,:ring,:decision,:note)
        """),{"id":vid,"event":event_id,"actor":actor["id"],
               "ring":payload.ring_number_seen.strip(),"decision":decision,
               "note":payload.evidence_note})
        db.execute(text("""
            INSERT INTO audit_logs(actor_id,action,entity_type,entity_id)
            VALUES (:actor,'guest_arrival.physically_verified','clocking_event',:event)
        """),{"actor":actor["id"],"event":event_id})
    return {"verification_id":vid,"event_id":event_id,
            "decision":decision,"ring_matched":ring_matches,
            "official_result_created":False}
