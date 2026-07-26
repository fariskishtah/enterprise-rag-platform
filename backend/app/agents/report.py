from app.schemas.intelligence import ReportRequest, ResearchReportRead
from app.services.intelligence import ReportService


class ReportAgent:
    """Runs deterministic context selection, analysis, verification, and formatting."""

    def __init__(self, reports: ReportService) -> None:
        self.reports = reports

    def run(self, request: ReportRequest) -> ResearchReportRead:
        return self.reports.create(request)
