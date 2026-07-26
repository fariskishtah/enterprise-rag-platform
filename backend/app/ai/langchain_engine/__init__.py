"""Optional LangChain course engine.

The custom EnterpriseRAG services remain the default production engine. This package
contains direct course-library integrations selected with ``RAG_ENGINE=langchain``.
"""

from app.ai.langchain_engine.chains import CourseChainSuite
from app.ai.langchain_engine.document_pipeline import LangChainDocumentPipeline
from app.ai.langchain_engine.llm import EnterpriseGenerationLLM

__all__ = [
    "CourseChainSuite",
    "EnterpriseGenerationLLM",
    "LangChainDocumentPipeline",
]
