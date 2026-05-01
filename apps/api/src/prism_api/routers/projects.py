"""Project endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from prism_api.deps import current_user, session_dep
from prism_api.models.user import User
from prism_api.repos.projects import ProjectRepo
from prism_api.schemas.project import CreateProjectRequest, ProjectOut

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.get("")
def list_projects(
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> list[ProjectOut]:
    return [
        ProjectOut(id=p.id, slug=p.slug, name=p.name, description=p.description)
        for p in ProjectRepo(session).list_all()
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_project(
    body: CreateProjectRequest,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ProjectOut:
    try:
        p = ProjectRepo(session).create(
            slug=body.slug, name=body.name, description=body.description
        )
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, "slug already exists") from exc
    return ProjectOut(id=p.id, slug=p.slug, name=p.name, description=p.description)


@router.get("/{slug}")
def get_project(
    slug: str,
    _: User = Depends(current_user),
    session: Session = Depends(session_dep),
) -> ProjectOut:
    p = ProjectRepo(session).get_by_slug(slug)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return ProjectOut(id=p.id, slug=p.slug, name=p.name, description=p.description)
