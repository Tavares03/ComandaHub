from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.rate_limit import client_ip, limiter, too_many
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.establishment import Establishment
from app.models.user import EstablishmentMembership, User
from app.schemas.auth import AuthUser, EstablishmentSummary, LoginRequest, PasswordChange, TokenResponse, UserOut
from app.services.auth_service import authenticate_user

router = APIRouter()

# Forca bruta: 5 erros seguidos no mesmo e-mail (por IP) ou 20 erros vindos do mesmo IP em 5 minutos
LOGIN_WINDOW_SECONDS = 300
LOGIN_FAILURES_PER_ACCOUNT = 5
LOGIN_FAILURES_PER_IP = 20


def serialize_user(db: Session, user: User) -> AuthUser:
    rows = db.execute(
        select(Establishment, EstablishmentMembership.role)
        .join(EstablishmentMembership, EstablishmentMembership.establishment_id == Establishment.id)
        .where(EstablishmentMembership.user_id == user.id)
        .order_by(Establishment.name)
    ).all()
    establishments = [EstablishmentSummary(id=est.id, name=est.name, role=role) for est, role in rows]
    return AuthUser.model_validate(UserOut.model_validate(user).model_dump() | {"establishments": establishments})


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    ip = client_ip(request)
    account_key = f"login:{ip}:{payload.email}"
    ip_key = f"login-ip:{ip}"
    if not (
        limiter.allowed(account_key, LOGIN_FAILURES_PER_ACCOUNT, LOGIN_WINDOW_SECONDS)
        and limiter.allowed(ip_key, LOGIN_FAILURES_PER_IP, LOGIN_WINDOW_SECONDS)
    ):
        raise too_many(LOGIN_WINDOW_SECONDS, "Muitas tentativas de login. Aguarde alguns minutos.")

    user = authenticate_user(db, payload.email, payload.password)
    if not user:
        limiter.hit(account_key, LOGIN_FAILURES_PER_ACCOUNT, LOGIN_WINDOW_SECONDS)
        limiter.hit(ip_key, LOGIN_FAILURES_PER_IP, LOGIN_WINDOW_SECONDS)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha invalidos")
    limiter.reset(account_key)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=serialize_user(db, user))


@router.get("/me", response_model=AuthUser)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthUser:
    return serialize_user(db, current_user)


@router.post("/me/password", status_code=204)
def change_my_password(
    payload: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=422, detail="Senha atual incorreta")
    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return Response(status_code=204)
