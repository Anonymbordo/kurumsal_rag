"""Kimlik.

Geliştirme aşamasında kullanıcı `X-User-Id` başlığıyla seçilir. Kurum kurulumunda
bu bağımlılık LDAP / Active Directory ya da SSO (OIDC/SAML) ile değiştirilecek;
uygulamanın geri kalanı yalnızca `current_user` ile çalıştığı için başka değişiklik gerekmez.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import User


def current_user(x_user_id: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    if x_user_id:
        user = db.get(User, x_user_id)
        if user is None:
            raise HTTPException(401, "Kullanıcı bulunamadı")
        return user
    user = db.scalar(select(User).where(User.is_lead.is_(False)).order_by(User.id))
    if user is None:
        raise HTTPException(401, "Kayıtlı kullanıcı yok")
    return user


def require_lead(user: User = Depends(current_user)) -> User:
    if not user.is_lead:
        raise HTTPException(403, "Bu işlem yalnızca takım liderlerine açık")
    return user
