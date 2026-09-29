# Casi BIRD

Questa cartella contiene, dopo la generazione, 30 casi di test estratti dal dataset [BIRD Mini-Dev](https://github.com/bird-bench/mini_dev) nello stesso formato `.sqlite` + `_caso_info` usato dal caso demo (`casi/pc_multivaluta.sqlite`).

I file `.sqlite` **non sono versionati in git** (alcuni superano il limite di 100MB di GitHub, e nel complesso pesano centinaia di MB) — vengono rigenerati in locale.

## Come rigenerarli

1. Scarica BIRD Mini-Dev:
   - JSON con domande/query gold: https://huggingface.co/datasets/birdsql/bird_mini_dev (file `data/mini_dev_sqlite-00000-of-00001.json`) -> salvalo come `bird-mini-dev/mini_dev_sqlite.json`
   - Database originali: scarica `dev.zip` da https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip, estrai `dev_20240627/dev_databases.zip`, e da questo estrai solo le cartelle degli 11 database elencati sotto in `bird-mini-dev/dev_databases/`
2. Esegui `python estrai_casi_bird.py` dalla root del progetto.

Struttura attesa prima di eseguire lo script:
```
bird-mini-dev/
  mini_dev_sqlite.json
  dev_databases/
    california_schools/california_schools.sqlite
    card_games/card_games.sqlite
    codebase_community/codebase_community.sqlite
    debit_card_specializing/debit_card_specializing.sqlite
    european_football_2/european_football_2.sqlite
    financial/financial.sqlite
    formula_1/formula_1.sqlite
    student_club/student_club.sqlite
    superhero/superhero.sqlite
    thrombosis_prediction/thrombosis_prediction.sqlite
    toxicology/toxicology.sqlite
```

## Criteri di selezione

- 30 esempi totali, stratificati per difficoltà secondo le proporzioni osservate nel dataset (~30% simple, ~50% moderate, ~20% challenging): 9 simple, 15 moderate, 6 challenging.
- Solo esempi la cui query gold coinvolge **al massimo 3 tabelle sorgente** (per mantenere i casi abbastanza semplici/leggeri).
- Selezione casuale con seed fisso (42) per riproducibilità: `_manifest.json` elenca esattamente quali 30 esempi sono stati scelti.

## Verifica

`python verifica_estrazione_bird.py` riesegue la query gold di ogni caso estratto e controlla, tramite `valuta_accuratezza`, che il risultato combaci al 100% con la tabella target salvata nel file — conferma che l'estrazione è fedele all'originale.

## Contenuto di ogni file `.sqlite`

- Le tabelle sorgente effettivamente referenziate dalla query gold (Stato A).
- `RISULTATO_ATTESO`: il risultato della query gold, già calcolato (Stato B).
- `_caso_info`: metadati letti da `carica_caso()` (nomi tabelle sorgente + nome tabella target).
- `_bird_info`: tracciabilità verso il dataset originale (question_id, db_id, difficulty, domanda, evidenza, query gold) — non viene mai passata al modello, serve solo per la documentazione della tesi.
