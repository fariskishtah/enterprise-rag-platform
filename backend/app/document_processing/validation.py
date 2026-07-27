import zipfile
from pathlib import Path

from app.core.errors import UploadValidationError
from app.models.document import DocumentType

ALLOWED_EXTENSIONS: dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".txt": DocumentType.TXT,
    ".docx": DocumentType.DOCX,
}

CANONICAL_MEDIA_TYPES: dict[DocumentType, str] = {
    DocumentType.PDF: "application/pdf",
    DocumentType.TXT: "text/plain",
    DocumentType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_DECLARED_MEDIA_TYPES: dict[DocumentType, set[str]] = {
    DocumentType.PDF: {"application/pdf", "application/octet-stream"},
    DocumentType.TXT: {"text/plain", "application/octet-stream"},
    DocumentType.DOCX: {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}

MAX_DOCX_MEMBERS = 5000
MAX_DOCX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 200


def safe_display_filename(filename: str) -> str:
    value = Path(filename).name.strip()
    if not value or len(value) > 255 or any(ord(character) < 32 for character in value):
        raise UploadValidationError(
            code="unsafe_filename",
            message="The uploaded filename is missing or contains unsafe characters.",
        )
    return value


def document_type_for_filename(filename: str) -> DocumentType:
    extension = Path(filename).suffix.lower()
    document_type = ALLOWED_EXTENSIONS.get(extension)
    if document_type is None:
        raise UploadValidationError(
            code="unsupported_document_type",
            message="Only PDF, TXT, and DOCX documents are supported.",
            status_code=415,
        )
    return document_type


def validate_declared_media_type(media_type: str | None, document_type: DocumentType) -> None:
    declared = (media_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if declared not in ALLOWED_DECLARED_MEDIA_TYPES[document_type]:
        raise UploadValidationError(
            code="unsupported_document_media_type",
            message="The declared document media type is not supported.",
            status_code=415,
        )


def validate_file_content(path: Path, document_type: DocumentType) -> None:
    if document_type is DocumentType.PDF:
        if not path.read_bytes()[:5] == b"%PDF-":
            raise UploadValidationError(
                code="invalid_pdf", message="The uploaded file is not a valid PDF document."
            )
        return

    if document_type is DocumentType.TXT:
        content = path.read_bytes()
        if b"\x00" in content:
            raise UploadValidationError(
                code="invalid_text_file", message="The text document contains binary data."
            )
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise UploadValidationError(
                code="invalid_text_encoding",
                message="Text documents must use UTF-8 encoding.",
            ) from exc
        return

    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_MEMBERS:
                raise UploadValidationError(
                    code="unsafe_docx_archive",
                    message="The DOCX archive contains too many internal files.",
                )
            total_size = sum(member.file_size for member in members)
            compressed_size = max(1, sum(member.compress_size for member in members))
            if (
                total_size > MAX_DOCX_UNCOMPRESSED_BYTES
                or total_size / compressed_size > MAX_DOCX_COMPRESSION_RATIO
            ):
                raise UploadValidationError(
                    code="unsafe_docx_archive",
                    message="The DOCX archive expands beyond the safe processing limit.",
                )
            names = {member.filename for member in members}
            if any(
                Path(name).is_absolute() or ".." in Path(name).parts
                for name in names
            ):
                raise UploadValidationError(
                    code="unsafe_docx_archive",
                    message="The DOCX archive contains an unsafe internal path.",
                )
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise UploadValidationError(
                    code="invalid_docx", message="The uploaded file is not a valid DOCX document."
                )
    except zipfile.BadZipFile as exc:
        raise UploadValidationError(
            code="invalid_docx", message="The uploaded file is not a valid DOCX document."
        ) from exc
