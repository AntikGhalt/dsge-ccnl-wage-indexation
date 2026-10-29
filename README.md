# DSGE CCNL wage indexation

Prototipo New Keynesian mensile con mercato del lavoro e regimi stilizzati di
indicizzazione salariale. **Versione di lavoro v3.1, non ancora validata per un paper.**

## Regimi

| Specifica | Scala mobile style | Annuale NEI | CCNL tradizionale |
|---|---|---|---|
| Frequenza | Mensile, lag 1 mese | Giugno | Rinnovo triennale staggered |
| Indice | Headline | NEI anno solare precedente | Sorpresa NEI rispetto alle previsioni |
| Base | Intera retribuzione | Minimo CCNL | Minimo CCNL |
| Bargaining | Ogni 36 mesi | Ogni 36 mesi | Ogni 36 mesi |
| Previsioni future | — | — | Nuove tranche al rinnovo |

`institutional` confronta questi disegni. `frequency_only` tiene comuni NEI,
minimo, intensità e bargaining, variando D=1,12,36. `none` è un benchmark separato.
Le IRF sono deviazioni dal sentiero atteso: il baseline nominale (default 2%
annuo) conta nel floor, che ammette deviazioni salariali negative.
L'energia influenza direttamente l'headline e indirettamente il NEI con ritardo.

## Avvio

Python 3.10 o successivo; CI configurata su Python 3.11.

```bash
python -m pip install -r requirements.txt
python run_model.py --mode institutional --shock energy
python run_model.py --mode frequency_only
python -m unittest discover -s tests -v
```

Senza `--shock` si eseguono cost-push, energia e tecnologia. PNG, CSV e
configurazione JSON del run finiscono in `outputs/`, esclusa dal versionamento.
Run con la stessa modalità e shock sovrascrivono gli output: usare
`--output outputs/run_02` per conservarli. `--terminal-check` aggiunge una
diagnostica su un regime, non certifica tutti gli scenari.

## Struttura

- `model/nk_ccnl_indexation_v3.py`: motore v3.1, nome conservato per compatibilità.
- `config/baseline.json`: parametri modificabili senza toccare le equazioni.
- `config/institutional.json`, `config/frequency_only.json`: esperimenti.
- `run_model.py`: runner locale e Colab.
- `notebooks/run_model_colab.ipynb`: notebook collegato al modello su GitHub.
- `docs/model_specification.md`: specifica economica originale.
- `docs/validation.md`: limiti e verifiche necessarie.
- `tests/`: controlli numerici automatici.

Il runner carica i JSON; `Parameters()` usa invece i default del motore.
Configurazioni alternative: `--parameters FILE` e `--experiment FILE`
(con modalità coerente con `--mode`).

**Stato v3.1:** è eliminata la falsa convergenza del vecchio active set.
Ogni soluzione restituita supera i controlli dei residui. Alcune configurazioni
restano non risolte e sono segnalate esplicitamente; il loro fallimento non
prova l'inesistenza dell'equilibrio. [Rapporto e risultati](docs/solver_v31/README.md).

## Riproducibilità

Conservare SHA del commit e `run_configuration.json` con i risultati.
Le dipendenze hanno intervalli compatibili, non un lockfile esatto.
Consultare [i limiti del solver](docs/validation.md) prima di interpretare le IRF.

## Colab e prima diagnostica

[Apri in Colab](https://colab.research.google.com/github/AntikGhalt/dsge-ccnl-wage-indexation/blob/main/notebooks/run_model_colab.ipynb).
Il notebook carica modello e JSON dal repository; non serve caricare manualmente il Python.
Ogni run conserva commit e configurazioni. Il salvataggio Drive è opzionale e non cancella le run precedenti.

[Rapporto diagnostico e prossimi test](docs/diagnostics/README.md): sensitivity,
confronto di orizzonti, shock piccoli e bug di complementarità confermato.

```bash
python diagnostics/run_diagnostics.py --output outputs/diagnostics
```

Il Colab mostra `run_status.json`, residui e metriche di propagazione.
`RUN_SENSITIVITY_DIAGNOSTICS=True` esegue una suite opzionale sulla configurazione
baseline; `RUN_TERMINAL_CHECK=True` confronta gli orizzonti per i regimi validi.
I grafici escludono i casi non risolti e vanno letti insieme alla tabella di stato.
Il runner CLI termina con errore se una run è incompleta, pur conservando i risultati validi.

Per ripetere la griglia di validazione:

```bash
python diagnostics/validate_solver.py --output outputs/solver_validation
```

Restano prioritari i casi non risolti e la verifica di determinazione, prima di
cambiare calibrazione, blocco energetico o Phillips curve.
