import gzip

from shadow.extract.declared import declared_dir, read_declared
from shadow.extract.google_collect import load_raw, raw_dir
from shadow.snapshot import compress_pages, write_declared_extracts
from tests.test_declared import JAR_SAMPLE, SODRA_SAMPLE


def test_compress_pages_keeps_the_exact_content(tmp_path):
    folder = raw_dir("2026-11", tmp_path)
    folder.mkdir(parents=True)
    original = '{"meta": {"category": "cafe_restaurant"}, "response": {"results": []}}'
    (folder / "cafe_restaurant__seskine.json").write_text(original, encoding="utf-8")

    assert compress_pages("2026-11", tmp_path) == 1
    assert not (folder / "cafe_restaurant__seskine.json").exists()
    with gzip.open(folder / "cafe_restaurant__seskine.json.gz", "rt", encoding="utf-8") as f:
        assert f.read() == original
    assert load_raw("2026-11", tmp_path)[0]["source_file"] == "cafe_restaurant__seskine.json.gz"


def test_extracts_give_the_same_result_as_the_full_files(tmp_path):
    folder = declared_dir("2026-11", tmp_path)
    folder.mkdir(parents=True)
    (folder / "JAR_IREGISTRUOTI.csv").write_text(JAR_SAMPLE, encoding="utf-8")
    (folder / "monthly-2026.csv").write_text("\ufeff" + SODRA_SAMPLE, encoding="utf-8")
    from_full = read_declared("2026-11", tmp_path)

    assert write_declared_extracts("2026-11", tmp_path) == (1, 2)
    (folder / "JAR_IREGISTRUOTI.csv").unlink()
    (folder / "monthly-2026.csv").unlink()

    assert read_declared("2026-11", tmp_path) == from_full