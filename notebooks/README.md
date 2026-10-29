# Notebook Colab da aggiungere

Caricare qui `run_model_colab.ipynb`. Il notebook non è ancora incluso.
Prima cella suggerita:

```python
!git clone https://github.com/AntikGhalt/dsge-ccnl-wage-indexation.git
%cd /content/dsge-ccnl-wage-indexation
%pip install -r requirements.txt
```

Esecuzione e import:

```python
!python run_model.py --mode institutional --shock energy
from model.nk_ccnl_indexation_v3 import Parameters, ExperimentConfig, run_all_default_shocks
```

Per la vecchia cella Colab v3, impostare `MODEL_FILE` a
`/content/dsge-ccnl-wage-indexation/model/nk_ccnl_indexation_v3.py`.
Confrontare il suo dizionario PARAMS con `config/baseline.json`.
Output in `outputs/`; salvarli su Drive per conservarli oltre la sessione.
Per riprodurre una ricerca, fissare un commit con `git checkout <SHA>`.
