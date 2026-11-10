"""Convierte una sección de canción en un ejercicio que se completa con "Terminé"."""

import secrets

from sqlalchemy.orm import Session

from guitarra_api.application.song_service import SongNotFoundError, SongService
from guitarra_api.domain.song_chart import SongChartContent
from guitarra_api.domain.song_exercise import SectionExerciseKind, build_section_exercise
from guitarra_api.infra.db.models import Exercise, SongSection
from guitarra_api.infra.db.repositories.songs import SongRepository

CATEGORY = "technique"


class SectionNotFoundError(Exception):
    def __init__(self, song_id: int, section_id: int) -> None:
        super().__init__(f"La sección {section_id} no existe en la canción {song_id}")


class SongExerciseService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = SongRepository(session)
        self._songs = SongService(session)

    def create(
        self, song_id: int, section_id: int, kind: SectionExerciseKind, instrument: str
    ) -> Exercise:
        """Raises: SongNotFoundError, SectionNotFoundError, ChartNotFoundError y los errores de
        `domain.song_exercise` (sección que ya no está en el chart, o sin acordes o rasgueo)."""
        song = self._repo.get(song_id)
        if song is None:
            raise SongNotFoundError(song_id)
        section = self._repo.get_section(song_id, section_id)
        if section is None:
            raise SectionNotFoundError(song_id, section_id)
        # Vista mezclada: trae también el riff de la sección (auto si el usuario no lo tocó).
        chart = self._songs.current_chart(song_id, instrument)

        content = SongChartContent.model_validate(chart.content)
        built = build_section_exercise(content, section.slug, kind)
        exercise = self._repo.add_exercise(
            Exercise(
                song_section_id=section.id,
                slug=_slug(section, kind),
                title=f"{song.title or 'Canción'} · {built.title_suffix}",
                type=kind,
                instrument=instrument,
                notation=built.notation.model_dump(mode="json"),
                bpm_start=built.bpm_start,
                bpm_target=built.bpm_target,
                duration_min=built.duration_min,
                category=CATEGORY,
                description=built.description,
            )
        )
        self._session.commit()
        return exercise

    def list_for_song(self, song_id: int) -> list[Exercise]:
        if self._repo.get(song_id) is None:
            raise SongNotFoundError(song_id)
        return self._repo.list_exercises(song_id)


def _slug(section: SongSection, kind: str) -> str:
    return f"cancion-{section.song_id}-{section.slug}-{kind}-{secrets.token_hex(3)}"
