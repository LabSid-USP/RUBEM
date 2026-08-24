import os
import pathlib

import pytest

from rubem.file._file_convertions import tss2csv


def write_tss(path, rows):
    with open(path, "w", encoding="utf8") as f:
        for row in rows:
            f.write(" ".join(str(value) for value in row) + "\n")


def refuse_to_install(name):
    """Build an ``os.replace`` that fails when the converted ``name`` is installed.

    Only the move of the temporary file onto the destination fails; moving a
    destination aside and putting it back keep working, as they do when the
    failure comes from the new file rather than from the destination.
    """
    real_replace = os.replace

    def replace(src, dst):
        if os.path.basename(dst) == name and str(src).endswith(".tmp"):
            raise PermissionError(f"{src} cannot be installed as {dst}")
        return real_replace(src, dst)

    return replace


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

    @pytest.mark.unit
    def test_failed_rename_restores_the_previous_csv(self, tmp_path, monkeypatch):
        first = tmp_path / "tss_a.tss"
        second = tmp_path / "tss_b.tss"
        write_tss(first, [(1, 10.5)])
        write_tss(second, [(1, 20.5)])
        (tmp_path / "tss_a.csv").write_text("previous a\n", encoding="utf8")
        (tmp_path / "tss_b.csv").write_text("previous b\n", encoding="utf8")

        monkeypatch.setattr(os, "replace", refuse_to_install("tss_b.csv"))

        with pytest.raises(PermissionError):
            tss2csv([first, second], ["1"])

        assert (tmp_path / "tss_a.csv").read_text(encoding="utf8") == "previous a\n"
        assert (tmp_path / "tss_b.csv").read_text(encoding="utf8") == "previous b\n"
        assert sorted(path.name for path in tmp_path.iterdir()) == [
            "tss_a.csv",
            "tss_a.tss",
            "tss_b.csv",
            "tss_b.tss",
        ]

    @pytest.mark.unit
    def test_failed_rename_removes_the_csv_installed_before_it(self, tmp_path, monkeypatch):
        first = tmp_path / "tss_a.tss"
        second = tmp_path / "tss_b.tss"
        write_tss(first, [(1, 10.5)])
        write_tss(second, [(1, 20.5)])

        monkeypatch.setattr(os, "replace", refuse_to_install("tss_b.csv"))

        with pytest.raises(PermissionError):
            tss2csv([first, second], ["1"])

        assert sorted(path.name for path in tmp_path.iterdir()) == ["tss_a.tss", "tss_b.tss"]

    @pytest.mark.unit
    def test_neighbouring_backup_and_staging_files_are_left_alone(self, tmp_path):
        """Files the user keeps next to a destination are not part of the transaction."""
        tss = tmp_path / "tss_itp.tss"
        write_tss(tss, [(1, 10.5)])
        (tmp_path / "tss_itp.csv").write_text("previous\n", encoding="utf8")
        (tmp_path / "tss_itp.csv.bak").write_text("kept backup\n", encoding="utf8")
        (tmp_path / "tss_itp.csv.tmp").write_text("kept staging\n", encoding="utf8")

        tss2csv([tss], ["1"])

        assert (tmp_path / "tss_itp.csv.bak").read_text(encoding="utf8") == "kept backup\n"
        assert (tmp_path / "tss_itp.csv.tmp").read_text(encoding="utf8") == "kept staging\n"
        assert (tmp_path / "tss_itp.csv").read_text(encoding="utf8").splitlines() == [
            "0;1",
            "1;10.5",
        ]
        assert sorted(path.name for path in tmp_path.iterdir()) == [
            "tss_itp.csv",
            "tss_itp.csv.bak",
            "tss_itp.csv.tmp",
        ]

    @pytest.mark.unit
    def test_failed_rename_restores_a_dangling_destination_symlink(self, tmp_path, monkeypatch):
        """A symlink destination is an entry to preserve, even if it points nowhere."""
        first = tmp_path / "tss_a.tss"
        second = tmp_path / "tss_b.tss"
        write_tss(first, [(1, 10.5)])
        write_tss(second, [(1, 20.5)])
        link = tmp_path / "tss_a.csv"
        try:
            link.symlink_to(tmp_path / "missing_target.csv")
        except OSError:
            pytest.skip("this platform does not allow creating symlinks")

        monkeypatch.setattr(os, "replace", refuse_to_install("tss_b.csv"))

        with pytest.raises(PermissionError):
            tss2csv([first, second], ["1"])

        assert os.path.islink(link)
        # Windows reports the target through its extended-length form, so the
        # name and the directory are compared instead of the literal string.
        restored = pathlib.Path(os.readlink(link))
        assert restored.name == "missing_target.csv"
        assert os.path.samefile(restored.parent, tmp_path)
        assert sorted(path.name for path in tmp_path.iterdir()) == [
            "tss_a.csv",
            "tss_a.tss",
            "tss_b.tss",
        ]

    @pytest.mark.unit
    def test_directory_destination_is_refused_without_touching_anything(self, tmp_path):
        tss = tmp_path / "tss_itp.tss"
        write_tss(tss, [(1, 10.5)])
        (tmp_path / "tss_itp.csv").mkdir()

        with pytest.raises(IsADirectoryError):
            tss2csv([tss], ["1"])

        assert (tmp_path / "tss_itp.csv").is_dir()
        assert sorted(path.name for path in tmp_path.iterdir()) == ["tss_itp.csv", "tss_itp.tss"]

    @pytest.mark.unit
    def test_undeletable_sources_are_reported_and_keep_the_conversion(
        self, tmp_path, monkeypatch, caplog
    ):
        """Deletion happens after the commit point, so it never undoes valid CSV files."""
        first = tmp_path / "tss_a.tss"
        second = tmp_path / "tss_b.tss"
        write_tss(first, [(1, 10.5)])
        write_tss(second, [(1, 20.5)])
        real_remove = os.remove

        def refuse_second(path):
            if os.path.basename(str(path)) == "tss_b.tss":
                raise PermissionError(f"{path} cannot be deleted")
            return real_remove(path)

        monkeypatch.setattr(os, "remove", refuse_second)

        with caplog.at_level("WARNING"):
            tss2csv([first, second], ["1"])

        assert not first.exists()
        assert second.exists()
        assert (tmp_path / "tss_a.csv").is_file()
        assert (tmp_path / "tss_b.csv").is_file()
        assert "tss_b.tss" in caplog.text

    @pytest.mark.unit
    def test_empty_source_fails_and_keeps_the_previous_csv(self, tmp_path):
        """A truncated run must not replace usable results with a header-only file."""
        first = tmp_path / "tss_a.tss"
        second = tmp_path / "tss_b.tss"
        write_tss(first, [(1, 10.5)])
        second.write_text("", encoding="utf8")
        (tmp_path / "tss_a.csv").write_text("previous a\n", encoding="utf8")
        (tmp_path / "tss_b.csv").write_text("previous b\n", encoding="utf8")

        with pytest.raises(ValueError, match="is empty"):
            tss2csv([first, second], ["1"])

        assert (tmp_path / "tss_a.csv").read_text(encoding="utf8") == "previous a\n"
        assert (tmp_path / "tss_b.csv").read_text(encoding="utf8") == "previous b\n"
        assert sorted(path.name for path in tmp_path.iterdir()) == [
            "tss_a.csv",
            "tss_a.tss",
            "tss_b.csv",
            "tss_b.tss",
        ]

    @pytest.mark.unit
    def test_converted_files_keep_ordinary_permissions(self, tmp_path):
        """The staging file is private to its owner; the installed CSV must not be."""
        tss = tmp_path / "tss_itp.tss"
        write_tss(tss, [(1, 10.5)])
        control = tmp_path / "control.csv"
        control.write_text("x\n", encoding="utf8")

        tss2csv([tss], ["1"])

        converted = tmp_path / "tss_itp.csv"
        assert converted.stat().st_mode & 0o777 == control.stat().st_mode & 0o777
