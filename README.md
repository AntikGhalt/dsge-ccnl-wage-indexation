# DSGE CCNL wage indexation

Prototipo New Keynesian mensile con mercato del lavoro e regimi stilizzati di
indicizzazione salariale. **Versione di lavoro v3, non ancora validata per un paper.**

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

- `model/nk_ccnl_indexation_v3.py`: motore v3 originale senza modifiche.
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

**Bug noto v3:** la scomposizione salariale esportata non sempre coincide con
la soluzione. Un test riproduce il problema come fallimento atteso; dettagli in
[validation.md](docs/validation.md).

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

Il solver v3 resta invariato: gli esiti per shock grandi non sono ancora affidabili
come risultati quantitativi. Il prossimo intervento prioritario è la complementarità,
prima di modificare la calibrazione o introdurre una Phillips ibrida.
