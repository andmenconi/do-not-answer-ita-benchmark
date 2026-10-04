# -*- coding: utf-8 -*-
"""
import_prompts.py

Importa il CSV originale Do-Not-Answer (`data_en.csv`) nella tabella
Supabase `prompts`. Mappa la colonna `question` su `prompt_en` e marca i
record come `source=original`.

Lo script non è idempotente: un secondo avvio tenta di reinserire gli
stessi id. Prima dell'inserimento chiede conferma interattiva.

Prerequisiti:
- File CSV con colonne: id, risk_area, types_of_harm, specific_harms,
  question. Percorso di default: data_en.csv nella working directory
  (sovrascrivibile con la variabile d'ambiente CSV_FILE_PATH).
- Tabella Supabase `prompts` con colonne: id, risk_area, types_of_harm,
  specific_harms, prompt_en, source.
- Variabili d'ambiente SUPABASE_URL e SUPABASE_KEY impostate (vedi
  .env.example). Su Colab puoi impostarle con:
      import os
      os.environ["SUPABASE_URL"] = "..."
      os.environ["SUPABASE_KEY"] = "..."
  oppure tramite i Colab Secrets.

Dipendenze: supabase.
"""

import csv
import os

from supabase import create_client

# ==========================================
# CONFIGURAZIONE
# ==========================================

BATCH_SIZE = 100
CSV_FILE_PATH = os.environ.get("CSV_FILE_PATH", "data_en.csv")
REQUIRED_COLUMNS = (
    "id",
    "risk_area",
    "types_of_harm",
    "specific_harms",
    "question",
)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError(
        "SUPABASE_URL e SUPABASE_KEY devono essere impostate come variabili "
        "d'ambiente (vedi .env.example)."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def load_records(csv_path):
    """Legge il CSV e restituisce i record mappati sullo schema `prompts`."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(
            f"Non trovo il file '{csv_path}' nella working directory. "
            "Imposta CSV_FILE_PATH se il file sta altrove."
        )

    print(f"Lettura del file '{csv_path}' in corso...")
    records = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing = [col for col in REQUIRED_COLUMNS if col not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(
                "Il CSV non contiene le colonne richieste: "
                + ", ".join(missing)
            )

        for row in reader:
            records.append(
                {
                    "id": int(row["id"]),
                    "risk_area": row["risk_area"],
                    "types_of_harm": row["types_of_harm"],
                    "specific_harms": row["specific_harms"],
                    "prompt_en": row["question"],
                    "source": "original",
                }
            )

    return records


def confirm_import(total):
    """Chiede conferma prima dell'inserimento totale. Restituisce True se si procede."""
    conferma = input(
        f"\nPronto a inserire {total} record nella tabella prompts. "
        "Procedere con il caricamento totale? (si/no): "
    )
    return conferma.strip().lower() == "si"


def insert_records(records):
    """Invia i record a Supabase a blocchi di BATCH_SIZE."""
    total = len(records)
    print(f"\nInizio caricamento su Supabase a blocchi di {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        supabase.table("prompts").insert(batch).execute()
        print(f"Inseriti {min(i + BATCH_SIZE, total)}/{total} record...")


def main():
    records = load_records(CSV_FILE_PATH)
    print(f"Verifica dati: estratti {len(records)} record dal CSV.")

    if not records:
        print("Il CSV non contiene record da importare.")
        return

    if not confirm_import(len(records)):
        print("Operazione annullata.")
        return

    try:
        insert_records(records)
    except Exception as e:
        print(f"\nErrore durante l'inserimento: {e}")
        print("Lo script si ferma qui. Controlla lo stato della tabella prima di rilanciare.")
        raise SystemExit(1)

    print("\nImport completato. Tutti i dati sono sul database.")


if __name__ == "__main__":
    main()
