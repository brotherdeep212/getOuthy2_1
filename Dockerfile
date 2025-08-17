# Usa un'immagine base Python ufficiale.
FROM python:3.11-slim

# Imposta la directory di lavoro nel container.
WORKDIR /app

# Copia il file delle dipendenze e installale.
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Installa le dipendenze di sistema per Playwright (browser Chromium) e pulisci la cache.
# Questo è il metodo raccomandato e più affidabile.
RUN playwright install-deps chromium --with-deps
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# Copia il resto del codice dell'applicazione.
COPY . .

# Imposta la variabile d'ambiente PORT che Cloud Run utilizzerà.
ENV PORT=8080

# Comando per avviare l'applicazione usando Gunicorn, un server WSGI di produzione.
CMD ["gunicorn", "--workers", "1", "--threads", "8", "--timeout", "300", "--bind", "0.0.0.0:8080", "main:app"]
