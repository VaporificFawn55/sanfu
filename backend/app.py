from typing import Optional, Union, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import (
    get_all_members,
    search_members_by_name,
    get_member_id_by_name,
    create_member,
    delete_member,
    add_offering,
    get_offerings_for_member,
)

app = FastAPI(title="Members API", version="1.0.0")

# CORS – open for dev; in prod, set your frontend origin(s)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # e.g., ["https://your-frontend.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Schemas ----------


class MemberCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    # Accept either ID (int) or code (str) or None
    membership_level: Optional[Union[int, str]] = Field(
        None, description="membership_levels.id or membership_levels.code"
    )
    interview_status: Optional[Union[int, str]] = Field(
        None, description="interview_statuses.id or interview_statuses.code"
    )
    gender: Optional[str] = None
    birthdate: Optional[datetime] = None  # or date if you prefer just dates
    phone: Optional[str] = None
    email: Optional[str] = None
    basic_info: Optional[dict] = None


class MemberOut(BaseModel):
    id: str
    name: str


class OfferingCreate(BaseModel):
    member_id: str
    amount: float = Field(..., ge=0)
    note: Optional[str] = ""
    donated_at: Optional[datetime] = None


class OfferingOut(BaseModel):
    id: int
    amount: float
    currency: str
    donated_at: datetime
    note: Optional[str] = None


class OfferingLogOut(BaseModel):
    member_id: str
    total: float
    log: List[OfferingOut]


# ---------- Endpoints ----------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/members", response_model=List[MemberOut])
def api_get_members():
    return get_all_members()


@app.get("/members/search", response_model=List[MemberOut])
def api_search_members(name: str = Query(..., min_length=1)):
    return search_members_by_name(name)


@app.get("/members/by-name/{name}")
def api_get_member_id(name: str):
    member_id = get_member_id_by_name(name)
    if not member_id:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"id": member_id}


@app.post("/members", response_model=MemberOut, status_code=201)
def api_add_member(member: MemberCreate):
    try:
        created = create_member(
            name=member.name,
            membership_level=member.membership_level,
            interview_status=member.interview_status,
            gender=member.gender,
            birthdate=member.birthdate.date() if isinstance(
                member.birthdate, datetime) else member.birthdate,
            phone=member.phone,
            email=member.email,
            basic_info=member.basic_info,
        )
        return created
    except ValueError as ve:
        # unknown codes, etc.
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create member")


@app.delete("/members/{member_id}", status_code=204)
def api_delete_member_ep(member_id: str):
    try:
        deleted = delete_member(member_id)
        if deleted == 0:
            raise HTTPException(status_code=404, detail="Member not found")
        return  # 204 No Content
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to delete member")


# ---------- offerings ----------
@app.post("/offerings", response_model=OfferingOut, status_code=201)
def api_add_offering(body: OfferingCreate):
    try:
        created = add_offering(
            member_id=body.member_id,
            amount=body.amount,
            note=body.note or "",
            donated_at=body.donated_at,
        )
        return created
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to add offering")


@app.get("/members/{member_id}/offerings", response_model=OfferingLogOut)
def api_member_offerings(member_id: str):
    try:
        return get_offerings_for_member(member_id)
    except Exception:
        raise HTTPException(
            status_code=400, detail="Failed to fetch offerings")
