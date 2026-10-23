import pytest

from guitarra_worker.domain.matching import Candidate, choose_youtube_candidate

TITLE, ARTIST = "Wonderwall", "Oasis"


def cand(id_, title, channel, duration_s):
    return Candidate(id=id_, title=title, channel=channel, duration_s=duration_s)


def choose(candidates, duration=258, title=TITLE, artist=ARTIST):
    return choose_youtube_candidate(title, artist, duration, candidates)


def test_prefiere_el_oficial_frente_al_en_vivo():
    live = cand("live", "Oasis - Wonderwall (Live at Knebworth)", "Oasis", 258)
    official = cand("off", "Oasis - Wonderwall (Official Audio)", "Oasis", 258)
    result = choose([live, official])
    assert result is not None
    assert result[0].id == "off"


def test_diferencia_de_2s_pasa_y_de_10s_no():
    lejos = cand("lejos", "Oasis - Wonderwall (Official Audio)", "Oasis", 268)
    cerca = cand("cerca", "Oasis - Wonderwall", "Fan channel", 256)
    result = choose([lejos, cerca])
    assert result is not None and result[0].id == "cerca"


def test_todos_fuera_de_duracion_da_none():
    assert choose([cand("a", "Oasis - Wonderwall", "Oasis", 300)]) is None


def test_descarta_cover_y_karaoke():
    cover = cand("cov", "Wonderwall (Cover) - Oasis", "Guitarrista", 258)
    karaoke = cand("kar", "Oasis - Wonderwall (Karaoke Version)", "Sing King", 258)
    assert choose([cover, karaoke]) is None


def test_descarta_acustico_remix_y_en_vivo_en_español():
    candidatos = [
        cand("a", "Oasis - Wonderwall (Versión acústica)", "x", 258),
        cand("b", "Oasis - Wonderwall (Remix)", "x", 258),
        cand("c", "Oasis - Wonderwall en vivo", "x", 258),
    ]
    assert choose(candidatos) is None


def test_en_vivo_buscado_a_proposito_no_se_descarta():
    live = cand("live", "Oasis - Wonderwall (Live at Knebworth)", "Oasis", 258)
    studio = cand("st", "Oasis - Wonderwall (Official Audio)", "Oasis", 258)
    result = choose([live, studio], title="Wonderwall (Live)")
    assert result is not None
    assert result[0].id == "live"


def test_topic_y_canal_oficial_desempatan():
    random = cand("r", "Wonderwall", "Subidas random", 258)
    topic = cand("t", "Wonderwall", "Oasis - Topic", 258)
    result = choose([random, topic])
    assert result is not None and result[0].id == "t"


def test_normaliza_tildes_y_mayusculas():
    result = choose_youtube_candidate(
        "Canción de Amor", "Él Mató", None, [cand("a", "EL MATO - CANCION DE AMOR", "x", 200)]
    )
    assert result is not None and result[0].id == "a"


def test_sin_duracion_objetivo_elige_por_similitud():
    cerca = cand("a", "Oasis - Wonderwall (Official Audio)", "Oasis", 258)
    otra = cand("b", "Oasis - Don't Look Back In Anger", "Oasis", 290)
    result = choose_youtube_candidate(TITLE, ARTIST, None, [otra, cerca])
    assert result is not None and result[0].id == "a"
    assert 0 < result[1] <= 1.5


def test_sin_candidatos():
    assert choose([]) is None


def test_ninguno_se_parece_al_titulo():
    assert choose([cand("a", "Otra canción cualquiera", "Alguien", 258)]) is None


# --- Las 5 canciones reales, con candidatos armados a mano ---

SONGS = {
    "flaca": ("Flaca", "Andrés Calamaro", 316, "Andrés Calamaro"),
    "ligera": ("De música ligera", "Soda Stereo", 217, "Soda Stéreo"),
    "boys": ("Boys Don't Cry", "The Cure", 156, "The Cure"),
    "fuego": ("Cerca del fuego", "Charly García", 255, "Charly García"),
    "tren": ("No voy en tren", "Charly García", 288, "Charly García"),
}


def good_candidates(key):
    title, artist, duration, channel = SONGS[key]
    return [
        cand("topic", f"{title}", f"{artist} - Topic", duration),
        cand("rem", f"{artist} - {title} (Remastered)", channel, duration + 1),
        cand("video", f"{artist} - {title} (Official Video)", channel, duration - 1),
    ]


@pytest.mark.parametrize("key", list(SONGS))
def test_cancion_real_acepta_oficial_remasterizado_y_video(key):
    title, artist, duration, _ = SONGS[key]
    for candidate in good_candidates(key):
        result = choose_youtube_candidate(title, artist, duration, [candidate])
        assert result is not None and result[0].id == candidate.id


@pytest.mark.parametrize("key", list(SONGS))
def test_cancion_real_descarta_unplugged_y_en_vivo(key):
    title, artist, duration, _ = SONGS[key]
    bad = [
        cand("mtv", f"{artist} - {title} (MTV Unplugged)", artist, duration),
        cand("vivo", f"{artist} - {title} (En vivo)", artist, duration),
        cand("live", f"{title} (Live)", artist, duration),
    ]
    assert choose_youtube_candidate(title, artist, duration, bad) is None


def test_flaca_rechaza_otro_artista_con_el_mismo_titulo():
    otro = cand("jarabe", "Jarabe de Palo - Flaca", "Jarabe de Palo", 316)
    assert choose_youtube_candidate("Flaca", "Andrés Calamaro", 316, [otro]) is None


def test_no_voy_en_tren_rechaza_otro_artista():
    otro = cand("otro", "Otro - Voy en tren", "Otro", 288)
    assert choose_youtube_candidate("No voy en tren", "Charly García", 288, [otro]) is None


def test_titulo_parcial_se_rechaza():
    parcial = cand("p", "Charly García - Cerca", "Charly García", 255)
    assert choose_youtube_candidate("Cerca del fuego", "Charly García", 255, [parcial]) is None


def test_artista_con_y_sin_tilde():
    c = cand("a", "Charly Garcia - Cerca del fuego", "Charly Garcia", 255)
    assert choose_youtube_candidate("Cerca del fuego", "Charly García", 255, [c]) is not None
    c2 = cand("b", "Soda Stereo - De Musica Ligera", "Soda Stereo", 217)
    assert choose_youtube_candidate("De música ligera", "Soda Stéreo", 217, [c2]) is not None


def test_boys_dont_cry_con_apostrofe_tipografico():
    c = cand("a", "The Cure - Boys Don’t Cry (Official Audio)", "The Cure", 156)
    assert choose_youtube_candidate("Boys Don't Cry", "The Cure", 156, [c]) is not None
