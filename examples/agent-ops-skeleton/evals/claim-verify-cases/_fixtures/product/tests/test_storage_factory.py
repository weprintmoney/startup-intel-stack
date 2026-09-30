from example_app.storage.factory import SUPPORTED_BACKENDS, make_store


def test_supported_backends_is_closed_set():
    assert SUPPORTED_BACKENDS == ("memory", "disk", "s3")


def test_unknown_backend_raises():
    import pytest
    with pytest.raises(ValueError):
        make_store("postgres")
