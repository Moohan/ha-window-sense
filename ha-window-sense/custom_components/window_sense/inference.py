"""Inference engine module for Window Sense Home Assistant integration."""
from __future__ import annotations

try:
    from window_sense.inference import (
        AdaptiveBaselineModel,
        PageHinkleyChangePoint,
        WindowState,
        WindowInferenceEngine,
    )
except ImportError:
    import sys
    from pathlib import Path
    root_dir = str(Path(__file__).resolve().parents[2])
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
    from window_sense.inference import (
        AdaptiveBaselineModel,
        PageHinkleyChangePoint,
        WindowState,
        WindowInferenceEngine,
    )

__all__ = [
    "AdaptiveBaselineModel",
    "PageHinkleyChangePoint",
    "WindowState",
    "WindowInferenceEngine",
]
