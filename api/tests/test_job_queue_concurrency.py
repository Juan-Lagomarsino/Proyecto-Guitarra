"""Claims concurrentes con sesiones y conexiones reales contra Postgres (sin mocks)."""

import datetime as dt
import threading
from collections import Counter

from sqlalchemy.orm import Session

from guitarra_api.application.job_queue import JobQueue
from guitarra_api.infra.db.repositories.jobs import JobRepository
from guitarra_api.infra.db.repositories.songs import SongRepository

WORKERS = 8
FAR_FUTURE = dt.datetime(2100, 1, 1, tzinfo=dt.UTC)


def seed(session, count: int) -> None:
    songs, jobs = SongRepository(session), JobRepository(session)
    for index in range(count):
        song = songs.add_song(
            title=f"c{index}", artist="a", source="youtube", youtube_id=f"v{index}"
        )
        jobs.add_job(song.id)


def run_concurrent_claims(engine) -> list[int | None]:
    barrier = threading.Barrier(WORKERS)
    results: list[int | None] = [None] * WORKERS

    def worker(index: int) -> None:
        with Session(engine, expire_on_commit=False) as own_session:
            queue = JobQueue(own_session, lease_seconds=300)
            barrier.wait()
            claimed = queue.claim(f"w{index}")
            results[index] = claimed.job_id if claimed else None

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


def test_un_solo_trabajo_lo_toma_exactamente_un_worker(session, migrated_engine):
    seed(session, 1)
    results = run_concurrent_claims(migrated_engine)
    assert Counter(r for r in results if r is not None) == {1: 1}
    assert results.count(None) == WORKERS - 1


def test_varios_trabajos_se_reparten_sin_repetirse(session, migrated_engine):
    seed(session, WORKERS)
    results = run_concurrent_claims(migrated_engine)
    assert sorted(r for r in results if r is not None) == list(range(1, WORKERS + 1))


def test_skip_locked_saltea_el_trabajo_bloqueado_por_otra_sesion(session, migrated_engine):
    seed(session, 2)
    with Session(migrated_engine) as holder:
        locked = JobRepository(holder).lock_next_available(now=FAR_FUTURE)
        assert locked is not None
        with Session(migrated_engine) as other:
            claimed = JobQueue(other, lease_seconds=300).claim("w-otro")
            assert claimed is not None
            assert claimed.job_id != locked.id
        holder.rollback()
