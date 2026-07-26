from app.ai.vectorstores.base import VectorSearchResult
from app.schemas.rag import VerificationRead
from app.services.verification import VerificationService


class VerificationAgent:
    """Checks answer support against the exact passages used for generation."""

    def __init__(self, verification: VerificationService | None = None) -> None:
        self.verification = verification or VerificationService()

    def run(self, answer: str, sources: list[VectorSearchResult]) -> VerificationRead:
        return self.verification.verify(answer, sources)
