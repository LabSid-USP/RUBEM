import pytest

from rubem.configuration.input_table_files import InputTableFiles
from rubem.validation.lookup_tables import LookupTableError, check_lookup_tables, read_lookup_table
from tests.helpers.synthetic import write_synthetic_dataset


def tables_of(config):
    t = config["TABLES"]
    return InputTableFiles(
        rainy_days=t["rainydays"],
        a_i=t["a_i"],
        a_o=t["a_o"],
        a_s=t["a_s"],
        a_v=t["a_v"],
        manning=t["manning"],
        bulk_density=t["bulk_density"],
        k_sat=t["k_sat"],
        t_fcap=t["t_fcap"],
        t_sat=t["t_sat"],
        t_wp=t["t_wp"],
        rootzone_depth=t["rootzone_depth"],
        kc_min=t["k_c_min"],
        kc_max=t["k_c_max"],
    )


def rewrite(path, text):
    with open(path, "w", encoding="utf8") as f:
        f.write(text)


class TestReadLookupTable:
    @pytest.mark.unit
    def test_reads_keys_and_values(self, tmp_path):
        table = tmp_path / "t.txt"
        table.write_text("1 0.5\n\n2\t1e-1\n[3,5] 2\n<6,> 3.5\n", encoding="utf8")

        assert read_lookup_table(table) == [
            (("1",), 0.5),
            (("2",), 0.1),
            (("[3,5]",), 2.0),
            (("<6,>",), 3.5),
        ]

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "text, message",
        [
            ("", "empty"),
            ("1\n", "no value column"),
            ("1 abc\n", "non-numeric value"),
            ("x 1\n", "invalid key"),
        ],
    )
    def test_rejects_malformed_tables(self, tmp_path, text, message):
        table = tmp_path / "t.txt"
        table.write_text(text, encoding="utf8")

        with pytest.raises(LookupTableError, match=message):
            read_lookup_table(table)


class TestCheckLookupTables:
    @pytest.mark.unit
    def test_the_synthetic_tables_are_clean(self, tmp_path):
        assert check_lookup_tables(tables_of(write_synthetic_dataset(str(tmp_path)))) == []

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "key, text, description",
        [
            (
                "rainydays",
                "1 0\n2 5\n3 5\n4 5\n5 5\n6 5\n7 5\n8 5\n9 5\n10 5\n11 5\n12 5\n",
                "non-positive",
            ),
            ("rainydays", "1 5\n2 5\n", "does not cover every month"),
            ("manning", "3 0\n4 0.1\n", "non-positive"),
            ("bulk_density", "1 -1\n", "non-positive"),
            ("rootzone_depth", "1 0\n", "non-positive"),
            ("t_sat", "1 0\n", "non-positive"),
            ("t_fcap", "1 0.1\n", "Tcc > Tw"),
            ("t_wp", "2 0.1\n", "do not share their keys"),
            ("k_sat", "1 nope\n", "cannot be read"),
        ],
    )
    def test_blocking_rules(self, tmp_path, key, text, description):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"][key], text)

        problems = check_lookup_tables(tables_of(config))

        matching = [p for p in problems if description in p.description or description in p.reason]
        assert matching, [str(p) for p in problems]
        assert all(p.blocking for p in matching)

    @pytest.mark.unit
    def test_kc_max_below_kc_min_is_reported_without_blocking(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["k_c_max"], "3 0.5\n4 0.5\n")

        problems = check_lookup_tables(tables_of(config))

        assert len(problems) == 1
        assert "kc_max >= kc_min" in problems[0].description
        assert not problems[0].blocking

    @pytest.mark.unit
    def test_area_fractions_not_adding_up_are_reported_without_blocking(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["a_v"], "3 0.5\n4 0.5\n")

        problems = check_lookup_tables(tables_of(config))

        assert [p.blocking for p in problems] == [False, False]
        assert all("do not add up to 1" in p.description for p in problems)

    @pytest.mark.unit
    def test_area_fractions_outside_the_unit_interval_block(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["a_v"], "3 1.5\n4 0.6\n")

        problems = check_lookup_tables(tables_of(config))

        assert any(p.blocking and "between 0 and 1" in p.description for p in problems)
