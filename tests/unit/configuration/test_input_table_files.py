import os
import pytest

from rubem.configuration.input_table_files import InputTableFiles


class TestInputTables:
    @pytest.mark.unit
    def test_input_table_files_exist(self, fs):
        fs.create_file("/path/to/rainy_days.csv", contents="42")
        fs.create_file("/path/to/a_i.csv", contents="42")
        fs.create_file("/path/to/a_o.csv", contents="42")
        fs.create_file("/path/to/a_s.csv", contents="42")
        fs.create_file("/path/to/a_v.csv", contents="42")
        fs.create_file("/path/to/manning.csv", contents="42")
        fs.create_file("/path/to/bulk_density.csv", contents="42")
        fs.create_file("/path/to/k_sat.csv", contents="42")
        fs.create_file("/path/to/t_fcap.csv", contents="42")
        fs.create_file("/path/to/t_sat.csv", contents="42")
        fs.create_file("/path/to/t_wp.csv", contents="42")
        fs.create_file("/path/to/rootzone_depth.csv", contents="42")
        fs.create_file("/path/to/kc_min.csv", contents="42")
        fs.create_file("/path/to/kc_max.csv", contents="42")
        input_tables = InputTableFiles(
            rainy_days="/path/to/rainy_days.csv",
            a_i="/path/to/a_i.csv",
            a_o="/path/to/a_o.csv",
            a_s="/path/to/a_s.csv",
            a_v="/path/to/a_v.csv",
            manning="/path/to/manning.csv",
            bulk_density="/path/to/bulk_density.csv",
            k_sat="/path/to/k_sat.csv",
            t_fcap="/path/to/t_fcap.csv",
            t_sat="/path/to/t_sat.csv",
            t_wp="/path/to/t_wp.csv",
            rootzone_depth="/path/to/rootzone_depth.csv",
            kc_min="/path/to/kc_min.csv",
            kc_max="/path/to/kc_max.csv",
            validate_input=True,
        )

        assert os.path.isfile(input_tables.rainy_days)
        assert os.path.isfile(input_tables.a_i)
        assert os.path.isfile(input_tables.a_o)
        assert os.path.isfile(input_tables.a_s)
        assert os.path.isfile(input_tables.a_v)
        assert os.path.isfile(input_tables.manning)
        assert os.path.isfile(input_tables.bulk_density)
        assert os.path.isfile(input_tables.k_sat)
        assert os.path.isfile(input_tables.t_fcap)
        assert os.path.isfile(input_tables.t_sat)
        assert os.path.isfile(input_tables.t_wp)
        assert os.path.isfile(input_tables.rootzone_depth)
        assert os.path.isfile(input_tables.kc_min)
        assert os.path.isfile(input_tables.kc_max)

    @pytest.mark.unit
    def test_input_table_files_empty(self, fs):
        fs.create_file("/path/to/rainy_days.csv")
        fs.create_file("/path/to/a_i.csv")
        fs.create_file("/path/to/a_o.csv")
        fs.create_file("/path/to/a_s.csv")
        fs.create_file("/path/to/a_v.csv")
        fs.create_file("/path/to/manning.csv")
        fs.create_file("/path/to/bulk_density.csv")
        fs.create_file("/path/to/k_sat.csv")
        fs.create_file("/path/to/t_fcap.csv")
        fs.create_file("/path/to/t_sat.csv")
        fs.create_file("/path/to/t_wp.csv")
        fs.create_file("/path/to/rootzone_depth.csv")
        fs.create_file("/path/to/kc_min.csv")
        fs.create_file("/path/to/kc_max.csv")
        with pytest.raises(Exception):
            _ = InputTableFiles(
                rainy_days="/path/to/rainy_days.csv",
                a_i="/path/to/a_i.csv",
                a_o="/path/to/a_o.csv",
                a_s="/path/to/a_s.csv",
                a_v="/path/to/a_v.csv",
                manning="/path/to/manning.csv",
                bulk_density="/path/to/bulk_density.csv",
                k_sat="/path/to/k_sat.csv",
                t_fcap="/path/to/t_fcap.csv",
                t_sat="/path/to/t_sat.csv",
                t_wp="/path/to/t_wp.csv",
                rootzone_depth="/path/to/rootzone_depth.csv",
                kc_min="/path/to/kc_min.csv",
                kc_max="/path/to/kc_max.csv",
                validate_input=True,
            )
