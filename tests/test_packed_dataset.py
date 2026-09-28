from pathlib import Path

from starcraft_ai.data import iter_jsonl_v1, load_npz_v1, pack_npz_v1


def test_fixture_packs_to_npz(tmp_path: Path) -> None:
    transitions = list(iter_jsonl_v1(Path("tests/fixtures/transitions_v1.jsonl")))
    output = tmp_path / "fixture.npz"

    assert pack_npz_v1(output, transitions) == 2

    packed = load_npz_v1(output)
    assert packed["observation_global"].shape == (2, 9)
    assert packed["next_observation_global"].shape == (2, 9)
    assert packed["actions"].shape == (2, 7)
    assert packed["observation_unit_offsets"].tolist() == [0, 2, 5]
    assert packed["next_observation_unit_offsets"].tolist() == [0, 2, 5]
    assert packed["terminals"].tolist() == [False, False]
