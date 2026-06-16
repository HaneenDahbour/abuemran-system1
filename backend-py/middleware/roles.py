from fastapi import HTTPException


def require_role(user, *roles):
    if not user or user.get("role") not in roles:
        raise HTTPException(
            status_code=403,
            detail=f"هذه الصفحة للـ {' / '.join(roles)} فقط — ليس لديك صلاحية",
        )


def require_permission(user, section):
    """تحقق من صلاحية المستخدم للوصول إلى قسم معين.
    admin: مسموح دائماً.
    permissions = NULL: مسموح (غير محدود — توافق مع الحسابات القديمة).
    permissions = قائمة: يجب أن تحتوي على section.
    """
    if not user:
        raise HTTPException(status_code=403, detail="غير مسموح")
    if user.get("role") == "admin":
        return
    permissions = user.get("permissions")
    if permissions is None:
        return
    if section not in permissions:
        raise HTTPException(status_code=403, detail="ليس لديك صلاحية الوصول لهذا القسم")
