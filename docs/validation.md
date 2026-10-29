# Stato della validazione

Il motore è importato senza modifiche dal bundle v3 del 29 ottobre 2026.
I test verificano valori finiti, stabilizzazione dell'active set, floor nominale
aggregato e risposta nulla a shock nullo.
Coprono entrambi gli esperimenti e i tre shock principali, incluso il benchmark.
Non costituiscono validazione econometrica né prova di determinazione DSGE.

## Questioni aperte prima di una versione da paper

- L'active set conservativo non disattiva i vincoli già attivati: la sua
  stabilizzazione non dimostra le condizioni complete di complementarità.
- Il floor è aggregato: per coorti staggered il baseline è approssimato con
  crescita mensile uniforme. Non verifica ogni singolo contratto.
- Verificare sensibilità all'orizzonte terminale (`--terminal-check`), calibrazione,
  ampiezza degli shock e ritorno delle IRF al baseline.
- Formalizzare aspettative e forecast delle tranche e verificare stabilità e
  determinazione con un metodo appropriato al sistema.
- IPCA-NEI e scala mobile sono rappresentazioni stilizzate.
- Il parametro 0,70 è la quota contrattuale nel salario effettivo, non una
  percentuale di imprese che applica gli aumenti; non è una stima empirica.
- I rinnovi sono uniformi e deterministici, non CCNL reali estratti casualmente.
  Il calendario empirico resta uno sviluppo futuro.

Il controllo generale del notebook seguirà il suo caricamento.

## Bug v3 riprodotto: scomposizione salariale

A 180 mesi, scala mobile con shock energia 0,01: le componenti esportate non
sommano a `wpi_contract` (scarto massimo osservato circa 0,002116 in unità
logaritmiche mensili). Il solver conserva i vincoli attivati, mentre il reporting
ricalcola il floor con un max sul percorso finale. Anche il catch-up usa logiche
diverse di attivazione e reporting. Non interpretare la scomposizione come una
identità contabile verificata. Il test dedicato è marcato `expectedFailure`: una
correzione dovrà rimuovere questa marcatura e controllare tutti gli scenari.
Il motore originale è preservato; il problema non è stato corretto in questa importazione.
