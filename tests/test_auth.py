from unittest.mock import patch

from agent_platform.auth.api_key import _load_api_keys


def test_load_api_keys_handles_invalid_json() -> None:
    with patch("agent_platform.auth.api_key.get_settings") as mock_settings:
        mock_settings.return_value.api_keys = "not-json"
        assert _load_api_keys() == {}
