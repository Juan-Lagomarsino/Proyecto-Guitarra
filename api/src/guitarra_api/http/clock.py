from guitarra_api.application.clock import Clock, utc_now


def get_clock() -> Clock:
    """Dependencia de FastAPI: los tests la sobreescriben para fijar la fecha."""
    return utc_now
