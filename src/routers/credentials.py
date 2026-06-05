"""
Platform Credentials API
Store and retrieve encrypted login credentials for job platforms.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from utils.database import PlatformCredential, User, get_db
from utils.crypto import encrypt, decrypt

router = APIRouter(prefix="/api/credentials", tags=["credentials"])

# ── Platforms we support with their default form-field mappings ──────────────
PLATFORMS = [
    "LinkedIn",
    "Indeed",
    "Glassdoor",
    "ZipRecruiter",
    "Dice",
    "Monster",
    "Greenhouse",
    "Lever",
    "Workday",
    "Other",
]


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CredentialCreate(BaseModel):
    platform: str
    username: str
    password: str
    notes: Optional[str] = ""
    user_id: int = 1


class CredentialUpdate(BaseModel):
    platform: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    user_id: int = 1


def _serialize(cred: PlatformCredential, show_password: bool = False) -> Dict[str, Any]:
    return {
        "id":         cred.id,
        "platform":   cred.platform,
        "username":   cred.username,
        "password":   decrypt(cred.password_enc) if show_password else "••••••••",
        "notes":      cred.notes or "",
        "is_active":  cred.is_active,
        "profile":    cred.extra or {},   # name, phone, location from APEX profile
        "created_at": cred.created_at.isoformat() if cred.created_at else None,
        "updated_at": cred.updated_at.isoformat() if cred.updated_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_credentials(user_id: int = 1, db: Session = Depends(get_db)):
    """List all platform credentials (passwords masked)."""
    creds = db.query(PlatformCredential).filter(
        PlatformCredential.user_id == user_id
    ).order_by(PlatformCredential.platform).all()
    return {
        "success": True,
        "credentials": [_serialize(c) for c in creds],
        "platforms": PLATFORMS,
    }


@router.get("/platforms")
def get_platforms():
    return {"platforms": PLATFORMS}


@router.get("/{cred_id}")
def get_credential(cred_id: int, show_password: bool = False, user_id: int = 1, db: Session = Depends(get_db)):
    cred = db.query(PlatformCredential).filter(
        PlatformCredential.id == cred_id,
        PlatformCredential.user_id == user_id,
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"success": True, "credential": _serialize(cred, show_password=show_password)}


@router.post("")
def create_credential(body: CredentialCreate, db: Session = Depends(get_db)):
    """Add a new platform credential. Password is encrypted before storage."""
    # Check for duplicate platform for this user
    existing = db.query(PlatformCredential).filter(
        PlatformCredential.user_id == body.user_id,
        PlatformCredential.platform == body.platform,
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Credential for {body.platform} already exists. Use PUT to update."
        )
    cred = PlatformCredential(
        user_id=body.user_id,
        platform=body.platform,
        username=body.username,
        password_enc=encrypt(body.password),
        notes=body.notes or "",
        is_active=True,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return {"success": True, "credential": _serialize(cred)}


@router.put("/{cred_id}")
def update_credential(cred_id: int, body: CredentialUpdate, db: Session = Depends(get_db)):
    cred = db.query(PlatformCredential).filter(
        PlatformCredential.id == cred_id,
        PlatformCredential.user_id == body.user_id,
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    if body.platform is not None:
        cred.platform = body.platform
    if body.username is not None:
        cred.username = body.username
    if body.password is not None:
        cred.password_enc = encrypt(body.password)
    if body.notes is not None:
        cred.notes = body.notes
    if body.is_active is not None:
        cred.is_active = body.is_active
    cred.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(cred)
    return {"success": True, "credential": _serialize(cred)}


@router.delete("/{cred_id}")
def delete_credential(cred_id: int, user_id: int = 1, db: Session = Depends(get_db)):
    cred = db.query(PlatformCredential).filter(
        PlatformCredential.id == cred_id,
        PlatformCredential.user_id == user_id,
    ).first()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    db.delete(cred)
    db.commit()
    return {"success": True, "message": f"{cred.platform} credential deleted"}


@router.post("/seed-from-profile")
def seed_from_profile(user_id: int = 1, db: Session = Depends(get_db)):
    """
    Pre-populate default credentials from the user's profile.
    Uses the user's email as username and the system password.
    Called once on first setup.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    default_password = "Tejamahesh@2294"
    # Read email from the APEX Profile page (User record).
    # If it's still the system placeholder, fall back to the real email.
    raw_email = (user.email or "").strip()
    placeholder = raw_email in ("", "user@jobsystem.local", "user@example.com")
    email = "tejamahesh23@gmail.com" if placeholder else raw_email

    # All platforms use the same email + password
    all_platforms = [
        "LinkedIn", "Indeed", "Glassdoor", "ZipRecruiter",
        "Dice", "Monster", "Greenhouse", "Lever", "Workday",
    ]

    # Extra profile data for the browser agent to use when filling forms
    profile_extra = {
        "name":          (user.name or "").strip(),
        "phone":         (user.phone or "").strip(),
        "location":      (user.location or "").strip(),
        "current_title": (user.current_title or "").strip(),
        "linkedin_url":  (user.linkedin_profile or "").strip(),
        "github_url":    (user.github_profile or "").strip(),
        "portfolio_url": (user.portfolio_url or "").strip(),
    }

    seeded = []
    updated = []
    for platform in all_platforms:
        exists = db.query(PlatformCredential).filter(
            PlatformCredential.user_id == user_id,
            PlatformCredential.platform == platform,
        ).first()
        if exists:
            exists.username = email
            exists.password_enc = encrypt(default_password)
            exists.extra = profile_extra
            exists.notes = "Synced from APEX profile"
            updated.append(platform)
        else:
            db.add(PlatformCredential(
                user_id=user_id,
                platform=platform,
                username=email,
                password_enc=encrypt(default_password),
                extra=profile_extra,
                notes="Auto-seeded from APEX profile",
                is_active=True,
            ))
            seeded.append(platform)

    db.commit()
    msg = []
    if seeded: msg.append(f"Added: {', '.join(seeded)}")
    if updated: msg.append(f"Updated: {', '.join(updated)}")
    return {"success": True, "seeded": seeded, "updated": updated, "message": " | ".join(msg) or "All credentials already up to date"}
