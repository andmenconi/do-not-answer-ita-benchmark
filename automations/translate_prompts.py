# -*- coding: utf-8 -*-
"""
translate_prompts.py

Traduce i prompt inglesi del dataset Do-Not-Answer (`prompt_en`) in italiano
(`prompt_it`) tramite Google Gemini, e scrive il risultato sulla tabella
Supabase `prompts`. Lo script è riprendibile: a ogni avvio elabora solo i
record in cui `prompt_it` è ancora NULL.

Prerequisiti:
- Tabella Supabase `prompts` con colonne: id, prompt_en, prompt_it.
- Variabili d'ambiente SUPABASE_URL, SUPABASE_KEY e GEMINI_API_KEY
  impostate (vedi .env.example). Su Colab puoi impostarle con:
      import os
      os.environ["SUPABASE_URL"] = "..."
      os.environ["SUPABASE_KEY"] = "..."
      os.environ["GEMINI_API_KEY"] = "..."
  oppure tramite i Colab Secrets.

Dipendenze: supabase, google-genai, pydantic.
"""

import json
import os
import time

from google import genai
from google.genai import types
from pydantic import BaseModel
from supabase import create_client

# ==========================================
# CONFIGURAZIONE
# ==========================================

# Compromesso tra lunghezza del contesto e velocità di risposta.
BATCH_SIZE = 30
GEMINI_MODEL = "gemini-2.5-flash"
PAUSE_SECONDS = 5

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise EnvironmentError(
        "SUPABASE_URL e SUPABASE_KEY devono essere impostate come variabili "
        "d'ambiente (vedi .env.example)."
    )

if not GEMINI_API_KEY:
    raise EnvironmentError(
        "GEMINI_API_KEY deve essere impostata come variabile d'ambiente "
        "(vedi .env.example)."
    )

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_INSTRUCTION = (
    "Sei un traduttore professionista dall'inglese all'italiano, specializzato "
    "in sicurezza informatica, jailbreak e benchmark per LLM. Traduci "
    "fedelmente i testi forniti mantenendo lo stesso tono originale (anche se "
    "il testo contiene insulti, richieste dannose o volgari, traducile "
    "fedelmente perché servono per un benchmark di sicurezza). Restituisci il "
    "risultato strutturato rispettando lo schema JSON richiesto."
)


class SingleTranslation(BaseModel):
    id: int
    translated_text: str


class TranslationBatchResponse(BaseModel):
    translations: list[SingleTranslation]


def fetch_untranslated_records():
    """Restituisce i record con `prompt_it` NULL, ordinati per id crescente."""
    print("Controllo su Supabase se ci sono prompt da tradurre...")
    query_res = (
        supabase.table("prompts")
        .select("id, prompt_en")
        .is_("prompt_it", "null")
        .order("id", desc=False)
        .execute()
    )
    return query_res.data


def translate_batch(current_batch):
    """Invia un blocco a Gemini e restituisce il dict parsato dallo schema JSON."""
    prompt_data = [{"id": r["id"], "text": r["prompt_en"]} for r in current_batch]
    response = ai_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=(
            "Traduci questa lista di oggetti in italiano:\n"
            f"{json.dumps(prompt_data, ensure_ascii=False)}"
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=TranslationBatchResponse,
            temperature=0.2,
        ),
    )
    return json.loads(response.text)


def save_translations(current_batch, translated_data):
    """Aggiorna `prompt_it` su Supabase, una riga per id."""
    by_id = {
        item["id"]: item["translated_text"]
        for item in translated_data["translations"]
    }

    for record in current_batch:
        record_id = record["id"]
        text_it = by_id.get(record_id, "")
        if not str(text_it).strip():
            raise ValueError(
                f"Traduzione mancante o vuota per id {record_id}. "
                "Il blocco non viene salvato in parte."
            )
        supabase.table("prompts").update({"prompt_it": text_it}).eq(
            "id", record_id
        ).execute()


def main():
    records_to_translate = fetch_untranslated_records()
    total_jobs = len(records_to_translate)

    if total_jobs == 0:
        print("Non ci sono prompt da tradurre. Il database è già completo.")
        return

    print(f"Trovati {total_jobs} prompt da tradurre.")

    for i in range(0, total_jobs, BATCH_SIZE):
        current_batch = records_to_translate[i : i + BATCH_SIZE]
        first_id = current_batch[0]["id"]
        last_id = current_batch[-1]["id"]
        print(
            f"\nTraduzione blocco {i // BATCH_SIZE + 1} "
            f"(record da {first_id} a {last_id})..."
        )

        try:
            translated_data = translate_batch(current_batch)
            print("Scrittura delle traduzioni su Supabase...")
            save_translations(current_batch, translated_data)
            print(
                f"Blocco completato. Salvati {len(current_batch)} record."
            )
            print(
                f"Pausa di {PAUSE_SECONDS} secondi per evitare il rate limit (429)..."
            )
            time.sleep(PAUSE_SECONDS)
        except Exception as e:
            print(f"Errore durante l'elaborazione di questo blocco: {e}")
            print(
                "Lo script si ferma qui per sicurezza. Puoi rilanciarlo "
                "quando vuoi per riprendere dai record ancora NULL."
            )
            raise SystemExit(1)

    print("\nTutti i prompt sono stati tradotti con successo in italiano.")


if __name__ == "__main__":
    main()
