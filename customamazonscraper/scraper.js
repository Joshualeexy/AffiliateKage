/**
 * Amazon PA-API Equivalent Scraper Engine
 * 
 * Replicates PA-API v5 GetItems & SearchItems data structure:
 * - Identifiers (ASIN, DetailPageURL with affiliate tag)
 * - ItemInfo (Full Title, Bullet Points / Features, Brand, Categories)
 * - Images (High-Res Primary Image, Gallery Variants)
 * - Ratings & Social Proof (Average Rating, Total Review Count, Badges)
 * - Offers & Pricing (Current Price, List Price, Savings, Prime eligibility, In Stock status)
 * - Specifications (Technical details key-value pairs)
 */

const { launchStealthBrowser } = require('./lib/browser');

class AmazonProductScraper {
    constructor(options = {}) {
        this.affiliateTag = options.affiliateTag || process.env.AMAZON_AFFILIATE_TAG || '';
        this.userDataDir = options.userDataDir || './amazon_profile';
        this.headless = options.headless !== undefined ? options.headless : true;
    }

    /**
     * Build an affiliate URL for an ASIN.
     */
    buildAffiliateUrl(asin) {
        let url = `https://www.amazon.com/dp/${asin}/`;
        if (this.affiliateTag) {
            url += `?tag=${this.affiliateTag}`;
        }
        return url;
    }

    /**
     * Search Amazon and return PA-API style SearchItems results.
     * @param {string} query Search query keyword
     * @param {Object} [opts] Options: limit (default 5)
     */
    async searchItems(query, opts = {}) {
        const limit = opts.limit || 5;
        const browser = await launchStealthBrowser({
            headless: this.headless,
            userDataDir: this.userDataDir
        });

        try {
            const page = await browser.newPage();
            const searchUrl = `https://www.amazon.com/s?k=${encodeURIComponent(query)}`;
            console.log(`[AmazonScraper] Searching for: "${query}"...`);

            await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
            await page.waitForSelector('[data-asin]', { timeout: 12000 }).catch(() => null);

            const items = await page.evaluate((maxItems) => {
                const results = [];
                const cards = document.querySelectorAll('[data-asin]');

                for (const card of cards) {
                    const asin = card.getAttribute('data-asin');
                    if (!asin || asin.length !== 10) continue;

                    // Title
                    const titleEl = card.querySelector('h2 a span, h2 span');
                    const title = titleEl ? titleEl.innerText.trim() : '';
                    if (!title) continue;

                    // Image
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

                    // Review count
                    const reviewsEl = card.querySelector('span[aria-label*="ratings"], a[href*="customerReviews"] span');
                    let reviewCount = null;
                    if (reviewsEl) {
                        const countStr = reviewsEl.innerText.replace(/[^\d]/g, '');
                        if (countStr) reviewCount = parseInt(countStr, 10);
                    }

                    // Prime
                    const isPrime = !!card.querySelector('i.a-icon-prime');

                    // Badge (Amazon's Choice, Best Seller)
                    const badgeEl = card.querySelector('.a-badge-text, span.a-badge-label');
                    const badge = badgeEl ? badgeEl.innerText.trim() : '';

                    results.push({
                        asin,
                        title,
                        primaryImage: image,
                        price: price ? { amount: price, currency: 'USD' } : null,
                        rating,
                        reviewCount,
                        isPrime,
                        badge: badge || null,
                    });

                    if (results.length >= maxItems) break;
                }

                return results;
            }, limit);

            // Inject detail URLs with affiliate tags
            return items.map(item => ({
                ...item,
                detailPageUrl: this.buildAffiliateUrl(item.asin)
            }));

        } finally {
            await browser.close();
        }
    }

    /**
     * Fetch comprehensive product details for a specific ASIN (like PA-API GetItems).
     * @param {string} asin 10-character Amazon ASIN
     */
    async getItems(asin) {
        const browser = await launchStealthBrowser({
            headless: this.headless,
            userDataDir: this.userDataDir
        });

        try {
            const page = await browser.newPage();
            const productUrl = `https://www.amazon.com/dp/${asin}/`;
            console.log(`[AmazonScraper] Fetching product details for ASIN: ${asin}...`);

            await page.goto(productUrl, { waitUntil: 'domcontentloaded', timeout: 35000 });
            await page.waitForSelector('#productTitle', { timeout: 12000 }).catch(() => null);

            const details = await page.evaluate((targetAsin) => {
                // Title
                const titleEl = document.querySelector('#productTitle');
                const title = titleEl ? titleEl.innerText.trim() : '';

                // Primary Image & Gallery
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

                // Bullet Points / Features
                const features = [];
                const bulletEls = document.querySelectorAll('#feature-bullets ul li span.a-list-item');
                for (const b of bulletEls) {
                    const txt = b.innerText.trim();
                    if (txt && !txt.toLowerCase().includes('make sure this fits')) {
                        features.push(txt);
                    }
                }

                // Price & Offers
                let currentPrice = null;
                const priceEl = document.querySelector('.apexPriceToPay .a-offscreen, .priceToPay .a-offscreen, #price_inside_buybox');
                if (priceEl) {
                    const match = priceEl.innerText.match(/[\d,.]+/);
                    if (match) currentPrice = parseFloat(match[0].replace(/,/g, ''));
                }

                let listPrice = null;
                const listPriceEl = document.querySelector('.basisPrice .a-offscreen, #listPrice');
                if (listPriceEl) {
                    const match = listPriceEl.innerText.match(/[\d,.]+/);
                    if (match) listPrice = parseFloat(match[0].replace(/,/g, ''));
                }

                // Availability
                const availEl = document.querySelector('#availability span');
                const availability = availEl ? availEl.innerText.trim() : 'In Stock';

                // Prime eligibility
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

                // Category Breadcrumbs
                const breadcrumbs = [];
                const crumbEls = document.querySelectorAll('#wayfinding-breadcrumbs_feature_div ul li a');
                for (const c of crumbEls) {
                    breadcrumbs.push(c.innerText.trim());
                }

                // Technical Specifications
                const specifications = {};
                const specRows = document.querySelectorAll('#productDetails_techSpec_section_1 tr, .po-row');
                for (const row of specRows) {
                    const keyEl = row.querySelector('th, .po-label span');
                    const valEl = row.querySelector('td, .po-value span');
                    if (keyEl && valEl) {
                        const k = keyEl.innerText.trim();
                        const v = valEl.innerText.trim();
                        if (k && v) specifications[k] = v;
                    }
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
                        listPrice: listPrice ? { amount: listPrice, currency: 'USD' } : null,
                        discountPercent: (listPrice && currentPrice && listPrice > currentPrice) 
                            ? Math.round(((listPrice - currentPrice) / listPrice) * 100)
                            : null,
                    },
                    availability,
                    isPrime,
                    rating,
                    reviewCount,
                    specifications,
                };
            }, asin);

            details.detailPageUrl = this.buildAffiliateUrl(asin);
            return details;

        } finally {
            await browser.close();
        }
    }
}

module.exports = { AmazonProductScraper };

// CLI Demonstration
if (require.main === module) {
    (async () => {
        const scraper = new AmazonProductScraper({ affiliateTag: 'ejiroinspire-20' });
        
        const action = process.argv[2] || 'search';
        const target = process.argv[3] || 'Sony WH-1000XM5';

        if (action === 'get') {
            console.log(`\n📦 Fetching detailed ItemInfo for ASIN: ${target}...`);
            const item = await scraper.getItems(target);
            console.log('\n--- PA-API ItemInfo Result ---');
            console.log(JSON.stringify(item, null, 2));
        } else {
            console.log(`\n🔍 Searching Amazon for: "${target}"...`);
            const items = await scraper.searchItems(target, { limit: 3 });
            console.log('\n--- PA-API SearchItems Result ---');
            console.log(JSON.stringify(items, null, 2));
        }
    })().catch(console.error);
}
