import unittest
import numpy as np
from model.nk_ccnl_indexation_v3 import Parameters, ExperimentConfig, get_regime_specs, benchmark_spec, solve_irf

class SmokeTests(unittest.TestCase):
    def test_scenarios(self):
        p = Parameters(solve_horizon_months=180, plot_horizon_months=60)
        for mode in ('institutional', 'frequency_only'):
            cfg = ExperimentConfig(mode=mode)
            for spec in get_regime_specs(cfg) + [benchmark_spec()]:
                for shock in ('cost_push', 'energy', 'technology'):
                    with self.subTest(mode=mode, regime=spec.key, shock=shock):
                        df = solve_irf(p, cfg, spec, shock, cfg.shock_sizes[shock])
                        self.assertEqual(len(df), 180)
                        self.assertTrue(np.isfinite(df.select_dtypes(include='number')).all().all())
                        self.assertTrue(df.active_set_converged.all())
                        self.assertGreaterEqual((df.baseline_contract_growth + df.wpi_contract).min(), -1e-8)
    @unittest.expectedFailure
    def test_known_v3_component_accounting_bug(self):
        # Regressione documentata: solver conservativo e reporting non coincidono.
        p = Parameters(solve_horizon_months=180)
        cfg = ExperimentConfig()
        df = solve_irf(p, cfg, get_regime_specs(cfg)[0], 'energy', cfg.shock_sizes['energy'])
        parts = df.wpi_indexation + df.wpi_catchup + df.wpi_bargaining + df.wpi_floor_adjustment
        np.testing.assert_allclose(df.wpi_contract, parts, atol=1e-8)

    def test_zero_shock(self):
        p = Parameters(solve_horizon_months=108)
        for mode in ('institutional','frequency_only'):
            cfg = ExperimentConfig(mode=mode)
            for spec in get_regime_specs(cfg):
                df = solve_irf(p,cfg,spec,'energy',0.)
                np.testing.assert_allclose(df[['y','pi_headline','pi_nei','wpi_contract','wpi_eff']],0.,atol=1e-10)

if __name__ == '__main__':
    unittest.main()
