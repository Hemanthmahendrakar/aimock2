"""
Business logic for institute profile, branding, and logo management.
Every method here takes an institute_id that MUST have come from
g.current_institute_id (set by require_institute_scope) — this service
does not re-derive or question that value, so the trust boundary lives
entirely in app/utils/authorization.py.
"""
import re
import uuid
from typing import Optional

from app.extensions import db
from app.models import Institute, BrandingField
from app.repositories.institute_repository import InstituteRepository
from app.services.audit_service import AuditService
from app.services.file_storage_service import FileStorageService, FileStorageError
from app.utils.file_validation import validate_upload, FileValidationError


class InstituteServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InstituteNotFound(InstituteServiceError):
    def __init__(self):
        super().__init__("institute_not_found", "Institute not found.", 404)


class InvalidBranding(InstituteServiceError):
    def __init__(self, message: str):
        super().__init__("invalid_branding", message, 422)


_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")


class InstituteService:
    def __init__(self):
        self.institutes = InstituteRepository()
        self.audit = AuditService()

    # ------------------------------------------------------------------
    def _get_or_404(self, institute_id: uuid.UUID) -> Institute:
        institute = self.institutes.get_by_id(institute_id)
        if institute is None:
            raise InstituteNotFound()
        return institute

    def get_profile(self, institute_id: uuid.UUID) -> dict:
        institute = self._get_or_404(institute_id)
        return self._serialize(institute)

    def update_profile(
        self,
        institute_id: uuid.UUID,
        *,
        name: Optional[str] = None,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        website: Optional[str] = None,
    ) -> dict:
        institute = self._get_or_404(institute_id)

        if name is not None:
            institute.name = name
        if phone is not None:
            institute.phone = phone
        if address is not None:
            institute.address = address
        if website is not None:
            institute.website = website

        self.institutes.save(institute)
        self.audit.log(
            event_type="institute.profile_updated",
            institute_id=institute.id,
            metadata={"fields": [k for k, v in {
                "name": name, "phone": phone, "address": address, "website": website,
            }.items() if v is not None]},
        )
        db.session.commit()
        return self._serialize(institute)

    def update_branding(self, institute_id: uuid.UUID, *, branding: dict) -> dict:
        institute = self._get_or_404(institute_id)

        for key in (BrandingField.PRIMARY_COLOR, BrandingField.SECONDARY_COLOR):
            value = branding.get(key)
            if value is not None and not _HEX_COLOR_RE.match(value):
                raise InvalidBranding(f"'{key}' must be a hex color like #1F6F5C.")

        merged = dict(institute.branding_config or {})
        merged.update({k: v for k, v in branding.items() if v is not None})
        institute.branding_config = merged

        self.institutes.save(institute)
        self.audit.log(
            event_type="institute.branding_updated",
            institute_id=institute.id,
            metadata={"keys": list(branding.keys())},
        )
        db.session.commit()
        return self._serialize(institute)

    # ------------------------------------------------------------------
    def upload_logo(self, institute_id: uuid.UUID, *, filename: str, data: bytes) -> dict:
        from flask import current_app

        institute = self._get_or_404(institute_id)

        try:
            content_type = validate_upload(
                data=data,
                max_size_bytes=current_app.config["LOGO_MAX_SIZE_BYTES"],
                allowed_content_types=current_app.config["LOGO_ALLOWED_CONTENT_TYPES"],
            )
        except FileValidationError as exc:
            raise InstituteServiceError("invalid_file", str(exc), 422) from exc

        storage = FileStorageService()
        old_key = institute.logo_url

        new_key = storage.build_object_key(
            prefix=f"institutes/{institute.id}/logo", filename=filename
        )
        try:
            storage.upload_bytes(key=new_key, data=data, content_type=content_type)
        except FileStorageError as exc:
            raise InstituteServiceError("storage_error", str(exc), 502) from exc

        institute.logo_url = new_key
        self.institutes.save(institute)

        if old_key:
            try:
                storage.delete_object(old_key)
            except FileStorageError:
                # Non-fatal: the new logo is already saved and pointed
                # to. An orphaned old object is a cleanup job, not a
                # user-facing failure.
                pass

        self.audit.log(event_type="institute.logo_uploaded", institute_id=institute.id)
        db.session.commit()
        return self._serialize(institute)

    def delete_logo(self, institute_id: uuid.UUID) -> dict:
        institute = self._get_or_404(institute_id)
        old_key = institute.logo_url
        institute.logo_url = None
        self.institutes.save(institute)

        if old_key:
            try:
                FileStorageService().delete_object(old_key)
            except FileStorageError:
                pass

        self.audit.log(event_type="institute.logo_deleted", institute_id=institute.id)
        db.session.commit()
        return self._serialize(institute)

    # ------------------------------------------------------------------
    def _serialize(self, institute: Institute) -> dict:
        logo_signed_url = None
        if institute.logo_url:
            try:
                logo_signed_url = FileStorageService().get_signed_url(institute.logo_url)
            except FileStorageError:
                logo_signed_url = None

        return {
            "id": str(institute.id),
            "name": institute.name,
            "email": institute.email,
            "phone": institute.phone,
            "address": institute.address,
            "website": institute.website,
            "logo_url": logo_signed_url,
            "branding": institute.branding_config or {},
            "status": institute.status,
        }
