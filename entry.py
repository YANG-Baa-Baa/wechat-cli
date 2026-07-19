"""PyInstaller entry point — avoids relative import issues."""

import os
import sys

from wechat_cli.main import cli


def _should_pause_on_exit():
    return getattr(sys, "frozen", False) and os.name == "nt" and len(sys.argv) == 1


if __name__ == "__main__":
    pause = _should_pause_on_exit()
    try:
        cli()
    finally:
        if pause:
            input("\nPress Enter to exit...")
