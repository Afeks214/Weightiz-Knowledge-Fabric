from enum import StrEnum

from pydantic import BaseModel


class SourceStatus(StrEnum):
    ALLOWED = "ALLOWED"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    METADATA_ONLY = "METADATA_ONLY"
    BLOCKED = "BLOCKED"
    UNKNOWN_REQUIRES_REVIEW = "UNKNOWN_REQUIRES_REVIEW"
    ABSTAINED = "ABSTAINED"


class SourceRecord(BaseModel):
    source_key: str
    source_type: str
    title: str
    homepage_url: str | None = None
    rights_policy: str
    license_configured: bool = False
    authorized_transcript: bool = False
    authorized_audio: bool = False


class RightsDecision(BaseModel):
    status: SourceStatus
    full_text_allowed: bool
    raw_export_allowed: bool
    reason: str


class RightsGate:
    def evaluate(self, record: SourceRecord) -> RightsDecision:
        url = (record.homepage_url or "").casefold()
        if "youtube.com" in url or "youtu.be" in url:
            if not record.authorized_transcript and not record.authorized_audio:
                return RightsDecision(
                    status=SourceStatus.ABSTAINED,
                    full_text_allowed=False,
                    raw_export_allowed=False,
                    reason="YouTube source lacks authorized transcript or audio access.",
                )

        if (
            record.rights_policy == "metadata_only_unless_licensed"
            and not record.license_configured
        ):
            return RightsDecision(
                status=SourceStatus.METADATA_ONLY,
                full_text_allowed=False,
                raw_export_allowed=False,
                reason="Full text requires an explicit license configuration.",
            )

        if record.rights_policy == "open_academic_metadata_api":
            return RightsDecision(
                status=SourceStatus.METADATA_ONLY,
                full_text_allowed=False,
                raw_export_allowed=False,
                reason=(
                    "Academic API metadata is allowed; full text requires "
                    "record-level open-access evidence."
                ),
            )

        if record.rights_policy == "blocked_without_authorization":
            if (
                record.authorized_transcript
                or record.authorized_audio
                or record.license_configured
            ):
                return RightsDecision(
                    status=SourceStatus.ALLOWED,
                    full_text_allowed=True,
                    raw_export_allowed=False,
                    reason="Authorized source material is configured.",
                )
            return RightsDecision(
                status=SourceStatus.ABSTAINED,
                full_text_allowed=False,
                raw_export_allowed=False,
                reason="Source requires authorization before ingestion.",
            )

        if record.rights_policy in {
            "official_public_research_private",
            "private_research_only",
        }:
            return RightsDecision(
                status=SourceStatus.ALLOWED,
                full_text_allowed=True,
                raw_export_allowed=False,
                reason="Allowed for private research with raw export disabled.",
            )

        return RightsDecision(
            status=SourceStatus.UNKNOWN_REQUIRES_REVIEW,
            full_text_allowed=False,
            raw_export_allowed=False,
            reason="Unknown rights policy requires manual review.",
        )
