"""Dictionary channels produced by the avionics extension (AD-51) and their output columns.

Each recorded channel is published as an output port ``rec_<channel>`` (SI, or dimensionless for status
words) listed in ``ports.RECORDED`` (AD-42 convention); numeric channels also publish their true measurand as
``tru_<channel>`` (restricted: CIR ``truth_value`` only, never a consumer topic).
"""

from __future__ import annotations

from . import adc as A
from . import ahrs as H
from . import ins as N

#: INS numeric outputs, in ins.OUT_NAMES order
INS_CHANNELS = (
    "NAV.INS.LAT",
    "NAV.INS.LON",
    "NAV.INS.ALT",
    "NAV.INS.VN",
    "NAV.INS.VE",
    "NAV.INS.VD",
    "NAV.INS.HDG_TRUE",
    "NAV.INS.PITCH",
    "NAV.INS.ROLL",
    "NAV.INS.ACCEL.X",
    "NAV.INS.ACCEL.Y",
    "NAV.INS.ACCEL.Z",
    "NAV.INS.BODY_RATES.P_NB",
    "NAV.INS.BODY_RATES.Q_NB",
    "NAV.INS.BODY_RATES.R_NB",
    "NAV.INS.BODY_RATES.P_WB",
    "NAV.INS.BODY_RATES.Q_WB",
    "NAV.INS.BODY_RATES.R_WB",
)
#: INS/GPS status words, in ins_kernel status column order (columns 0-2)
INS_STATUS_CHANNELS = ("NAV.GPS.STATUS.INS_MODE", "NAV.GPS.STATUS.GPS_FIX", "NAV.GPS.STATUS.FOM")
AHRS_CHANNELS = ("NAV.AHRS.HEADING", "NAV.AHRS.PITCH", "NAV.AHRS.ROLL")
RADALT_CHANNEL = "NAV.RADALT"
ADC_CHANNELS = A.OUT_CHANNELS
ADC_VALID_CHANNELS = A.VALID_CHANNELS
SMS_STATION_CHANNELS = tuple(f"STORES.CONFIG.STATION_{k}" for k in range(1, 10))
SMS_RELEASE_CHANNEL = "STORES.CONFIG.RELEASE"

#: numeric channels (float ports + truth companions)
NUMERIC = (*INS_CHANNELS, *AHRS_CHANNELS, RADALT_CHANNEL, *ADC_CHANNELS)
#: status / discrete words (int ports, no truth companion: the word is its own truth)
WORDS = (*INS_STATUS_CHANNELS, *ADC_VALID_CHANNELS, *SMS_STATION_CHANNELS, SMS_RELEASE_CHANNEL)
ALL = (*NUMERIC, *WORDS)

assert len(INS_CHANNELS) == N.N_OUT and len(AHRS_CHANNELS) == H.N_OUT


def rec_port(channel_id: str) -> str:
    """Output port of a recorded channel: ``NAV.INS.LAT`` -> ``rec_nav_ins_lat``."""
    return "rec_" + channel_id.lower().replace(".", "_")


def tru_port(channel_id: str) -> str:
    """Restricted truth companion of a numeric recorded channel."""
    return "tru_" + channel_id.lower().replace(".", "_")
