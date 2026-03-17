from fastapi import APIRouter, HTTPException

from app.core.validation import validate_uuid
from app.core.audit import log_audit
from app.services.store import student_export, student_delete

router = APIRouter()


@router.post("/export-data")
async def export_user_data(user_id: str):
    """GDPR: export all data we hold for the user (student_id)."""
    err = validate_uuid(user_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    data = student_export(user_id)
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(user_id, "export_data", "student", user_id, {"exported": True})
    return data


@router.delete("/delete-data")
async def delete_user_data(user_id: str):
    """GDPR: delete all data for the user (student_id)."""
    err = validate_uuid(user_id)
    if err:
        raise HTTPException(status_code=400, detail=err)
    deleted = student_delete(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    log_audit(user_id, "delete_data", "student", user_id, {"deleted": True})
    return {"message": "User data deleted"}
