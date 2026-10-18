"""M09 consumes M18 `mx.action` MODs (AD-44): known mod_ids change config; other actions are no-ops."""

from __future__ import annotations

import numpy as np
import pytest
from test_utilities_support import event, module

from phalanx.utilities import UtilitiesConfig
from phalanx.utilities import layout as L
from phalanx.utilities.module import MOD_EFFECTS


@pytest.mark.unit
def test_mx_action_mod_embodies_known_modifications():
    m, st = module(UtilitiesConfig(f1a_mod=0, jfs_variant=1))
    assert int(st["i"][L.I_F1A_MOD]) == 0 and int(st["i"][L.I_JFS_VARIANT]) == 1
    st2, _ = m.on_event(st, event("mx.action", tail="T1", action="MOD", mod_id="F1A_PICKUP_MOD"), 0)
    assert int(st2["i"][L.I_F1A_MOD]) == 1
    st3, _ = m.on_event(st, event("mx.action", tail="T1", action="MOD", mod_id="GTSU110_M2"), 0)
    assert int(st3["i"][L.I_JFS_VARIANT]) == 2


@pytest.mark.unit
def test_mx_action_without_m09_effect_is_a_no_op():
    m, st = module()
    for pl in (
        {"tail": "T1", "action": "RR", "pos": "ENG", "serial": "X1", "job_no": "J1"},
        {"tail": "T1", "action": "MOD", "mod_id": "SOME_AVIONICS_MOD"},
        {"tail": "T1", "action": "WASH", "pos": "ENG", "job_no": "J2"},
    ):
        st2, _ = m.on_event(st, event("mx.action", **pl), 0)
        assert np.array_equal(st2["i"], st["i"]) and np.array_equal(st2["f"], st["f"]), pl
    assert set(MOD_EFFECTS) == {"F1A_PICKUP_MOD", "GTSU110_M2"}
