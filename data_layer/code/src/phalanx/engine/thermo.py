"""Humid-air and combustion-products thermodynamics for M07 (frozen composition,
NASA 9-coefficient polynomials).

Evidence: species polynomials are NASA Glenn thermodynamic data (McBride, Zehe & Gordon 2002,
NASA/TP-2002-211556)
as distributed in pyCycle ``thermo/cea/thermo_data/janaf.py`` (Apache-2.0, commit ``ee7e161``)
[TRANSFER: NASA Glenn / pyCycle]. Jet-A is represented as C12H23 (pyCycle's ``Jet-A(g)`` reactant definition).
Dry-air composition is the US Standard Atmosphere 1976 sea-level mole fractions [DIRECT standard].

Method (architecture §6 M07 "humid-air thermodynamics"):

- Any gas in the engine is a mixture of three **basis compositions** per kg of dry air: 1 kg dry air,
``f`` kg of
  "burnt-fuel delta" (CO2 + H2O produced minus O2 consumed per kg of C12H23 burnt) and ``w`` kg of water
  vapour
  (humidity ratio). Mass-specific properties are ``X = (X_air + f X_pd + w X_h2o) / (1 + f + w)``.
- Enthalpies are **sensible** (zero at 298.15 K for every basis); heat release is added as ``eta * Wf * LHV``.
- Isentropic processes use the entropy function ``phi(T) = s°(T)`` with ``phi(T2s) = phi(T1) + R ln(P2/P1)``.

All functions are scalar, ``@njit``, dtype-generic and complex-step safe (branches on ``.real`` only, no
``abs``/``min``/``max``), so the same source serves float64 simulation and complex128 Jacobians (AD-22,
AD-34).
"""

from __future__ import annotations

import numpy as np
from numba import njit

R_UNIVERSAL = 8.314462618  # J/(mol K), CODATA 2018 (exact SI definition)
T_REF_SENSIBLE = 298.15  # K, sensible-enthalpy datum
T_RANGE_SPLIT = 1000.0  # K, NASA-9 range boundary
SPECIES = ("N2", "O2", "Ar", "CO2", "H2O")
# US Standard Atmosphere 1976 dry-air mole fractions (N2, O2, Ar, CO2), normalised to 1
AIR_MOLE_FRACTIONS = (0.78084, 0.209476, 0.00934, 0.000314)
FUEL_C, FUEL_H = 12.0, 23.0  # C12H23 (pyCycle Jet-A(g))
N_BASIS = 3  # dry air, burnt-fuel delta, water vapour
T_MIN_GUARD = 100.0  # K, Newton iterate guard (abnormal transients only)
T_MAX_GUARD = 5500.0  # K
NEWTON_T = 2  # Newton iterations for T(h) and T(phi); accuracy tested in tests/unit/test_engine_thermo.py

_JIT = {"cache": True, "fastmath": False, "error_model": "numpy", "nogil": True}


def species_table_to_coeffs(table: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Reshape the loaded ``nasa9_species.csv`` columns into ``a[species, range,
    9]`` and ``molar_mass[species]``
    (kg/mol). Columns a1..a7, b1, b2 are dimensionless (cp/R form)."""
    sid = np.asarray(table["species_id"]).astype(int)
    rid = np.asarray(table["range_id"]).astype(int)
    a = np.zeros((len(SPECIES), 2, 9))
    mm = np.zeros(len(SPECIES))
    cols = ["a1", "a2", "a3", "a4", "a5", "a6", "a7", "b1", "b2"]
    for row in range(sid.size):
        for j, c in enumerate(cols):
            a[sid[row], rid[row], j] = table[c][row]
        mm[sid[row]] = table["molar_mass"][row] * 1e-3  # g/mol -> kg/mol
    return a, mm


def basis_coefficients(a: np.ndarray, molar_mass: np.ndarray) -> np.ndarray:
    """Mass-specific basis coefficients ``B[basis, range, 10]``.

    Entries 0..6: cp polynomial (J/kg/K); 7: enthalpy constant (sensible, J/kg); 8: entropy constant (J/kg/K);
    9: gas constant contribution (J/kg/K). Basis 0 = 1 kg dry air; 1 = burnt-fuel delta per kg fuel;
    2 = 1 kg water vapour.
    """
    n2, o2, ar, co2, h2o = range(5)
    x = np.asarray(AIR_MOLE_FRACTIONS, float)
    x = x / x.sum()
    air_sp = np.array([n2, o2, ar, co2])
    m_air = x * molar_mass[air_sp]
    y_air = np.zeros(5)
    y_air[air_sp] = m_air / m_air.sum()
    # C12H23 + 17.75 O2 -> 12 CO2 + 11.5 H2O, per kg fuel (species weights from the same table)
    m_fuel = FUEL_C * (molar_mass[co2] - molar_mass[o2]) + FUEL_H / 2.0 * (
        molar_mass[h2o] - molar_mass[o2] / 2.0
    )
    y_pd = np.zeros(5)
    y_pd[co2] = FUEL_C * molar_mass[co2] / m_fuel
    y_pd[h2o] = FUEL_H / 2.0 * molar_mass[h2o] / m_fuel
    y_pd[o2] = -(FUEL_C + FUEL_H / 4.0) * molar_mass[o2] / m_fuel
    y_w = np.zeros(5)
    y_w[h2o] = 1.0
    B = np.zeros((N_BASIS, 2, 10))
    for k, y in enumerate((y_air, y_pd, y_w)):
        rs = y * R_UNIVERSAL / molar_mass  # J/kg/K per species weight
        for r in (0, 1):
            B[k, r, :9] = rs @ a[:, r, :]
            B[k, r, 9] = rs.sum()
        # sensible enthalpy datum: h(298.15) = 0 (low range), same shift applied to both ranges
        h_ref = _poly_h(B[k, 0], T_REF_SENSIBLE)
        B[k, :, 7] -= h_ref
    return B


def fuel_molar_mass(molar_mass: np.ndarray) -> float:
    """C12H23 molar mass consistent with the species table (kg/mol)."""
    return FUEL_C * (molar_mass[3] - molar_mass[1]) + FUEL_H / 2.0 * (molar_mass[4] - molar_mass[1] / 2.0)


def _poly_h(c: np.ndarray, T: float) -> float:
    """Reference (Python) enthalpy polynomial with constant c[7] (used to build the datum)."""
    return (
        -c[0] / T
        + c[1] * np.log(T)
        + c[2] * T
        + c[3] * T**2 / 2
        + c[4] * T**3 / 3
        + c[5] * T**4 / 4
        + c[6] * T**5 / 5
        + c[7]
    )


# ------------------------------------------------------------------------------------------------- kernels


@njit(**_JIT)
def _basis_hcp(c, Ti, lnT, T, T2, T3, T4):
    cp = c[0] * Ti * Ti + c[1] * Ti + c[2] + c[3] * T + c[4] * T2 + c[5] * T3 + c[6] * T4
    h = (
        -c[0] * Ti
        + c[1] * lnT
        + c[2] * T
        + c[3] * T2 * 0.5
        + c[4] * T3 / 3.0
        + c[5] * T4 * 0.25
        + c[6] * T4 * T * 0.2
        + c[7]
    )
    return h, cp


@njit(**_JIT)
def _basis_phicp(c, Ti, lnT, T, T2, T3, T4):
    cp = c[0] * Ti * Ti + c[1] * Ti + c[2] + c[3] * T + c[4] * T2 + c[5] * T3 + c[6] * T4
    phi = (
        -c[0] * Ti * Ti * 0.5
        - c[1] * Ti
        + c[2] * lnT
        + c[3] * T
        + c[4] * T2 * 0.5
        + c[5] * T3 / 3.0
        + c[6] * T4 * 0.25
        + c[8]
    )
    return phi, cp


@njit(**_JIT)
def h_cp(T, f, w, B):
    """Sensible enthalpy (J/kg) and cp (J/kg/K) of the mixture (f, w per kg dry air) at T (K)."""
    r = 0
    if T.real >= T_RANGE_SPLIT:
        r = 1
    Ti = 1.0 / T
    lnT = np.log(T)
    T2 = T * T
    T3 = T2 * T
    T4 = T3 * T
    h0, c0 = _basis_hcp(B[0, r], Ti, lnT, T, T2, T3, T4)
    h1, c1 = _basis_hcp(B[1, r], Ti, lnT, T, T2, T3, T4)
    h2, c2 = _basis_hcp(B[2, r], Ti, lnT, T, T2, T3, T4)
    inv = 1.0 / (1.0 + f + w)
    return (h0 + f * h1 + w * h2) * inv, (c0 + f * c1 + w * c2) * inv


@njit(**_JIT)
def phi_cp(T, f, w, B):
    """Entropy function s°(T) (J/kg/K) and cp (J/kg/K) of the mixture."""
    r = 0
    if T.real >= T_RANGE_SPLIT:
        r = 1
    Ti = 1.0 / T
    lnT = np.log(T)
    T2 = T * T
    T3 = T2 * T
    T4 = T3 * T
    p0, c0 = _basis_phicp(B[0, r], Ti, lnT, T, T2, T3, T4)
    p1, c1 = _basis_phicp(B[1, r], Ti, lnT, T, T2, T3, T4)
    p2, c2 = _basis_phicp(B[2, r], Ti, lnT, T, T2, T3, T4)
    inv = 1.0 / (1.0 + f + w)
    return (p0 + f * p1 + w * p2) * inv, (c0 + f * c1 + w * c2) * inv


@njit(**_JIT)
def gas_r(f, w, B):
    """Gas constant (J/kg/K) of the mixture."""
    return (B[0, 0, 9] + f * B[1, 0, 9] + w * B[2, 0, 9]) / (1.0 + f + w)


@njit(**_JIT)
def _t_guard(T):
    """Keep Newton iterates inside the polynomial range (guards abnormal transients; inactive normally)."""
    if T.real < T_MIN_GUARD:
        return T_MIN_GUARD + 0.0 * T
    if T.real > T_MAX_GUARD:
        return T_MAX_GUARD + 0.0 * T
    return T


@njit(**_JIT)
def t_from_h(h, f, w, B, T0):
    """Temperature (K) with sensible enthalpy h; Newton from the initial guess T0 (NEWTON_T iterations)."""
    T = _t_guard(T0 + 0.0 * h)
    for _ in range(NEWTON_T):
        hh, cp = h_cp(T, f, w, B)
        T = _t_guard(T - (hh - h) / cp)
    return T


@njit(**_JIT)
def t_from_phi(phi, f, w, B, T0):
    """Temperature (K) with entropy function phi; Newton (derivative cp/T) from T0."""
    T = _t_guard(T0 + 0.0 * phi)
    for _ in range(NEWTON_T):
        pp, cp = phi_cp(T, f, w, B)
        T = _t_guard(T - (pp - phi) * T / cp)
    return T


@njit(**_JIT)
def compress(T1, pr, eta, f, w, B):
    """Adiabatic compression with isentropic efficiency eta. Returns (T2, dh) with dh = h2 - h1 > 0."""
    R = gas_r(f, w, B)
    p1, cp1 = phi_cp(T1, f, w, B)
    h1, _ = h_cp(T1, f, w, B)
    g = cp1 / (cp1 - R)
    t2s0 = T1 * pr ** ((g - 1.0) / g)
    t2s = t_from_phi(p1 + R * np.log(pr), f, w, B, t2s0)
    h2s, _ = h_cp(t2s, f, w, B)
    dh = (h2s - h1) / eta
    T2 = t_from_h(h1 + dh, f, w, B, T1 + (t2s - T1) / eta)
    return T2, dh


@njit(**_JIT)
def expand(T1, pr, eta, f, w, B):
    """Adiabatic expansion over pressure ratio pr = P1/P2 > 1. Returns (T2, dh) with dh = h1 - h2 > 0."""
    R = gas_r(f, w, B)
    p1, cp1 = phi_cp(T1, f, w, B)
    h1, _ = h_cp(T1, f, w, B)
    g = cp1 / (cp1 - R)
    t2s0 = T1 * pr ** (-(g - 1.0) / g)
    t2s = t_from_phi(p1 - R * np.log(pr), f, w, B, t2s0)
    h2s, _ = h_cp(t2s, f, w, B)
    dh = eta * (h1 - h2s)
    T2 = t_from_h(h1 - dh, f, w, B, T1 - eta * (T1 - t2s))
    return T2, dh


@njit(**_JIT)
def gamma_of(T, f, w, B):
    _, cp = h_cp(T, f, w, B)
    R = gas_r(f, w, B)
    return cp / (cp - R)
