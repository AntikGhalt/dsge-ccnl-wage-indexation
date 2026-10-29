# Solver v3.1: ambito della correzione

Questa versione sostituisce l'active set monotono della v3 con un Newton
semismooth che permette attivazione e disattivazione di floor e catch-up.
Un backtracking sul residuo salariale evita di accettare passi che lo peggiorano.
Prima di restituire una traiettoria vengono verificati regola salariale esatta,
equazioni macro e fattibilità del floor. Il reporting usa le stesse componenti
che definiscono la regola risolta.

Non sono cambiati i parametri economici, le equazioni macro, gli shock o il
calendario contrattuale. Il nome del modulo resta compatibile con il Colab.

## Cosa è risolto e cosa rimane aperto

È eliminata la falsa convergenza: un active set che smette di cambiare non viene
più scambiato per una soluzione. Alcuni casi prima incoerenti ora hanno una
soluzione verificata; altri provocano `SolverConvergenceError`.

La ricerca non è un solver globale di complementarità e non garantisce di
risolvere qualsiasi configurazione. Un fallimento NON dimostra che l'equilibrio
non esista; una soluzione con residui piccoli NON dimostra unicità, determinazione
o plausibilità economica. Le configurazioni non risolte restano un limite
esplicito di questa versione. Non sono state alterate per farle convergere.

Il batch continua con gli altri scenari, scrive `run_status.json` e non esporta
le traiettorie non validate. Il Colab mostra le assenze prima dei grafici.
Il runner da terminale termina con errore se una run è incompleta.
Il test di regressione che prima era un fallimento atteso ora verifica che la
vecchia falsa soluzione sia rifiutata. Questo è un test di corretto rifiuto,
non una prova che quel caso sia stato risolto.

## Output aggiuntivi

- `numerical_diagnostics.csv`: residui, numero di iterazioni, passi ridotti,
  floor nominale e date dei vincoli attivati.
- `propagation_metrics.csv`: area positiva, variazione cumulata dei prezzi in
  punti logaritmici, coda assoluta dal mese 24 e picco dopo l'esaurimento del forcing.
- `run_status.json`: esito per ciascun regime, errori e stato dei test terminali.
- `terminal_horizon_check.csv`: se richiesto, confronto 600/840 per tutti i
  regimi principali che hanno una soluzione, non più soltanto l'ultimo.

Le metriche hanno una finestra finita, non dimostrano un ritorno permanente
all'equilibrio. Il forcing energetico include la pressione indiretta ritardata.
Per lo shock tecnologico non si attribuisce un picco a un forcing NKPC assente.

## Diagnostica opzionale in Colab

`RUN_SENSITIVITY_DIAGNOSTICS=True` esegue la suite separata sui JSON baseline del
repository (non sui CUSTOM_PARAMS del notebook). Include il controllo gamma=0
con stesso scope/bargaining e i confronti a massa esogena costante.
I casi non risolti sono registrati in `failures.csv`, mai inclusi come risultati.
`RUN_TERMINAL_CHECK=True` verifica anche la sensibilità all'orizzonte delle run
personalizzate. Queste opzioni possono richiedere diversi minuti.

## Prossimi passi

1. Studiare i casi non risolti con una formulazione MCP/LCP e un controllo di
   determinazione/stabilità del blocco macro. Evitare di attribuire tutti i
   fallimenti a un'unica causa senza una prova.
2. Verificare il floor per singola coorte e la distribuzione delle tranche:
   il vincolo attuale resta aggregato.
3. Solo dopo: energia come input importato e Phillips ibrida come estensione
   economica separata. Non aggiunte in questa versione.

## Verifica eseguita

Griglia in `validation.csv`: 82 esecuzioni, comprese ripetizioni del benchmark
nei due modi e controlli terminali. 67 soluzioni validate, 15 ricerche fallite.
Tra i 24 casi baseline (benchmark incluso in entrambi i modi): 18 validi e 6
non risolti. Tra 48 casi piccoli con entrambi i segni: 39 validi e 9 non risolti.
Tutti i 10 confronti aggiuntivi di orizzonte sui casi selezionati sono riusciti.
Residuo salariale massimo tra i successi: 3,47e-17; residuo delle equazioni:
1,06e-15. Il massimo scarto relativo nei confronti 600/840/1200 sui primi 120
mesi è inferiore a 7e-6, per le variabili selezionate. Non estendere questa
conclusione agli scenari falliti o a tutte le sensitivity.

| Shock istituzionale | Mobile | Annuale NEI | Triennale |
|---|---|---|---|
| Cost-push | Validato | Non risolto | Validato |
| Energia | Non risolto | Non risolto | Validato |
| Tecnologia | Validato | Validato | Non risolto |

In `frequency_only`, restano non risolti gli shock energia con D=1 e D=12.
I benchmark senza indicizzazione superano i controlli nei casi baseline.

## Confronto con la run Drive

`before_after.csv` confronta solo gli scenari con soluzione verificata nuova.
La vecchia run è `20261029T112329_628949Z_3601f752`; il motore originale è stato
verificato identico al sorgente v3. Non si sostituiscono i fallimenti con i vecchi
risultati. I valori seguenti si riferiscono ai primi 180 mesi:

| Energia, regime triennale | v3 precedente | v3.1 verificata |
|---|---:|---:|
| Picco headline, p.p. annualizzati | 12,900 | 14,002 |
| Minimo output, % rispetto al baseline | -3,984 | -5,110 |

Mobile cost-push, mobile tecnologia e triennale cost-push sono invariati entro
l'errore numerico. L'annuale tecnologia cambia poco (massimo scarto dell'output
circa 0,0041 punti percentuali). Per le configurazioni fallite non viene prodotto
un nuovo confronto quantitativo.

## Riproduzione

```bash
python -m unittest discover -s tests -v
python diagnostics/validate_solver.py --output outputs/solver_validation
```

Per il confronto con una copia locale dei CSV originali, aggiungere
`--reference /percorso/csv`; i nomi attesi sono `cost_push_irf_all_scenarios.csv`,
`energy_irf_all_scenarios.csv`, `technology_irf_all_scenarios.csv`.
Il manifest conserva hash SHA256 del motore e configurazione completa.
