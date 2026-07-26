from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import Settings


@dataclass(frozen=True)
class DocumentIndexInput:
    path: Path
    document_id: str
    knowledge_base_id: str
    source_filename: str
    document_type: str


class LangChainDocumentPipeline:
    """Persistent per-knowledge-base loader → splitter → embedding → FAISS pipeline."""

    _lock = Lock()

    def __init__(
        self,
        *,
        index_root: Path,
        embeddings: Any,
        chunk_size: int,
        chunk_overlap: int,
    ) -> None:
        self.index_root = index_root.resolve()
        self.index_root.mkdir(parents=True, exist_ok=True)
        self.embeddings = embeddings
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    @classmethod
    def from_settings(cls, settings: Settings, *, device: str) -> LangChainDocumentPipeline:
        embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model_name,
            cache_folder=str(settings.model_cache_path),
            model_kwargs={
                "device": device,
                "local_files_only": settings.hf_local_files_only,
            },
            encode_kwargs={"normalize_embeddings": True},
        )
        return cls(
            index_root=settings.langchain_index_path,
            embeddings=embeddings,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def load_documents(self, item: DocumentIndexInput) -> list[Document]:
        suffix = item.document_type.lower().lstrip(".")
        if suffix == "pdf":
            loader = PyPDFLoader(str(item.path))
        elif suffix == "txt":
            loader = TextLoader(str(item.path), encoding="utf-8", autodetect_encoding=False)
        elif suffix == "docx":
            loader = Docx2txtLoader(str(item.path))
        else:
            raise ValueError(f"Unsupported LangChain loader type: {item.document_type}")

        loaded = loader.load()
        for section, document in enumerate(loaded):
            page = document.metadata.get("page")
            document.metadata.update(
                {
                    "source": str(item.path),
                    "source_filename": item.source_filename,
                    "document_id": item.document_id,
                    "knowledge_base_id": item.knowledge_base_id,
                    "section": section,
                    "page": int(page) + 1 if isinstance(page, int) and suffix == "pdf" else page,
                }
            )
        return loaded

    def split_documents(self, documents: list[Document]) -> list[Document]:
        chunks = self.splitter.split_documents(documents)
        for chunk_index, chunk in enumerate(chunks):
            start_index = int(chunk.metadata.get("start_index", 0))
            identity = (
                f"{chunk.metadata['knowledge_base_id']}:{chunk.metadata['document_id']}:"
                f"{chunk.metadata.get('section')}:{start_index}:{chunk.page_content}"
            )
            chunk.metadata.update(
                {
                    "chunk_id": hashlib.sha256(identity.encode()).hexdigest(),
                    "chunk_index": chunk_index,
                }
            )
        return chunks

    def create_index(self, item: DocumentIndexInput) -> FAISS:
        chunks = self.split_documents(self.load_documents(item))
        if not chunks:
            raise ValueError("The LangChain document pipeline produced no chunks.")
        ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
        store = FAISS.from_documents(chunks, self.embeddings, ids=ids)
        self._save_index(item.knowledge_base_id, store)
        return store

    def index_document(self, item: DocumentIndexInput, *, replace: bool = True) -> int:
        chunks = self.split_documents(self.load_documents(item))
        if not chunks:
            raise ValueError("The LangChain document pipeline produced no chunks.")
        ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
        with self._lock:
            store = self.load_index(item.knowledge_base_id)
            if store is not None and replace:
                self._delete_from_store(store, item.document_id)
            if store is None or store.index.ntotal == 0:
                store = FAISS.from_documents(chunks, self.embeddings, ids=ids)
            else:
                store.add_documents(chunks, ids=ids)
            self._save_index(item.knowledge_base_id, store)
        return len(chunks)

    def reindex(self, knowledge_base_id: str, items: list[DocumentIndexInput]) -> int:
        if any(item.knowledge_base_id != knowledge_base_id for item in items):
            raise ValueError("All reindex inputs must belong to the target knowledge base.")
        with self._lock:
            self._remove_index_files(knowledge_base_id)
            all_chunks: list[Document] = []
            for item in items:
                all_chunks.extend(self.split_documents(self.load_documents(item)))
            if not all_chunks:
                return 0
            ids = [str(chunk.metadata["chunk_id"]) for chunk in all_chunks]
            store = FAISS.from_documents(all_chunks, self.embeddings, ids=ids)
            self._save_index(knowledge_base_id, store)
            return len(all_chunks)

    def load_index(self, knowledge_base_id: str) -> FAISS | None:
        location = self._index_dir(knowledge_base_id)
        if not (location / "index.faiss").is_file() or not (location / "index.pkl").is_file():
            return None
        # The pickle is generated and loaded only from EnterpriseRAG's private index root.
        return FAISS.load_local(
            str(location),
            self.embeddings,
            allow_dangerous_deserialization=True,
        )

    def delete_document_vectors(self, knowledge_base_id: str, document_id: str) -> int:
        with self._lock:
            store = self.load_index(knowledge_base_id)
            if store is None:
                return 0
            deleted = self._delete_from_store(store, document_id)
            if store.index.ntotal:
                self._save_index(knowledge_base_id, store)
            else:
                self._remove_index_files(knowledge_base_id)
            return deleted

    def retriever(
        self,
        knowledge_base_id: str,
        *,
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> BaseRetriever:
        store = self.load_index(knowledge_base_id)
        if store is None:
            raise FileNotFoundError(
                f"No LangChain FAISS index exists for knowledge base {knowledge_base_id}."
            )
        search_kwargs: dict[str, Any] = {"k": top_k}
        if document_ids:
            search_kwargs["filter"] = {"document_id": {"$in": document_ids}}
        return store.as_retriever(
            search_type="similarity",
            search_kwargs=search_kwargs,
        )

    def retrieve(self, knowledge_base_id: str, query: str, *, top_k: int) -> list[Document]:
        return self.retriever(knowledge_base_id, top_k=top_k).invoke(query)

    @staticmethod
    def _delete_from_store(store: FAISS, document_id: str) -> int:
        ids: list[str] = []
        for store_id in store.index_to_docstore_id.values():
            document = store.docstore.search(store_id)
            if (
                isinstance(document, Document)
                and document.metadata.get("document_id") == document_id
            ):
                ids.append(store_id)
        if ids:
            store.delete(ids)
        return len(ids)

    def _save_index(self, knowledge_base_id: str, store: FAISS) -> None:
        location = self._index_dir(knowledge_base_id)
        location.mkdir(parents=True, exist_ok=True)
        store.save_local(str(location))
        documents: dict[str, dict[str, Any]] = {}
        for store_id in store.index_to_docstore_id.values():
            document = store.docstore.search(store_id)
            if not isinstance(document, Document):
                continue
            document_id = str(document.metadata.get("document_id", ""))
            documents[document_id] = {
                "source_filename": document.metadata.get("source_filename"),
                "knowledge_base_id": knowledge_base_id,
            }
        (location / "manifest.json").write_text(
            json.dumps(
                {
                    "knowledge_base_id": knowledge_base_id,
                    "embedding_class": type(self.embeddings).__name__,
                    "vector_count": int(store.index.ntotal),
                    "documents": documents,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _index_dir(self, knowledge_base_id: str) -> Path:
        if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", knowledge_base_id):
            directory_name = knowledge_base_id
        else:
            directory_name = hashlib.sha256(knowledge_base_id.encode()).hexdigest()
        return self.index_root / directory_name

    def _remove_index_files(self, knowledge_base_id: str) -> None:
        location = self._index_dir(knowledge_base_id)
        if self.index_root not in location.resolve().parents:
            raise ValueError("LangChain index path escaped the configured index root.")
        for filename in ("index.faiss", "index.pkl", "manifest.json"):
            (location / filename).unlink(missing_ok=True)
        if location.is_dir() and not any(location.iterdir()):
            location.rmdir()
