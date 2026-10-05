"""Backward-compatible request-schema facade.

Request contracts are grouped by presentation domain under
``apps.zte_manager.presentation.schemas``. Keep this import surface stable
while controllers and tests migrate incrementally.
"""

from apps.zte_manager.presentation.schemas import *  # noqa: F401,F403
