"""Physical constants used throughout the package."""

import math

# Speed of light in vacuum [m/s]
C = 299_792_458.0
C_LIGHT = C  # Alias for clarity

# Boltzmann constant [J/K]
K_B = 1.380649e-23

# Standard reference temperature [K]
T_REF = 290.0

# Pi (for convenience)
PI = math.pi


# Conversion functions
def db_to_linear(db: float) -> float:
    """Convert dB to linear scale (power)."""
    return 10 ** (db / 10)


def linear_to_db(linear: float) -> float:
    """Convert linear scale to dB (power)."""
    return 10 * math.log10(linear) if linear > 0 else float("-inf")


def dbw_to_w(dbw: float) -> float:
    """Convert dBW to Watts."""
    return 10 ** (dbw / 10)


def w_to_dbw(w: float) -> float:
    """Convert Watts to dBW."""
    return 10 * math.log10(w) if w > 0 else float("-inf")


def db_to_linear_voltage(db: float) -> float:
    """Convert dB to linear scale (voltage/amplitude)."""
    return 10 ** (db / 20)


def linear_to_db_voltage(linear: float) -> float:
    """Convert linear scale to dB (voltage/amplitude)."""
    return 20 * math.log10(linear) if linear > 0 else float("-inf")


# Backward-compatible aliases (uppercase)
DB_TO_LINEAR = db_to_linear
LINEAR_TO_DB = linear_to_db
DBW_TO_W = dbw_to_w
W_TO_DBW = w_to_dbw
DB_TO_LINEAR_VOLTAGE = db_to_linear_voltage
LINEAR_TO_DB_VOLTAGE = linear_to_db_voltage
