"""Centres & Tests endpoints (admin-manageable catalog)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import CentreTest, DiagnosticCentre, MedicalTest, User
from app.schemas_centres import (
    CentreCreate, CentreDetail, CentreOut, OfferCreate, OfferOut,
    TestCreate, TestOut,
)
from app.types import Id

router = APIRouter(prefix="/centres", tags=["centres"])


@router.post("", response_model=CentreOut, status_code=status.HTTP_201_CREATED)
def create_centre(
    payload: CentreCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),  # auth required — not a public write
) -> DiagnosticCentre:
    centre = DiagnosticCentre(**payload.model_dump())
    db.add(centre)
    db.commit()
    db.refresh(centre)
    return centre


@router.get("", response_model=list[CentreOut])
def list_centres(db: Session = Depends(get_db)) -> list[DiagnosticCentre]:
    """GET is public: browsing the catalog needs no login (good UX).
    Pagination is a bonus feature — todo for later."""
    return list(db.scalars(select(DiagnosticCentre).order_by(DiagnosticCentre.id)))


# ---- tests (flat catalog) ----
# ROUTE ORDER MATTERS: FastAPI matches top-down. "/tests" MUST be declared
# BEFORE "/{centre_id}" — otherwise GET /centres/tests is parsed as
# centre_id="tests" → int() fails → bogus 422. (We hit exactly this bug.)


@router.get("/tests", response_model=list[TestOut], tags=["tests"])
def list_tests(db: Session = Depends(get_db)) -> list[MedicalTest]:
    return list(db.scalars(select(MedicalTest).order_by(MedicalTest.id)))


@router.get("/{centre_id}", response_model=CentreDetail)
def get_centre(centre_id: Id, db: Session = Depends(get_db)) -> CentreDetail:
    """404 on unknown id — returning empty 200 hides client bugs."""
    centre = db.get(DiagnosticCentre, centre_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Centre not found")
    offers = db.scalars(
        select(CentreTest).where(CentreTest.centre_id == centre_id)
    ).all()
    return CentreDetail(
        id=centre.id, name=centre.name, location=centre.location,
        tests=[OfferOut(id=o.id, test_id=o.test_id, centre_id=o.centre_id, price=float(o.price))
               for o in offers],
    )


@router.post("/tests", response_model=TestOut, status_code=201, tags=["tests"])
def create_test(
    payload: TestCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> MedicalTest:
    test = MedicalTest(**payload.model_dump())
    db.add(test)
    db.commit()
    db.refresh(test)
    return test


@router.post("/{centre_id}/tests", response_model=OfferOut, status_code=201, tags=["tests"])
def offer_test(
    centre_id: Id,
    payload: OfferCreate,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> CentreTest:
    """Attach a test to a centre with a price → row in centre_tests."""
    if db.get(DiagnosticCentre, centre_id) is None:
        raise HTTPException(status_code=404, detail="Centre not found")
    if db.get(MedicalTest, payload.test_id) is None:
        raise HTTPException(status_code=404, detail="Test not found")
    offer = CentreTest(centre_id=centre_id, test_id=payload.test_id, price=payload.price)
    db.add(offer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()  # uq_centre_test: same test offered twice → clean 409
        raise HTTPException(status_code=409, detail="Test already offered at this centre")
    db.refresh(offer)
    return offer
