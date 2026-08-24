import pytest

from rubem.file._file_convertions import tss2csv


def write_tss(path, rows):
    with open(path, "w", encoding="utf8") as f:
        for row in rows:
            f.write(" ".join(str(value) for value in row) + "\n")


class TestTss2Csv:
    @pytest.mark.unit
    def test_converts_content_and_removes_sources(self, tmp_path):
        tss = tmp_path / "tss_itp.tss"
        write_tss(tss, [(1, 10.5, 20.5), (2, 11.0, 21.0)])

        tss2csv([tss], ["1", "2"])

        csv_path = tmp_path / "tss_itp.csv"
        assert csv_path.read_text(encoding="utf8").splitlines() == [
            "0;1;2",
            "1;10.5;20.5",
            "2;11.0;21.0",
        ]
        assert not tss.exists()

    @pytest.mark.unit
    def test_keeps_sources_when_asked(self, tmp_path):
        tss = tmp_path / "tss_itp.tss"
        write_tss(tss, [(1, 10.5)])

        tss2csv([tss], ["1"], should_delete_src_tss=False)

        assert tss.exists()
        assert (tmp_path / "tss_itp.csv").exists()

    @pytest.mark.unit
    def test_only_listed_files_are_touched(self, tmp_path):
        listed = tmp_path / "tss_itp.tss"
        stale = tmp_path / "stale.tss"
        write_tss(listed, [(1, 10.5)])
        write_tss(stale, [(1, 99.0)])

        tss2csv([listed], ["1"])

        assert stale.exists()
        assert not (tmp_path / "stale.csv").exists()

    @pytest.mark.unit
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            tss2csv([tmp_path / "absent.tss"], ["1"])

    @pytest.mark.unit
    def test_empty_column_names_raise(self, tmp_path):
        with pytest.raises(ValueError):
            tss2csv([], [])

    @pytest.mark.unit
    def test_failure_leaves_sources_and_no_partial_outputs(self, tmp_path):
        good = tmp_path / "tss_good.tss"
        bad = tmp_path / "tss_bad.tss"
        write_tss(good, [(1, 10.5)])
        write_tss(bad, [(1, 10.5, 99.0)])

        with pytest.raises(ValueError):
            tss2csv([good, bad], ["1"])

        assert good.exists()
        assert bad.exists()
        assert not list(tmp_path.glob("*.csv"))
        assert not list(tmp_path.glob("*.tmp"))
