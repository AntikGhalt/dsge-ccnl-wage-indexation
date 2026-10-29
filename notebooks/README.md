# Colab collegato al repository

[Apri il notebook](https://colab.research.google.com/github/AntikGhalt/dsge-ccnl-wage-indexation/blob/main/notebooks/run_model_colab.ipynb).
Anche `DSGE_run_save.ipynb` e `SDGE_run.ipynb` nella radice sono stati aggiornati.

1. Eseguire il setup: scarica codice e configurazioni da GitHub.
2. Scegliere esperimenti e modificare soltanto `CUSTOM_PARAMS` / `CUSTOM_SHOCK_SIZES`.
3. Eseguire simulazioni, grafici e tabelle.
4. Opzionalmente impostare `SAVE_TO_DRIVE=True`: salva una cartella distinta per run.

`GIT_REF='main'` usa la versione corrente; uno SHA fissa una versione riproducibile.
Ogni run conserva commit, parametri, codice ed elenco delle librerie installate.
Il salvataggio non cancella più la cartella dei risultati precedenti.

Una copia già aperta/salvata in Colab non aggiorna le proprie celle automaticamente:
riaprire il link GitHub per usare il notebook aggiornato. Le modifiche fatte in
Colab non tornano automaticamente su GitHub.

Verifica locale: sintassi di tutte le celle e run cost-push a 180 mesi con grafici.
Il clone/setup e il mount di Google Drive richiedono verifica nella sessione Colab.
