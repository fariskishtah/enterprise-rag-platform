from __future__ import annotations

import re

from app.models.conversation import ChatMessage, ChatRole

FOLLOW_UP_PATTERN = re.compile(
    r"\b(it|its|they|their|them|that|those|this|these|former|latter|"
    r"هو|هي|هم|هذا|هذه|ذلك|تلك|هؤلاء|السابق|اللاحق)\b",
    re.IGNORECASE,
)


class QueryRewriteService:
    """Deterministically resolves conversational references for retrieval."""

    def rewrite(self, question: str, history: list[ChatMessage]) -> str:
        words = question.split()
        needs_context = len(words) <= 7 or bool(FOLLOW_UP_PATTERN.search(question))
        if not needs_context:
            return question
        previous_user = next(
            (message for message in reversed(history) if message.role is ChatRole.USER),
            None,
        )
        if previous_user is None:
            return question
        prior = previous_user.original_question or previous_user.content
        return f"{prior} Follow-up question: {question}"
