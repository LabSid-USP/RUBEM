from pathlib import Path

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
            ("1 2 0.5\n", "more than one key column"),
            ("1 2 3 0.5\n", "more than one key column"),
            ("[foo,bar] 0.5\n", "invalid bounds"),
            ("[,] 0.5\n", "invalid bounds"),
            ("[1,bar] 0.5\n", "invalid bounds"),
        ],
    )
    def test_rejects_malformed_tables(self, tmp_path, text, message):
        table = tmp_path / "t.txt"
        table.write_text(text, encoding="utf8")

        with pytest.raises(LookupTableError, match=message):
            read_lookup_table(table)

    @pytest.mark.unit
    @pytest.mark.parametrize("key", ["[1,3]", "<1,3]", "[1,>", "<,3]"])
    def test_accepts_one_sided_and_two_sided_numeric_intervals(self, tmp_path, key):
        table = tmp_path / "t.txt"
        table.write_text(f"{key} 0.5\n", encoding="utf8")

        assert read_lookup_table(table) == [((key,), 0.5)]


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


class TestKeySpellings:
    """Keys are compared numerically: ``1``, ``01`` and ``1.0`` are one class."""

    @pytest.mark.unit
    def test_zero_padded_and_decimal_months_cover_the_year(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["rainydays"], "".join(f"{m:02d} 5\n" for m in range(1, 13)))
        assert check_lookup_tables(tables_of(config)) == []

        rewrite(config["TABLES"]["rainydays"], "".join(f"{m}.0 5\n" for m in range(1, 13)))
        assert check_lookup_tables(tables_of(config)) == []

    @pytest.mark.unit
    def test_interval_keys_cover_the_months_they_span(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["rainydays"], "[1,6] 3\n<6,12] 9\n")
        assert check_lookup_tables(tables_of(config)) == []

        rewrite(config["TABLES"]["rainydays"], "[1,6] 3\n<6,11] 9\n")
        problems = check_lookup_tables(tables_of(config))
        assert any("Missing months: [12]" in p.reason for p in problems)

    @pytest.mark.unit
    def test_paired_tables_match_equivalent_spellings(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["t_fcap"], "1.0 0.26\n")
        rewrite(config["TABLES"]["t_wp"], "01 0.12\n")

        assert check_lookup_tables(tables_of(config)) == []

        rewrite(config["TABLES"]["t_wp"], "01 0.30\n")
        problems = check_lookup_tables(tables_of(config))
        assert any("Tcc > Tw" in p.description and p.blocking for p in problems)

    @pytest.mark.unit
    def test_an_unreadable_fraction_table_names_its_path(self, tmp_path):
        config = write_synthetic_dataset(str(tmp_path))
        rewrite(config["TABLES"]["a_o"], "3 nope\n")

        problems = check_lookup_tables(tables_of(config))

        fraction_problems = [
            p for p in problems if "Area fraction lookup table cannot be read" in p.description
        ]
        assert fraction_problems and Path(fraction_problems[0].file) == Path(
            config["TABLES"]["a_o"]
        )
