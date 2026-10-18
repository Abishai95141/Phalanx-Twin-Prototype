"""M13 idiosyncratic noise (acceptance A3) and the noise ceiling (W0.5 finding; A-W1.6-22, A-W1.6-23).

Noise-ceiling rule: adding independent noise at +-1 LSB to real flights FAILs B1, B3 (i) and B4, because the
fast band is quantisation-dominated. M13's configured effective sigma must therefore stay at or below the
measured idiosyncratic level of its class (N1 0.0313 %, N2 0.0082 %, EGT 0, FF 0 on 687-CAL; q/sqrt(12)
otherwise). The behavioural version on real flights is
``tests/integration/test_acquisition_noise_ceiling_data.py`` (data, slow).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from phalanx.acquisition import kernel as K
from phalanx.acquisition.config import build_acquisition_config, effective_sigma
from phalanx.core.module import ContractError
from phalanx.dictionary import load_dictionary
from phalanx.dictionary.params import load_params
from phalanx.sensors.config import build_sensor_config


@pytest.fixture(scope="module")
def d():
    return load_dictionary()


@pytest.fixture(scope="module")
def sens(d):
    return build_sensor_config(d)


@pytest.mark.unit
def test_noise_ceiling_holds_for_tejas_configuration(d, sens):
    """Every Tejas sensor channel: effective sigma <= its class ceiling; measured-zero classes (T5, WFM) carry
    no noise; N1/N2 sit below the proxy maxima."""
    acq = build_acquisition_config(d, sens.channels, sensor_channels=sens.channels)
    assert np.all(acq.sigma_eff_eu <= acq.ceiling_eu * (1 + 1e-12))
    for c, cid in enumerate(acq.channels):
        if cid.startswith(("ENG.T5", "ENG.WFM")):
            assert acq.P[c, K.AP_SIGMA] == 0.0
        if cid.startswith("ENG.N1."):
            assert acq.sigma_eff_eu[c] < 0.0313
        if cid.startswith("ENG.N2."):
            assert acq.sigma_eff_eu[c] < 0.0083
        # at or below the quantiser variance of the recorded-word step, the step the evidence is measured on;
        # a FADEC lane's native step is the finer FADEC converter step (dictionary 0.1.3, R-FADEC-ADC), so its
        # word step is the recorder LSB of the voted word
        ch = d.channel(cid)
        if ch["native_step"] is None:  # a discrete word (W2.2 word path, ENG.AB_LIT): no noise at all
            assert acq.sigma_eff_eu[c] == 0.0
            continue
        fadec_lane = ch["prov"]["native_step"] == "R-FADEC-ADC"
        word_step = float(
            d.channel(f"{ch['measurand_id']}.V")["recorder_lsb"] if fadec_lane else ch["native_step"]
        )
        assert acq.sigma_eff_eu[c] <= word_step / math.sqrt(12.0) or cid.startswith("ENG.N1.")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("set_name", "edit", "channel"),
    [
        ("noise_n1", {"sigma_eu": 1.2 * 0.03125}, "ENG.N1.A"),  # above the measured N1 maximum (1.0 step)
        ("noise_n1", {"regime_mult": [1.0, 1.0, 1.0, 2.0] + [1.0] * 12}, "ENG.N1.A"),  # 0.61 x 2
        ("noise_n1", {"tail_p": 0.2, "tail_k": 5.0}, "ENG.N1.A"),  # tail variance inflation
        ("noise_egt", {"sigma_steps": 0.577}, "ENG.T5.HARNESS_A"),  # +-1 LSB uniform (sigma 1/sqrt(3))
        ("noise_default", {"sigma_steps": 0.5}, "ENG.P5"),  # above q/sqrt(12)
        ("noise_fadec_ps3", {"sigma_eu": 0.5 * 0.5}, "ENG.PS3.A"),  # converter-step lane, EU noise (W2.2)
    ],
)
def test_config_refuses_noise_above_ceiling(d, sens, set_name, edit, channel):
    """Negative tests: the builder refuses any configuration whose effective sigma exceeds the ceiling,
    including through phase multipliers and the heavy-tail mixture, and the +-1 LSB noise of the W0.5
    finding."""
    p = load_params("M13")
    ps = p[set_name]
    if "sigma_steps" in edit and ps["sigma_steps"].tag.kind == "MEASURED":
        from phalanx.core.module import Param, ParamSet

        new = dict(ps)
        new["sigma_steps"] = Param(edit["sigma_steps"], "1", "ASSUMPTION", "test override")
        p[set_name] = ParamSet(ps.name, new)
    else:
        p[set_name] = ps.replace(**edit)
    with pytest.raises(ContractError, match="noise-ceiling"):
        build_acquisition_config(d, (channel,), sensor_channels=sens.channels, params=p)


@pytest.mark.unit
def test_effective_sigma_formula():
    assert effective_sigma(1.0, np.ones(8), 0.0, 3.0) == 1.0
    assert effective_sigma(2.0, np.array([1, 1, 1, 1.5, 1, 1, 1, 1.0]), 0.002, 3.0) == pytest.approx(
        3.0 * math.sqrt(1.016)
    )
