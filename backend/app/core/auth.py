import os
import logging
import httpx
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text
from core.database import get_db

load_dotenv(Path(__file__).parent.parent / ".env")

TENANT_ID = os.getenv("AZURE_TENANT_ID")
CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
JWKS_URI = f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"

bearer_scheme = HTTPBearer()
logger = logging.getLogger(__name__)

_jwks_cache: dict | None = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get(JWKS_URI)
        resp.raise_for_status()
        _jwks_cache = resp.json()
    return _jwks_cache


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    token = credentials.credentials
    try:
        jwks = await _get_jwks()
        header = jwt.get_unverified_header(token)
        key = next(
            (k for k in jwks["keys"] if k["kid"] == header["kid"]),
            None,
        )
        if key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증 키를 찾을 수 없습니다.")

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=f"api://{CLIENT_ID}",
        )

        try:
            db.execute(
                text("""
                    INSERT INTO users (user_id, email, display_name, last_login_at)
                    VALUES (:user_id, :email, :display_name, :last_login_at)
                    ON DUPLICATE KEY UPDATE
                        email = VALUES(email),
                        display_name = VALUES(display_name),
                        last_login_at = VALUES(last_login_at)
                """),
                {
                    "user_id": payload.get("oid"),
                    "email": payload.get("preferred_username") or payload.get("upn"),
                    "display_name": payload.get("name"),
                    "last_login_at": datetime.now(),
                }
            )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning("users upsert 실패 (비치명적): %s", e)

        row = db.execute(
            text("SELECT role FROM users WHERE user_id = :user_id"),
            {"user_id": payload.get("oid")}
        ).fetchone()
        payload["db_role"] = row.role if row else "member"

        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"토큰 검증 실패: {str(e)}",
        )
    
async def verify_admin(
    token: dict = Depends(verify_token),
) -> dict:
    if token.get("db_role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다."
        )
    return token