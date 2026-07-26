"""Action Template Library API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.templates import TemplateService

router = APIRouter(prefix="/templates", tags=["templates"])


class ActionTemplateRead(BaseModel):
    id: str
    title: str
    description: str
    category: str
    prompt_instruction: str
    supported_source_types: list[str]
    output_schema_type: str
    safety_classification: str
    icon_name: str


@router.get("", response_model=list[ActionTemplateRead])
def list_templates() -> list[ActionTemplateRead]:
    svc = TemplateService()
    templates = svc.list_templates()
    return [
        ActionTemplateRead(
            id=t.id,
            title=t.title,
            description=t.description,
            category=t.category,
            prompt_instruction=t.prompt_instruction,
            supported_source_types=t.supported_source_types,
            output_schema_type=t.output_schema_type,
            safety_classification=t.safety_classification,
            icon_name=t.icon_name,
        )
        for t in templates
    ]


@router.get("/{template_id}", response_model=ActionTemplateRead)
def get_template_detail(template_id: str) -> ActionTemplateRead:
    svc = TemplateService()
    template = svc.get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    return ActionTemplateRead(
        id=template.id,
        title=template.title,
        description=template.description,
        category=template.category,
        prompt_instruction=template.prompt_instruction,
        supported_source_types=template.supported_source_types,
        output_schema_type=template.output_schema_type,
        safety_classification=template.safety_classification,
        icon_name=template.icon_name,
    )
