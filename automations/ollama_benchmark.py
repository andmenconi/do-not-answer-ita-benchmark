# -*- coding: utf-8 -*-
"""
ollama_benchmark.py

Script pensato per essere eseguito su Google Colab. Esegue l'inferenza
sui tre modelli del benchmark (Mistral, Gemma, Minerva) tramite Ollama,
ciclando automaticamente su ciascuno, e salva le risposte su Supabase
nella tabella `prompts` (una colonna per modello: response_mistral,
response_gemma, response_minerva).

Prerequisiti:
- Tabella Supabase `prompts` con colonne: id, prompt_it, response_mistral,
  response_gemma, response_minerva.
- Variabili d'ambiente SUPABASE_URL e SUPABASE_KEY impostate (vedi
  .env.example). Su Colab puoi impostarle con:
      import os
      os.environ["SUPABASE_URL"] = "..."
      os.environ["SUPABASE_KEY"] = "..."
  oppure tramite i Colab Secrets.
"""

import os
import time
import subprocess

import requests
from supabase import create_client
from ollama import Client

# ==========================================
# SETUP AMBIENTE (Colab)
# ==========================================

# Dipendenze di sistema necessarie all'installer di Ollama.
subprocess.run(["apt-get", "install", "-y", "zstd"], check=True)
subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)


def start_ollama_server():
    """Avvia il server Ollama in background se non è già attivo."""
    try:
        requests.get("http://localhost:11434")
        print("Ollama server è già attivo e raggiungibile.")
        return
    except requests.exceptions.ConnectionError:
        pass

    print("Ollama server non risponde. Avvio in corso...")
    env = os.environ.copy()
    env["OLLAMA_HOST"] = "127.0.0.1:11434"
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    # Il server ha bisogno di qualche secondo per essere pronto ad accettare richieste.
    time.sleep(5)

    try:
        requests.get("http://localhost:11434")
        print("Ollama server avviato con successo.")
    except requests.exceptions.ConnectionError as e:
        raise RuntimeError(f"Impossibile avviare il server Ollama: {e}")


start_ollama_server()

# ==========================================
# CONFIGURAZIONE BENCHMARK
# ==========================================

# Nome del modello Ollama da scaricare (chiave) -> colonna Supabase da aggiornare (valore).
# Il nome "minerva" usato per il pull HuggingFace è quello indicato nel notebook originale;
# verificare che corrisponda ancora al tag disponibile su Ollama al momento dell'esecuzione.
MODELS = {
    "mistral": "response_mistral",
    "gemma": "response_gemma",
    "hf.co/sapienzanlp/Minerva-7B-instruct-v1.0-GGUF:Q4_K_M": "response_minerva",
}

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError(
        "SUPABASE_URL e SUPABASE_KEY devono essere impostate come variabili "
        "d'ambiente (vedi .env.example)."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ollama_client = Client(host="http://localhost:11434")


def pull_model(model_name):
    """Scarica il modello tramite Ollama, se non già presente."""
    print(f"Scaricamento di {model_name}...")
    subprocess.run(["ollama", "pull", model_name], check=True)


def get_ollama_response(model_name, prompt):
    """Interroga il modello e restituisce (risposta, errore)."""
    try:
        response = ollama_client.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options={
                "num_predict": 2048,
                "temperature": 0.1,
            },
        )
        return response["message"]["content"], None
    except Exception as e:
        return None, str(e)


def run_benchmark_for_model(model_name, response_column):
    """Elabora tutti i record con `response_column` mancante per il modello dato."""
    while True:
        print(
            f"Recupero del prossimo blocco di record mancanti su colonna "
            f"'{response_column}' per {model_name}..."
        )

        # Includiamo sia i valori NULL che le stringhe vuote come "da elaborare".
        response = (
            supabase.table("prompts")
            .select("*")
            .or_(f"{response_column}.is.null,{response_column}.eq.''")
            .order("id")
            .limit(1000)
            .execute()
        )
        records = response.data

        if not records:
            print(f"Tutti i record per {model_name} sono stati completati.")
            break

        print(f"Trovati {len(records)} record da elaborare in questo blocco.")

        for record in records:
            record_id = record["id"]
            prompt_it = record["prompt_it"]

            print(f"ID: {record_id} -> chiamata a {model_name}...")
            res, err = get_ollama_response(model_name, prompt_it)

            if err:
                print(f"  Errore su ID {record_id}: {err}")
                # Nessun update: la cella resta vuota e verrà ritentata.
            else:
                print(f"  Risposta registrata per ID {record_id}.")
                supabase.table("prompts").update(
                    {response_column: res}
                ).eq("id", record_id).execute()

            time.sleep(0.2)


def main():
    for model_name, response_column in MODELS.items():
        pull_model(model_name)
        run_benchmark_for_model(model_name, response_column)


if __name__ == "__main__":
    main()
