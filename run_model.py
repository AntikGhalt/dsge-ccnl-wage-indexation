"""Eseguire dalla radice del repository."""
import argparse
import json
from pathlib import Path
from model.nk_ccnl_indexation_v3 import Parameters, ExperimentConfig, run_all_default_shocks
ROOT = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['institutional', 'frequency_only'], default='institutional')
    parser.add_argument('--parameters', type=Path, default=ROOT/'config/baseline.json')
    parser.add_argument('--experiment', type=Path)
    parser.add_argument('--shock', choices=['cost_push','energy','technology','monetary_easing','monetary_tightening'])
    parser.add_argument('--output', type=Path, default=ROOT/'outputs')
    parser.add_argument('--terminal-check', action='store_true')
    args = parser.parse_args()
    params = Parameters(**json.loads(args.parameters.read_text()))
    cfg = ExperimentConfig(**json.loads((args.experiment or ROOT/f'config/{args.mode}.json').read_text()))
    if cfg.mode != args.mode:
        parser.error('La modalità della configurazione non coincide con --mode')
    if args.shock:
        cfg.shocks_to_run = (args.shock,)
    for folder in run_all_default_shocks(params, cfg, args.output, run_terminal_check=args.terminal_check):
        print(folder.resolve())

if __name__ == '__main__':
    main()
