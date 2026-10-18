"""M17 ground decoder, full path: Ch10 recording -> contract ``param.samples`` (arch §6 M17, AD-12, AD-38).

Independent of M15/M16 code: it reads the recording's own TMATS and the M01 dictionary only. See README.md.
"""

from .decode import (
    PROVENANCE,
    DecoderConfig,
    DecodeReport,
    DecoderError,
    DecodeResult,
    cumulative_sequence,
    decode_recording,
)
from .reader import Ch10File, Packet, read_file
from .setup import DecoderSetup, SetupMismatch, parse_tmats, setup_from_tmats
from .timebase import TimeBase

__all__ = [
    "PROVENANCE",
    "Ch10File",
    "DecodeReport",
    "DecodeResult",
    "DecoderConfig",
    "DecoderError",
    "DecoderSetup",
    "Packet",
    "SetupMismatch",
    "TimeBase",
    "cumulative_sequence",
    "decode_recording",
    "parse_tmats",
    "read_file",
    "setup_from_tmats",
]
