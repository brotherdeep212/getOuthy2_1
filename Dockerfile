# Usa l'immagine Playwright con Python e browser inclusi
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Imposta working dir
WORKDIR /app

# Copia i requirements e installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il resto del codice (incluso main.py)
COPY . .

# Variabile PORT richiesta da Cloud Run
ENV PORT=8080

# Comando di avvio con gunicorn (Flask async supportato)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
