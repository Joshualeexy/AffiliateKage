/**
 * Suspends execution for specified milliseconds.
 * @param {number} ms 
 * @returns {Promise<void>}
 */
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Returns a randomized duration in milliseconds.
 * @param {number} min Seconds.
 * @param {number} max Seconds.
 * @returns {number} Delay in ms.
 */
function getRandomDelay(min, max) {
    return (Math.random() * (max - min) + min) * 1000;
}

/**
 * Standard text cleaner that consolidates whitespace and strips hidden/control characters.
 * Safe for international/non-ASCII languages.
 * @param {string} text 
 * @returns {string} Cleaned text.
 */
function cleanText(text) {
    if (!text) return '';
    return text
        .replace(/[\u200E\u200F\u202A-\u202E\u0000-\u001F]/g, '') // remove hidden control characters
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * Sanitizes text to be safe for filesystem paths (stripping non-ASCII, emojis, and forbidden characters).
 * @param {string} text 
 * @returns {string} Safe filename.
 */
function sanitizeFilename(text) {
    if (!text) return '';
    return text
        .normalize('NFKD')
        .replace(/[^\x00-\x7F]/g, '') // remove non-ascii
        .replace(/[<>:"/\\|?*\u0000-\u001F]/g, '') // remove forbidden characters for filesystem paths
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * Retries a promise-returning function up to a limit.
 * @param {Function} fn Promise-returning function.
 * @param {Object} [options]
 * @param {number} [options.maxRetries=2] Number of retries.
 * @param {number} [options.delay=1000] Delay between retries in ms.
 * @param {string} [options.context='Action'] Description for logs.
 * @returns {Promise<any>}
 */
async function withRetries(fn, options = {}) {
    const { maxRetries = 2, delay = 1000, context = 'Action' } = options;
    let attempt = 0;
    while (true) {
        try {
            return await fn();
        } catch (err) {
            attempt++;
            if (attempt > maxRetries) {
                throw err;
            }
            console.warn(`⚠️ [${context}] Attempt ${attempt}/${maxRetries} failed: ${err.message}. Retrying in ${delay * attempt}ms...`);
            await sleep(delay * attempt);
        }
    }
}

/**
 * Scroll page until element count satisfies target or no new content is loaded.
 * Handles stale checks and page network states.
 * @param {import('playwright').Page} page Playwright Page.
 * @param {string} selector CSS selector to check count.
 * @param {number} targetCount Target count of elements.
 * @param {Object} [options] Options.
 * @param {number} [options.maxScrolls=60] Max scrolls.
 * @param {number} [options.scrollDelay=2500] Delay between scrolls.
 * @param {number} [options.maxStagnantAttempts=5] Max consecutive scrolls with 0 new items.
 * @returns {Promise<void>}
 */
async function scrollPageToLoadItems(page, selector, targetCount, options = {}) {
    const {
        maxScrolls = 60,
        scrollDelay = 2500,
        maxStagnantAttempts = 5,
        waitForNetworkIdle = false
    } = options;

    let lastCount = 0;
    let stagnantCount = 0;

    console.log(`🔄 Scrolling page to load elements matching "${selector}" (Target: ${targetCount})...`);

    for (let i = 0; i < maxScrolls; i++) {
        // Evaluate selectors count on page
        const currentCount = await page.$$eval(selector, els => els.length);
        console.log(`🔍 Scroll ${i + 1}/${maxScrolls}: ${currentCount} elements found.`);

        if (currentCount >= targetCount) {
            console.log(`✅ Target count of ${targetCount} reached!`);
            break;
        }

        if (currentCount === lastCount) {
            stagnantCount++;
            console.warn(`⏳ No new elements loaded (${stagnantCount}/${maxStagnantAttempts} attempts)`);
            if (stagnantCount >= maxStagnantAttempts) {
                console.log(`⛔ Stoppping scrolling - no new content loading.`);
                break;
            }
            // Wait slightly longer if stagnant
            await sleep(scrollDelay + 1000);
        } else {
            stagnantCount = 0;
        }

        lastCount = currentCount;

        // Scroll
        await page.evaluate(() => {
            window.scrollBy(0, window.innerHeight * 2);
        });

        await sleep(scrollDelay);

        if (waitForNetworkIdle) {
            try {
                await page.waitForLoadState('networkidle', { timeout: 3000 });
            } catch (e) {
                // ignore networkidle timeout and proceed
            }
        }
    }
}

module.exports = {
    sleep,
    getRandomDelay,
    cleanText,
    sanitizeFilename,
    withRetries,
    scrollPageToLoadItems
};
