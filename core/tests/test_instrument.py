import pytest

from guitarra_core.chord_shapes import lowest_pitch_class, shape_pitch_classes, shape_position
from guitarra_core.instrument import best_capo, capo_cost, voicings_for
from guitarra_core.theory import NOTE_NAMES, parse_chord, parse_note, pitch_classes


def barre_count(forms):
    voicings = voicings_for(forms, "classical", 0, False)
    return sum(1 for v in voicings if v.shape and v.shape.barre)


def max_jump(voicings):
    positions = [shape_position(v.shape.shape) for v in voicings if v.shape]
    return max(abs(a - b) for a, b in zip(positions, positions[1:], strict=False))


class TestBestCapo:
    def test_f_sharp_m_d_a_e_gets_easier_with_capo(self):
        progression = ["F#m", "D", "A", "E"]
        result = best_capo(progression)
        assert result.capo == 2
        assert barre_count(result.forms) == 0
        assert capo_cost(progression, result.capo) < capo_cost(progression, 0)

    def test_capo_transposes_every_chord_down(self):
        forms = best_capo(["Bm", "G", "D", "A"], max_capo=7).forms
        capo = best_capo(["Bm", "G", "D", "A"], max_capo=7).capo
        for original, form in zip(["Bm", "G", "D", "A"], forms, strict=True):
            expected = (parse_note(parse_chord(original).root) - capo) % 12
            assert parse_note(parse_chord(form).root) == expected

    def test_f_c_dm_bb_removes_barres(self):
        progression = ["F", "C", "Dm", "Bb"]
        result = best_capo(progression)
        assert result.capo > 0
        assert barre_count(result.forms) < barre_count(progression)

    def test_progression_without_barres_keeps_capo_zero(self):
        result = best_capo(["G", "D", "Em", "C"])
        assert result.capo == 0
        assert result.forms == ["G", "D", "Em", "C"]

    @pytest.mark.parametrize(
        "progression",
        [
            ["G", "D", "Em", "C"],  # Flaca
            ["D", "A", "Bm", "G"],  # De música ligera: una sola cejilla, no vale subir 7 trastes
            ["Bm", "G", "D", "A"],
        ],
    )
    def test_songs_with_open_chords_stay_without_capo(self, progression):
        assert best_capo(progression).capo == 0

    def test_boys_dont_cry_does_not_get_a_high_capo(self):
        # Dos cejillas (Bm, C#m): un capo bajo las reduce, pero nunca el 7 que salía antes.
        assert best_capo(["Bm", "Dbm", "A", "D"]).capo <= 2

    def test_noisy_detected_progression_does_not_suggest_high_capo(self):
        # Flaca detectada: G, D, C, Em dominan y B (cejilla) aparece suelto.
        progression = ["G"] * 49 + ["D"] * 29 + ["C"] * 16 + ["B"] * 14 + ["Em"] * 13 + ["B7"] * 9
        assert best_capo(progression).capo == 0

    def test_open_forms_never_get_a_capo(self):
        assert best_capo(["Am", "E", "G", "C", "D"]).capo == 0

    def test_tie_prefers_capo_zero(self):
        assert best_capo(["E", "A"]).capo == 0

    def test_respects_max_capo(self):
        assert best_capo(["Bm", "G", "D", "A"], max_capo=0).capo == 0
        assert best_capo(["Bm", "G", "D", "A"], max_capo=3).capo <= 3

    def test_no_chord_is_kept(self):
        result = best_capo(["N", "Am", "N"])
        assert result.forms[0] == "N"
        assert result.forms[2] == "N"

    def test_empty_progression(self):
        result = best_capo([])
        assert (result.capo, result.forms) == (0, [])

    def test_slash_bass_is_transposed_too(self):
        result = best_capo(["Bm", "A/C#", "G", "D"], max_capo=2)
        for form in result.forms:
            assert parse_chord(form) is not None


class TestVoicingsClassical:
    def test_prefers_open_chords(self):
        voicings = voicings_for(["C", "G", "Am", "F"], "classical", 0, False)
        assert [v.shape.kind for v in voicings][:3] == ["open", "open", "open"]
        assert voicings[3].shape.barre is not None

    def test_every_voicing_plays_the_form(self):
        voicings = voicings_for(["Bm", "G", "D", "A"], "classical", 2, False)
        for voicing in voicings:
            expected = pitch_classes(parse_chord(voicing.form))
            assert shape_pitch_classes(voicing.shape.shape) == expected

    def test_capo_changes_the_form_but_keeps_the_written_chord(self):
        voicings = voicings_for(["Bm", "G"], "classical", 2, False)
        assert [v.chord for v in voicings] == ["Bm", "G"]
        assert [v.form for v in voicings] == ["Am", "F"]

    def test_no_chord_has_no_shape(self):
        voicings = voicings_for(["C", "N", "G"], "classical", 0, False)
        assert voicings[1].shape is None
        assert voicings[1].form == "N"

    def test_classical_never_uses_power_chords(self):
        voicings = voicings_for(["G", "C"], "classical", 0, True)
        assert all(v.shape.kind != "power" for v in voicings)

    def test_position_coherence_for_barre_chords(self):
        voicings = voicings_for(["Gm", "Cm", "Eb", "Bb", "F"], "classical", 0, False)
        assert max_jump(voicings) <= 4

    def test_repeated_chord_keeps_the_same_shape(self):
        voicings = voicings_for(["Bm", "G", "Bm"], "classical", 0, False)
        assert voicings[0].shape.shape == voicings[2].shape.shape

    def test_coherence_beats_isolated_cheapest_choice(self):
        progression = ["F#m", "B", "E", "C#m"]
        voicings = voicings_for(progression, "classical", 0, False)
        assert max_jump(voicings) <= 5

    def test_unknown_instrument_is_rejected(self):
        with pytest.raises(ValueError):
            voicings_for(["C"], "banjo", 0, False)  # type: ignore[arg-type]


class TestElectricPowerChords:
    def test_major_and_minor_become_fifths(self):
        voicings = voicings_for(["G", "Cm", "D"], "electric", 0, True)
        assert [v.form for v in voicings] == ["G5", "C5", "D5"]
        assert all(v.shape.kind == "power" for v in voicings)

    def test_power_chord_notes_are_root_and_fifth(self):
        for root in NOTE_NAMES:
            voicing = voicings_for([root], "electric", 0, True)[0]
            expected = pitch_classes(parse_chord(root + "5"))
            assert shape_pitch_classes(voicing.shape.shape) == expected
            assert lowest_pitch_class(voicing.shape.shape) == parse_note(root)

    def test_picks_the_string_that_minimises_the_jump(self):
        voicings = voicings_for(["G", "C", "D"], "electric", 0, True)
        assert max_jump(voicings) <= 3
        # G5 en la 6ta (traste 3), C5 en la 5ta (traste 3): no sube al 8.
        assert voicings[0].shape.shape == (3, 5, 5, "x", "x", "x")
        assert voicings[1].shape.shape == ("x", 3, 5, 5, "x", "x")

    def test_sevenths_and_others_are_not_converted(self):
        voicings = voicings_for(["G7", "Em7", "Csus4"], "electric", 0, True)
        assert [v.form for v in voicings] == ["G7", "Em7", "Csus4"]
        assert all(v.shape.kind != "power" for v in voicings)

    def test_without_power_chords_electric_uses_normal_shapes(self):
        voicings = voicings_for(["G", "C"], "electric", 0, False)
        assert all(v.shape.kind != "power" for v in voicings)
        assert [v.form for v in voicings] == ["G", "C"]

    def test_slash_chords_become_power_of_the_root(self):
        voicing = voicings_for(["C/G"], "electric", 0, True)[0]
        assert voicing.form == "C5"

    def test_power_with_capo(self):
        voicing = voicings_for(["A"], "electric", 2, True)[0]
        assert voicing.form == "G5"
        assert voicing.chord == "A"
