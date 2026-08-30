require('dotenv').config();
const { chromium } = require('playwright-extra');
const stealth = require('puppeteer-extra-plugin-stealth')();
chromium.use(stealth);

const { FingerprintGenerator } = require('fingerprint-generator');
const { FingerprintInjector } = require('fingerprint-injector');
const fs = require('fs');
const path = require('path');
const os = require('os');

// Initialize generators
const fingerprintGenerator = new FingerprintGenerator();
const fingerprintInjector = new FingerprintInjector();

// Helper to copy a directory recursively
function copyDirSync(src, dest) {
    fs.mkdirSync(dest, { recursive: true });
    const entries = fs.readdirSync(src, { withFileTypes: true });
    for (const entry of entries) {
        const srcPath = path.join(src, entry.name);
        const destPath = path.join(dest, entry.name);
        if (entry.isDirectory()) {
            copyDirSync(srcPath, destPath);
        } else {
            fs.copyFileSync(srcPath, destPath);
        }
    }
}

/**
 * Launches a Playwright chromium browser (or persistent context if extension is loaded).
 * @param {Object} options Options for launching the browser.
 * @param {boolean} [options.headless=false] Whether to launch headlessly.
 * @param {string} [options.userDataDir] Custom path to persistent browser profile.
 * @param {string} [options.capsolverApiKey] CapSolver API key to inject into capsolver-extension.
 * @param {Object} [options.fingerprintOptions] Custom fingerprinting options.
 * @returns {Promise<import('playwright').Browser>}
 */
async function launchStealthBrowser(options = {}) {
    const headless = options.headless !== undefined ? options.headless : false;
    const apiKey = options.capsolverApiKey || process.env.CAPSOLVER_API_KEY;
    const userDataDir = options.userDataDir;

    const launchOptions = {
        headless,
        executablePath: options.executablePath || (fs.existsSync('/usr/bin/chromium') ? '/usr/bin/chromium' : undefined),
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
            '--window-position=0,0',
            '--ignore-certificate-errors',
            '--ignore-certificate-errors-spki-list',
        ],
    };

    // Decouple persistent profiles from capsolver API key
    const isPersistent = !!userDataDir || !!apiKey;

    if (isPersistent) {
        const resolvedUserDataDir = userDataDir || path.resolve(__dirname, '..', 'browser_profile');

        try {
            // Prevent the Chromium profile picker and welcome screens
            if (!fs.existsSync(resolvedUserDataDir)) {
                fs.mkdirSync(resolvedUserDataDir, { recursive: true });
            }
            const localStatePath = path.join(resolvedUserDataDir, 'Local State');
            const localStateContent = {
                profile: {
                    last_used: 'Default',
                    should_show_user_profile_picker: false
                }
            };
            fs.writeFileSync(localStatePath, JSON.stringify(localStateContent), 'utf8');

            let tempBaseDir = null;
            let loadExtensions = [];

            if (apiKey) {
                console.log('[CapSolver] API Key detected. Setting up CapSolver browser extension...');

                // Locate extension files in the bot-framework directory
                const extSourcePath = path.resolve(__dirname, '..', 'extensions', 'capsolver-extension');
                const vpnExtSourcePath = path.resolve(__dirname, '..', 'extensions', 'vpn-extension');

                // Create a unique temporary directory for this browser session's extension files
                tempBaseDir = path.join(os.tmpdir(), `capsolver-ext-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`);
                const tempExtPath = path.join(tempBaseDir, 'extension');

                console.log(`[CapSolver] Copying extension template to: ${tempExtPath}`);
                copyDirSync(extSourcePath, tempExtPath);

                // Write the config.js containing the API Key
                const configPath = path.join(tempExtPath, 'assets', 'config.js');
                if (fs.existsSync(configPath)) {
                    let configContent = fs.readFileSync(configPath, 'utf8');
                    configContent = configContent.replace(/apiKey:\s*['""'](.*?)['""']/, `apiKey: '${apiKey}'`);
                    fs.writeFileSync(configPath, configContent, 'utf8');
                    console.log('[CapSolver] Extension config.js written with API key.');
                }
                loadExtensions.push(tempExtPath);

                if (fs.existsSync(vpnExtSourcePath)) {
                    const tempVpnPath = path.join(tempBaseDir, 'vpn-extension');
                    console.log(`[VPN] Copying VPN extension to: ${tempVpnPath}`);
                    copyDirSync(vpnExtSourcePath, tempVpnPath);
                    loadExtensions.push(tempVpnPath);
                }

                // Extensions require headed browser or new headless mode to run
                if (headless) {
                    launchOptions.headless = false;
                    launchOptions.args.push('--headless=new');
                } else {
                    launchOptions.headless = false;
                }

                launchOptions.args.push(
                    `--disable-extensions-except=${loadExtensions.join(',')}`,
                    `--load-extension=${loadExtensions.join(',')}`,
                    '--profile-directory=Default'
                );
            }

            // Generate realistic fingerprint
            const fingerprintOptions = options.fingerprintOptions || {};
            const generatorOptions = fingerprintOptions.fingerprintGeneratorOptions || {
                browsers: ['chrome'],
                devices: ['desktop'],
                locales: ['en-US'],
            };

            const { fingerprint, headers } = fingerprintGenerator.getFingerprint(generatorOptions);

            // Map fingerprint parameters to persistent context options
            launchOptions.userAgent = fingerprint.userAgent;
            launchOptions.viewport = {
                width: fingerprint.screen.width,
                height: fingerprint.screen.height,
            };
            launchOptions.locale = fingerprint.navigator.language || 'en-US';
            launchOptions.deviceScaleFactor = fingerprint.screen.devicePixelRatio || 1;
            launchOptions.hasTouch = fingerprint.navigator.maxTouchPoints > 0;
            launchOptions.timezoneId = options.timezoneId || 'America/New_York';

            console.log('[Browser] Launching persistent browser context...');
            const context = await chromium.launchPersistentContext(resolvedUserDataDir, launchOptions);
            context._hasCapSolverExtension = !!apiKey;
            context._isHeaded = !launchOptions.headless;

            // Inject generated fingerprint using the correct attachFingerprintToPlaywright API
            await fingerprintInjector.attachFingerprintToPlaywright(context, { fingerprint, headers });

            if (apiKey) {
                // Wait 5 seconds for extensions (Windscribe VPN & CapSolver) to fully load and connect in the background
                console.log('[Browser] Waiting 5 seconds for extensions to initialize and connect...');
                await new Promise(resolve => setTimeout(resolve, 5000));
            }

            // Return a mock Browser object that mirrors standard Playwright methods
            const mockBrowser = {
                _context: context,
                _tempDir: tempBaseDir,
                newContext: async () => {
                    return context;
                },
                newPage: async () => {
                    return await context.newPage();
                },
                close: async () => {
                    console.log('[Browser] Closing persistent context and cleaning up temp files...');
                    await context.close();
                    try {
                        if (tempBaseDir && fs.existsSync(tempBaseDir)) {
                            fs.rmSync(tempBaseDir, { recursive: true, force: true });
                        }
                    } catch (e) {
                        console.debug(`Failed to delete temp dir: ${e.message}`);
                    }
                }
            };

            return mockBrowser;

        } catch (err) {
            console.error(`[Browser] Failed to initialize persistent context: ${err.message}. Falling back to standard browser.`);
        }
    }

    console.log(`Launching standard browser (headless: ${launchOptions.headless})...`);
    const browserObj = await chromium.launch(launchOptions);
    browserObj._isHeaded = !launchOptions.headless;
    return browserObj;
}

/**
 * Creates or wraps a stealthy browser context.
 * @param {import('playwright').Browser} browser Playwright Browser or Mock Browser instance.
 * @param {Object} [options] Context options.
 * @param {string} [options.proxyUrl] Optional proxy server URL.
 * @param {Object} [options.fingerprintOptions] Custom fingerprinting options.
 * @returns {Promise<import('playwright').BrowserContext>}
 */
async function createStealthContext(browser, options = {}) {
    let context;

    // If it's a persistent context wrapped in our mock browser
    if (browser._context) {
        console.log('Using persistent browser context with extension.');
        context = browser._context;

        if (options.proxyUrl) {
            console.warn('ProxyUrl requested on persistent context. Proxy must be configured in launchOptions for persistent contexts.');
        }
    } else {
        const fingerprintOptions = options.fingerprintOptions || {};
        const generatorOptions = fingerprintOptions.fingerprintGeneratorOptions || {
            browsers: ['chrome'],
            devices: ['desktop'],
            locales: ['en-US'],
        };

        const { fingerprint, headers } = fingerprintGenerator.getFingerprint(generatorOptions);

        const contextOptions = {
            userAgent: fingerprint.userAgent,
            viewport: {
                width: fingerprint.screen.width,
                height: fingerprint.screen.height,
            },
            locale: fingerprint.navigator.language || 'en-US',
            deviceScaleFactor: fingerprint.screen.devicePixelRatio || 1,
            hasTouch: fingerprint.navigator.maxTouchPoints > 0,
            timezoneId: 'America/New_York',
        };

        if (options.proxyUrl) {
            contextOptions.proxy = { server: options.proxyUrl };
            console.log('Using proxy configuration for the browser context.');
        }

        context = await browser.newContext(contextOptions);
        context._isHeaded = browser._isHeaded;

        // Inject generated fingerprint using the correct attachFingerprintToPlaywright API
        await fingerprintInjector.attachFingerprintToPlaywright(context, { fingerprint, headers });
    }

    return context;
}

module.exports = {
    launchStealthBrowser,
    createStealthContext
};
