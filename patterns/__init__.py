from .base import Signal, PatternDetector
from .double_bottom      import DoubleBottomDetector
from .volume_breakout    import VolumeBreakoutDetector
from .rsi_divergence     import RSIDivergenceDetector
from .vwap_deviation     import VWAPDeviationDetector
from .squeeze_breakout   import SqueezeBreakoutDetector

ALL_DETECTORS: list[type[PatternDetector]] = [
    DoubleBottomDetector,
    VolumeBreakoutDetector,
    RSIDivergenceDetector,
    VWAPDeviationDetector,
    SqueezeBreakoutDetector,
]
