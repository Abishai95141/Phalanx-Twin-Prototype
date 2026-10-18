"""Synthetic engine channel group for one flight, from INPUTS ONLY (PREREGISTRATION section 6.4).

Inputs used: PLA_1..4, ALT, MACH, TAT and PH of the flight. Nothing in the flight's N1, N2, EGT or FF is read
(the caller passes a dict produced by r2common.load(path, with_outputs=False) plus the container dtypes, which
are file metadata, not output values).

Arms: R2a = M-A + M-B; R2b = M-A + M-C + M-B. Offsets: "prior" (primary: one virtual unseen tail drawn from
the fleet prior, key fixed per run) or "cal" (secondary: CAL-fitted offsets of each engine position).
Engine running state (inputs only): PH in 2..7 (taxi, take-off, climb, cruise, approach, rollout). Outside it the
channel holds its CAL engine-off reading (N1 per-position off reading; N2 0; FF 0; EGT = TAT + CAL median
offset); state is initialised at the steady value of each map when a running segment starts.
"""
import numpy as np

import r2common as R
import ma_model as MAM
import mb_model as MBM


def unit_params(ma, mode, tail_key="virtual_tail_1"):
    """4-vectors of unit parameters: 'prior' = one unseen virtual tail drawn from the fleet prior (primary);
    'cal' = CAL-fitted per position (secondary)."""
    if mode == "prior":
        return ma.draw_offsets(tail_key)
    if mode == "cal":
        return ma.cal_offsets()
    raise ValueError(mode)


def synth_flight(d, ma, mb, off_table, mode="prior", mc=None, tail_key="virtual_tail_1", return_parts=False):
    n = d["n"]
    run = MAM.running_mask_inputs(d)
    B = MAM.Batch([d], [run], with_outputs=False, min_len_s=0.25, burn_s=0.0)
    sim = ma.simulate(B, override=unit_params(ma, mode, tail_key))
    cont = {}
    for f in R.FAM:
        arr = np.zeros((4, n))
        for k in range(4):
            if f == "EGT":
                arr[k] = d["TAT"] + off_table["EGT_minus_TAT"][k]
            else:
                arr[k] = off_table[f][k]
        cont[f] = arr
    for f in R.FAM:
        cont[f][B.eng, B.idx] = sim[f]
    disc = None
    if mc is not None:
        disc = mc.simulate(run, d["fid"])            # {fam: (4, n)} coupled discrepancy, zero when not running
        for f in R.FAM:
            cont[f] = cont[f] + np.where(run, disc[f], 0.0)
    air = np.isin(d["PH"], [3, 4, 5, 6])
    Y = {}
    for f in R.FAM:
        rows = []
        for k in range(4):
            ch = f"{f}_{k + 1}"
            rows.append(mb.apply(ch, cont[f][k], run[k], air, d["fid"], truth_for_gate=cont[f][k]))
        Y[f] = np.vstack(rows)
    if return_parts:
        return Y, {"continuous": cont, "running": run, "discrepancy": disc}
    return Y


def off_state_table(flights):
    """CAL engine-off readings per position: median over PH == 1 samples (engines off at the gate)."""
    vals = {f: [[] for _ in range(4)] for f in R.FAM}
    egt = [[] for _ in range(4)]
    for d in flights:
        m = d["PH"] == 1
        if m.sum() < 20:
            continue
        for k in range(4):
            off = d["Y"]["N2"][k][m] < 5
            if off.sum() < 20:
                continue
            for f in ("N1", "N2", "FF"):
                vals[f][k].append(np.median(d["Y"][f][k][m][off]))
            egt[k].append(np.median(d["Y"]["EGT"][k][m][off] - d["TAT"][m][off]))
    out = {f: [float(np.median(v)) if v else 0.0 for v in vals[f]] for f in ("N1", "N2", "FF")}
    out["EGT_minus_TAT"] = [float(np.median(v)) if v else 0.0 for v in egt]
    return out


def to_containers(Y, dtypes):
    return {f"{f}_{k + 1}": MBM.cast(Y[f][k], dtypes[f"{f}_{k + 1}"]) for f in R.FAM for k in range(4)}
