import os

from agent_platform.settings import Settings, get_settings

__all__ = ("Settings", "get_settings")

os.chdir(get_settings().root_dir)
