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
            names = set(archive.namelist())
            required = {"[Content_Types].xml", "word/document.xml"}
            if not required.issubset(names):
                raise UploadValidationError(
                    code="invalid_docx", message="The uploaded file is not a valid DOCX document."
                )
    except zipfile.BadZipFile as exc:
        raise UploadValidationError(
            code="invalid_docx", message="The uploaded file is not a valid DOCX document."
        ) from exc
