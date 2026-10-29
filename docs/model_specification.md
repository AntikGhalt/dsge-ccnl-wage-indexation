# Specifica economica — modello CCNL v3

## 1. Concetti da non confondere

| Concetto | Significato nel modello | Cosa NON significa |
|---|---|---|
| **Baseline** | Sentiero già atteso prima dello shock: inflazione prevista e aumenti salariali già programmati. Le IRF mostrano solo le deviazioni da questo sentiero. | Non è un terzo indice di inflazione. |
| **Headline** | Inflazione complessiva, inclusa la componente energetica importata diretta. | Non è l'IPCA-NEI. |
| **IPCA-NEI stilizzato** | Inflazione al netto dell'energia importata diretta, ma con pass-through indiretto dell'energia sugli altri prezzi. | Non è immune agli shock energetici. |
| **None** | Benchmark diagnostico senza indicizzazione automatica allo shock. Restano wage drift e bargaining. | Non è uno dei tre regimi principali e non è un tipo di inflazione. |
| **Bargaining** | Revisione reale del minimo verso il benchmark Nash. | Non coincide con l'indicizzazione. |
| **Catch-up** | Recupero dell'errore positivo di inflazione non già compensato. | Non è un aumento reale negoziato. |
| **Wage drift** | Aumenti individuali: superminimi, promozioni, mobilità, merit pay. | Non richiede un rinnovo del minimo CCNL. |

## 2. Esperimento principale: `institutional`

| Regime | Indicizzazione | Indice | Base salariale | Calendario indicizzazione | Bargaining | Inflazione futura prevista |
|---|---|---|---|---|---|---|
| **Scala mobile style — N=1** | Automatica mensile | Headline | Intera retribuzione | Ogni mese, con un mese di lag di osservazione nel baseline numerico | Ogni 36 mesi, orologio separato | Non serve una tranche previsionale: l'adeguamento è mensile |
| **Aggiornamento annuale — N=12** | Automatica ex post | IPCA-NEI | Minimo CCNL | Tutti a giugno; usa il NEI dell'anno solare precedente | Ogni 36 mesi, orologio separato | Non serve per la compensazione ordinaria: il meccanismo usa il consuntivo annuale |
| **CCNL tradizionale — N=36** | L'inflazione prevista è già nelle tranche del baseline; lo shock inatteso viene recuperato al rinnovo | IPCA-NEI | Minimo CCNL | Rinnovi triennali staggered | Al rinnovo triennale | Sì: al nuovo rinnovo si forma una nuova previsione condizionata allo shock e viene distribuita nelle tranche future |

### Regime triennale: cosa significa lavorare in deviazioni dal baseline

Se a inizio contratto erano previsti aumenti coerenti con un'inflazione del 2% annuo, queste tranche sono già nel baseline e quindi non appaiono nelle IRF.

Se dopo la firma arriva uno shock che porta l'inflazione al 4%, il modello vede la **sorpresa di +2 punti**, non il 4% intero. Al rinnovo successivo la parte di inflazione inattesa non già compensata viene recuperata come `catch-up`.

Al nuovo rinnovo, lo shock già avvenuto modifica anche la previsione dell'inflazione futura: questa deviazione attesa entra nelle nuove tranche del contratto successivo.

## 3. Le tre componenti del rinnovo

\[
\Delta W^{CCNL}=I_t+C_t+B_t
\]

- **Indicizzazione / tranche previste (`I_t`)**: compensazione dell'inflazione prevista o consuntiva secondo il regime.
- **Catch-up (`C_t`)**: recupero della perdita di potere d'acquisto dovuta a un errore positivo di previsione e non già compensata.
- **Bargaining (`B_t`)**: aumento reale negoziato, separato dall'inflazione, guidato nel prototipo dal gap rispetto al benchmark Nash.

Il bargaining ha sempre un proprio orologio di 36 mesi.

## 4. Downward nominal wage rigidity

Il minimo nominale non può diminuire. Il vincolo corretto è applicato al salario totale:

\[
\Delta W^{baseline}_t + \Delta W^{IRF}_t \ge 0.
\]

Quindi una IRF salariale negativa è ammessa se riduce un aumento già previsto senza trasformarlo in un taglio nominale.

Esempio: baseline +2%, shock -1% -> aumento nominale effettivo +1%, non 0%.

## 5. Shock energetico e IPCA-NEI

Lo shock energia ha due canali:

1. **diretto e immediato** sull'headline;
2. **indiretto e ritardato** sul NEI tramite uno stato `xenergy_core`:

\[
x^E_t = \rho_x x^E_{t-1}+\lambda_E z^E_{t-1}.
\]

Quindi uno shock energetico persistente contamina progressivamente anche trasporti, input, margini, servizi e altri prezzi inclusi nell'IPCA-NEI.

## 6. Durata degli shock nel baseline numerico

Gli shock non durano un numero fisso di mesi: seguono processi AR(1) e decadono gradualmente.

| Shock | Persistenza default | Half-life indicativa |
|---|---:|---:|
| Cost-push domestico | 0,55 mensile | ~1,2 mesi |
| Energia importata diretta | 0,75 mensile | ~2,4 mesi |
| Tecnologia | 0,80 trimestrale, convertita mensilmente | ~9,3 mesi |

La pressione energetica indiretta sul core ha inoltre una propria persistenza (`rho_energy_core_m`, default 0,85).

## 7. Esperimento di identificazione: `frequency_only`

Per isolare la sola frequenza, si tiene tutto il resto uguale:

- indice: IPCA-NEI;
- scope: minimo CCNL;
- gamma: 1;
- bargaining: ogni 36 mesi;
- timing: staggered;
- stessi shock e stessi parametri macro.

Cambia soltanto la frequenza di recupero dell'inflazione passata: `D=1`, `D=12`, `D=36`.

Questo serve a distinguere l'effetto puro del **ritardo temporale** dall'effetto del diverso disegno istituzionale.
