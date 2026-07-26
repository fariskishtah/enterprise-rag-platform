import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import UploadValidationError
from app.document_processing.validation import validate_file_content
from app.models.document import DocumentType


@dataclass(frozen=True)
class StoredUpload:
    storage_key: str
    size_bytes: int
    checksum_sha256: str


class LocalFileStorage:
    """Filesystem storage behind a small interface that can be replaced later."""

    chunk_size = 1024 * 1024

    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        self.root = root.resolve()
        self.max_upload_bytes = max_upload_bytes

    async def save(
        self,
        *,
        upload: UploadFile,
        knowledge_base_id: str,
        document_id: str,
        document_type: DocumentType,
    ) -> StoredUpload:
        relative_key = Path(knowledge_base_id) / f"{document_id}.{document_type.value}"
        destination = self.root / relative_key
        temporary = destination.with_suffix(destination.suffix + ".uploading")
        destination.parent.mkdir(parents=True, exist_ok=True)

        size = 0
        digest = hashlib.sha256()
        try:
            with temporary.open("xb") as output:
                while chunk := await upload.read(self.chunk_size):
                    size += len(chunk)
                    if size > self.max_upload_bytes:
                        raise UploadValidationError(
                            code="upload_too_large",
                            message=f"Documents may not exceed {self.max_upload_bytes} bytes.",
                            status_code=413,
                        )
                    digest.update(chunk)
                    output.write(chunk)

            if size == 0:
                raise UploadValidationError(
                    code="empty_document", message="The uploaded document is empty."
                )
            validate_file_content(temporary, document_type)
            os.replace(temporary, destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        return StoredUpload(
            storage_key=relative_key.as_posix(),
            size_bytes=size,
            checksum_sha256=digest.hexdigest(),
        )

    def delete(self, storage_key: str) -> None:
        candidate = (self.root / storage_key).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Storage key resolves outside the configured storage root.")
        candidate.unlink(missing_ok=True)

    def resolve(self, storage_key: str) -> Path:
        candidate = (self.root / storage_key).resolve()
        if self.root not in candidate.parents:
            raise ValueError("Storage key resolves outside the configured storage root.")
        return candidate
