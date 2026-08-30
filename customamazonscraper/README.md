# 🤖 Bot Framework (`bot-framework`)

A lightweight, site-agnostic browser automation engine powered by Playwright Stealth, custom hardware fingerprint spoofing, and pre-packaged extensions (CapSolver & Windscribe VPN).

---

## Features
- **True Stealth Evasion**: Built on Playwright and `puppeteer-extra-plugin-stealth` to automatically patch WebGL, CDP leaks, and canvas variables.
- **Hardware Fingerprint Spoofing**: Generates and injects highly realistic screen, audio, and device scale properties.
- **Integrated Extension Support**: Automatically loads and configures the CapSolver browser extension (for resolving slides and captchas) and the Windscribe VPN extension.
- **Persistent User Profiles**: Exposes the `userDataDir` parameter so you can store and restore distinct browser sessions (cookies, localStorage, logins) for different users.

---

## Installation

Run the following command inside the framework directory:
```bash
npm install
npx playwright install chromium
```

---

## Usage Example

```javascript
const { launchStealthBrowser } = require('./lib/browser');

async function run() {
    // Launch a persistent browser session for a specific user
    const browser = await launchStealthBrowser({
        userDataDir: './profiles/user_1', // Stores user cookies and session on disk
        headless: false,                 // Set to true to run headlessly (uses --headless=new)
        capsolverApiKey: 'YOUR_CAPSOLVER_API_KEY' // Injected automatically into the capsolver extension
    });

    const page = await browser.newPage();
    
    // Navigate and automate any site!
    await page.goto('https://www.tiktok.com');
    
    // Cleanup when done (closes context and removes temporary extension files)
    await browser.close();
}

run().catch(console.error);
```
