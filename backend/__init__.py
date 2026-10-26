"""AutoClip backend, CLI, and MCP package."""
__version__ = "1.5.8"

# take the shutdown-intent secret out of os.environ before anything can spawn a child.
from backend.core import launch_token as _launch_token  # noqa: E402,F401
