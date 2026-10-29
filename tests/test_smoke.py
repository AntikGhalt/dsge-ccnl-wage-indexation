import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import numpy as np
from model import nk_ccnl_indexation_v3 as nk

class SolverTests(unittest.TestCase):
    def check_solution(self,df):
        self.assertTrue(np.isfinite(df.select_dtypes(include='number')).all().all())
        self.assertTrue(df.numerically_valid.all())
        self.assertLessEqual(df.wage_rule_residual.abs().max(),1e-10)
        self.assertLessEqual(df.equation_residual_max.max(),1e-9)
        parts=df.wpi_indexation+df.wpi_catchup+df.wpi_bargaining+df.wpi_floor_adjustment
        np.testing.assert_allclose(df.wpi_contract,parts,atol=1e-10,rtol=0)
        proposed=df.wpi_indexation+df.wpi_catchup+df.wpi_bargaining
        wage=df.wpi_contract.to_numpy();base=df.baseline_contract_growth.to_numpy()
        # Indipendente dalle maschere: fattibilità + complementarità del floor.
        self.assertGreaterEqual((wage+base).min(),-1e-9)
        self.assertGreaterEqual((wage-proposed).min(),-1e-9)
        np.testing.assert_allclose(np.minimum(wage+base,wage-proposed),0,atol=1e-9,rtol=0)

    def test_valid_reference_cases(self):
        p=nk.Parameters();cfg=nk.ExperimentConfig()
        cases=[(nk.get_regime_specs(cfg)[0],'cost_push'),
               (nk.get_regime_specs(cfg)[0],'technology'),
               (nk.get_regime_specs(cfg)[2],'energy'),
               (nk.benchmark_spec(),'energy')]
        for spec,shock in cases:
            with self.subTest(regime=spec.key,shock=shock):
                self.check_solution(nk.solve_irf(p,cfg,spec,shock,cfg.shock_sizes[shock]))

    def test_previously_false_convergence_is_rejected(self):
        # La vecchia v3 restituiva True con un residuo ~0,0021.
        cfg=nk.ExperimentConfig()
        with self.assertRaises(nk.SolverConvergenceError):
            nk.solve_irf(nk.Parameters(),cfg,nk.get_regime_specs(cfg)[0],'energy',.01)

    def test_small_energy_and_scaling(self):
        p=nk.Parameters();cfg=nk.ExperimentConfig();spec=nk.get_regime_specs(cfg)[0]
        a=nk.solve_irf(p,cfg,spec,'energy',.001)
        b=nk.solve_irf(p,cfg,spec,'energy',.0001)
        self.check_solution(a);self.check_solution(b)
        np.testing.assert_allclose(a[['y','pi_headline','wpi_eff']],10*b[['y','pi_headline','wpi_eff']],atol=1e-10,rtol=1e-8)

    def test_zero_shock(self):
        for mode in ('institutional','frequency_only'):
            cfg=nk.ExperimentConfig(mode=mode)
            for spec in nk.get_regime_specs(cfg)+[nk.benchmark_spec()]:
                df=nk.solve_irf(nk.Parameters(solve_horizon_months=108),cfg,spec,'energy',0.)
                self.check_solution(df)
                np.testing.assert_allclose(df[nk.VARS],0,atol=1e-10)

    def test_iteration_limit_is_an_error(self):
        cfg=nk.ExperimentConfig()
        with self.assertRaises(nk.SolverConvergenceError):
            nk.solve_irf(nk.Parameters(active_set_max_iter=1),cfg,nk.get_regime_specs(cfg)[2],'cost_push',.001)

    def test_failed_batch_has_status_and_no_invalid_irfs(self):
        cfg=nk.ExperimentConfig(run_no_indexation_benchmark=True)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(nk,'solve_irf',side_effect=nk.SolverConvergenceError('test failure')):
                path=nk.run_shock_batch(nk.Parameters(),cfg,'energy',folder,variables_to_plot=[])
            status=json.loads((path/'run_status.json').read_text())
            self.assertFalse(status['all_requested_scenarios_valid'])
            self.assertEqual(len(status['scenarios']),4)
            self.assertTrue(all(x['status']=='failed' for x in status['scenarios']))
            self.assertEqual(len((path/'irf_all_scenarios.csv').read_text().splitlines()),1)

    def test_notebook_sources_compile(self):
        root=Path(__file__).resolve().parents[1]
        n=json.loads((root/'notebooks/run_model_colab.ipynb').read_text())
        for cell in n['cells']:
            if cell['cell_type']=='code': compile(''.join(cell['source']),'notebook','exec')

if __name__=='__main__': unittest.main()
