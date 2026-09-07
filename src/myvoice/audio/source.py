from collections.abc import Generator
from typing import Protocol

import numpy as np


class AudioSource(Protocol):
    def stream(self) -> Generator[np.ndarray, None, None]:
        ...
