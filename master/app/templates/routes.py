"""
Notebook template API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.session import get_db
from app.auth.dependencies import get_current_active_user, get_current_admin_user
from app.users.models import User
from .service import TemplateService
from .schemas import (
    TemplateCreate,
    TemplateUpdate,
    TemplateResponse,
    TemplateForkRequest,
    TemplateForkResponse,
    TemplateFromProjectRequest,
)

router = APIRouter(tags=["Templates"])


# =============================================================================
# Public routes (authenticated users)
# =============================================================================

@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(
    category: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all public templates."""
    service = TemplateService(db)
    templates = await service.list_public(category=category)
    return templates


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get template details."""
    service = TemplateService(db)
    template = await service.get_by_id(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    return template


@router.post("/templates/{template_id}/fork", response_model=TemplateForkResponse)
async def fork_template(
    template_id: str,
    request: TemplateForkRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Fork a template to create a new project."""
    service = TemplateService(db)
    result = await service.fork_to_project(
        template_id=template_id,
        user=current_user,
        project_name=request.name,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    await db.commit()

    return TemplateForkResponse(
        project_id=result["project_id"],
        project_name=result["project_name"],
        message=f"Created project '{result['project_name']}' from template",
    )


# =============================================================================
# Admin routes
# =============================================================================

@router.post("/admin/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: TemplateCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: create a new template."""
    service = TemplateService(db)
    template = await service.create(
        data=request.model_dump(),
        notebook_data=None,
        created_by=current_user.id,
    )
    await db.commit()
    return template


@router.post("/admin/templates/from-project/{project_id}", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template_from_project(
    project_id: str,
    request: TemplateFromProjectRequest,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: create a template from an existing project."""
    service = TemplateService(db)
    template = await service.create_from_project(
        project_id=project_id,
        data=request.model_dump(),
        created_by=current_user.id,
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    await db.commit()
    return template


@router.put("/admin/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    request: TemplateUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: update a template."""
    service = TemplateService(db)
    template = await service.update(
        template_id=template_id,
        data=request.model_dump(exclude_unset=True),
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    await db.commit()
    return template


@router.delete("/admin/templates/{template_id}")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: delete a template."""
    service = TemplateService(db)
    deleted = await service.delete(template_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    await db.commit()
    return {"success": True, "message": "Template deleted"}
