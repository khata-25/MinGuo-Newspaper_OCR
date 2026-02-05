from dataclasses import dataclass
from typing import Tuple, Optional
import numpy as np

@dataclass
class LayoutRegion:
    bbox: Tuple[int, int, int, int]
    region_type: str
    confidence: float
    order: int
    image: Optional[np.ndarray] = None
    text: Optional[str] = None
