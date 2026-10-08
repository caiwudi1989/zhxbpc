"""Generic PC script IDE core package.

The package is deliberately independent from the legacy business application.
It owns project files, the form model, script execution, plugins, vision mocks,
and incremental build metadata.
"""

from .paths import IDE_VERSION, Paths

__all__ = ["IDE_VERSION", "Paths"]
