# Prompt utilizzati nella pipeline

Questa cartella raccoglie i prompt usati per i due passaggi della pipeline che richiedevano un modello linguistico come strumento, e solo per quelli:

1. [`01_generazione_domande_custom_it.md`](01_generazione_domande_custom_it.md) — il prompt dato a Google Gemini per produrre le 160 domande italiane a framing **indiretto** del blocco `custom_it`.
2. [`02_giudice_llm_valutazione.md`](02_giudice_llm_valutazione.md) — il prompt dato a Claude Sonnet per votare, sulla scala 0–5 di Do-Not-Answer (Wang et al., 2024), le risposte di Mistral, Gemma e Minerva sull'intero corpus (939 `original` + 160 `custom_it`).
3. [`03_generazione_domande_dirette.md`](03_generazione_domande_dirette.md) — il prompt (ricostruito, non conservato in originale — vedi nota nel file) per produrre le domande a framing **diretto**, controparte esplicita del blocco indiretto.

I tre modelli sotto test (Mistral, Gemma, Minerva) hanno ricevuto la domanda italiana come semplice messaggio utente, **senza** un system prompt aggiuntivo — non c'è quindi un prompt dedicato a loro da documentare qui.

Non sono riportati in questa cartella: il codice Colab (vedi [`../ollama_benchmark.py`](../ollama_benchmark.py)), lo script di import del CSV originale (vedi [`../import_prompts.py`](../import_prompts.py)), lo script di traduzione inglese-italiano (vedi [`../translate_prompts.py`](../translate_prompts.py)), le chiavi di accesso al database, né l'elenco completo delle 1099 domande del dataset.
