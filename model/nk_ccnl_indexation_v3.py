"""
===============================================================================
NEW KEYNESIAN + SEARCH & MATCHING + CCNL INDEXATION / BARGAINING
Versione 3 - prototipo mensile per confronto istituzionale e ceteris paribus
===============================================================================

IDEA CENTRALE
-------------
Il modello lavora in DEVIAZIONI da un sentiero di base nel quale:
- esiste un'inflazione attesa positiva (default 2% annuo);
- i CCNL tradizionali hanno gia' incorporato l'inflazione prevista nelle tranche;
- lo shock rappresenta solo la sorpresa rispetto a quel sentiero.

Quindi, nel regime triennale, non assumiamo che il salario nominale resti fermo
per 36 mesi: gli aumenti previsti sono nel baseline e si elidono nelle IRF.
La parte che resta scoperta fino al rinnovo e' soltanto l'ERRORE di inflazione
rispetto alle previsioni del contratto precedente.

DUE MODALITA' DI ESPERIMENTO
---------------------------
1) institutional
   - SCALA MOBILE STYLE: aggiornamento mensile dell'intera retribuzione alla
     headline realizzata; bargaining separato ogni 36 mesi.
   - ANNUALE NEI: ogni giugno tutti i minimi recuperano l'IPCA-NEI effettivo
     dell'anno solare precedente; bargaining separato ogni 36 mesi.
   - TRADIZIONALE 36M: il contratto incorpora nel baseline l'inflazione prevista
     tramite tranche annuali; al rinnovo staggered recupera l'errore di inflazione
     passato + bargaining, e programma nuove tranche sulla previsione futura
     condizionata allo shock osservato.

2) frequency_only
   Stesso indice (NEI), stesso scope (minimo), stesso bargaining e stessi shock.
   Cambia soltanto la frequenza con cui coorti staggered recuperano l'inflazione
   passata: D = 1, 12, 36 mesi.

BENCHMARK "NONE"
----------------
Opzionale e separato dai grafici principali. Significa nessuna indicizzazione
automatica allo shock; restano wage drift e bargaining triennale.

DOWNWARD NOMINAL WAGE RIGIDITY
------------------------------
La componente contrattuale totale non puo' produrre una riduzione del salario
nominale. Il vincolo e' applicato al SALARIO TOTALE (baseline + deviazione), non
alla sola IRF. Una deviazione negativa e' quindi ammessa finche' l'aumento totale
resta >= 0.

ENERGIA -> CORE / IPCA-NEI
--------------------------
Lo shock energetico entra subito nell'headline, ma passa all'IPCA-NEI con ritardo
attraverso uno stato xenergy_core. In questo modo un rincaro persistente dell'
energia contamina progressivamente anche i prezzi degli altri beni/servizi.

METODO NUMERICO
---------------
Il blocco macro e' lineare dato un sentiero di crescita salariale contrattuale.
La regola salariale e il floor nominale rendono il sistema piecewise/nonlineare.
Usiamo quindi un fixed point:
  1. ipotizziamo un sentiero wpi_contract;
  2. risolviamo il sistema macro lineare con aspettative perfette;
  3. ricalcoliamo indicizzazione/catch-up/bargaining/floor;
  4. aggiorniamo il sentiero e ripetiamo.

Questo resta un PROTOTIPO. Non e' stimato sull'Italia e non sostituisce una
verifica QZ/Gensys/Blanchard-Kahn formale.
===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, Iterable, List, Literal, Tuple
import json
import math
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import splu


# =============================================================================
# 0. TIPI E UTILITA'
# =============================================================================

ShockType = Literal[
    "cost_push", "energy", "technology",
    "monetary_easing", "monetary_tightening",
]
ExperimentMode = Literal["institutional", "frequency_only"]
WageScope = Literal["minimum", "full"]
TimingMode = Literal["staggered", "synchronized"]
IndexBasis = Literal["headline", "nei", "none"]


def quarterly_persistence_to_monthly(rho_q: float) -> float:
    return rho_q ** (1.0 / 3.0)


def quarterly_event_probability_to_monthly(prob_q: float) -> float:
    return 1.0 - (1.0 - prob_q) ** (1.0 / 3.0)


def half_life_months(rho_m: float) -> float:
    if rho_m <= 0:
        return 0.0
    if rho_m >= 1:
        return np.inf
    return math.log(0.5) / math.log(rho_m)


# =============================================================================
# 1. PARAMETRI
# =============================================================================

@dataclass
class Parameters:
    # Famiglie / domanda
    beta_q: float = 1.0 / 1.0035
    sigma: float = 1.0
    habit_m: float = 0.35

    # Produzione / ore
    alpha: float = 0.70
    phi: float = 1.0

    # Prezzi / politica monetaria
    omega_q: float = 0.75
    phi_pi: float = 2.0
    phi_y: float = 0.05
    rho_i_q: float = 0.65
    policy_inflation_measure: Literal["headline", "nei"] = "headline"

    # Shock
    rho_a_q: float = 0.80
    rho_m_q: float = 0.20
    rho_cost_m: float = 0.55
    rho_energy_m: float = 0.75

    # Energia -> prezzi
    energy_weight_headline: float = 0.10
    energy_core_loading: float = 0.08
    rho_energy_core_m: float = 0.85

    # Mercato del lavoro
    separation_q: float = 0.10
    matching_elasticity_v: float = 0.50
    vacancy_fill_q: float = 0.70
    employment_ss: float = 0.80
    labor_force_ss: float = 0.86
    rho_lfp_m: float = 0.95
    lfp_wage_elasticity: float = 0.03
    lfp_output_elasticity: float = 0.02

    # Surplus / bargaining benchmark
    markup_ss: float = 1.20
    bargaining_power: float = 0.15
    replacement_rate: float = 0.54
    vacancy_cost_m: float = 5.0

    # Minimo vs salario effettivo
    minimum_share_effective_wage: float = 0.70
    wage_drift_speed_m: float = 0.08
    wage_drift_inertia_m: float = 0.40

    # Baseline nominale: usato per il floor, NON come shock nelle IRF.
    baseline_inflation_annual: float = 0.02

    # Bargaining: orologio separato dall'indicizzazione.
    bargaining_period_months: int = 36
    bargaining_strength: float = 0.20
    bargaining_timing: TimingMode = "staggered"
    bargaining_first_reset_month: int = 1

    # Recupero inflazione persa al rinnovo tradizionale.
    catchup_rate: float = 1.0

    # Contratto tradizionale: inflazione futura prevista distribuita in tranche.
    # 3 tranche per anno ai mesi 4, 8, 12 del relativo anno contrattuale.
    traditional_tranche_offsets: Tuple[int, ...] = (4, 8, 12)

    # Calendario del regime annuale: shock di default in gennaio, reset in giugno.
    shock_calendar_month: int = 1
    annual_reset_calendar_month: int = 6

    # Scala-mobile-style: 1 = usa l'inflazione del mese appena concluso.
    mobile_index_lag_months: int = 1

    # Solver / active set piecewise-lineare
    solve_horizon_months: int = 600
    plot_horizon_months: int = 180
    active_set_max_iter: int = 30
    active_set_tol: float = 1e-10

    # Soglia solo diagnostica: oltre questa deviazione il prototipo lineare va
    # letto con cautela. Non modifica la soluzione.
    linearization_warning_pct: float = 20.0


@dataclass
class ExperimentConfig:
    mode: ExperimentMode = "institutional"

    # Benchmark diagnostico separato: nessuna indicizzazione automatica.
    run_no_indexation_benchmark: bool = True

    # Intensita' trasferimento dell'indice scelto.
    gamma_mobile: float = 1.0
    gamma_annual_nei: float = 1.0
    gamma_traditional: float = 1.0

    # frequency_only: tutto uguale, cambia solo D.
    frequency_intervals: Tuple[int, ...] = (1, 12, 36)
    frequency_basis: IndexBasis = "nei"
    frequency_scope: WageScope = "minimum"
    frequency_timing: TimingMode = "staggered"
    frequency_gamma: float = 1.0

    shocks_to_run: Tuple[ShockType, ...] = ("cost_push", "energy", "technology")
    shock_sizes: Dict[str, float] = field(default_factory=lambda: {
        "cost_push": 0.001,
        "energy": 0.010,
        "technology": 0.010,
        "monetary_easing": 0.0002,
        "monetary_tightening": 0.0002,
    })

    output_prefix: str = "ccnl_indexation_irf"


@dataclass(frozen=True)
class RegimeSpec:
    key: str
    label: str
    D: int
    index_basis: IndexBasis
    scope: WageScope
    rule: str
    timing: TimingMode
    gamma: float


@dataclass
class MonthlyCalibration:
    beta: float
    habit: float
    omega: float
    kappa_price: float
    rho_i: float
    rho_a: float
    rho_m: float
    separation: float
    q_fill: float
    n_ss: float
    lfp_ss: float
    u_ss: float
    h_ss: float
    y_ss: float
    markup_ss: float
    v_ss: float
    searchers_ss: float
    theta_ss: float
    p_find: float
    matching_efficiency: float
    technology_ss: float
    lambda_ss: float
    mpl_ss: float
    mrs_ss: float
    wage_ss: float
    unemployment_value: float
    vacancy_cost: float


def calibrate_monthly(p: Parameters) -> MonthlyCalibration:
    if not (p.labor_force_ss > p.employment_ss):
        raise ValueError("labor_force_ss deve essere > employment_ss")
    if not (0 <= p.habit_m < 1):
        raise ValueError("habit_m deve essere in [0,1)")
    if not (1 <= p.shock_calendar_month <= 12):
        raise ValueError("shock_calendar_month deve essere 1..12")
    if not (1 <= p.annual_reset_calendar_month <= 12):
        raise ValueError("annual_reset_calendar_month deve essere 1..12")

    beta = p.beta_q ** (1.0 / 3.0)
    habit = p.habit_m
    omega = p.omega_q ** (1.0 / 3.0)
    rho_i = quarterly_persistence_to_monthly(p.rho_i_q)
    rho_a = quarterly_persistence_to_monthly(p.rho_a_q)
    rho_m = quarterly_persistence_to_monthly(p.rho_m_q)
    separation = quarterly_event_probability_to_monthly(p.separation_q)
    q_fill = quarterly_event_probability_to_monthly(p.vacancy_fill_q)
    kappa_price = ((1.0 - beta * omega) * (1.0 - omega)) / omega

    n_ss = p.employment_ss
    lfp_ss = p.labor_force_ss
    u_ss = lfp_ss - n_ss
    h_ss = 1.0
    y_ss = 1.0
    markup_ss = p.markup_ss

    matches_ss = separation * n_ss
    v_ss = matches_ss / q_fill
    searchers_ss = u_ss + separation * n_ss
    theta_ss = v_ss / searchers_ss
    p_find = matches_ss / searchers_ss

    xi = p.matching_elasticity_v
    matching_efficiency = matches_ss / (
        (v_ss ** xi) * (searchers_ss ** (1.0 - xi))
    )

    technology_ss = y_ss / (n_ss * h_ss ** p.alpha)
    c_ss = y_ss
    lambda_ss = ((1.0 - habit) ** (-p.sigma)) * (c_ss ** (-p.sigma))
    mpl_ss = p.alpha * technology_ss * h_ss ** (p.alpha - 1.0)

    theta_pref = (
        p.alpha * technology_ss * lambda_ss
        / (markup_ss * h_ss ** (1.0 + p.phi - p.alpha))
    )
    mrs_ss = theta_pref * (h_ss ** p.phi / lambda_ss)

    vacancy_cost = p.vacancy_cost_m
    d = p.bargaining_power
    vpi = p.replacement_rate
    wage_ss = (1.0 / (1.0 - (1.0 - d) * vpi)) * (
        ((1.0 - d) * (mrs_ss / (1.0 + p.phi)))
        + d * (
            (mpl_ss / (p.alpha * markup_ss))
            + beta * (1.0 - separation) * (vacancy_cost / q_fill)
        )
    )
    unemployment_value = vpi * wage_ss * h_ss

    return MonthlyCalibration(
        beta=beta, habit=habit, omega=omega, kappa_price=kappa_price,
        rho_i=rho_i, rho_a=rho_a, rho_m=rho_m,
        separation=separation, q_fill=q_fill,
        n_ss=n_ss, lfp_ss=lfp_ss, u_ss=u_ss,
        h_ss=h_ss, y_ss=y_ss, markup_ss=markup_ss,
        v_ss=v_ss, searchers_ss=searchers_ss,
        theta_ss=theta_ss, p_find=p_find,
        matching_efficiency=matching_efficiency,
        technology_ss=technology_ss, lambda_ss=lambda_ss,
        mpl_ss=mpl_ss, mrs_ss=mrs_ss, wage_ss=wage_ss,
        unemployment_value=unemployment_value,
        vacancy_cost=vacancy_cost,
    )


# =============================================================================
# 2. REGIMI
# =============================================================================

def get_regime_specs(cfg: ExperimentConfig) -> List[RegimeSpec]:
    if cfg.mode == "institutional":
        return [
            RegimeSpec(
                key="mobile_1m",
                label="Scala mobile style — 1 mese",
                D=1, index_basis="headline", scope="full",
                rule="mobile", timing="synchronized", gamma=cfg.gamma_mobile,
            ),
            RegimeSpec(
                key="annual_nei_12m",
                label="Aggiornamento annuale IPCA-NEI — giugno",
                D=12, index_basis="nei", scope="minimum",
                rule="annual_june", timing="synchronized", gamma=cfg.gamma_annual_nei,
            ),
            RegimeSpec(
                key="traditional_36m",
                label="CCNL tradizionale — rinnovi 36 mesi staggered",
                D=36, index_basis="nei", scope="minimum",
                rule="traditional", timing="staggered", gamma=cfg.gamma_traditional,
            ),
        ]

    if cfg.mode == "frequency_only":
        out = []
        for D in cfg.frequency_intervals:
            out.append(RegimeSpec(
                key=f"frequency_{D}m",
                label=f"Solo frequenza — D={D} mesi",
                D=int(D), index_basis=cfg.frequency_basis,
                scope=cfg.frequency_scope,
                rule="generic_frequency", timing=cfg.frequency_timing,
                gamma=cfg.frequency_gamma,
            ))
        return out

    raise ValueError(f"mode non valido: {cfg.mode}")


def benchmark_spec() -> RegimeSpec:
    return RegimeSpec(
        key="benchmark_none",
        label="Benchmark — nessuna indicizzazione automatica",
        D=36, index_basis="none", scope="minimum",
        rule="none", timing="staggered", gamma=0.0,
    )


# =============================================================================
# 3. VARIABILI DEL MODELLO
# =============================================================================

VARS: List[str] = [
    "lambda", "pi_nei", "pi_headline", "i", "mc", "c",
    "v", "n", "u", "lfp", "searchers", "q", "y", "a", "h",
    "mrs", "mpl", "m", "theta", "ur", "zcost", "zenergy",
    "xenergy_core",
    "wmin_r", "wpi_contract", "weff_r", "wpi_drift", "wpi_eff", "wb",
]
VAR_INDEX = {name: j for j, name in enumerate(VARS)}
NVAR = len(VARS)


# =============================================================================
# 4. REGOLE SALARIALI LINEARI + ACTIVE SET PER VINCOLI
# =============================================================================

def _calendar_month_year(t: int, shock_calendar_month: int) -> Tuple[int, int]:
    z = (shock_calendar_month - 1) + t
    return (z % 12) + 1, z // 12


def _baseline_contract_growth(params: Parameters, regime: RegimeSpec, T: int) -> np.ndarray:
    """Crescita nominale del contratto nel baseline, usata SOLO per il floor.

    Le IRF sono deviazioni dal baseline. Il floor corretto e':
        baseline_growth_t + deviation_t >= 0.
    """
    annual_log = math.log1p(params.baseline_inflation_annual)
    monthly_log = annual_log / 12.0
    out = np.zeros(T)

    if regime.rule == "mobile":
        out[:] = monthly_log
    elif regime.rule == "annual_june":
        for t in range(T):
            month, _ = _calendar_month_year(t, params.shock_calendar_month)
            if month == params.annual_reset_calendar_month:
                out[t] = annual_log
    else:
        # Con molte coorti staggered le tranche baseline si distribuiscono
        # nell'aggregato: approssimiamo la crescita media come mensile regolare.
        out[:] = monthly_log
    return out


def _bargaining_coeffs(params: Parameters, T: int) -> List[Dict[Tuple[int, str], float]]:
    """Coefficienti della componente di bargaining in ciascun mese.

    Ritorna una lista di dizionari: per ogni t, coefficiente moltiplicato per
    variabili (time,var). Con timing staggered, 1/36 dei CCNL rinnova ogni mese.
    """
    B = int(params.bargaining_period_months)
    out: List[Dict[Tuple[int, str], float]] = [dict() for _ in range(T)]
    s = params.bargaining_strength

    if params.bargaining_timing == "staggered":
        share = 1.0 / B
        first = max(0, params.bargaining_first_reset_month)
        for t in range(first, T):
            out[t][(t, "wb")] = out[t].get((t, "wb"), 0.0) + share * s
            if t > 0:
                out[t][(t - 1, "wmin_r")] = out[t].get((t - 1, "wmin_r"), 0.0) - share * s
    else:
        first = params.bargaining_first_reset_month
        for t in range(first, T, B):
            out[t][(t, "wb")] = out[t].get((t, "wb"), 0.0) + s
            if t > 0:
                out[t][(t - 1, "wmin_r")] = out[t].get((t - 1, "wmin_r"), 0.0) - s
    return out


def _traditional_forecast_matrix(params: Parameters, regime: RegimeSpec, T: int) -> np.ndarray:
    """F[t,s]: contributo a wpi_contract_t di pi_nei_s previsto al rinnovo.

    Ogni coorte rinnova ogni 36 mesi. Al rinnovo programma tre anni di tranche
    usando la previsione perfect-foresight/RE del NEI futuro condizionata allo shock.
    """
    B = int(params.bargaining_period_months)
    share = 1.0 / B
    offsets = tuple(sorted(params.traditional_tranche_offsets))
    ntr = max(len(offsets), 1)
    F = np.zeros((T, T))

    for cohort in range(B):
        first = cohort + 1
        for r in range(first, T, B):
            for yr in range(3):
                y0 = r + 12 * yr
                y1 = min(r + 12 * (yr + 1), T)
                if y0 >= T or y1 <= y0:
                    continue
                coeff = share * regime.gamma / ntr
                for off in offsets:
                    event_t = y0 + off - 1
                    if event_t < T:
                        F[event_t, y0:y1] += coeff
    return F


def _traditional_catchup_coeffs(
    params: Parameters,
    regime: RegimeSpec,
    T: int,
) -> Dict[int, np.ndarray]:
    """Gap d'inflazione di ciascuna coorte al rinnovo.

    gap = inflazione NEI realizzata dall'ultimo rinnovo
          - tranche di deviazione gia' previste/pagate dal contratto precedente.

    Il catch-up effettivo e' max(0,gap)*catchup_rate e viene pesato 1/36.
    """
    B = int(params.bargaining_period_months)
    share = 1.0 / B
    offsets = tuple(sorted(params.traditional_tranche_offsets))
    ntr = max(len(offsets), 1)
    out: Dict[int, np.ndarray] = {}

    for cohort in range(B):
        first = cohort + 1
        for r in range(first, T, B):
            coeff = np.zeros(T)
            start = max(0, r - B)
            coeff[start:r] += 1.0  # inflazione effettivamente realizzata

            prev = r - B
            if prev >= 0:
                # Sottrai le tranche previste dal contratto precedente che sono
                # state pagate prima del rinnovo corrente.
                for yr in range(3):
                    y0 = prev + 12 * yr
                    y1 = min(prev + 12 * (yr + 1), T)
                    if y0 >= T or y1 <= y0:
                        continue
                    per_tranche = regime.gamma / ntr
                    for off in offsets:
                        event_t = y0 + off - 1
                        if start <= event_t < r and event_t < T:
                            coeff[y0:y1] -= per_tranche

            out[r] = share * params.catchup_rate * coeff
    return out


def _wage_rule_linear_objects(params: Parameters, regime: RegimeSpec, T: int):
    """Precalcola oggetti lineari indipendenti dalla soluzione."""
    bargaining = _bargaining_coeffs(params, T)
    forecast_F = np.zeros((T, T))
    catchup_coeffs: Dict[int, np.ndarray] = {}

    if regime.rule == "traditional":
        forecast_F = _traditional_forecast_matrix(params, regime, T)
        catchup_coeffs = _traditional_catchup_coeffs(params, regime, T)

    return bargaining, forecast_F, catchup_coeffs


def _add_coeff_dict(add_fn, row: int, coeffs: Dict[Tuple[int, str], float], sign: float = -1.0):
    for (tt, var), coeff in coeffs.items():
        add_fn(row, tt, var, sign * coeff)


def _add_unconstrained_wage_rule(
    add_fn,
    row: int,
    t: int,
    params: Parameters,
    regime: RegimeSpec,
    bargaining_coeffs,
    forecast_F: np.ndarray,
    catchup_coeffs: Dict[int, np.ndarray],
    catchup_active: np.ndarray,
    T: int,
):
    """Aggiunge RHS endogeno della regola wpi_contract = componenti."""
    # Bargaining simmetrico sul gap reale; l'eventuale riduzione nominale e'
    # impedita dal floor sul salario totale.
    _add_coeff_dict(add_fn, row, bargaining_coeffs[t], sign=-1.0)

    if regime.rule == "none":
        return

    if regime.rule == "mobile":
        src = t - max(0, int(params.mobile_index_lag_months))
        if src >= 0:
            var = "pi_headline" if regime.index_basis == "headline" else "pi_nei"
            add_fn(row, src, var, -regime.gamma)
        return

    if regime.rule == "annual_june":
        month, year = _calendar_month_year(t, params.shock_calendar_month)
        if month == params.annual_reset_calendar_month and year - 1 >= 0:
            prev_year = year - 1
            for s in range(T):
                _, ys = _calendar_month_year(s, params.shock_calendar_month)
                if ys == prev_year:
                    add_fn(row, s, "pi_nei", -regime.gamma)
        return

    if regime.rule == "generic_frequency":
        D = int(regime.D)
        # Coorti uniformi: ogni mese 1/D rinnova e recupera l'inflazione degli
        # ultimi D mesi. Prima dello shock le deviazioni sono zero.
        if t >= 1:
            start = max(0, t - D)
            var = "pi_headline" if regime.index_basis == "headline" else "pi_nei"
            for s in range(start, t):
                add_fn(row, s, var, -(regime.gamma / D))
        return

    if regime.rule == "traditional":
        # Tranche future previste al rinnovo.
        nz = np.nonzero(forecast_F[t])[0]
        for s in nz:
            add_fn(row, int(s), "pi_nei", -float(forecast_F[t, s]))

        # Catch-up positivo: active set decide se max(0,gap) e' attivo.
        if t in catchup_coeffs and catchup_active[t]:
            coeff = catchup_coeffs[t]
            nz2 = np.nonzero(coeff)[0]
            for s in nz2:
                add_fn(row, int(s), "pi_nei", -float(coeff[s]))
        return

    raise ValueError(f"Regola salariale sconosciuta: {regime.rule}")


# =============================================================================
# 5. COSTRUZIONE E SOLUZIONE DEL SISTEMA PIECEWISE-LINEARE
# =============================================================================

def _build_and_solve(
    params: Parameters,
    cal: MonthlyCalibration,
    regime: RegimeSpec,
    shock_type: ShockType,
    shock_size: float,
    T: int,
    floor_active: np.ndarray,
    catchup_active: np.ndarray,
    bargaining_coeffs,
    forecast_F,
    catchup_coeffs,
) -> pd.DataFrame:
    A = lil_matrix((NVAR * T, NVAR * T), dtype=float)
    b = np.zeros(NVAR * T)
    base_growth = _baseline_contract_growth(params, regime, T)

    def idx(t: int, var: str) -> int:
        return t * NVAR + VAR_INDEX[var]

    def add(row: int, t: int, var: str, value: float) -> None:
        if 0 <= t < T:
            A[row, idx(t, var)] += value

    row = 0
    for t in range(T):
        # 1 Euler
        add(row, t, "lambda", +1); add(row, t+1, "lambda", -1)
        add(row, t, "i", -1); add(row, t+1, "pi_headline", +1); row += 1

        # 2 Marginal utility + habit
        cc = params.sigma / (1-cal.habit)
        add(row, t, "lambda", +1); add(row, t, "c", +cc)
        add(row, t-1, "c", -cc*cal.habit); row += 1

        # 3 Occupazione
        add(row, t, "n", +1); add(row, t-1, "n", -(1-cal.separation))
        add(row, t, "m", -cal.separation); row += 1

        # 4 Partecipazione
        add(row, t, "lfp", +1); add(row, t-1, "lfp", -params.rho_lfp_m)
        add(row, t, "weff_r", -params.lfp_wage_elasticity)
        add(row, t, "y", -params.lfp_output_elasticity); row += 1

        # 5 Disoccupazione
        add(row, t, "u", +1); add(row, t, "lfp", -(cal.lfp_ss/cal.u_ss))
        add(row, t, "n", +(cal.n_ss/cal.u_ss)); row += 1

        # 6 Searchers
        add(row, t, "searchers", +1); add(row, t, "u", -(cal.u_ss/cal.searchers_ss))
        add(row, t-1, "n", -(cal.separation*cal.n_ss/cal.searchers_ss)); row += 1

        # 7 MRS
        add(row, t, "mrs", +1); add(row, t, "h", -params.phi)
        add(row, t, "lambda", +1); row += 1

        # 8 NKPC NEI
        add(row, t, "pi_nei", +1); add(row, t+1, "pi_nei", -cal.beta)
        add(row, t, "mc", -cal.kappa_price); add(row, t, "zcost", -1)
        add(row, t, "xenergy_core", -1); row += 1

        # 9 Headline
        add(row, t, "pi_headline", +1); add(row, t, "pi_nei", -1)
        add(row, t, "zenergy", -params.energy_weight_headline); row += 1

        # 10 Pass-through energia -> core, con un mese di ritardo
        add(row, t, "xenergy_core", +1); add(row, t-1, "xenergy_core", -params.rho_energy_core_m)
        add(row, t-1, "zenergy", -params.energy_core_loading); row += 1

        # 11 MC
        add(row, t, "mc", +1); add(row, t, "weff_r", -1); add(row, t, "mpl", +1); row += 1

        # 12 Produzione
        add(row, t, "y", +1); add(row, t, "a", -1); add(row, t, "h", -params.alpha); add(row, t, "n", -1); row += 1

        # 13 MPL
        add(row, t, "mpl", +1); add(row, t, "a", -1); add(row, t, "h", -(params.alpha-1)); row += 1

        # 14 Vacancy free entry
        k_over_q = cal.vacancy_cost/cal.q_fill
        prod_term = cal.technology_ss*(cal.h_ss**params.alpha)/cal.markup_ss
        wage_bill = cal.wage_ss*cal.h_ss
        cont = cal.beta*(1-cal.separation)*k_over_q
        add(row, t, "q", -k_over_q); add(row, t, "h", -prod_term*params.alpha+wage_bill)
        add(row, t, "mc", -prod_term); add(row, t, "weff_r", +wage_bill)
        add(row, t+1, "lambda", -cont); add(row, t, "lambda", +cont); add(row, t+1, "q", +cont); row += 1

        # 15 Benchmark Nash
        d=params.bargaining_power
        b1=((1-d)/(1+params.phi))*cal.mrs_ss
        b2=((1-d)*cal.unemployment_value)/cal.h_ss
        b3=d*(cal.mpl_ss/(cal.markup_ss*params.alpha))
        b4=d*(1-cal.separation)*cal.beta*cal.vacancy_cost/(cal.h_ss*cal.q_fill)
        add(row,t,"wb",+cal.wage_ss); add(row,t,"mrs",-b1); add(row,t,"h",+(b2+b4))
        add(row,t,"mpl",-b3); add(row,t,"mc",-b3); add(row,t+1,"lambda",-b4)
        add(row,t,"lambda",+b4); add(row,t+1,"q",+b4); row += 1

        # 16 Tightness
        add(row,t,"theta",+1); add(row,t,"v",-1); add(row,t,"searchers",+1); row += 1

        # 17 Matching
        xi=params.matching_elasticity_v
        add(row,t,"m",+1); add(row,t,"v",-xi); add(row,t,"searchers",-(1-xi)); row += 1

        # 18 Taylor
        add(row,t,"i",+1); add(row,t-1,"i",-cal.rho_i)
        piv="pi_headline" if params.policy_inflation_measure=="headline" else "pi_nei"
        add(row,t,piv,-(1-cal.rho_i)*params.phi_pi); add(row,t,"y",-(1-cal.rho_i)*params.phi_y)
        add(row,t,"ur",+1); row += 1

        # 19 Resource
        add(row,t,"y",+1); add(row,t,"c",-1); row += 1

        # 20 q
        add(row,t,"q",+1); add(row,t,"m",-1); add(row,t,"v",+1); row += 1

        # 21 Tecnologia
        add(row,t,"a",+1); add(row,t-1,"a",-cal.rho_a)
        if t==0 and shock_type=="technology": b[row]=shock_size
        row += 1

        # 22 Monetario
        add(row,t,"ur",+1); add(row,t-1,"ur",-cal.rho_m)
        if t==0 and shock_type=="monetary_easing": b[row]=shock_size
        elif t==0 and shock_type=="monetary_tightening": b[row]=-shock_size
        row += 1

        # 23 Cost-push
        add(row,t,"zcost",+1); add(row,t-1,"zcost",-params.rho_cost_m)
        if t==0 and shock_type=="cost_push": b[row]=shock_size
        row += 1

        # 24 Energia
        add(row,t,"zenergy",+1); add(row,t-1,"zenergy",-params.rho_energy_m)
        if t==0 and shock_type=="energy": b[row]=shock_size
        row += 1

        # 25 Minimo reale
        add(row,t,"wmin_r",+1); add(row,t-1,"wmin_r",-1)
        add(row,t,"wpi_contract",-1); add(row,t,"pi_headline",+1); row += 1

        # 26 Regola salariale piecewise
        add(row,t,"wpi_contract",+1)
        if floor_active[t]:
            # baseline + deviazione = 0 => deviazione = -baseline
            b[row] = -base_growth[t]
        else:
            _add_unconstrained_wage_rule(
                add, row, t, params, regime,
                bargaining_coeffs, forecast_F, catchup_coeffs,
                catchup_active, T,
            )
        row += 1

        # 27 Salario effettivo reale
        add(row,t,"weff_r",+1); add(row,t-1,"weff_r",-1)
        add(row,t,"wpi_eff",-1); add(row,t,"pi_headline",+1); row += 1

        # 28 Wage drift
        rho_d=params.wage_drift_inertia_m; speed=params.wage_drift_speed_m
        add(row,t,"wpi_drift",+1); add(row,t-1,"wpi_drift",-rho_d)
        add(row,t,"wb",-(1-rho_d)*speed); add(row,t-1,"weff_r",+(1-rho_d)*speed); row += 1

        # 29 Effettivo = quota CCNL + drift
        share=1.0 if regime.scope=="full" else params.minimum_share_effective_wage
        add(row,t,"wpi_eff",+1); add(row,t,"wpi_contract",-share); add(row,t,"wpi_drift",-1); row += 1

    if row != NVAR*T:
        raise RuntimeError(f"Sistema non quadrato: {row} vs {NVAR*T}")

    sol = splu(A.tocsc()).solve(b)
    if not np.all(np.isfinite(sol)):
        raise RuntimeError("Soluzione con NaN/Inf")
    df=pd.DataFrame(sol.reshape(T,NVAR), columns=VARS)
    df.insert(0,"month",np.arange(T))
    return df


def _evaluate_wage_components(
    df: pd.DataFrame,
    params: Parameters,
    regime: RegimeSpec,
    bargaining_coeffs,
    forecast_F: np.ndarray,
    catchup_coeffs: Dict[int,np.ndarray],
) -> Dict[str,np.ndarray]:
    T=len(df)
    pi_head=df["pi_headline"].to_numpy(); pi_nei=df["pi_nei"].to_numpy()
    index=np.zeros(T); forecast=np.zeros(T); catch=np.zeros(T); bargain=np.zeros(T)

    # Bargaining simmetrico sul gap reale; il floor impedisce tagli nominali.
    for t in range(T):
        val=0.0
        for (tt,var),coef in bargaining_coeffs[t].items():
            val += coef*float(df[var].iloc[tt])
        bargain[t]=val

    if regime.rule=="mobile":
        src_lag=max(0,int(params.mobile_index_lag_months))
        ref=pi_head if regime.index_basis=="headline" else pi_nei
        for t in range(T):
            src=t-src_lag
            if src>=0: index[t]=regime.gamma*ref[src]

    elif regime.rule=="annual_june":
        for t in range(T):
            month,year=_calendar_month_year(t,params.shock_calendar_month)
            if month==params.annual_reset_calendar_month and year-1>=0:
                vals=[]
                for s in range(T):
                    _,ys=_calendar_month_year(s,params.shock_calendar_month)
                    if ys==year-1: vals.append(pi_nei[s])
                if vals: index[t]=regime.gamma*float(np.sum(vals))

    elif regime.rule=="generic_frequency":
        D=int(regime.D); ref=pi_head if regime.index_basis=="headline" else pi_nei
        for t in range(1,T):
            index[t]=(regime.gamma/D)*float(np.sum(ref[max(0,t-D):t]))

    elif regime.rule=="traditional":
        forecast=forecast_F.dot(pi_nei)
        index=forecast.copy()
        for t,coef in catchup_coeffs.items():
            gap=float(np.dot(coef,pi_nei)) / max(params.catchup_rate,1e-15) if params.catchup_rate>0 else 0.0
            # coef include gia' share*catchup_rate; ricostruiamo direttamente il contributo positivo.
            raw=float(np.dot(coef,pi_nei))
            catch[t]=max(0.0,raw)

    proposed=index+catch+bargain
    base=_baseline_contract_growth(params,regime,T)
    floor=np.maximum(proposed,-base)-proposed
    final=proposed+floor
    return {"indexation":index,"forecast":forecast,"catchup":catch,"bargaining":bargain,
            "proposed":proposed,"baseline_growth":base,"floor_adjustment":floor,"final":final}


# =============================================================================
# 6. SOLVER ACTIVE-SET
# =============================================================================

def solve_irf(
    params: Parameters,
    cfg: ExperimentConfig,
    regime: RegimeSpec,
    shock_type: ShockType,
    shock_size: float,
    solve_horizon_months: int | None = None,
) -> pd.DataFrame:
    T=int(solve_horizon_months or params.solve_horizon_months)
    cal=calibrate_monthly(params)
    bargaining_coeffs,forecast_F,catchup_coeffs=_wage_rule_linear_objects(params,regime,T)

    floor_active=np.zeros(T,dtype=bool)
    catchup_active=np.zeros(T,dtype=bool)
    converged=False
    max_iter=int(params.active_set_max_iter)
    tol=float(params.active_set_tol)

    for it in range(max_iter):
        df=_build_and_solve(
            params,cal,regime,shock_type,shock_size,T,
            floor_active,catchup_active,
            bargaining_coeffs,forecast_F,catchup_coeffs,
        )
        comp=_evaluate_wage_components(df,params,regime,bargaining_coeffs,forecast_F,catchup_coeffs)
        # Per il floor usiamo un active set conservativo: una volta che un mese
        # richiede il vincolo nominale, resta vincolato nelle iterazioni successive.
        # Evita cicli numerici vicino alla frontiera baseline+deviazione=0.
        new_floor = floor_active | (comp["proposed"] < (-comp["baseline_growth"]-tol))

        new_catch=catchup_active.copy()
        if regime.rule=="traditional" and params.catchup_rate>0:
            pi=df["pi_nei"].to_numpy()
            for t,coef in catchup_coeffs.items():
                raw=float(np.dot(coef,pi))
                if raw>tol:
                    new_catch[t]=True

        if np.array_equal(new_floor,floor_active) and np.array_equal(new_catch,catchup_active):
            converged=True
            break
        floor_active=new_floor
        catchup_active=new_catch

    # Ultima soluzione coerente con active set finale.
    df=_build_and_solve(
        params,cal,regime,shock_type,shock_size,T,
        floor_active,catchup_active,bargaining_coeffs,forecast_F,catchup_coeffs,
    )
    comp=_evaluate_wage_components(df,params,regime,bargaining_coeffs,forecast_F,catchup_coeffs)

    if not converged:
        warnings.warn(f"Active set non stabilizzato entro {max_iter} iterazioni: {regime.key}, shock={shock_type}")

    df["wpi_indexation"]=comp["indexation"]
    df["wpi_forecast"]=comp["forecast"]
    df["wpi_catchup"]=comp["catchup"]
    df["wpi_bargaining"]=comp["bargaining"]
    df["wpi_floor_adjustment"]=comp["floor_adjustment"]
    df["baseline_contract_growth"]=comp["baseline_growth"]
    df["floor_binding"]=floor_active.astype(int)
    df["catchup_binding"]=catchup_active.astype(int)

    df["price_level_headline"]=df["pi_headline"].cumsum()
    df["price_level_nei"]=df["pi_nei"].cumsum()
    df["contract_wage_level"]=df["wpi_contract"].cumsum()
    df["effective_wage_level"]=df["wpi_eff"].cumsum()
    df["wage_gap"]=df["wb"]-df["weff_r"]

    df["regime_key"]=regime.key; df["regime_label"]=regime.label
    df["D"]=regime.D; df["indexation_basis"]=regime.index_basis
    df["wage_scope"]=regime.scope; df["timing_mode"]=regime.timing
    df["experiment_mode"]=cfg.mode; df["shock_type"]=shock_type
    df["active_set_converged"]=converged
    return df


# =============================================================================
# 7. METADATI, GUIDE E TABELLA DI SPECIFICA
# =============================================================================

IRF_META: Dict[str, Dict[str, str]] = {
    "pi_headline": {
        "label": "Inflazione headline",
        "unit": "p.p. annualizzati",
        "reading": "Inflazione complessiva. Nello shock energia reagisce subito alla componente importata e poi anche al pass-through core.",
    },
    "pi_nei": {
        "label": "Inflazione IPCA-NEI stilizzata",
        "unit": "p.p. annualizzati",
        "reading": "Esclude l'energia importata diretta. Lo shock energia entra solo con ritardo tramite xenergy_core.",
    },
    "xenergy_core": {
        "label": "Pressione energetica indiretta sui prezzi core",
        "unit": "% deviazione",
        "reading": "Stato che accumula gradualmente il pass-through dell'energia su input, trasporti, servizi e altri prezzi inclusi nel NEI.",
    },
    "wpi_contract": {
        "label": "Crescita salariale contrattuale — deviazione dal baseline",
        "unit": "p.p. annualizzati",
        "reading": "Deviazione dagli aumenti gia' previsti nel contratto. Nel tradizionale le tranche sull'inflazione prevista di base sono gia' nel baseline.",
    },
    "wpi_indexation": {
        "label": "Componente di indicizzazione / tranche previste",
        "unit": "p.p. annualizzati",
        "reading": "Mobile: headline mensile; annuale: NEI anno precedente a giugno; tradizionale: nuove tranche sulla previsione futura condizionata allo shock.",
    },
    "wpi_catchup": {
        "label": "Catch-up dell'inflazione persa",
        "unit": "p.p. annualizzati",
        "reading": "Recupero dell'errore positivo di inflazione non gia' compensato. Nel regime tradizionale avviene al rinnovo triennale staggered.",
    },
    "wpi_bargaining": {
        "label": "Componente di bargaining",
        "unit": "p.p. annualizzati",
        "reading": "Aggiustamento reale verso il benchmark Nash. Ha sempre orologio separato di 36 mesi.",
    },
    "wpi_drift": {
        "label": "Wage drift individuale",
        "unit": "p.p. annualizzati",
        "reading": "Superminimi, promozioni e aggiustamenti individuali: possono muoversi anche quando il minimo non viene aggiornato.",
    },
    "wpi_eff": {
        "label": "Inflazione salariale effettiva",
        "unit": "p.p. annualizzati",
        "reading": "Somma della componente contrattuale trasmessa all'effettivo e del wage drift individuale.",
    },
    "wmin_r": {
        "label": "Minimo contrattuale reale",
        "unit": "% deviazione",
        "reading": "Potere d'acquisto del minimo rispetto al baseline contrattuale.",
    },
    "weff_r": {
        "label": "Salario effettivo reale",
        "unit": "% deviazione",
        "reading": "Retribuzione effettivamente pagata; e' questa, non il solo minimo, che entra nel costo marginale.",
    },
    "wage_gap": {
        "label": "Wage gap: benchmark Nash meno salario effettivo",
        "unit": "% deviazione",
        "reading": "Positivo = salario effettivo sotto il benchmark; alimenta wage drift e bargaining.",
    },
    "mc": {
        "label": "Costo marginale reale",
        "unit": "% deviazione",
        "reading": "Ponte tra salario effettivo, produttivita' e inflazione NEI.",
    },
    "i": {
        "label": "Tasso di policy",
        "unit": "p.p. annualizzati",
        "reading": "Risposta della banca centrale a inflazione e output.",
    },
    "y": {
        "label": "Output",
        "unit": "% deviazione",
        "reading": "Produzione rispetto al sentiero di base.",
    },
    "n": {
        "label": "Occupazione",
        "unit": "% deviazione",
        "reading": "Stock di occupati generato da separazioni e nuovi match.",
    },
    "u": {
        "label": "Disoccupazione",
        "unit": "% deviazione dello stock",
        "reading": "Stock U=L-N. Non leggere l'asse come punti percentuali del tasso ISTAT.",
    },
    "lfp": {
        "label": "Partecipazione / forza lavoro",
        "unit": "% deviazione",
        "reading": "Entrata/uscita dalla forza lavoro in risposta a ciclo e salario reale.",
    },
    "v": {
        "label": "Vacancies",
        "unit": "% deviazione",
        "reading": "Domanda di lavoro delle imprese; utile per diagnosticare surplus eccessivi da salari reali bassi.",
    },
    "theta": {
        "label": "Labour market tightness",
        "unit": "% deviazione",
        "reading": "Vacancies relative ai searchers.",
    },
    "price_level_headline": {
        "label": "Livello cumulato dei prezzi headline",
        "unit": "% deviazione cumulata",
        "reading": "Somma dell'inflazione headline: mostra il livello dei prezzi, non solo il tasso.",
    },
    "price_level_nei": {
        "label": "Livello cumulato dei prezzi NEI",
        "unit": "% deviazione cumulata",
        "reading": "Livello cumulato della componente NEI/core.",
    },
    "contract_wage_level": {
        "label": "Livello cumulato del salario contrattuale",
        "unit": "% deviazione cumulata",
        "reading": "Deviazione cumulata rispetto al sentiero salariale contrattuale gia' programmato nel baseline.",
    },
    "effective_wage_level": {
        "label": "Livello cumulato del salario nominale effettivo",
        "unit": "% deviazione cumulata",
        "reading": "Include CCNL e wage drift; confrontalo con il livello dei prezzi.",
    },
}

CORE_PLOT_VARS = [
    "pi_headline", "pi_nei", "xenergy_core",
    "wpi_contract", "wpi_indexation", "wpi_catchup", "wpi_bargaining",
    "wpi_drift", "wpi_eff", "wmin_r", "weff_r", "wage_gap",
    "mc", "i", "y", "n", "u", "lfp", "v", "theta",
    "price_level_headline", "price_level_nei",
    "contract_wage_level", "effective_wage_level",
]


def transform_irf(series: pd.Series, var: str) -> pd.Series:
    if var in {
        "pi_nei", "pi_headline", "i", "wpi_contract", "wpi_indexation",
        "wpi_catchup", "wpi_bargaining", "wpi_drift", "wpi_eff",
    }:
        return series * 1200.0
    return series * 100.0


def parameter_guide(params: Parameters, cfg: ExperimentConfig) -> pd.DataFrame:
    cal = calibrate_monthly(params)
    rows = [
        ["beta_q", params.beta_q, "0.985-0.999", "Discount factor", "↑ piu' forward-looking", "Fattore di sconto intertemporale"],
        ["sigma", params.sigma, "0.5-3", "CRRA / 1-IES", "↑ consumo meno elastico", "CRRA = Constant Relative Risk Aversion; IES = Intertemporal Elasticity of Substitution"],
        ["habit_m", params.habit_m, "0-0.8", "Habit mensile", "↑ c e y piu' persistenti", "Habit formation = consumo corrente dipende dal consumo passato"],
        ["omega_q", params.omega_q, "0.5-0.9", "Calvo pricing", "↑ prezzi piu' rigidi", "Calvo = probabilita' di non poter riottimizzare il prezzo"],
        ["phi_pi", params.phi_pi, "1.2-3", "Taylor rule", "↑ risposta monetaria piu' aggressiva", "Reazione del tasso nominale all'inflazione"],
        ["rho_cost_m", params.rho_cost_m, "0-0.95", "Cost-push", "↑ shock piu' persistente", f"AR(1) mensile; half-life ≈ {half_life_months(params.rho_cost_m):.1f} mesi"],
        ["rho_energy_m", params.rho_energy_m, "0-0.98", "Energia importata", "↑ shock piu' persistente", f"AR(1) mensile; half-life ≈ {half_life_months(params.rho_energy_m):.1f} mesi"],
        ["energy_weight_headline", params.energy_weight_headline, "0.05-0.20", "Energia -> headline", "↑ impatto diretto", "Componente importata diretta nell'inflazione complessiva"],
        ["energy_core_loading", params.energy_core_loading, "0.02-0.20", "Energia -> core", "↑ maggiore pass-through", "Quanto lo shock energia alimenta con ritardo xenergy_core"],
        ["rho_energy_core_m", params.rho_energy_core_m, "0.5-0.98", "Persistenza pass-through", "↑ contaminazione core piu' lenta/persistente", "Persistenza della pressione energetica indiretta su IPCA-NEI"],
        ["baseline_inflation_annual", params.baseline_inflation_annual, "0.01-0.03", "Baseline nominale", "↑ floor meno spesso binding", "Inflazione attesa gia' incorporata nel sentiero base; usata per il floor, non come shock IRF"],
        ["minimum_share_effective_wage", params.minimum_share_effective_wage, "0.4-0.95", "Minimo -> effettivo", "↑ minimo pesa di piu' sul salario pagato", "Non e' copertura CCNL: misura la quota di retribuzione effettiva esposta meccanicamente al minimo"],
        ["wage_drift_speed_m", params.wage_drift_speed_m, "0-0.30", "Wage drift", "↑ gap di mercato chiuso piu' rapidamente", "Superminimi, promozioni, mobilita' e aumenti individuali"],
        ["bargaining_period_months", params.bargaining_period_months, "36 baseline", "Orologio bargaining", "↑ bargaining meno frequente", "Separato dall'orologio di indicizzazione"],
        ["bargaining_strength", params.bargaining_strength, "0-0.5", "Bargaining reale", "↑ minimo segue piu' il benchmark Nash", "Quota del gap reale incorporata a ogni rinnovo triennale"],
        ["catchup_rate", params.catchup_rate, "0-1", "Catch-up", "↑ maggiore recupero arretrato", "Quota dell'errore positivo di inflazione recuperata al rinnovo tradizionale"],
        ["traditional_tranche_offsets", str(params.traditional_tranche_offsets), "es. (4,8,12)", "Tranche previste", "piu' tranche = compensazione piu' distribuita", "Mesi dell'anno contrattuale in cui si distribuisce la previsione futura"],
        ["annual_reset_calendar_month", params.annual_reset_calendar_month, "1-12", "Reset annuale", "sposta il lag calendario", "6 = giugno; usa il NEI dell'anno solare precedente"],
        ["shock_calendar_month", params.shock_calendar_month, "1-12", "Calendario shock", "cambia il tempo fino al prossimo giugno", "1 = gennaio nel baseline"],
        ["mode", cfg.mode, "institutional/frequency_only", "Disegno esperimento", "-", "institutional confronta istituzioni; frequency_only cambia soltanto la frequenza"],
    ]
    df = pd.DataFrame(rows, columns=["parameter", "start", "sensitivity_range", "role", "direction_if_higher", "economic_element"])
    df.attrs["monthly_calibration"] = asdict(cal)
    return df


def specification_table(params: Parameters, cfg: ExperimentConfig) -> pd.DataFrame:
    annual_log = math.log1p(params.baseline_inflation_annual)
    rows = [
        ["Baseline comune", "Inflazione attesa", f"{100*params.baseline_inflation_annual:.1f}% annuo", "Gia' incorporata nelle tranche del sentiero base; le IRF mostrano solo sorprese/deviazioni"],
        ["Baseline comune", "Floor nominale", "Salario nominale non puo' diminuire", "La deviazione puo' essere negativa finche' baseline + deviazione resta >= 0"],
        ["Scala mobile style", "Indicizzazione", "Ogni mese", "Headline realizzata; intera retribuzione; bargaining separato ogni 36 mesi"],
        ["Annuale NEI", "Indicizzazione", "Tutti a giugno", "Minimo: recupera l'IPCA-NEI dell'anno solare precedente; bargaining separato ogni 36 mesi"],
        ["Tradizionale 36m", "Inflazione prevista", "Tranche nel baseline", "La previsione fatta al contratto e' gia' nel sentiero base e quindi non appare nelle IRF"],
        ["Tradizionale 36m", "Errore inflazione", "Recuperato al rinnovo", "Solo la sorpresa rispetto alla previsione precedente resta scoperta fino al rinnovo staggered"],
        ["Tradizionale 36m", "Previsione futura dopo lo shock", "Nuovo contratto", "Al rinnovo usa il sentiero futuro atteso/RE dell'IPCA-NEI e lo distribuisce nelle nuove tranche"],
        ["Tutti i regimi", "Bargaining", f"Ogni {params.bargaining_period_months} mesi", "Orologio separato dall'indicizzazione; default staggered"],
        ["Tutti i regimi", "Salari individuali", "Continuamente", "Wage drift/superminimi/promozioni possono muovere il salario effettivo anche con minimo fermo"],
        ["Shock energia", "Headline", "Immediato", "L'energia importata entra direttamente nell'inflazione complessiva"],
        ["Shock energia", "IPCA-NEI", "Ritardato", "zenergy -> xenergy_core -> NEI: pass-through progressivo agli altri prezzi"],
        ["Cost-push", "Persistenza", f"rho={params.rho_cost_m:.2f}", f"Half-life circa {half_life_months(params.rho_cost_m):.1f} mesi"],
        ["Energia", "Persistenza shock diretto", f"rho={params.rho_energy_m:.2f}", f"Half-life circa {half_life_months(params.rho_energy_m):.1f} mesi"],
        ["Tecnologia", "Persistenza", f"rho_m={quarterly_persistence_to_monthly(params.rho_a_q):.3f}", f"Half-life circa {half_life_months(quarterly_persistence_to_monthly(params.rho_a_q)):.1f} mesi"],
        ["frequency_only", "Identificazione", "D=1,12,36", "Stesso NEI, stesso scope minimo, stesso bargaining; cambia soltanto la frequenza di recupero"],
        ["Benchmark none", "Controllo", "Nessuna indicizzazione automatica", "Non e' un terzo indice: serve solo a misurare il valore aggiunto dell'automatismo"],
    ]
    return pd.DataFrame(rows, columns=["blocco", "elemento", "specifica", "interpretazione"])


def equation_guide() -> pd.DataFrame:
    rows = [
        [1, "Euler", "lambda_t = E lambda_t+1 + i_t - E pi_headline,t+1", "Domanda intertemporale"],
        [2, "NKPC-NEI", "pi_nei = beta E pi_nei+1 + kappa mc + zcost + xenergy_core", "Core inflation / IPCA-NEI stilizzato"],
        [3, "Headline", "pi_headline = pi_nei + omega_E zenergy", "Componente energetica diretta"],
        [4, "Energy core pass-through", "xE_t = rho_x xE_t-1 + lambda_E zenergy_t-1", "Energia contamina il core con ritardo"],
        [5, "Marginal cost", "mc = weff_r - mpl", "Il costo usa il salario effettivo"],
        [6, "Employment", "n_t=(1-s)n_t-1+s*m_t", "Stock occupati"],
        [7, "Participation", "lfp_t=rho_L lfp_t-1+chi_w weff_r+chi_y y", "Partecipazione separata"],
        [8, "Unemployment", "U=L-N", "Disoccupazione stock"],
        [9, "Matching", "m=xi v+(1-xi)searchers", "Nuovi match"],
        [10, "Taylor", "i=rho_i i(-1)+(1-rho_i)(phi_pi*pi+phi_y*y)-ur", "Politica monetaria"],
        [11, "Minimo reale", "wmin_r=wmin_r(-1)+wpi_contract-pi_headline", "Potere d'acquisto del minimo"],
        [12, "Salario effettivo", "weff_r=weff_r(-1)+wpi_eff-pi_headline", "Retribuzione pagata"],
        [13, "Wage drift", "drift=rho_d drift(-1)+(1-rho_d)lambda_d(wb-weff_r(-1))", "Aumenti individuali"],
        [14, "Regola salariale", "wpi_contract = indexation + catchup + bargaining + floor", "Piecewise fixed point"],
    ]
    return pd.DataFrame(rows, columns=["eq", "name", "equation", "interpretation"])


# =============================================================================
# 8. DIAGNOSTICA / PLOT
# =============================================================================

def first_sustained_return_month(values: np.ndarray, threshold_share: float = 0.10, window: int = 12) -> float:
    peak = float(np.max(np.abs(values)))
    if peak == 0:
        return 0.0
    thr = threshold_share * peak
    for t in range(len(values) - window + 1):
        if np.all(np.abs(values[t:t+window]) <= thr):
            return float(t)
    return np.nan


def summarize_irfs(results: Dict[str, pd.DataFrame], months: int) -> pd.DataFrame:
    keyvars = ["pi_headline", "pi_nei", "wpi_contract", "wpi_eff", "weff_r", "mc", "y", "n", "u", "v", "i"]
    rows = []
    for key, df in results.items():
        H = min(months, len(df))
        for var in keyvars:
            raw = df[var].iloc[:H].to_numpy()
            disp = transform_irf(df[var].iloc[:H], var).to_numpy()
            j = int(np.argmax(np.abs(disp)))
            rows.append({
                "regime": key,
                "label": df["regime_label"].iloc[0],
                "D_months": int(df["D"].iloc[0]),
                "indexation_basis": df["indexation_basis"].iloc[0],
                "scope": df["wage_scope"].iloc[0],
                "variable": var,
                "impact": float(disp[0]),
                "peak_abs_signed": float(disp[j]),
                "peak_month": j,
                "return_10pct_month": first_sustained_return_month(disp),
                "cumulative_pct": float(100*np.sum(raw)) if var in {"pi_headline", "pi_nei"} else np.nan,
                "active_set_converged": bool(df["active_set_converged"].iloc[0]),
            })
    return pd.DataFrame(rows)


def _plot_comparison(
    results: Dict[str, pd.DataFrame],
    params: Parameters,
    shock_type: ShockType,
    output_dir: Path,
    variables: Iterable[str],
) -> pd.DataFrame:
    manifest = []
    H = params.plot_horizon_months
    plot_dir = output_dir / "plots"
    plot_dir.mkdir(parents=True, exist_ok=True)

    for var in variables:
        meta = IRF_META[var]
        fig, ax = plt.subplots(figsize=(11, 6.2))
        max_abs = 0.0
        for key, df in results.items():
            HH = min(H, len(df))
            yy = transform_irf(df[var].iloc[:HH], var)
            max_abs = max(max_abs, float(np.max(np.abs(yy))))
            ax.plot(df["month"].iloc[:HH], yy, linewidth=2, label=df["regime_label"].iloc[0])
        ax.axhline(0, linewidth=0.9)
        ax.set_xlabel("Mesi dallo shock")
        ax.set_ylabel(meta["unit"])
        ax.set_title(f"IRF — {meta['label']} | shock={shock_type}")
        ax.legend(frameon=False, fontsize=9)
        ax.grid(alpha=0.20)
        fig.tight_layout()
        rel = Path("plots") / f"IRF_{var}.png"
        fig.savefig(output_dir / rel, dpi=175, bbox_inches="tight")
        plt.close(fig)

        warning = ""
        if max_abs > params.linearization_warning_pct and meta["unit"].startswith("%"):
            warning = f"ATTENZIONE: max |IRF|={max_abs:.1f}% supera la soglia diagnostica del prototipo lineare."

        manifest.append({
            "file": str(rel),
            "variable": var,
            "note": meta["reading"],
            "warning": warning,
        })
    return pd.DataFrame(manifest)


def terminal_horizon_check(
    params: Parameters,
    cfg: ExperimentConfig,
    regime: RegimeSpec,
    shock_type: ShockType,
    shock_size: float,
    compare_first_months: int = 120,
    extra_horizon: int = 240,
) -> Dict[str, float | str]:
    T1 = params.solve_horizon_months
    T2 = T1 + extra_horizon
    a = solve_irf(params, cfg, regime, shock_type, shock_size, T1)
    b = solve_irf(params, cfg, regime, shock_type, shock_size, T2)
    key = ["pi_headline", "pi_nei", "wpi_eff", "weff_r", "mc", "y", "n", "i", "v", "u"]
    H = min(compare_first_months, len(a), len(b))
    xa = a.loc[:H-1, key].to_numpy()
    xb = b.loc[:H-1, key].to_numpy()
    diff = float(np.max(np.abs(xa - xb)))
    scale = max(float(np.max(np.abs(xb))), 1e-12)
    return {
        "regime": regime.key,
        "shock_type": shock_type,
        "absolute_max_difference": diff,
        "relative_to_max_irf": diff / scale,
        "horizon_1": T1,
        "horizon_2": T2,
    }


# =============================================================================
# 9. BATCH RUN
# =============================================================================

def run_shock_batch(
    params: Parameters,
    cfg: ExperimentConfig,
    shock_type: ShockType,
    base_dir: str | Path = ".",
    variables_to_plot: Iterable[str] = CORE_PLOT_VARS,
    run_terminal_check: bool = False,
) -> Path:
    suffix = {
        "cost_push": "costpush",
        "energy": "energy",
        "technology": "technology",
        "monetary_easing": "monetary_easing",
        "monetary_tightening": "monetary_tightening",
    }[shock_type]

    output_dir = Path(base_dir) / f"{cfg.output_prefix}_{cfg.mode}_{suffix}"
    output_dir.mkdir(parents=True, exist_ok=True)

    specs = get_regime_specs(cfg)
    shock_size = cfg.shock_sizes[shock_type]
    results: Dict[str, pd.DataFrame] = {}

    for spec in specs:
        print(
            f"Solvo {cfg.mode:>14} | shock={shock_type:>10} | "
            f"{spec.key:>20} | basis={spec.index_basis:>8} | scope={spec.scope}"
        )
        results[spec.key] = solve_irf(params, cfg, spec, shock_type, shock_size)

    all_irfs = pd.concat(results.values(), ignore_index=True)
    all_irfs.to_csv(output_dir / "irf_all_scenarios.csv", index=False)
    summarize_irfs(results, params.plot_horizon_months).to_csv(output_dir / "irf_summary.csv", index=False)
    parameter_guide(params, cfg).to_csv(output_dir / "parameter_guide.csv", index=False)
    equation_guide().to_csv(output_dir / "equation_guide.csv", index=False)
    specification_table(params, cfg).to_csv(output_dir / "model_specification.csv", index=False)

    manifest = _plot_comparison(results, params, shock_type, output_dir, variables_to_plot)
    manifest.to_csv(output_dir / "plot_manifest.csv", index=False)

    with open(output_dir / "run_configuration.json", "w", encoding="utf-8") as f:
        json.dump({"parameters": asdict(params), "experiment": asdict(cfg)}, f, indent=2, ensure_ascii=False, default=str)

    if run_terminal_check:
        checks = []
        # Per costo computazionale controlliamo il regime piu' lento / ultimo.
        for spec in specs[-1:]:
            checks.append(terminal_horizon_check(params, cfg, spec, shock_type, shock_size))
        pd.DataFrame(checks).to_csv(output_dir / "terminal_horizon_check.csv", index=False)

    if cfg.run_no_indexation_benchmark:
        bdir = output_dir / "benchmark_no_indexation"
        bdir.mkdir(exist_ok=True)
        bs = benchmark_spec()
        bdf = solve_irf(params, cfg, bs, shock_type, shock_size)
        bdf.to_csv(bdir / "benchmark_irf.csv", index=False)
        summarize_irfs({bs.key: bdf}, params.plot_horizon_months).to_csv(bdir / "benchmark_summary.csv", index=False)

    return output_dir


def run_all_default_shocks(
    params: Parameters | None = None,
    cfg: ExperimentConfig | None = None,
    base_dir: str | Path = ".",
    variables_to_plot: Iterable[str] = CORE_PLOT_VARS,
    run_terminal_check: bool = False,
) -> List[Path]:
    params = params or Parameters()
    cfg = cfg or ExperimentConfig()
    out = []
    for shock in cfg.shocks_to_run:
        out.append(run_shock_batch(
            params, cfg, shock, base_dir,
            variables_to_plot=variables_to_plot,
            run_terminal_check=run_terminal_check,
        ))
    return out


# =============================================================================
# 10. MAIN
# =============================================================================

def main() -> None:
    params = Parameters()
    cfg = ExperimentConfig(mode="institutional")
    folders = run_all_default_shocks(params, cfg, base_dir=".")
    print("\nCartelle create:")
    for f in folders:
        print(" -", f.resolve())


if __name__ == "__main__":
    main()
