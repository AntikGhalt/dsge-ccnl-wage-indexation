"""Griglia di regressione v3.1. Registra fallimenti, non li conta come soluzioni."""
import argparse,json,sys,platform,subprocess
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from model import nk_ccnl_indexation_v3 as nk

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/solver_validation')
    parser.add_argument('--reference',type=Path,help='Cartella locale dei CSV della run originale, opzionale')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    p=nk.Parameters(**json.loads((ROOT/'config/baseline.json').read_text()))
    rows=[];comparison=[];cache={}
    def attempt(cfg,spec,shock,size,T,case):
        row=dict(case=case,mode=cfg.mode,regime=spec.key,shock=shock,shock_size=size,horizon=T)
        try:
            df=nk.solve_irf(p,cfg,spec,shock,size,T)
            row.update(status='valid',error=None,**{k:v for k,v in nk.numerical_diagnostics(df).items() if k!='regime'})
            row.update({k:v for k,v in nk.propagation_metrics(df,p,180).items() if k!='regime'})
            if args.reference and cfg.mode=='institutional' and case=='baseline':
                f=args.reference/f'{shock}_irf_all_scenarios.csv'
                if f.exists():
                    old=pd.read_csv(f);old=old[old.regime_key==spec.key].reset_index(drop=True)
                    if len(old)==len(df):
                        comparison.append(dict(regime=spec.key,shock=shock,
                            old_pi_peak_pp=float(old.pi_headline.iloc[:180].max()*1200),new_pi_peak_pp=float(df.pi_headline.iloc[:180].max()*1200),
                            old_output_min_pct=float(old.y.iloc[:180].min()*100),new_output_min_pct=float(df.y.iloc[:180].min()*100),
                            max_output_change_pct=float(np.abs(old.y.iloc[:180]-df.y.iloc[:180]).max()*100)))
        except nk.SolverConvergenceError as exc:
            df=None;row.update(status='failed',error=str(exc))
        rows.append(row);print(case,cfg.mode,spec.key,shock,size,T,row['status'],flush=True)
        return df
    for mode in ('institutional','frequency_only'):
        cfg=nk.ExperimentConfig(mode=mode)
        for spec in nk.get_regime_specs(cfg)+[nk.benchmark_spec()]:
            for shock in ('cost_push','energy','technology'):
                size=cfg.shock_sizes[shock]
                cache[(mode,spec.key,shock)]=attempt(cfg,spec,shock,size,600,'baseline')
                # Entrambi i segni, ampiezza ridotta; non cambia il baseline economico.
                for scale in (.1,-.1):
                    attempt(cfg,spec,shock,size*scale,600,'small_signed')
    horizons=[];cfg=nk.ExperimentConfig()
    for spec in nk.get_regime_specs(cfg):
        for shock in ('cost_push','energy','technology'):
            a=cache[('institutional',spec.key,shock)]
            if a is None: continue
            for T in (840,1200):
                b=attempt(cfg,spec,shock,cfg.shock_sizes[shock],T,'horizon')
                if b is not None:
                    cols=['pi_headline','pi_nei','y','weff_r','mc','i']
                    x=a[cols].iloc[:120].to_numpy();y=b[cols].iloc[:120].to_numpy()
                    horizons.append(dict(regime=spec.key,shock=shock,T1=600,T2=T,
                        relative_difference=float(np.abs(x-y).max()/max(np.abs(y).max(),1e-12)),
                        pi_max_difference_pp=float(1200*np.abs(a.pi_headline.iloc[:120]-b.pi_headline.iloc[:120]).max())))
    pd.DataFrame(rows).to_csv(args.output/'validation.csv',index=False)
    pd.DataFrame(comparison).to_csv(args.output/'before_after.csv',index=False)
    pd.DataFrame(horizons).to_csv(args.output/'horizon_checks.csv',index=False)
    (args.output/'manifest.json').write_text(json.dumps(dict(
        base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        model_sha256=__import__('hashlib').sha256((ROOT/'model/nk_ccnl_indexation_v3.py').read_bytes()).hexdigest(),
        python=platform.python_version(),parameters=p.__dict__,valid=sum(x['status']=='valid' for x in rows),failed=sum(x['status']=='failed' for x in rows)),indent=2))
if __name__=='__main__':main()
