from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from langchain_core.documents import Document
from langchain_core.exceptions import OutputParserException
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable, RunnableLambda, RunnablePassthrough
from pydantic import BaseModel

from app.ai.langchain_engine.prompts import (
    COMPARISON_PROMPT,
    GROUNDED_QA_PROMPT,
    PARSER_REPAIR_PROMPT,
    QUERY_REWRITE_PROMPT,
    REPORT_PROMPT,
    SUMMARY_PROMPT,
    UNTRUSTED_CONTEXT_RULES,
    VERIFICATION_PROMPT,
)
from app.ai.langchain_engine.schemas import (
    ComparisonResult,
    GroundedAnswer,
    QueryRewriteResult,
    ReportResult,
    SummaryResult,
    VerificationResult,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def format_documents(documents: list[Document]) -> str:
    blocks: list[str] = []
    for document in documents:
        metadata = document.metadata
        blocks.append(
            "\n".join(
                [
                    f"[BEGIN_UNTRUSTED_SOURCE {metadata.get('chunk_id', 'unknown')}]",
                    f"document_id: {metadata.get('document_id', '')}",
                    f"source_filename: {metadata.get('source_filename', '')}",
                    f"page: {metadata.get('page')}",
                    f"section: {metadata.get('section')}",
                    document.page_content,
                    "[END_UNTRUSTED_SOURCE]",
                ]
            )
        )
    return "\n\n".join(blocks)


@dataclass
class ParsedLCELChain(Generic[SchemaT]):
    """Direct prompt | llm | PydanticOutputParser chain with bounded repair retries."""

    parser: PydanticOutputParser[SchemaT]
    primary: Runnable[Any, SchemaT]
    repair: Runnable[Any, SchemaT]
    retries: int

    def invoke(self, values: dict[str, Any]) -> SchemaT:
        try:
            return self.primary.invoke(values)
        except OutputParserException as exc:
            last_error: OutputParserException = exc
            bad_output = exc.llm_output or ""
            for _ in range(self.retries):
                try:
                    return self.repair.invoke(
                        {
                            "bad_output": bad_output,
                            "error": str(last_error),
                        }
                    )
                except OutputParserException as repair_error:
                    last_error = repair_error
                    bad_output = repair_error.llm_output or bad_output
            raise last_error from exc

    def as_runnable(self) -> RunnableLambda[dict[str, Any], SchemaT]:
        return RunnableLambda(self.invoke)


def structured_chain(
    prompt: Any,
    llm: Runnable[Any, Any],
    schema: type[SchemaT],
    *,
    retries: int,
) -> ParsedLCELChain[SchemaT]:
    parser: PydanticOutputParser[SchemaT] = PydanticOutputParser(pydantic_object=schema)
    format_instructions = parser.get_format_instructions()
    partial_values = {"format_instructions": format_instructions}
    if "untrusted_context_rules" in prompt.input_variables:
        partial_values["untrusted_context_rules"] = UNTRUSTED_CONTEXT_RULES
    primary = prompt.partial(**partial_values) | llm | parser
    repair = (
        PARSER_REPAIR_PROMPT.partial(
            format_instructions=format_instructions,
        )
        | llm
        | parser
    )
    return ParsedLCELChain(parser=parser, primary=primary, repair=repair, retries=retries)


class CourseChainSuite:
    """Required LangChain structured chains and their composed LCEL orchestration."""

    def __init__(
        self,
        *,
        llm: Runnable[Any, Any],
        retriever: Runnable[Any, list[Document]],
        parser_retries: int = 1,
    ) -> None:
        self.query_rewrite = structured_chain(
            QUERY_REWRITE_PROMPT,
            llm,
            QueryRewriteResult,
            retries=parser_retries,
        )
        self.answer = structured_chain(
            GROUNDED_QA_PROMPT,
            llm,
            GroundedAnswer,
            retries=parser_retries,
        )
        self.verification = structured_chain(
            VERIFICATION_PROMPT,
            llm,
            VerificationResult,
            retries=parser_retries,
        )
        self.summary = structured_chain(
            SUMMARY_PROMPT,
            llm,
            SummaryResult,
            retries=parser_retries,
        )
        self.comparison = structured_chain(
            COMPARISON_PROMPT,
            llm,
            ComparisonResult,
            retries=parser_retries,
        )
        self.report = structured_chain(
            REPORT_PROMPT,
            llm,
            ReportResult,
            retries=parser_retries,
        )

        self.query_rewrite_chain = self.query_rewrite.as_runnable()
        self.retrieval_chain = (
            RunnableLambda(
                lambda value: (
                    value.standalone_query if isinstance(value, QueryRewriteResult) else str(value)
                )
            )
            | retriever
        )
        self.answer_chain = self.answer.as_runnable()
        self.verification_chain = self.verification.as_runnable()
        self.report_chain = self.report.as_runnable()

        self.orchestration_chain = (
            RunnablePassthrough.assign(rewrite=self.query_rewrite_chain)
            | RunnablePassthrough.assign(
                documents=RunnableLambda(lambda state: state["rewrite"]) | self.retrieval_chain
            )
            | RunnablePassthrough.assign(
                answer=RunnableLambda(self._answer_values) | self.answer_chain
            )
            | RunnablePassthrough.assign(
                verification=RunnableLambda(self._verification_values) | self.verification_chain
            )
        )

    @staticmethod
    def _answer_values(state: dict[str, Any]) -> dict[str, Any]:
        rewrite: QueryRewriteResult = state["rewrite"]
        documents: list[Document] = state["documents"]
        return {
            "question": f"{state['question']}\n\n{state['answer_language_instruction']}",
            "standalone_query": rewrite.standalone_query,
            "context": format_documents(documents),
        }

    @staticmethod
    def _verification_values(state: dict[str, Any]) -> dict[str, Any]:
        answer: GroundedAnswer = state["answer"]
        return {
            "answer": answer.answer,
            "context": format_documents(state["documents"]),
        }

    def invoke(
        self,
        *,
        question: str,
        conversation_history: str = "",
        answer_language_instruction: str = "Answer in English.",
    ) -> dict[str, Any]:
        return self.orchestration_chain.invoke(
            {
                "question": question,
                "conversation_history": conversation_history or "No previous conversation.",
                "answer_language_instruction": answer_language_instruction,
            }
        )

    def summarize(self, documents: list[Document]) -> SummaryResult:
        return self.summary.as_runnable().invoke({"context": format_documents(documents)})

    def compare(self, question: str, documents: list[Document]) -> ComparisonResult:
        return self.comparison.as_runnable().invoke(
            {"question": question, "context": format_documents(documents)}
        )

    def create_report(self, question: str, documents: list[Document]) -> ReportResult:
        return self.report_chain.invoke(
            {"question": question, "context": format_documents(documents)}
        )
