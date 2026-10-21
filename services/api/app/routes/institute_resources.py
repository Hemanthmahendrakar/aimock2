"""Institute-scoped campus, company catalog and question-bank APIs."""
import uuid
from flask import Blueprint, request, g
from sqlalchemy import or_
from app.extensions import db
from app.models import RoleName, Campus, Company, QuestionBankQuestion
from app.utils.authorization import require_auth, require_role, require_institute_scope
from app.utils.responses import ok, error

bp = Blueprint("institute_resources", __name__, url_prefix="/api/v1/institute")

def _uuid(value):
    try: return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError): return None

def _payload():
    return request.get_json(silent=True) or {}

def _row(x):
    return {k: (str(getattr(x,k)) if k in ("id","institute_id","company_id") and getattr(x,k) is not None else getattr(x,k)) for k in ("id","institute_id","name","code","location","is_active","website","description","company_id","question","expected_answer_criteria","role","round_type","category","difficulty") if hasattr(x,k)}

# Campus CRUD
@bp.get("/campuses")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_campuses():
    rows = Campus.query.filter_by(institute_id=g.current_institute_id, deleted_at=None).order_by(Campus.name).all()
    return ok([_row(x) for x in rows])

@bp.post("/campuses")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def create_campus():
    p=_payload(); name=str(p.get("name","")).strip()
    if not name or len(name)>180: return error("validation_error","Campus name is required (max 180 characters).",422)
    row=Campus(institute_id=g.current_institute_id,name=name,code=(str(p["code"]).strip() or None) if p.get("code") is not None else None,location=(str(p["location"]).strip() or None) if p.get("location") is not None else None)
    db.session.add(row)
    try: db.session.commit()
    except Exception:
        db.session.rollback(); return error("duplicate_campus","Campus name or code already exists for this institute.",409)
    return ok(_row(row),201)

@bp.patch("/campuses/<campus_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_campus(campus_id):
    ident=_uuid(campus_id); row=Campus.query.filter_by(id=ident,institute_id=g.current_institute_id,deleted_at=None).first() if ident else None
    if row is None: return error("not_found","Campus not found.",404)
    p=_payload()
    for key in ("name","code","location","is_active"):
        if key in p:
            if key=="name" and (not str(p[key]).strip() or len(str(p[key]).strip())>180): return error("validation_error","Invalid campus name.",422)
            setattr(row,key,str(p[key]).strip() if key in ("name","code","location") and p[key] is not None else p[key])
    try: db.session.commit()
    except Exception: db.session.rollback(); return error("duplicate_campus","Campus name or code already exists.",409)
    return ok(_row(row))

@bp.delete("/campuses/<campus_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def delete_campus(campus_id):
    ident=_uuid(campus_id); row=Campus.query.filter_by(id=ident,institute_id=g.current_institute_id,deleted_at=None).first() if ident else None
    if row is None: return error("not_found","Campus not found.",404)
    row.soft_delete(); db.session.commit(); return ok({"message":"Campus deactivated."})

# Company catalog: global entries + tenant-owned entries.
@bp.get("/companies")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_companies():
    rows=Company.query.filter(Company.deleted_at.is_(None),or_(Company.institute_id.is_(None),Company.institute_id==g.current_institute_id)).order_by(Company.name).all()
    return ok([_row(x) for x in rows])

@bp.post("/companies")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def create_company():
    p=_payload(); name=str(p.get("name","")).strip()
    if not name or len(name)>180: return error("validation_error","Company name is required (max 180 characters).",422)
    row=Company(institute_id=g.current_institute_id,name=name,website=p.get("website"),description=p.get("description"))
    db.session.add(row)
    try: db.session.commit()
    except Exception: db.session.rollback(); return error("duplicate_company","Company already exists for this institute.",409)
    return ok(_row(row),201)

# Institute-owned question bank. Never expose another institute's questions.
@bp.get("/question-bank")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def list_questions():
    q=QuestionBankQuestion.query.filter_by(institute_id=g.current_institute_id,deleted_at=None)
    round_type=request.args.get("round_type"); difficulty=request.args.get("difficulty"); company_id=request.args.get("company_id")
    if round_type:
        if round_type not in ("technical","managerial","hr"): return error("validation_error","Invalid round_type.",422)
        q=q.filter_by(round_type=round_type)
    if difficulty:
        if difficulty not in ("easy","medium","hard"): return error("validation_error","Invalid difficulty.",422)
        q=q.filter_by(difficulty=difficulty)
    if company_id:
        ident=_uuid(company_id)
        if ident is None: return error("validation_error","Invalid company_id.",422)
        q=q.filter_by(company_id=ident)
    return ok([_row(x) for x in q.order_by(QuestionBankQuestion.created_at.desc()).limit(500).all()])

@bp.post("/question-bank")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def create_question():
    p=_payload(); question=str(p.get("question","")).strip(); rt=p.get("round_type","technical"); diff=p.get("difficulty","medium")
    if not question or len(question)>10000: return error("validation_error","Question is required (max 10000 characters).",422)
    if rt not in ("technical","managerial","hr") or diff not in ("easy","medium","hard"): return error("validation_error","Invalid round_type or difficulty.",422)
    company_id=None
    if p.get("company_id"):
        company_id=_uuid(p["company_id"]); c=Company.query.filter(Company.id==company_id,Company.deleted_at.is_(None),or_(Company.institute_id.is_(None),Company.institute_id==g.current_institute_id)).first() if company_id else None
        if c is None: return error("invalid_company","Company not found.",422)
    row=QuestionBankQuestion(institute_id=g.current_institute_id,company_id=company_id,question=question,expected_answer_criteria=p.get("expected_answer_criteria"),role=p.get("role"),round_type=rt,category=p.get("category"),difficulty=diff,is_active=bool(p.get("is_active",True)))
    db.session.add(row); db.session.commit(); return ok(_row(row),201)

@bp.patch("/question-bank/<question_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def update_question(question_id):
    ident=_uuid(question_id); row=QuestionBankQuestion.query.filter_by(id=ident,institute_id=g.current_institute_id,deleted_at=None).first() if ident else None
    if row is None: return error("not_found","Question not found.",404)
    p=_payload()
    allowed={"question","expected_answer_criteria","role","category","is_active","round_type","difficulty"}
    for key in allowed.intersection(p): setattr(row,key,p[key])
    if not str(row.question).strip() or row.round_type not in ("technical","managerial","hr") or row.difficulty not in ("easy","medium","hard"): return error("validation_error","Invalid question, round_type, or difficulty.",422)
    db.session.commit(); return ok(_row(row))

@bp.delete("/question-bank/<question_id>")
@require_auth
@require_role(RoleName.INSTITUTE_ADMIN)
@require_institute_scope
def delete_question(question_id):
    ident=_uuid(question_id); row=QuestionBankQuestion.query.filter_by(id=ident,institute_id=g.current_institute_id,deleted_at=None).first() if ident else None
    if row is None: return error("not_found","Question not found.",404)
    row.soft_delete(); db.session.commit(); return ok({"message":"Question archived."})
