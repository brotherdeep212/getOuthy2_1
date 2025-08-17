#!/usr/bin/env python3
"""
Microsoft OAuth Automator for Google Cloud Run
Optimized version with direct code extraction from URL
"""

import asyncio
import json
import os
import urllib.parse
import time
from datetime import datetime
from playwright.async_api import async_playwright
from flask import Flask, request, jsonify
import requests
import logging

# Configure logging to reduce Flask output
logging.getLogger('werkzeug').setLevel(logging.ERROR)

# --- Configuration ---
CLIENT_ID = os.environ.get('CLIENT_ID', '8caf5ed3-088c-4fa5-b3a8-684e6f0d1616')
SCOPES = os.environ.get('SCOPES', 'offline_access Mail.Read Mail.ReadWrite User.Read')
REDIRECT_URI = os.environ.get('REDIRECT_URI', 'http://localhost:8080/callback')

# Initialize Flask
app = Flask(__name__)
app.logger.setLevel(logging.INFO)

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
        """Generate Microsoft authorization URL."""
        return (f'{self.auth_endpoint}?client_id={self.client_id}&response_type=code'
                f'&redirect_uri={urllib.parse.quote(self.redirect_uri)}'
                f'&response_mode=query&scope={urllib.parse.quote(self.scopes)}&state=12345')

    async def automate_login(self, email, password):
        """Automate login process and capture authorization code."""
        async with async_playwright() as p:
            app.logger.info("Starting Microsoft login automation in headless mode...")
            
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()

            try:
                auth_url = self.generate_auth_url()
                app.logger.info("Navigating to Microsoft login...")
                await page.goto(auth_url, wait_until='domcontentloaded')
                
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(2000)

                # Step 1: Email
                await self._handle_email_input(page, email)
                
                # Step 2: Password
                await self._handle_password_input(page, password)
                
                # Step 3: Check account status (moved after password input)
                account_status = await self._check_account_status(page)
                if account_status != "OK":
                    self.error = f"Account error: {account_status}"
                    return
                
                # Step 4: Additional prompts
                await self._handle_additional_prompts(page)
                
                # Step 5: Extract code with direct URL check
                await self._extract_auth_code(page)

            except Exception as e:
                app.logger.error(f"Error during Playwright automation: {e}")
                self.error = f"Automation error: {str(e)}"
            finally:
                await browser.close()
                app.logger.info("Browser closed.")

    async def _extract_auth_code(self, page):
        """Extract authorization code by checking page URL"""
        app.logger.info("Starting authorization code extraction...")
        
        timeout = 30
        start_time = time.time()
        
        while not self.auth_code and (time.time() - start_time) < timeout:
            try:
                current_url = page.url
                app.logger.info(f"Current URL: {current_url}")
                
                # Check if we're at callback with code
                if '/callback' in current_url and 'code=' in current_url:
                    app.logger.info(f"🎯 Found callback URL: {current_url}")
                    
                    # Extract code
                    parsed_url = urllib.parse.urlparse(current_url)
                    query_params = urllib.parse.parse_qs(parsed_url.query)
                    code = query_params.get('code', [None])[0]
                    
                    if code:
                        self.auth_code = code
                        app.logger.info(f"✅ Code extracted successfully: {code[:50]}...")
                        break
                    else:
                        app.logger.warning("Code not found in URL parameters")
                
                # Wait before next check
                await asyncio.sleep(0.5)
                
            except Exception as e:
                app.logger.error(f"Error during code extraction: {e}")
                await asyncio.sleep(1)
        
        if not self.auth_code:
            # Last desperate attempt
            try:
                final_url = page.url
                app.logger.info(f"🔄 Last attempt with URL: {final_url}")
                
                if 'code=' in final_url:
                    # Extract manually
                    import re
                    code_match = re.search(r'code=([^&]+)', final_url)
                    if code_match:
                        self.auth_code = code_match.group(1)
                        app.logger.info(f"✅ Code extracted with regex: {self.auth_code[:50]}...")
                    
            except Exception as e:
                app.logger.error(f"Error in final attempt: {e}")
        
        if not self.auth_code:
            self.error = "Unable to extract authorization code"
            app.logger.error("❌ Code extraction failed completely")
        else:
            app.logger.info("🎉 Code extraction completed successfully")

    async def _handle_email_input(self, page, email):
        """Handle email input"""
        app.logger.info("📧 Email input...")
        
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)
        
        email_selectors = [
            'input[type="email"]',
            '#i0116',
            'input[name="loginfmt"]',
            'input[placeholder*="email" i]',
            'input[placeholder*="Email" i]'
        ]
        
        email_filled = False
        for selector in email_selectors:
            try:
                await page.wait_for_selector(selector, timeout=3000, state='visible')
                
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        await page.fill(selector, '')
                        await page.fill(selector, email)
                        await page.wait_for_timeout(500)
                        
                        app.logger.info(f"✅ Email entered with selector: {selector}")
                        email_filled = True
                        break
            except Exception as e:
                app.logger.warning(f"⚠️ Email attempt failed with {selector}: {str(e)}")
                continue
        
        if not email_filled:
            raise Exception("Unable to enter email")
        
        # Click Next
        next_selectors = [
            '#idSIButton9',
            'input[type="submit"]',
            'button[type="submit"]',
            'button:has-text("Next")',
            'button:has-text("Avanti")'
        ]
        
        next_clicked = False
        for selector in next_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        await page.click(selector)
                        app.logger.info(f"✅ Clicked 'Next' with selector: {selector}")
                        await page.wait_for_timeout(2000)
                        next_clicked = True
                        break
            except Exception as e:
                app.logger.warning(f"⚠️ Next attempt failed with {selector}: {str(e)}")
                continue
        
        if not next_clicked:
            try:
                await page.keyboard.press('Enter')
                app.logger.info("✅ Pressed Enter as alternative")
                await page.wait_for_timeout(2000)
            except:
                raise Exception("Unable to proceed after email entry")

    async def _handle_password_input(self, page, password):
        """Handle password input"""
        app.logger.info("🔐 Password input...")
        
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)
        
        password_selectors = [
            'input[type="password"]',
            '#i0118',
            'input[name="passwd"]',
            'input[name="Password"]',
            'input[placeholder*="password" i]'
        ]
        
        password_filled = False
        for selector in password_selectors:
            try:
                await page.wait_for_selector(selector, timeout=8000, state='visible')
                
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        await page.fill(selector, '')
                        await page.fill(selector, password)
                        await page.wait_for_timeout(500)
                        
                        app.logger.info(f"✅ Password entered with selector: {selector}")
                        password_filled = True
                        break
            except Exception as e:
                app.logger.warning(f"⚠️ Password attempt failed with {selector}: {str(e)}")
                continue
        
        if not password_filled:
            raise Exception("Unable to enter password")
        
        signin_selectors = [
            '#idSIButton9',
            'input[type="submit"]',
            'button[type="submit"]',
            'button:has-text("Sign in")',
            'button:has-text("Accedi")'
        ]
        
        signin_clicked = False
        for selector in signin_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    is_visible = await element.is_visible()
                    is_enabled = await element.is_enabled()
                    
                    if is_visible and is_enabled:
                        await page.click(selector)
                        app.logger.info(f"✅ Clicked 'Sign in' with selector: {selector}")
                        await page.wait_for_timeout(3000)
                        signin_clicked = True
                        break
            except Exception as e:
                app.logger.warning(f"⚠️ Sign in attempt failed with {selector}: {str(e)}")
                continue
        
        if not signin_clicked:
            try:
                await page.keyboard.press('Enter')
                app.logger.info("✅ Pressed Enter for login")
                await page.wait_for_timeout(3000)
            except:
                raise Exception("Unable to perform login")

    async def _check_account_status(self, page):
        """Check for login errors - improved version"""
        app.logger.info("🔍 Checking account status...")
        
        # Wait longer for any error messages to appear
        await page.wait_for_timeout(3000)
        
        try:
            # Check for password error message specifically
            password_error_selectors = [
                '#field-8__validationMessage',
                '.fui-Field__validationMessage',
                '[id*="validationMessage"]',
                '[class*="validationMessage"]',
                '[class*="error"]',
                '.alert-error',
                '.error-message'
            ]
            
            for selector in password_error_selectors:
                try:
                    error_element = await page.query_selector(selector)
                    if error_element:
                        error_text = await error_element.inner_text()
                        if error_text and error_text.strip():
                            error_text_lower = error_text.lower()
                            app.logger.info(f"Found error element with text: {error_text}")
                            
                            # Check for password-specific errors
                            if any(phrase in error_text_lower for phrase in [
                                'password is incorrect',
                                'that password is incorrect',
                                'incorrect password',
                                'wrong password',
                                'invalid password'
                            ]):
                                app.logger.error(f"❌ Invalid password detected: {error_text}")
                                return "INVALID_CREDENTIALS"
                except Exception as e:
                    app.logger.debug(f"Error checking selector {selector}: {e}")
                    continue
            
            # Check page content for general errors
            page_content = await page.text_content('body')
            if page_content:
                page_content_lower = page_content.lower()
                
                error_indicators = [
                    ('account has been locked', 'ACCOUNT_LOCKED'),
                    ('account is locked', 'ACCOUNT_LOCKED'),
                    ('temporarily locked', 'ACCOUNT_LOCKED'),
                    ('incorrect username or password', 'INVALID_CREDENTIALS'),
                    ('sign-in name or password is incorrect', 'INVALID_CREDENTIALS'),
                    ('that password is incorrect', 'INVALID_CREDENTIALS'),
                    ('password is incorrect', 'INVALID_CREDENTIALS'),
                    ('we couldn\'t find an account', 'ACCOUNT_NOT_FOUND'),
                    ('account doesn\'t exist', 'ACCOUNT_NOT_FOUND'),
                    ('invalid username or password', 'INVALID_CREDENTIALS')
                ]
                
                for indicator, error_type in error_indicators:
                    if indicator in page_content_lower:
                        app.logger.error(f"❌ Detected: {error_type}")
                        return error_type
            
            # Check current URL for error indicators
            current_url = page.url
            if 'error' in current_url.lower():
                app.logger.warning(f"Error detected in URL: {current_url}")
                if 'invalid_grant' in current_url.lower():
                    return "INVALID_CREDENTIALS"
            
            # If we're still on a login.live.com page after password entry, it's likely an error
            if 'login.live.com' in current_url and 'post.srf' in current_url:
                # Wait a bit more to see if there's a redirect
                await page.wait_for_timeout(3000)
                final_url = page.url
                
                if 'login.live.com' in final_url and 'post.srf' in final_url:
                    app.logger.warning("Still on login page after credentials - likely invalid password")
                    # Check one more time for error messages
                    final_content = await page.text_content('body')
                    if final_content and 'password is incorrect' in final_content.lower():
                        return "INVALID_CREDENTIALS"
                    # If we're stuck on the same login page, assume invalid credentials
                    return "INVALID_CREDENTIALS"
            
            app.logger.info("✅ Account OK")
            return "OK"
            
        except Exception as e:
            app.logger.warning(f"⚠️ Error checking account: {e}")
            return "OK"

    async def _handle_additional_prompts(self, page):
        """Handle additional prompts"""
        app.logger.info("🔍 Handling additional prompts...")
        
        await page.wait_for_load_state('domcontentloaded')
        await page.wait_for_timeout(2000)
        
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            try:
                page_content = await page.text_content('body')
                page_content_lower = page_content.lower()
                current_url = page.url
                
                app.logger.info(f"📍 Current URL: {current_url}")
                
                # If already at callback, exit
                if '/callback' in current_url:
                    app.logger.info("✅ Already at callback, skipping additional prompts")
                    break
                
                # Handle consent
                if any(keyword in page_content_lower for keyword in [
                    'permissions requested', 'consent', 'accept', 'allow',
                    'wants to access', 'autorizzazioni', 'consenso'
                ]):
                    app.logger.info("📋 Consent prompt detected...")
                    
                    accept_selectors = [
                        '#idSIButton9',
                        'button:has-text("Accept")',
                        'button:has-text("Allow")',
                        'button:has-text("Accetta")',
                        'input[type="submit"][value*="Accept"]'
                    ]
                    
                    accepted = False
                    for selector in accept_selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element and await element.is_visible() and await element.is_enabled():
                                await page.click(selector)
                                app.logger.info(f"✅ Accepted consent with: {selector}")
                                await page.wait_for_timeout(3000)
                                accepted = True
                                break
                        except Exception as e:
                            app.logger.warning(f"⚠️ Consent attempt failed: {e}")
                            continue
                    
                    if accepted:
                        attempt += 1
                        continue
                
                # Handle "Stay signed in"
                elif any(keyword in page_content_lower for keyword in [
                    'stay signed in', 'rimani connesso', 'stay signed'
                ]):
                    app.logger.info("🔄 'Stay signed in' prompt detected...")
                    
                    yes_selectors = [
                        '#idSIButton9',
                        'button:has-text("Yes")',
                        'button:has-text("Sì")',
                        'input[type="submit"][value*="Yes"]'
                    ]
                    
                    accepted = False
                    for selector in yes_selectors:
                        try:
                            element = await page.query_selector(selector)
                            if element and await element.is_visible() and await element.is_enabled():
                                await page.click(selector)
                                app.logger.info(f"✅ Clicked 'Yes' with: {selector}")
                                await page.wait_for_timeout(3000)
                                accepted = True
                                break
                        except Exception as e:
                            app.logger.warning(f"⚠️ Stay signed in attempt failed: {e}")
                            continue
                    
                    if accepted:
                        attempt += 1
                        continue
                
                else:
                    app.logger.info("✅ No additional prompts detected")
                    break
                
            except Exception as e:
                app.logger.warning(f"⚠️ Error during prompt handling: {e}")
                break
            
            attempt += 1
        
        app.logger.info("✅ Prompt handling completed")

    def exchange_code_for_token(self):
        """Exchange authorization code for tokens."""
        if self.error:
            return {"error": "AUTOMATION_FAILED", "message": self.error}
        if not self.auth_code:
            return {"error": "AUTH_CODE_MISSING", "message": "Unable to obtain authorization code."}

        app.logger.info(f"🔄 Exchanging authorization code: {self.auth_code[:20]}...")
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
                app.logger.info("🎉 Refresh token obtained successfully.")
                return {
                    'refresh_token': token_data.get('refresh_token'),
                    'access_token': token_data.get('access_token'),
                    'expires_in': token_data.get('expires_in'),
                    'scope': token_data.get('scope'),
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'obtained_at': datetime.now().isoformat()
                }
            else:
                app.logger.error(f"❌ Error during token exchange: {token_data}")
                return {"error": "TOKEN_EXCHANGE_FAILED", "message": token_data}
        except Exception as e:
            app.logger.error(f"❌ Error in token exchange request: {e}")
            return {"error": "REQUEST_FAILED", "message": str(e)}

# --- Flask Endpoints ---

@app.route('/', methods=['POST'])
def get_refresh_token():
    """Main endpoint to obtain refresh token."""
    if not request.is_json:
        return jsonify({"error": "INVALID_REQUEST", "message": "Request must be in JSON format."}), 400

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "MISSING_CREDENTIALS", "message": "Email and password are required."}), 400

    app.logger.info(f"📧 Received request for email: {email}")

    # Dynamic URL for Cloud Run
    service_url = request.headers.get("X-Forwarded-Proto", "http") + "://" + request.headers.get("Host", "localhost:8080")
    dynamic_redirect_uri = f"{service_url}/callback"
    
    app.logger.info(f"🌐 Using dynamic redirect_uri: {dynamic_redirect_uri}")

    automator = MicrosoftOAuthAutomator(CLIENT_ID, dynamic_redirect_uri, SCOPES)

    # Run automation
    result = asyncio.run(automator.automate_login(email, password))
    
    # If there was an error in automation, return it
    if automator.error:
        return jsonify({"error": "AUTOMATION_FAILED", "message": automator.error}), 500

    # Exchange code for token
    result = automator.exchange_code_for_token()

    if 'error' in result:
        return jsonify(result), 500
    else:
        return jsonify(result), 200

@app.route('/callback', methods=['GET'])
def callback():
    """Dummy callback endpoint."""
    return "Callback reached. You can close this window.", 200

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "ok", "service": "microsoft-oauth-automator"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
