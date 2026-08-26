import pytest

from rubem.configuration.output_format import OutputFileFormat
from rubem.configuration.output_variables import VARIABLE_IDS, OutputVariable, OutputVariables


class TestOutputVariables:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "itp, bfw, srn, eta, lfw, rec, smc, rnf, tss, output_format",
        [
            (True, True, True, True, True, True, True, True, True, OutputFileFormat.PCRASTER),
            (True, True, True, True, True, True, True, True, True, OutputFileFormat.GEOTIFF),
            (
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                OutputFileFormat.PCRASTER,
            ),
            (
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                False,
                OutputFileFormat.GEOTIFF,
            ),
        ],
    )
    def test_output_variables_constructor(
        self, itp, bfw, srn, eta, lfw, rec, smc, rnf, tss, output_format
    ):
        _ = OutputVariables(
            itp=itp,
            bfw=bfw,
            srn=srn,
            eta=eta,
            lfw=lfw,
            rec=rec,
            smc=smc,
            rnf=rnf,
            tss=tss,
            output_formats=output_format,
        )


class TestOutputVariablesStr:
    @pytest.mark.unit
    def test_str_reflects_the_enablement_flags(self):
        variables = OutputVariables(itp=False, arn=True, tss=False)
        text = str(variables)
        assert "Total Interception (ITP): Disabled" in text
        assert "Accumulated Total Runoff (ARN): Enabled" in text
        assert "Create time output time series (TSS): Disabled" in text


class TestOutputVariableObjects:
    @pytest.mark.unit
    def test_flags_expand_into_variable_objects(self):
        variables = OutputVariables(itp=True, arn=True, tss=True)

        assert isinstance(variables.itp, OutputVariable)
        assert variables.itp.id == "itp"
        assert variables.itp.raster_filename_prefix == "itp"
        assert variables.itp.table_filename_prefix == "tss_itp"
        assert variables.itp.is_raster_series_enabled and variables.itp.is_time_series_enabled
        assert not variables.bfw.is_raster_series_enabled
        assert not variables.bfw.is_time_series_enabled

    @pytest.mark.unit
    def test_time_series_need_tss_and_the_variable(self):
        variables = OutputVariables(itp=True, tss=False)

        assert variables.itp.is_raster_series_enabled
        assert not variables.itp.is_time_series_enabled
        assert variables.get_enabled_time_series() == []
        assert [v.id for v in variables.get_enabled_raster_series()] == ["itp"]

    @pytest.mark.unit
    def test_variables_keep_the_documented_order(self):
        variables = OutputVariables(**{name: True for name in VARIABLE_IDS}, tss=True)

        assert tuple(v.id for v in variables.variables) == VARIABLE_IDS
        assert variables.all_enabled() and variables.any_enabled()
        assert len(variables.get_enabled_time_series()) == 9

    @pytest.mark.unit
    def test_nothing_enabled(self):
        variables = OutputVariables()

        assert not variables.any_enabled() and not variables.all_enabled()
        assert variables.file_formats == OutputFileFormat.PCRASTER
        assert variables.no_data_value == -9999

    @pytest.mark.unit
    def test_dictionary_access_is_deprecated(self):
        variables = OutputVariables(itp=True)

        with pytest.warns(DeprecationWarning, match="OutputVariable.get"):
            assert variables.itp.get("id") == "itp"
        with pytest.warns(DeprecationWarning):
            assert variables.itp.get("missing", "default") == "default"

    @pytest.mark.unit
    def test_is_frozen_and_rejects_unknown_fields(self):
        from pydantic import ValidationError

        variables = OutputVariables(itp=True)

        with pytest.raises(ValidationError):
            variables.tss = True
        with pytest.raises(ValidationError):
            OutputVariables(itp=True, xyz=True)

    @pytest.mark.unit
    def test_round_trips_through_model_dump(self):
        variables = OutputVariables(itp=True, tss=True, output_formats=OutputFileFormat.GEOTIFF)

        rebuilt = OutputVariables.model_validate(variables.model_dump())

        assert rebuilt == variables
        assert rebuilt.itp.is_time_series_enabled


class TestTssBoolSemantics:
    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, expected", [("false", False), ("0", False), ("true", True), (1, True)]
    )
    def test_tss_uses_pydantic_bool_semantics_not_pythons(self, value, expected):
        variables = OutputVariables(itp=True, tss=value)

        assert variables.tss is expected
        assert variables.itp.is_time_series_enabled is expected

    @pytest.mark.unit
    def test_an_unparsable_tss_string_is_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OutputVariables(itp=True, tss="not-a-boolean")

    @pytest.mark.unit
    @pytest.mark.parametrize(
        "value, expected",
        [("false", False), ("0", False), ("no", False), (0, False), ("true", True), (1, True)],
    )
    def test_variable_flags_use_pydantic_bool_semantics_not_pythons(self, value, expected):
        variables = OutputVariables(itp=value, tss=True)

        assert variables.itp.is_raster_series_enabled is expected
        assert variables.itp.is_time_series_enabled is expected

    @pytest.mark.unit
    def test_an_unparsable_variable_flag_is_rejected(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            OutputVariables(itp="not-a-boolean")


class TestNestedObjectConsistency:
    @pytest.mark.unit
    def test_an_explicit_tss_false_overrides_nested_objects_and_dicts(self):
        variables = OutputVariables(
            itp=OutputVariable(
                id="itp",
                is_raster_series_enabled=True,
                is_time_series_enabled=True,
                raster_filename_prefix="itp",
                table_filename_prefix="tss_itp",
            ),
            bfw={
                "id": "bfw",
                "is_raster_series_enabled": True,
                "is_time_series_enabled": True,
                "raster_filename_prefix": "bfw",
                "table_filename_prefix": "tss_bfw",
            },
            tss=False,
        )

        assert variables.tss is False
        assert variables.itp.is_raster_series_enabled
        assert not variables.itp.is_time_series_enabled
        assert not variables.bfw.is_time_series_enabled

    @pytest.mark.unit
    def test_nested_ids_must_match_their_field_name(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="mismatched"):
            OutputVariables(
                bfw=OutputVariable(
                    id="itp",
                    is_raster_series_enabled=True,
                    is_time_series_enabled=False,
                    raster_filename_prefix="bfw",
                    table_filename_prefix="tss_bfw",
                )
            )
