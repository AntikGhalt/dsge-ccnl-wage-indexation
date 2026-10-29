# Validazione numerica — v3.1

Il modello economico e la calibrazione v3 sono invariati. Il solver ora aggiorna
i vincoli in entrambe le direzioni e verifica i residui prima di restituire una
soluzione. Vedere [rapporto v3.1](solver_v31/README.md) per risultati e limiti.

## Garanzie operative

- Ogni DataFrame restituito da `solve_irf` supera il controllo della regola
  salariale, delle equazioni e del floor nominale entro le tolleranze dichiarate.
- Se il solver non trova una soluzione verificata, solleva un errore esplicito.
- Il batch registra gli scenari falliti in `run_status.json` e li esclude da CSV
  delle IRF e grafici; il Colab segnala che il confronto è incompleto.
- I test coprono soluzioni valide, shock nullo, proporzionalità per piccoli shock,
  complementarità, identità delle componenti e corretto rifiuto di vecchi falsi positivi.

## Limiti aperti

Alcune configurazioni baseline restano non risolte. Il solver non è globale e
un suo fallimento non dimostra inesistenza dell'equilibrio. Convergenza verificata
non implica unicità o determinazione DSGE (da studiare separatamente).
Il floor è aggregato, con crescita baseline mensile uniforme per le coorti
staggered: non è una verifica contratto per contratto.
L'energia è ancora un forcing stilizzato, non un settore di input importati.
Le ampiezze e i parametri non sono una calibrazione empirica italiana.
Le IRF grandi richiedono anche una valutazione dell'approssimazione locale.

## Provenienza

La [diagnostica v3](diagnostics/README.md) rimane un rapporto storico del motore
prima della correzione. I suoi CSV non sono stati sovrascritti.
I risultati della nuova versione sono in `docs/solver_v31/`.
Il confronto di riferimento usa la run Drive `20261029T112329_628949Z_3601f752`.
