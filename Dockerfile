# Usa un'immagine base Python ufficiale con Ubuntu
FROM python:3.11-slim

# Imposta la directory di lavoro nel container
WORKDIR /app

# Installa dipendenze di sistema essenziali
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    software-properties-common \
    curl \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libexpat1 \
    libfontconfig1 \
    libgcc1 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libstdc++6 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    lsb-release \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e installa le dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installa Playwright e i browser
RUN playwright install-deps chromium
RUN playwright install chromium

# Verifica l'installazione di Playwright
RUN playwright install-deps
RUN python -c "from playwright.sync_api import sync_playwright; print('Playwright installed successfully')"

# Copia il codice dell'applicazione
COPY . .

# Imposta variabili d'ambiente
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Esponi la porta
EXPOSE 8080

# Comando di avvio
CMD ["gunicorn", "--workers", "1", "--threads", "4", "--timeout", "600", "--bind", "0.0.0.0:8080", "main:app"]
