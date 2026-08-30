const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env') });
require('dotenv').config(); // local overrides if any
const express = require('express');
const cors = require('cors');
const { launchStealthBrowser } = require('./lib/browser');

const app = express();
const PORT = process.env.SCRAPER_PORT || 4000;
const AFFILIATE_TAG = process.env.AMAZON_AFFILIATE_TAG || '';

app.use(cors());
app.use(express.json());

// Global persistent browser reference
let persistentBrowser = null;
let isInitializing = false;

/**
 * Initialize or retrieve the persistent stealth browser.
 */
async function getBrowser() {
    if (persistentBrowser) return persistentBrowser;
    if (isInitializing) {
        // Wait until initialization completes
        while (isInitializing) {
            await new Promise(r => setTimeout(r, 200));
        }
        return persistentBrowser;
    }

    isInitializing = true;
    try {
        console.log('[Server] Launching persistent stealth browser pool...');
        persistentBrowser = await launchStealthBrowser({
            headless: true,
            userDataDir: './amazon_profile'
        });
        console.log('[Server] Persistent stealth browser is ready!');
        return persistentBrowser;
    } catch (err) {
        console.error('[Server] Failed to launch browser:', err);
        throw err;
    } finally {
        isInitializing = false;
    }
}

/**
 * Build affiliate URL with tracking tag.
 */
function buildAffiliateUrl(asin) {
    let url = `https://www.amazon.com/dp/${asin}/`;
    if (AFFILIATE_TAG) {
        url += `?tag=${AFFILIATE_TAG}`;
    }
    return url;
}

// ── Health Check ─────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
    res.json({
        status: 'ok',
        browserReady: !!persistentBrowser,
        port: PORT,
        affiliateTag: AFFILIATE_TAG
    });
});

// ── Search Items (PA-API SearchItems equivalent) ──────────────────────────────
app.get('/api/search', async (req, res) => {
    const query = req.query.q || req.query.query;
    const limit = parseInt(req.query.limit || '5', 10);

    if (!query) {
        return res.status(400).json({ error: 'Missing required query parameter "q"' });
    }

    let page = null;
    try {
        const browser = await getBrowser();
        page = await browser.newPage();

        const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(query)}`;
        console.log(`[API] Searching: "${query}" (limit: ${limit})`);

        await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForSelector('[data-asin]', { timeout: 10000 }).catch(() => null);

        const items = await page.evaluate((maxItems) => {
            const results = [];
            const cards = document.querySelectorAll('[data-asin]');

            for (const card of cards) {
                const asin = card.getAttribute('data-asin');
                if (!asin || asin.length !== 10) continue;

                const titleEl = card.querySelector('h2 a span, h2 span');
                const title = titleEl ? titleEl.innerText.trim() : '';
                if (!title) continue;

                const imgEl = card.querySelector('img.s-image');
                const image = imgEl ? imgEl.getAttribute('src') : '';

                // Price
                const priceWhole = card.querySelector('.a-price-whole');
                const priceFraction = card.querySelector('.a-price-fraction');
                let price = null;
                if (priceWhole) {
                    const whole = priceWhole.innerText.replace(/[^\d]/g, '');
                    const frac = priceFraction ? priceFraction.innerText.replace(/[^\d]/g, '') : '00';
                    price = parseFloat(`${whole}.${frac}`);
                }

                // Rating
                const ratingEl = card.querySelector('i.a-icon-star-small span, .a-icon-alt');
                let rating = null;
                if (ratingEl) {
                    const rMatch = ratingEl.innerText.match(/([\d.]+)\s*out of/i);
                    if (rMatch) rating = parseFloat(rMatch[1]);
                }

                // Reviews count
                const reviewsEl = card.querySelector('span[aria-label*="ratings"], a[href*="customerReviews"] span');
                let reviewCount = null;
                if (reviewsEl) {
                    const countStr = reviewsEl.innerText.replace(/[^\d]/g, '');
                    if (countStr) reviewCount = parseInt(countStr, 10);
                }

                const isPrime = !!card.querySelector('i.a-icon-prime');
                const badgeEl = card.querySelector('.a-badge-text, span.a-badge-label');
                const badge = badgeEl ? badgeEl.innerText.trim() : null;

                results.push({
                    asin,
                    title,
                    primaryImage: image,
                    price: price ? { amount: price, currency: 'USD' } : null,
                    rating,
                    reviewCount,
                    isPrime,
                    badge,
                });

                if (results.length >= maxItems) break;
            }

            return results;
        }, limit);

        const enriched = items.map(it => ({
            ...it,
            detailPageUrl: buildAffiliateUrl(it.asin)
        }));

        res.json({ success: true, count: enriched.length, data: enriched });

    } catch (err) {
        console.error(`[API] Search failed for "${query}":`, err.message);
        res.status(500).json({ success: false, error: err.message });
    } finally {
        if (page) await page.close().catch(() => null);
    }
});

// ── Get Item Details (PA-API GetItems equivalent) ─────────────────────────────
app.get('/api/product/:asin', async (req, res) => {
    const asin = req.params.asin.trim().toUpperCase();

    if (!asin || asin.length !== 10) {
        return res.status(400).json({ error: 'Invalid ASIN. Must be 10 alphanumeric characters.' });
    }

    let page = null;
    try {
        const browser = await getBrowser();
        page = await browser.newPage();

        const productUrl = `https://www.amazon.com/dp/${asin}/`;
        console.log(`[API] Fetching product: ${asin}`);

        await page.goto(productUrl, { waitUntil: 'domcontentloaded', timeout: 35000 });
        await page.waitForSelector('#productTitle', { timeout: 12000 }).catch(() => null);

        const details = await page.evaluate((targetAsin) => {
            const titleEl = document.querySelector('#productTitle');
            const title = titleEl ? titleEl.innerText.trim() : '';

            // High-res primary image
            let primaryImage = '';
            const mainImgEl = document.querySelector('#landingImage, #imgBlkFront');
            if (mainImgEl) {
                primaryImage = mainImgEl.getAttribute('data-old-hires') || 
                               mainImgEl.getAttribute('data-a-dynamic-image') || 
                               mainImgEl.getAttribute('src');
                if (primaryImage && primaryImage.startsWith('{')) {
                    try {
                        const dyn = JSON.parse(primaryImage);
                        primaryImage = Object.keys(dyn)[0] || '';
                    } catch (e) {}
                }
            }

            // Features bullets
            const features = [];
            const bulletEls = document.querySelectorAll('#feature-bullets ul li span.a-list-item');
            for (const b of bulletEls) {
                const txt = b.innerText.trim();
                if (txt && !txt.toLowerCase().includes('make sure this fits')) {
                    features.push(txt);
                }
            }

            // Price
            let currentPrice = null;
            const priceEl = document.querySelector('.apexPriceToPay .a-offscreen, .priceToPay .a-offscreen, #price_inside_buybox');
            if (priceEl) {
                const match = priceEl.innerText.match(/[\d,.]+/);
                if (match) currentPrice = parseFloat(match[0].replace(/,/g, ''));
            }

            // Stock availability
            const availEl = document.querySelector('#availability span');
            const availability = availEl ? availEl.innerText.trim() : 'In Stock';

            const isPrime = !!document.querySelector('#primeSavingsUpper, i.a-icon-prime');

            // Rating & Reviews
            let rating = null;
            const ratingEl = document.querySelector('#acrPopover i.a-icon-star, #averageCustomerReviews .a-icon-alt');
            if (ratingEl) {
                const rMatch = ratingEl.innerText.match(/([\d.]+)\s*out of/i);
                if (rMatch) rating = parseFloat(rMatch[1]);
            }

            let reviewCount = null;
            const reviewCountEl = document.querySelector('#acrCustomerReviewText');
            if (reviewCountEl) {
                const countStr = reviewCountEl.innerText.replace(/[^\d]/g, '');
                if (countStr) reviewCount = parseInt(countStr, 10);
            }

            // Brand
            const brandEl = document.querySelector('#bylineInfo, .po-brand .a-span9 span');
            const brand = brandEl ? brandEl.innerText.replace(/^Visit the\s+/i, '').replace(/\s+Store$/i, '').trim() : '';

            // Breadcrumbs
            const breadcrumbs = [];
            const crumbEls = document.querySelectorAll('#wayfinding-breadcrumbs_feature_div ul li a');
            for (const c of crumbEls) {
                breadcrumbs.push(c.innerText.trim());
            }

            return {
                asin: targetAsin,
                title,
                brand,
                primaryImage,
                features,
                breadcrumbs,
                pricing: {
                    currentPrice: currentPrice ? { amount: currentPrice, currency: 'USD' } : null,
                },
                availability,
                isPrime,
                rating,
                reviewCount,
            };
        }, asin);

        details.detailPageUrl = buildAffiliateUrl(asin);

        res.json({ success: true, data: details });

    } catch (err) {
        console.error(`[API] Get product ${asin} failed:`, err.message);
        res.status(500).json({ success: false, error: err.message });
    } finally {
        if (page) await page.close().catch(() => null);
    }
});

// Start server and warm up browser in background
app.listen(PORT, '127.0.0.1', () => {
    console.log(`🚀 Amazon Scraper API microservice listening on http://127.0.0.1:${PORT}`);
    // Warm up the browser pool immediately
    getBrowser().catch(err => console.error('[Server] Initial browser warmup error:', err.message));
});

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('[Server] Shutting down...');
    if (persistentBrowser) {
        await persistentBrowser.close().catch(() => null);
    }
    process.exit(0);
});
