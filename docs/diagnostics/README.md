# Prima diagnostica v3 — 29 ottobre 2026

Motore invariato; commit sorgente e configurazioni in `configuration.json`.
Riproduzione: `python diagnostics/run_diagnostics.py --output outputs/diagnostics`.
`metrics.csv` contiene tutte le metriche; `horizons.csv` i confronti terminali.
Sono test interni del prototipo, non stime empiriche.

## Decisioni consigliate

1. Correggere e verificare la complementarità del solver prima di usare gli
   shock grandi. Distinguere correzione della soluzione da correzione del reporting.
2. Conservare il baseline, aggiungere confronti una variabile alla volta e shock
   piccoli. Non modificare parametri per ottenere una spirale desiderata.
3. Formalizzare il significato dello shock energia (livello del prezzo relativo
   o inflazione energetica). Oggi `zenergy` entra direttamente nell'inflazione e
   in un residuo ritardato NKPC; non esiste un settore di input energetici importati
   né una perdita di risorse esplicita (il vincolo di risorse è y=c).
4. Solo successivamente introdurre input importati e distinguere prezzo al
   consumo, prezzo alla produzione, salario reale e ragioni di scambio.
5. Phillips ibrida come estensione separata, motivata e calibrata su dati.

## Risultati cost-push

Area positiva = 100 × somma di max(inflazione mensile, 0), primi 120 mesi,
in punti logaritmici percentuali. Non è il livello finale dei prezzi.
Il controllo gamma=0 mantiene stesso scope, calendario e bargaining della
scala mobile, disattivando soltanto l'indicizzazione. Il benchmark `none`
originale cambia anche scope; viene conservato come diagnostica separata.

| Variazione | Area positiva mobile | Controllo gamma=0 | Rapporto |
|---|---:|---:|---:|
| Baseline | 0,537 | 0,438 | 1,22 |
| rho=0,75, stessa area dello shock esogeno | 0,923 | 0,586 | 1,57 |
| rho=0,90, stessa area dello shock esogeno | 1,862 | 0,704 | 2,65 |
| phi_pi=1,2 | 0,584 | 0,618 | 0,95 |
| Wage drift=0 | 0,662 | 0,317 | 2,09 |

Aumentare rho a parità di innovazione aumenta anche la massa dello shock.
Per separare durata e massa usiamo innovazione × (1-rho)/(1-0,55).
L'indicizzazione amplifica l'area positiva anche a massa esogena costante.
Ma una banca centrale meno reattiva non aumenta meccanicamente il rapporto
mobile/controllo. Con rho=0,90 il picco successivo all'esaurimento dello shock
è addirittura inferiore nel mobile. Le misure di amplificazione e persistenza
non sono intercambiabili.

## Coerenza numerica

Confronti 600 vs 840 mesi: nei primi 120 mesi la massima differenza relativa
al massimo valore assoluto del vettore confrontato è 1,54e-5 (0,00154%).
Copertura: tre regimi istituzionali e benchmark, cost-push ed energia.
Non è una prova di determinazione/unicità; le altre sensitivity richiedono
ulteriori controlli terminali prima di diventare risultati da pubblicare.

La stabilizzazione dell'active set NON garantisce la regola economica:
`wpi_contract = max(indexation + catchup + bargaining, -baseline_growth)`.
A 600 mesi nello shock energia originale (0,01), gli scarti massimi sono:

| Regime | Errore massimo, log mensile | Mesi con errore >1e-8 |
|---|---:|---:|
| Mobile | 0,002103 | 24 |
| Annuale | 0,018410 | 90 |
| Triennale | 0,001973 | 8 |

Il problema riguarda quindi anche la soluzione rispetto alla regola dichiarata,
non soltanto le colonne esportate. Il floor nominale resta soddisfatto, ma alcuni
vincoli restano attivi quando non dovrebbero: fattibilità non è complementarità.
Anche il regime annuale cost-push presenta un errore massimo 1,42e-5.
Il motore non è stato modificato per questa diagnosi.

## Scala dello shock energia

Nel mobile, innovazione 0,01: picco headline 23,37 p.p. annualizzati,
output minimo -11,81%, oltre ai problemi di complementarità.
Con innovazione 0,001: picco 2,465 p.p., output minimo -1,286%, errore della
regola salariale circa 6e-18. Con 0,0001 la risposta scala proporzionalmente.
Questa verifica è per mobile e controlli; non certifica i regimi annuale/triennale.
L'innovazione non va etichettata come aumento del prezzo dell'energia dell'1%:
la variabile entra nell'inflazione, non in un'equazione del livello relativo.

## Metriche e interpretazione

- Picco post-esaurimento: massimo (con segno) dopo che TUTTO il forcing esogeno
  nella NKPC/headline scende definitivamente sotto il 5% del suo massimo.
  Per energia include xenergy_core, non soltanto zenergy. Finestra fino a mese 119.
- Ultimo superamento del 10% del picco: osservato nella finestra di 120 mesi,
  non garantisce rientro permanente oltre la finestra. Il picco è specifico a ogni IRF.
- Area assoluta dal mese 24 distingue le code persistenti di entrambi i segni.
- Differenza tra gamma=1 e gamma=0: effetto dell'indicizzazione nel modello,
  inclusa la risposta di equilibrio generale; non stima causale empirica e non
  attribuzione isolata del solo canale costo marginale.

## Phillips ibrida: correzione alla proposta nell'altra chat

Non aggiungere semplicemente iota*pi[t-1] mantenendo tutti gli altri coefficienti.
Una specifica con indicizzazione dei prezzi è:

(1 + beta*iota) pi[t] = beta E(pi[t+1]) + iota*pi[t-1] + kappa*mc[t] + u[t].

Dunque vanno normalizzati anche i coefficienti forward-looking e degli altri
termini. Definizione e scala di u vanno rese coerenti con la derivazione.
Riferimento: [ECB WP 2400, eq. 1](https://www.ecb.europa.eu/pub/pdf/scpwps/ecb.wp2400~6e8bfb6fd2.en.pdf).
La forma va derivata per il modello scelto; aggiungerla ora confonderebbe nuovi
meccanismi economici con la correzione dei difetti numerici.

## Prossimi test prima di cambiare la calibrazione

- Solver con attivazione E disattivazione dei vincoli; test del residuo di
  complementarità a ogni data, gestione dei cicli e fallimento esplicito se non risolto.
- Tutti i regimi, shock positivi/negativi e griglia di ampiezze; residui delle
  equazioni, soluzione a shock zero e sensibilità 600/840/1200 mesi.
- Calendar month sensitivity e verifica delle tranche per singola coorte.
- Dopo il solver: gamma=0/0,5/1 a parità di scope/indice; energia headline/NEI
  separata dalla frequenza; calibrazione empirica del pass-through e del wage drift.
