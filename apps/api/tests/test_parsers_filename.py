from prism_api.parsers.filename import ArtifactOwner, parse_artifact_filename


def test_run_level() -> None:
    got = parse_artifact_filename("readme.log")
    assert got == ArtifactOwner(scope="run", suite=None, case=None, label="readme", ext=".log")


def test_suite_level() -> None:
    got = parse_artifact_filename("dsp__suite-log.log")
    assert got == ArtifactOwner(scope="suite", suite="dsp", case=None, label="suite-log", ext=".log")


def test_case_level() -> None:
    got = parse_artifact_filename("dsp__sine_sweep_1khz__waveform.csv")
    assert got == ArtifactOwner(scope="case", suite="dsp", case="sine_sweep_1khz", label="waveform", ext=".csv")


def test_case_level_with_label_underscores() -> None:
    got = parse_artifact_filename("dsp__sine__fft_magnitude.csv")
    # label can contain single underscores — only `__` delimits scopes
    assert got.scope == "case"
    assert got.case == "sine"
    assert got.label == "fft_magnitude"
