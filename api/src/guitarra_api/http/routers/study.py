from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from guitarra_api.application.study_service import NotFoundError, StudyService
from guitarra_api.http.auth import require_token
from guitarra_api.http.study_schemas import (
    CompletionIn,
    CompletionOut,
    ExerciseDetailOut,
    ExerciseOut,
    LessonOut,
    LessonSummaryOut,
    LevelOut,
)
from guitarra_api.infra.db.session import get_session

router = APIRouter(dependencies=[Depends(require_token)], tags=["estudio"])


def get_study_service(session: Annotated[Session, Depends(get_session)]) -> StudyService:
    return StudyService(session)


Service = Annotated[StudyService, Depends(get_study_service)]


def _not_found(error: NotFoundError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))


@router.get("/levels", response_model=list[LevelOut])
def list_levels(service: Service):
    return service.list_levels()


@router.get("/levels/{level_id}/lessons", response_model=list[LessonSummaryOut])
def list_lessons(level_id: int, service: Service):
    try:
        return service.list_lessons(level_id)
    except NotFoundError as error:
        raise _not_found(error) from error


@router.get("/lessons/{lesson_id}", response_model=LessonOut)
def get_lesson(lesson_id: int, service: Service):
    try:
        lesson, exercises = service.get_lesson(lesson_id)
    except NotFoundError as error:
        raise _not_found(error) from error
    return LessonOut(
        **LessonSummaryOut.model_validate(lesson).model_dump(),
        content_md=lesson.content_md,
        exercises=[ExerciseOut.model_validate(item) for item in exercises],
    )


@router.get("/exercises/{exercise_id}", response_model=ExerciseDetailOut)
def get_exercise(exercise_id: int, service: Service):
    try:
        detail = service.get_exercise(exercise_id)
    except NotFoundError as error:
        raise _not_found(error) from error
    return ExerciseDetailOut(
        **ExerciseOut.model_validate(detail.exercise).model_dump(), best_bpm=detail.best_bpm
    )


@router.post(
    "/exercises/{exercise_id}/complete",
    response_model=CompletionOut,
    status_code=status.HTTP_201_CREATED,
)
def complete_exercise(exercise_id: int, body: CompletionIn, service: Service):
    try:
        result = service.complete_exercise(exercise_id, body.bpm_logrado, body.instrumento)
    except NotFoundError as error:
        raise _not_found(error) from error
    completion = result.completion
    return CompletionOut(
        id=completion.id,
        exercise_id=completion.exercise_id,
        completed_at=completion.completed_at,
        bpm_logrado=body.bpm_logrado,
        instrumento=completion.instrument,
        best_bpm=result.best_bpm,
    )
