from prism_api.schemas.log import commit_url


def test_commit_url() -> None:
    assert commit_url("https://github.com/org/linux", "abc1234") == \
        "https://github.com/org/linux/commit/abc1234"
    assert commit_url("https://github.com/org/linux/", "abc1234") == \
        "https://github.com/org/linux/commit/abc1234"
    assert commit_url(None, "abc1234") is None
    assert commit_url("https://x", None) is None
