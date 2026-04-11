"""Shared pytest fixtures."""

import numpy as np
import pytest


@pytest.fixture
def blank_frame() -> np.ndarray:
    """640×480 black BGR frame for testing."""
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def noise_frame() -> np.ndarray:
    """640×480 random noise BGR frame."""
    rng = np.random.default_rng(42)
    return rng.integers(0, 256, (480, 640, 3), dtype=np.uint8)
