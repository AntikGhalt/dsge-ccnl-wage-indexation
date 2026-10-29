"""Diagnostica riproducibile del motore v3 invariato. Non calibrazione empirica."""
import argparse,json,sys,subprocess,platform
from pathlib import Path
from dataclasses import replace,asdict
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from model import nk_ccnl_indexation_v3 as nk

def measure(df,p,cfg,spec,shock,H=120):
    cal=nk.calibrate_monthly(p)
    bc,F,cc=nk._wage_rule_linear_objects(p,spec,len(df))
    comp=nk._evaluate_wage_components(df,p,spec,bc,F,cc)
    # Test della regola economica dichiarata, non del solo active-set monotono.
    intended=np.maximum(comp['proposed'],-comp['baseline_growth'])
    gap=df.wpi_contract.to_numpy()-intended
    pi=df.pi_headline.to_numpy()[:H]
    forcing=(df.zcost+df.xenergy_core).to_numpy()
    if shock=='energy': forcing=forcing+p.energy_weight_headline*df.zenergy.to_numpy()
    threshold=.05*np.max(np.abs(forcing))
    hits=np.flatnonzero(np.abs(forcing)>threshold)
    exhausted=int(hits[-1]+1) if len(hits) else 0
    post=pi[exhausted:]
    tail=np.flatnonzero(np.abs(pi)>.1*np.max(np.abs(pi)))
    return dict(peak_pp_annual=float(1200*pi.max()),positive_area_logpct=float(100*np.maximum(pi,0).sum()),
      net_price_logpct=float(100*pi.sum()),last_above_10pct=int(tail[-1]) if len(tail) else -1,
      forcing_exhausted_month=exhausted,post_forcing_peak_pp_annual=float(1200*post.max()) if len(post) else np.nan,
      absolute_tail_logpct=float(100*np.abs(pi[24:]).sum()),y_min_pct=float(100*df.y.iloc[:H].min()),
      mc_peak_pct=float(100*df.mc.iloc[:H].max()),kappa=cal.kappa_price,
      floor_rule_max_error=float(np.abs(gap).max()),floor_rule_bad_months=int((np.abs(gap)>1e-8).sum()),
      component_max_error=float(np.abs(df.wpi_contract-comp['final']).max()),
      floor_nominal_min=float((df.wpi_contract+df.baseline_contract_growth).min()),
      active_set_converged=bool(df.active_set_converged.all()),
      max_abs_state=float(np.abs(df[nk.VARS].to_numpy()).max()))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'outputs/diagnostics')
    a=parser.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    p=nk.Parameters(**json.loads((ROOT/'config/baseline.json').read_text()))
    cfg=nk.ExperimentConfig(**json.loads((ROOT/'config/institutional.json').read_text()))
    mobile=nk.get_regime_specs(cfg)[0];none=nk.benchmark_spec()
    matched=replace(mobile,key="mobile_gamma0",label="Mobile con gamma=0",gamma=0.)
    cases=[('baseline',{},1.),('rho_075',{'rho_cost_m':.75},1.),('rho_090',{'rho_cost_m':.9},1.),
      ('rho_075_equal_area',{'rho_cost_m':.75},.25/.45),('rho_090_equal_area',{'rho_cost_m':.9},.1/.45),
      ('phi_15',{'phi_pi':1.5},1.),('phi_12',{'phi_pi':1.2},1.),
      ('omega_065',{'omega_q':.65},1.),('omega_085',{'omega_q':.85},1.),
      ('drift_zero',{'wage_drift_speed_m':0.},1.)]
    rows=[];horizons=[];cache={}
    for name,overrides,scale in cases:
      for spec in (mobile,matched,none):
        pp=replace(p,**overrides);df=nk.solve_irf(pp,cfg,spec,'cost_push',cfg.shock_sizes['cost_push']*scale)
        row=dict(case=name,regime=spec.key,shock='cost_push',horizon=pp.solve_horizon_months,shock_scale=scale,**measure(df,pp,cfg,spec,'cost_push'))
        rows.append(row);cache[(name,spec.key)]=df
        print(name,spec.key,'rule_error',row['floor_rule_max_error'],flush=True)
    # Orizzonti: tutti i regimi, entrambi gli shock; confronti entro 120 mesi.
    for shock in ('cost_push','energy'):
      for spec in nk.get_regime_specs(cfg)+[none]:
        small=cache.get(('baseline',spec.key)) if shock=='cost_push' else None
        if small is None: small=nk.solve_irf(p,cfg,spec,shock,cfg.shock_sizes[shock])
        large=nk.solve_irf(p,cfg,spec,shock,cfg.shock_sizes[shock],840)
        cols=['pi_headline','pi_nei','wpi_contract','weff_r','mc','y','i']
        x=small[cols].iloc[:120].to_numpy();y=large[cols].iloc[:120].to_numpy()
        horizons.append(dict(shock=shock,regime=spec.key,T1=600,T2=840,
           max_abs_difference=float(np.abs(x-y).max()),relative_max_difference=float(np.abs(x-y).max()/max(np.abs(y).max(),1e-12)),
           inflation_max_diff_pp_annual=float(1200*np.abs(small.pi_headline.iloc[:120]-large.pi_headline.iloc[:120]).max())))
        for T,df in ((600,small),(840,large)):
          rows.append(dict(case='horizon',regime=spec.key,shock=shock,horizon=T,shock_scale=1.,**measure(df,p,cfg,spec,shock)))
        print('horizon',shock,spec.key,horizons[-1]['relative_max_difference'],flush=True)
    # Scala shock energia: distingue amplificazione lineare e vincoli nonlineari.
    for scale in (.1,.01):
      for spec in (mobile,matched,none):
        df=nk.solve_irf(p,cfg,spec,'energy',cfg.shock_sizes['energy']*scale)
        rows.append(dict(case='energy_scale',regime=spec.key,shock='energy',horizon=600,shock_scale=scale,**measure(df,p,cfg,spec,'energy')))
    pd.DataFrame(rows).to_csv(a.output/'metrics.csv',index=False)
    pd.DataFrame(horizons).to_csv(a.output/'horizons.csv',index=False)
    meta=dict(parameters=asdict(p),experiment=asdict(cfg),cases=cases,measurement_months=120,
      source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),python=platform.python_version())
    (a.output/'configuration.json').write_text(json.dumps(meta,indent=2))

if __name__=='__main__': main()
