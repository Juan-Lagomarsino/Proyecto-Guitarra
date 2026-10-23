import pytest

from guitarra_api.domain.song_source import InvalidSongUrlError, parse_song_url

YT = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={YT}",
        f"http://youtube.com/watch?v={YT}",
        f"youtube.com/watch?v={YT}",
        f"https://www.youtube.com/watch?v={YT}&t=42s&list=PLabc",
        f"https://www.youtube.com/watch?list=PLabc&v={YT}",
        f"https://youtu.be/{YT}",
        f"https://youtu.be/{YT}?si=abc123&t=10",
        f"https://www.youtube.com/shorts/{YT}",
        f"https://music.youtube.com/watch?v={YT}&si=xyz",
        f"https://m.youtube.com/watch?v={YT}",
        f"  https://www.youtube.com/watch?v={YT}  ",
    ],
)
def test_youtube(url):
    parsed = parse_song_url(url)
    assert (parsed.source, parsed.youtube_id, parsed.spotify_id) == ("youtube", YT, None)


@pytest.mark.parametrize(
    "url",
    [
        "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC",
        "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC?si=abc",
        "https://open.spotify.com/intl-es/track/4uLU6hMCjMI75M1A2tKUQC?si=abc",
    ],
)
def test_spotify(url):
    parsed = parse_song_url(url)
    assert (parsed.source, parsed.spotify_id, parsed.youtube_id) == (
        "spotify",
        "4uLU6hMCjMI75M1A2tKUQC",
        None,
    )


@pytest.mark.parametrize(
    "url",
    [
        "",
        "hola",
        "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M",
        "https://open.spotify.com/album/4uLU6hMCjMI75M1A2tKUQC",
        "https://open.spotify.com/track/corto",
        "https://example.com/watch?v=" + YT,
        "https://evil.com/youtube.com/watch?v=" + YT,
        "https://www.youtube.com/watch?v=corto",
        "https://www.youtube.com/watch?v=" + YT + "extra",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/playlist?list=PLabc",
        "https://youtu.be/",
        "https://[abc",
        "http://[::1",
        f"https://www.youtube-nocookie.com/embed/{YT}",
        "spotify:album:4uLU6hMCjMI75M1A2tKUQC",
    ],
)
def test_invalid(url):
    with pytest.raises(InvalidSongUrlError):
        parse_song_url(url)


def test_spotify_uri():
    parsed = parse_song_url("spotify:track:4uLU6hMCjMI75M1A2tKUQC")
    assert (parsed.source, parsed.spotify_id) == ("spotify", "4uLU6hMCjMI75M1A2tKUQC")
