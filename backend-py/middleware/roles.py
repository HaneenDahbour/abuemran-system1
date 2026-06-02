from fastapi import HTTPException


def require_role(user, *roles):
    if not user or user.get("role") not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"هذه الصفحة للـ {' / '.join(roles)} فقط — ليس لديك صلاحية"
        )