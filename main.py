#!/usr/bin/env python3
"""
Microsoft OAuth Automator per Google Cloud Run
Adattato per ricevere credenziali via HTTP POST e restituire il refresh token.
"""

import asyncio
import json
import os
import urllib.parse
from datetime import datetime
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
import requests
import logging

# --- Configurazione ---
# È consigliabile impostare queste variabili come variabili d'ambiente in Cloud Run
CLIENT_ID = os.environ.get('CLIENT_ID', '8caf5ed3-088c-4fa5-b3a8-684e6f0d1616')
SCOPES = os.environ.get('SCOPES', 'offline_access Mail.Read Mail.ReadWrite User.Read')

# L'URL di redirect deve essere autorizzato nella tua app Azure AD.
# Per Cloud Run, questo sarà l'URL del servizio stesso.
# Puoi usare un segnaposto e aggiornarlo dopo il primo deploy.
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:8080/callback')

# Inizializza Flask
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# --- Logica di Automazione OAuth ---

class MicrosoftOAuthAutomator:
    def __init__(self, client_id, redirect_uri, scopes):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.scopes = scopes
        self.authority = 'https://login.microsoftonline.com/common'
        self.auth_endpoint = f'{self.authority}/oauth2/v2.0/authorize'
        self.token_endpoint = f'{self.authority}/oauth2/v2.0/token'
        self.auth_code = None
        self.error = None

    def generate_auth_url(self):
        """Genera l'URL di autorizzazione Microsoft."""
        return (f'{self.auth_endpoint}?client_id={self.client_id}&response_type=code'
                f'&redirect_uri={urllib.parse.quote(self.redirect_uri)}'
                f'&response_mode=query&scope={urllib.parse.quote(self.scopes)}&state=12345')

    async def automate_login(self, email, password):
        """Automatizza il processo di login e cattura il codice di autorizzazione."""
        async with async_playwright() as p:
            app.logger.info("Avvio automazione login Microsoft in headless mode...")
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()

            # Funzione per intercettare il redirect al callback
            def handle_route(route, request_obj):
                if '/callback' in request_obj.url and 'code=' in request_obj.url:
                    app.logger.info("Rilevato redirect al callback. Estraggo il codice.")
                    parsed_url = urllib.parse.urlparse(request_obj.url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    self.auth_code = query_params.get('code', [None])[0]
                route.continue_()

            await page.route("**/callback**", handle_route)

            try:
                auth_url = self.generate_auth_url()
                app.logger.info("Navigando al login Microsoft...")
                await page.goto(auth_url, wait_until='domcontentloaded', timeout=60000)

                # Inserimento Email
                await page.fill('input[type="email"]', email, timeout=15000)
                await page.click('#idSIButton9')
                app.logger.info("Email inserita.")

                # Inserimento Password
                await page.fill('input[type="password"]', password, timeout=15000)
                await page.click('#idSIButton9')
                app.logger.info("Password inserita.")
                
                # --- NUOVA FUNZIONE: Gestione del prompt "Skip for now" ---
                try:
                    app.logger.info("Controllo per il prompt 'Skip for now'...")
                    # Attendi che il selettore sia visibile, ma con un timeout breve per non rallentare.
                    skip_button_selector = '#iShowSkip'
                    await page.wait_for_selector(skip_button_selector, timeout=5000, state='visible')
                    await page.click(skip_button_selector)
                    app.logger.info("Cliccato sul pulsante 'Skip for now'.")
                    # Attendi un istante per far caricare la pagina successiva
                    await asyncio.sleep(2)
                except Exception:
                    # Se il pulsante non viene trovato, è normale. Logga un avviso e continua.
                    app.logger.warning("Prompt 'Skip for now' non trovato, proseguo.")

                # Gestione prompt "Stay signed in"
                try:
                    await page.click('#idSIButton9', timeout=15000) # Clicca "Yes" o "Sì"
                    app.logger.info("Gestito prompt 'Stay signed in'.")
                except Exception:
                    app.logger.warning("Prompt 'Stay signed in' non trovato o già gestito.")

                # Attendi che il codice di autorizzazione venga catturato
                await asyncio.sleep(10) # Attesa extra per assicurare il redirect

            except Exception as e:
                app.logger.error(f"Errore durante l'automazione Playwright: {e}")
                self.error = f"Errore automazione: {str(e)}"
            finally:
                await browser.close()
                app.logger.info("Browser chiuso.")

    def exchange_code_for_token(self):
        """Scambia il codice di autorizzazione per i token."""
        if self.error:
            return {"error": "AUTOMATION_FAILED", "message": self.error}
        if not self.auth_code:
            return {"error": "AUTH_CODE_MISSING", "message": "Impossibile ottenere il codice di autorizzazione."}

        app.logger.info("Scambio del codice di autorizzazione per il token...")
        data = {
            'client_id': self.client_id,
            'scope': self.scopes,
            'code': self.auth_code,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        try:
            response = requests.post(self.token_endpoint, data=data, timeout=30)
            token_data = response.json()

            if 'refresh_token' in token_data:
                app.logger.info("Refresh token ottenuto con successo.")
                return {
                    'refresh_token': token_data.get('refresh_token'),
                    'access_token': token_data.get('access_token'),
                    'expires_in': token_data.get('expires_in'),
                    'obtained_at': datetime.now().isoformat()
                }
            else:
                app.logger.error(f"Errore durante lo scambio del token: {token_data}")
                return {"error": "TOKEN_EXCHANGE_FAILED", "message": token_data}
        except Exception as e:
            app.logger.error(f"Errore nella richiesta di scambio token: {e}")
            return {"error": "REQUEST_FAILED", "message": str(e)}

# --- Endpoint Flask ---

@app.route('/', methods=['POST'])
async def get_refresh_token():
    """Endpoint principale per ottenere il refresh token."""
    if not request.is_json:
        return jsonify({"error": "RICHIESTA_NON_VALIDA", "message": "La richiesta deve essere in formato JSON."}), 400

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "CREDENZIALI_MANCANTI", "message": "Email e password sono obbligatori."}), 400

    app.logger.info(f"Ricevuta richiesta per l'email: {email}")

    # Ottieni l'URL del servizio Cloud Run per il redirect_uri dinamico
    # Questo sovrascrive il default se l'header è presente
    service_url = request.headers.get("X-Forwarded-Proto", "http") + "://" + request.headers.get("Host", "localhost")
    dynamic_redirect_uri = f"{service_url}/callback"
    
    app.logger.info(f"Utilizzo redirect_uri dinamico: {dynamic_redirect_uri}")

    automator = MicrosoftOAuthAutomator(CLIENT_ID, dynamic_redirect_uri, SCOPES)

    # Esegui l'automazione
    await automator.automate_login(email, password)

    # Scambia il codice per il token
    result = automator.exchange_code_for_token()

    if 'error' in result:
        return jsonify(result), 500
    else:
        return jsonify(result), 200

@app.route('/callback', methods=['GET'])
def callback():
    """
    Endpoint di callback fittizio.
    Playwright intercetterà la richiesta a questo endpoint senza che venga effettivamente eseguito.
    Serve solo per avere un URL valido da usare nel flusso OAuth.
    """
    return "Callback raggiunto. Puoi chiudere questa finestra.", 200

if __name__ == '__main__':
    # Google Cloud Run usa un server di produzione come Gunicorn, non questo.
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
