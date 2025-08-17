FROM python:3.11-slim

WORKDIR /app

# Installa le dipendenze di sistema necessarie per Playwright e Chromium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
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
    libgcc-s1 \
    libgdk-pixbuf-2.0-0 \
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
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements.txt
COPY requirements.txt .

# Installa le dipendenze Python
RUN pip install --no-cache-dir -r requirements.txt

# Installa Playwright e scarica Chromium
RUN playwright install chromium

# Installa le dipendenze specifiche per Chromium se mancanti
RUN playwright install-deps chromium

# Copia il codice dell'applicazione
COPY . .

# Crea un utente non-root per motivi di sicurezza
RUN useradd -m -u 1000 playwright && \
    chown -R playwright:playwright /app
USER playwright

# Espone la porta
EXPOSE 8080

# Comando per avviare l'applicazione
CMD ["python", "main.py"]
