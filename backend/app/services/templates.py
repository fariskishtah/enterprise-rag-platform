"""Action Template Library service providing structured enterprise AI workflows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionTemplate:
    id: str
    title: str
    description: str
    category: str  # HR, Contracts, Meetings, Study, Analysis
    prompt_instruction: str
    supported_source_types: list[str]
    output_schema_type: str
    safety_classification: str
    icon_name: str


TEMPLATES: list[ActionTemplate] = [
    ActionTemplate(
        id="executive_summary",
        title="Executive Summary",
        description="Write a high-level executive summary tailored for decision-makers.",
        category="Analysis",
        prompt_instruction=(
            "Write an executive summary: context, key findings, strategic implications, and risks."
        ),
        supported_source_types=["pdf", "docx", "txt"],
        output_schema_type="prose",
        safety_classification="safe",
        icon_name="FileText",
    ),
    ActionTemplate(
        id="extract_key_facts",
        title="Extract Key Facts",
        description="Extract bulleted list of essential factual claims backed by citations.",
        category="Analysis",
        prompt_instruction=(
            "Extract key facts as a Markdown bullet list. "
            "Every claim must have a [SOURCE:id] marker."
        ),
        supported_source_types=["pdf", "docx", "txt", "media"],
        output_schema_type="bullet_list",
        safety_classification="safe",
        icon_name="CheckSquare",
    ),
    ActionTemplate(
        id="extract_risks",
        title="Identify Risks & Liabilities",
        description="Identify contractual or operational risks stated in the documents.",
        category="Contracts",
        prompt_instruction="Identify all stated risks, liabilities, penalties, or compliance gaps.",
        supported_source_types=["pdf", "docx"],
        output_schema_type="bullet_list",
        safety_classification="safe",
        icon_name="AlertTriangle",
    ),
    ActionTemplate(
        id="extract_obligations",
        title="Extract Contract Obligations",
        description="List all explicit obligations, SLAs, and party responsibilities.",
        category="Contracts",
        prompt_instruction="List all legal and operational obligations for each party.",
        supported_source_types=["pdf", "docx"],
        output_schema_type="structured_table",
        safety_classification="safe",
        icon_name="ShieldCheck",
    ),
    ActionTemplate(
        id="extract_dates",
        title="Key Dates & Deadlines",
        description="Extract dates, deadlines, renewal windows, and milestones.",
        category="Contracts",
        prompt_instruction="Extract all dates, deadlines, and milestones chronologically.",
        supported_source_types=["pdf", "docx", "txt"],
        output_schema_type="bullet_list",
        safety_classification="safe",
        icon_name="Calendar",
    ),
    ActionTemplate(
        id="compare_policies",
        title="Compare Policies",
        description="Compare two policy documents across themes, differences, and gaps.",
        category="Analysis",
        prompt_instruction=(
            "Compare documents across common themes, differences, contradictions, and limitations."
        ),
        supported_source_types=["pdf", "docx", "txt"],
        output_schema_type="comparison_sections",
        safety_classification="safe",
        icon_name="GitCompare",
    ),
    ActionTemplate(
        id="study_notes",
        title="Generate Study Notes",
        description=(
            "Convert technical documents or lecture transcripts into structured revision notes."
        ),
        category="Study",
        prompt_instruction=(
            "Generate comprehensive study notes: main concepts, formulas/definitions, summary."
        ),
        supported_source_types=["pdf", "docx", "txt", "media"],
        output_schema_type="prose",
        safety_classification="safe",
        icon_name="BookOpen",
    ),
    ActionTemplate(
        id="quiz_generator",
        title="Generate Practice Quiz",
        description=(
            "Generate multiple-choice practice questions with answer keys based on sources."
        ),
        category="Study",
        prompt_instruction=(
            "Generate 5 multiple-choice questions with answer keys based on source context."
        ),
        supported_source_types=["pdf", "docx", "txt", "media"],
        output_schema_type="quiz_json",
        safety_classification="safe",
        icon_name="HelpCircle",
    ),
    ActionTemplate(
        id="create_glossary",
        title="Create Terminology Glossary",
        description="Build a dictionary of specialized terms, abbreviations, and definitions.",
        category="Study",
        prompt_instruction=(
            "List all specialized terms, acronyms, and definitions found in the context."
        ),
        supported_source_types=["pdf", "docx", "txt"],
        output_schema_type="glossary_table",
        safety_classification="safe",
        icon_name="List",
    ),
    ActionTemplate(
        id="meeting_minutes",
        title="Meeting Minutes & Action Items",
        description=(
            "Extract decisions, action items, owners, and deadlines from meeting transcripts."
        ),
        category="Meetings",
        prompt_instruction=(
            "Summarize meeting discussion, key decisions, and action items with owners."
        ),
        supported_source_types=["media"],
        output_schema_type="structured_minutes",
        safety_classification="safe",
        icon_name="Video",
    ),
    ActionTemplate(
        id="analyse_cv",
        title="Analyse CV & Candidate Profile",
        description=(
            "Extract candidate skills, years of experience, and compare to job requirements."
        ),
        category="HR",
        prompt_instruction=(
            "Analyse CV: technical skills, work history, key achievements, and candidate summary."
        ),
        supported_source_types=["pdf", "docx"],
        output_schema_type="candidate_profile",
        safety_classification="safe",
        icon_name="UserCheck",
    ),
    ActionTemplate(
        id="extract_tables",
        title="Extract Data Tables",
        description="Find and summarize numerical data tables in source documents.",
        category="Analysis",
        prompt_instruction="Summarize all data tables found in the context as Markdown tables.",
        supported_source_types=["pdf", "docx"],
        output_schema_type="markdown_tables",
        safety_classification="safe",
        icon_name="Grid",
    ),
    ActionTemplate(
        id="missing_info",
        title="Identify Missing Information",
        description="Identify gaps, missing evidence, or unanswered questions in documents.",
        category="Analysis",
        prompt_instruction=(
            "Identify what required information, evidence, or data is missing from these sources."
        ),
        supported_source_types=["pdf", "docx", "txt"],
        output_schema_type="bullet_list",
        safety_classification="safe",
        icon_name="HelpCircle",
    ),
]


class TemplateService:
    def list_templates(self) -> list[ActionTemplate]:
        return TEMPLATES

    def get_template(self, template_id: str) -> ActionTemplate | None:
        for template in TEMPLATES:
            if template.id == template_id:
                return template
        return None
