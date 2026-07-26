from app.schemas.intelligence import SummaryRead, SummaryRequest
from app.services.intelligence import SummaryService


class SummaryAgent:
    """Creates one grounded summary from an explicit source selection."""

    def __init__(self, summaries: SummaryService) -> None:
        self.summaries = summaries

    def run(self, request: SummaryRequest) -> SummaryRead:
        return self.summaries.generate(request)
