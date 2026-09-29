import json
import os
import random
import re
import sqlite3

CARTELLA_BIRD = "bird-mini-dev"
PERCORSO_JSON = os.path.join(CARTELLA_BIRD, "mini_dev_sqlite.json")
CARTELLA_DB = os.path.join(CARTELLA_BIRD, "dev_databases")
CARTELLA_CASI_OUT = "casi_bird"

N_TOTALE = 30
SEED = 42
MAX_TABELLE_SORGENTE = 3
NOME_TABELLA_TARGET = "RISULTATO_ATTESO"

# Proporzioni osservate nel dataset (simple/moderate/challenging): ~30/50/20
QUOTE_DIFFICOLTA = {"simple": 9, "moderate": 15, "challenging": 6}


def tabelle_del_db(cursor):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    return [riga[0] for riga in cursor.fetchall()]


def tabelle_referenziate(sql, nomi_tabelle):
    trovate = []
    for nome in nomi_tabelle:
        if re.search(r'\b' + re.escape(nome) + r'\b', sql, flags=re.IGNORECASE):
            trovate.append(nome)
    return trovate


def carica_tabelle_per_db(db_ids):
    mappa = {}
    for db_id in db_ids:
        percorso_db = os.path.join(CARTELLA_DB, db_id, f"{db_id}.sqlite")
        conn = sqlite3.connect(percorso_db)
        mappa[db_id] = tabelle_del_db(conn.cursor())
        conn.close()
    return mappa


def copia_tabella(cursor_origine, cursor_destinazione, nome_tabella):
    cursor_origine.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name = ?", (nome_tabella,))
    ddl = cursor_origine.fetchone()[0]
    cursor_destinazione.execute(ddl)

    cursor_origine.execute(f'SELECT * FROM "{nome_tabella}"')
    righe = cursor_origine.fetchall()
    if righe:
        placeholders = ",".join(["?"] * len(righe[0]))
        cursor_destinazione.executemany(f'INSERT INTO "{nome_tabella}" VALUES ({placeholders})', righe)


def crea_tabella_target(cursor_destinazione, colonne, righe):
    nomi_colonna_sicuri = []
    usati = set()
    for i, nome in enumerate(colonne):
        nome_sicuro = nome if nome else f"col_{i}"
        base = nome_sicuro
        contatore = 1
        while nome_sicuro in usati:
            nome_sicuro = f"{base}_{contatore}"
            contatore += 1
        usati.add(nome_sicuro)
        nomi_colonna_sicuri.append(nome_sicuro)

    colonne_ddl = ", ".join(f'"{nome}"' for nome in nomi_colonna_sicuri)
    cursor_destinazione.execute(f'CREATE TABLE {NOME_TABELLA_TARGET} ({colonne_ddl})')
    if righe:
        placeholders = ",".join(["?"] * len(nomi_colonna_sicuri))
        cursor_destinazione.executemany(f'INSERT INTO {NOME_TABELLA_TARGET} VALUES ({placeholders})', righe)


def estrai_caso(esempio, nomi_sorgente):
    db_id = esempio["db_id"]
    percorso_db_origine = os.path.join(CARTELLA_DB, db_id, f"{db_id}.sqlite")

    conn_origine = sqlite3.connect(percorso_db_origine)
    cursor_origine = conn_origine.cursor()

    cursor_origine.execute(esempio["SQL"])
    colonne = [d[0] for d in cursor_origine.description]
    righe_target = cursor_origine.fetchall()

    os.makedirs(CARTELLA_CASI_OUT, exist_ok=True)
    nome_file = f"{esempio['question_id']}_{db_id}.sqlite"
    percorso_out = os.path.join(CARTELLA_CASI_OUT, nome_file)
    if os.path.exists(percorso_out):
        os.remove(percorso_out)

    conn_out = sqlite3.connect(percorso_out)
    cursor_out = conn_out.cursor()

    for nome_tabella in nomi_sorgente:
        copia_tabella(cursor_origine, cursor_out, nome_tabella)

    crea_tabella_target(cursor_out, colonne, righe_target)

    cursor_out.execute("CREATE TABLE _caso_info (tabelle_sorgente TEXT, tabella_target TEXT)")
    cursor_out.execute("INSERT INTO _caso_info VALUES (?, ?)", (",".join(nomi_sorgente), NOME_TABELLA_TARGET))

    cursor_out.execute(
        "CREATE TABLE _bird_info (question_id INTEGER, db_id TEXT, difficulty TEXT, question TEXT, evidence TEXT, sql_gold TEXT)"
    )
    cursor_out.execute(
        "INSERT INTO _bird_info VALUES (?, ?, ?, ?, ?, ?)",
        (esempio["question_id"], db_id, esempio["difficulty"], esempio["question"], esempio["evidence"], esempio["SQL"]),
    )

    conn_out.commit()
    conn_out.close()
    conn_origine.close()
    return percorso_out


def filtra_e_annota_candidati(tutti_esempi):
    db_ids = sorted({e["db_id"] for e in tutti_esempi})
    tabelle_per_db = carica_tabelle_per_db(db_ids)

    candidati = []
    for esempio in tutti_esempi:
        nomi_sorgente = tabelle_referenziate(esempio["SQL"], tabelle_per_db[esempio["db_id"]])
        if 1 <= len(nomi_sorgente) <= MAX_TABELLE_SORGENTE:
            candidati.append((esempio, nomi_sorgente))
    return candidati


def seleziona_candidati(candidati):
    random.seed(SEED)
    per_difficolta = {}
    for esempio, nomi_sorgente in candidati:
        per_difficolta.setdefault(esempio["difficulty"], []).append((esempio, nomi_sorgente))

    selezionati = []
    for difficolta, quota in QUOTE_DIFFICOLTA.items():
        gruppo = per_difficolta.get(difficolta, [])
        random.shuffle(gruppo)
        selezionati.append((difficolta, gruppo))
    return selezionati


def main():
    with open(PERCORSO_JSON, encoding="utf-8") as f:
        tutti_esempi = json.load(f)

    candidati = filtra_e_annota_candidati(tutti_esempi)
    print(f"Candidati con al massimo {MAX_TABELLE_SORGENTE} tabelle sorgente: {len(candidati)} su {len(tutti_esempi)}")

    gruppi_per_difficolta = seleziona_candidati(candidati)

    riusciti = []
    falliti = []

    for difficolta, gruppo in gruppi_per_difficolta:
        quota = QUOTE_DIFFICOLTA[difficolta]
        i = 0
        while len([r for r in riusciti if r["difficulty"] == difficolta]) < quota and i < len(gruppo):
            esempio, nomi_sorgente = gruppo[i]
            i += 1
            try:
                percorso_out = estrai_caso(esempio, nomi_sorgente)
                riusciti.append({
                    "question_id": esempio["question_id"],
                    "db_id": esempio["db_id"],
                    "difficulty": difficolta,
                    "percorso": percorso_out,
                    "tabelle_sorgente": nomi_sorgente,
                })
                print(f"[OK] {esempio['question_id']} ({esempio['db_id']}, {difficolta}, {len(nomi_sorgente)} tabelle) -> {percorso_out}")
            except Exception as e:
                falliti.append({"question_id": esempio["question_id"], "db_id": esempio["db_id"], "errore": str(e)})
                print(f"[SALTATO] {esempio['question_id']} ({esempio['db_id']}): {e}")

    print(f"\nEstratti {len(riusciti)} casi su {N_TOTALE} richiesti, {len(falliti)} saltati.")

    manifest_path = os.path.join(CARTELLA_CASI_OUT, "_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"riusciti": riusciti, "falliti": falliti}, f, indent=2, ensure_ascii=False)
    print(f"Manifest salvato in {manifest_path}")


if __name__ == "__main__":
    main()
