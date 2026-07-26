from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_db_session,
    get_file_storage,
)
from app.core.errors import ConflictError, NotFoundError
from app.db.session import session_scope
from app.models.document import DocumentStatus
from app.repositories.documents import DocumentRepository
from app.repositories.knowledge_bases import KnowledgeBaseRepository
from app.schemas.document import (
    DocumentChunkList,
    DocumentChunkRead,
    DocumentExtractionRead,
    DocumentList,
    DocumentPreviewRead,
    DocumentRead,
    ExtractedSectionRead,
)
from app.services.documents import DocumentService
from app.services.processing import DocumentProcessingService
from app.services.storage import LocalFileStorage

router = APIRouter(tags=["documents"])

ACTIVE_PROCESSING_STATUSES = {
    DocumentStatus.VALIDATING,
    DocumentStatus.EXTRACTING,
    DocumentStatus.EXTRACTED,
    DocumentStatus.CHUNKING,
    DocumentStatus.EMBEDDING,
    DocumentStatus.VECTOR_INDEXING,
    DocumentStatus.INDEXED,
}


def run_document_processing(app: FastAPI, document_id: str) -> None:
    session_factory = app.state.session_factory
    with session_scope(session_factory) as session:
        DocumentProcessingService(
            session=session,
            storage=app.state.file_storage,
            settings=app.state.settings,
            embedding_provider=app.state.embedding_provider,
            langchain_pipeline=(
                app.state.langchain_runtime.document_pipeline
                if app.state.langchain_runtime is not None
                else None
            ),
        ).process(document_id)


@router.post(
    "/knowledge-bases/{knowledge_base_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    knowledge_base_id: str,
    file: Annotated[UploadFile, File()],
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
) -> DocumentRead:
    document = await DocumentService(session, storage).upload(knowledge_base_id, file)
    return DocumentRead.model_validate(document)


@router.get("/knowledge-bases/{knowledge_base_id}/documents", response_model=DocumentList)
def list_documents(
    knowledge_base_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentList:
    if KnowledgeBaseRepository(session).get(knowledge_base_id) is None:
        raise NotFoundError("Knowledge base")
    documents = DocumentRepository(session).list_for_knowledge_base(knowledge_base_id)
    items = [DocumentRead.model_validate(document) for document in documents]
    return DocumentList(items=items, total=len(items))


@router.get("/documents/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentRead:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise NotFoundError("Document")
    return DocumentRead.model_validate(document)


@router.get("/documents/{document_id}/content", response_class=FileResponse)
def original_document(
    document_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
) -> FileResponse:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise NotFoundError("Document")
    path = storage.resolve(document.storage_key)
    if not path.is_file():
        raise NotFoundError("Stored document")
    return FileResponse(
        path,
        media_type=document.media_type,
        filename=document.name,
        content_disposition_type="inline",
    )


def queue_processing(
    *,
    request: Request,
    background_tasks: BackgroundTasks,
    document_id: str,
    session: Session,
    retry_only: bool,
) -> DocumentRead:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise NotFoundError("Document")
    if document.status in ACTIVE_PROCESSING_STATUSES:
        raise ConflictError(
            code="processing_already_active",
            message="Document processing is already active.",
        )
    if retry_only and document.status is not DocumentStatus.FAILED:
        raise ConflictError(
            code="document_not_failed",
            message="Only failed documents can use the retry endpoint.",
        )
    document.status = DocumentStatus.VALIDATING
    document.status_message = "Processing has been queued."
    document.processing_error = None
    session.add(document)
    session.commit()
    session.refresh(document)
    response = DocumentRead.model_validate(document)
    background_tasks.add_task(run_document_processing, request.app, document_id)
    return response


@router.post(
    "/documents/{document_id}/process",
    response_model=DocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_processing(
    document_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentRead:
    return queue_processing(
        request=request,
        background_tasks=background_tasks,
        document_id=document_id,
        session=session,
        retry_only=False,
    )


@router.post(
    "/documents/{document_id}/retry",
    response_model=DocumentRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_processing(
    document_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentRead:
    return queue_processing(
        request=request,
        background_tasks=background_tasks,
        document_id=document_id,
        session=session,
        retry_only=True,
    )


@router.get("/documents/{document_id}/processing", response_model=DocumentRead)
def processing_status(
    document_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentRead:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise NotFoundError("Document")
    return DocumentRead.model_validate(document)


@router.get(
    "/documents/{document_id}/extraction",
    response_model=DocumentExtractionRead,
)
def extraction_details(
    document_id: str,
    session: Annotated[Session, Depends(get_db_session)],
) -> DocumentExtractionRead:
    repository = DocumentRepository(session)
    document = repository.get(document_id)
    if document is None:
        raise NotFoundError("Document")
    return DocumentExtractionRead(
        document_id=document.id,
        filename=document.name,
        document_type=document.document_type,
        status=document.status,
        page_count=document.page_count,
        character_count=document.character_count,
        extraction_completed_at=document.extraction_completed_at,
        warnings=document.extraction_warnings,
        error=document.processing_error,
        metadata=document.extraction_metadata,
        sections=[
            ExtractedSectionRead.model_validate(section)
            for section in repository.list_sections(document_id)
        ],
    )


@router.get("/documents/{document_id}/preview", response_model=DocumentPreviewRead)
def extracted_preview(
    document_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=20000)] = 5000,
) -> DocumentPreviewRead:
    document = DocumentRepository(session).get(document_id)
    if document is None:
        raise NotFoundError("Document")
    full_text = document.extracted_text or ""
    text = full_text[offset : offset + limit]
    return DocumentPreviewRead(
        document_id=document.id,
        text=text,
        offset=offset,
        returned_characters=len(text),
        total_characters=len(full_text),
        truncated=offset + len(text) < len(full_text),
    )


@router.get("/documents/{document_id}/chunks", response_model=DocumentChunkList)
def list_chunks(
    document_id: str,
    session: Annotated[Session, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> DocumentChunkList:
    repository = DocumentRepository(session)
    document = repository.get(document_id)
    if document is None:
        raise NotFoundError("Document")
    chunks = repository.list_chunks(document_id, offset=(page - 1) * page_size, limit=page_size)
    return DocumentChunkList(
        items=[DocumentChunkRead.model_validate(chunk) for chunk in chunks],
        page=page,
        page_size=page_size,
        total=document.chunk_count,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
    storage: Annotated[LocalFileStorage, Depends(get_file_storage)],
) -> None:
    DocumentService(
        session,
        storage,
        langchain_pipeline=(
            request.app.state.langchain_runtime.document_pipeline
            if request.app.state.langchain_runtime is not None
            else None
        ),
    ).delete(document_id)
