from pipeline.data_quality import DataQualityChecker


def test_checker_loads_expected_rows_from_config():
    checker = DataQualityChecker(
        master_csv="data/raw/idx_daily_prices_2002_2007.csv",
        split_log_csv="data/reference/corporate_action_split_log.csv",
    )
    assert checker.expected_rows["ASII"] == 1564
    assert checker.quality_rules is not None
    assert checker.quality_rules.apply_split_adjustment is False


def test_checker_falls_back_when_config_missing():
    checker = DataQualityChecker(
        master_csv="data/raw/idx_daily_prices_2002_2007.csv",
        split_log_csv="data/reference/corporate_action_split_log.csv",
        quality_rules_path="config/does_not_exist.yaml",
    )
    # Falls back to hardcoded defaults rather than crashing
    assert checker.expected_rows["ASII"] == 1564
    assert checker.quality_rules is None
