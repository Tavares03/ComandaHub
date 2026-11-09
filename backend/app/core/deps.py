from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models.establishment import Establishment
from app.models.user import EstablishmentMembership, User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> User:
    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem usuario")
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inativo ou inexistente")
    return user


def require_establishment_access(
    establishment_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[Establishment, EstablishmentMembership]:
    membership = db.scalar(
        select(EstablishmentMembership).where(
            EstablishmentMembership.user_id == current_user.id,
            EstablishmentMembership.establishment_id == establishment_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este estabelecimento")
    establishment = db.get(Establishment, establishment_id)
    if not establishment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estabelecimento nao encontrado")
    return establishment, membership


def require_roles(membership: EstablishmentMembership, roles: set[UserRole]) -> None:
    if membership.role not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permissao insuficiente")


Access = tuple[Establishment, EstablishmentMembership]

STAFF_ROLES = frozenset({UserRole.ADMIN, UserRole.ATTENDANT})


def require_role(*roles: UserRole):
    """Dependencia: acesso a loja + um dos perfis. Uso: ``access=Depends(staff_access)``."""
    allowed = set(roles)

    def dependency(access: Annotated[Access, Depends(require_establishment_access)]) -> Access:
        require_roles(access[1], allowed)
        return access

    return dependency


# Atendimento e gerencia (cozinha fica de fora: dados de clientes, caixa e vendas)
staff_access = require_role(*STAFF_ROLES)
# So gerencia: relatorios financeiros, usuarios e configuracoes da loja
admin_access = require_role(UserRole.ADMIN)
