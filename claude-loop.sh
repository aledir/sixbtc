#!/bin/bash
cd ~/sixbtc
echo "🚀 Claude Loop - Directory: $(pwd)"
echo "⚠️  Ctrl+C per fermare"
echo ""
PROMPT="RIMUOVI tutti i @pytest.mark.skip dai test e IMPLEMENTA il codice necessario per farli passare. Non è accettabile skippare test - ogni test deve PASSARE con codice funzionante. Esegui: grep -r 'pytest.mark.skip' tests/ per trovare tutti gli skip, rimuovili, poi implementa il codice mancante. Obiettivo: 0 skipped, 0 failed, 0 errors. Quando raggiungi questo scrivi TUTTI I TEST IMPLEMENTATI."
while true; do
    echo ">>> Lancio Claude..."
    claude --dangerously-skip-permissions -p "$PROMPT"
    echo ""
    echo "🔄 Riprendo in 3 secondi..."
    sleep 3
    PROMPT="Continua a rimuovere skip e implementare codice. Obiettivo: 0 skipped. Ogni test deve passare con implementazione reale, non skip. Quando hai 0 skipped scrivi TUTTI I TEST IMPLEMENTATI."
done
