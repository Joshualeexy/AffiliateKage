# 🚀 Ejiro Inspire: Autonomous Content & Affiliate Publishing Engine

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Node Version](https://img.shields.io/badge/node-18%2B-green.svg)](https://nodejs.org/)
[![Engine](https://img.shields.io/badge/LLM-Ollama-purple.svg)](https://ollama.ai/)
[![Image Generation](https://img.shields.io/badge/Image-ComfyUI%20SDXL-orange.svg)](https://github.com/comfyanonymous/ComfyUI)
[![Scraper](https://img.shields.io/badge/Scraper-Playwright%20Stealth-red.svg)](https://github.com/berstend/puppeteer-extra)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

An end-to-end autonomous publishing, research, monetization, and content orchestration engine. It continuously discovers high-intent buyer topics, performs grounded web research, generates publication-ready long-form articles, classifies physical vs. digital entities, extracts verified Amazon product data without official PA-API requirements, renders AI hero images, and publishes directly to a headless CMS.

---

## 🌟 Key Features

- **Autonomous Topic Ideation & Trend Discovery:** Generates high-converting affiliate topics across 30+ product categories, rotating formats (*Reviews, Buying Guides, Comparisons, Alternatives, Tutorials*) while eliminating duplicate and stale year titles.
- **Grounded Web Research:** Leverages `Crawl4AI` and DuckDuckGo to extract live, real-world context, specifications, and competitor data before generating outlines.
- **Structured Long-Form Content (Ollama):** Strict prompt templates enforce 2,000+ word deep-dive reviews, comparison matrices, evaluation criteria, pros/cons, and FAQs.
- **Smart Entity Classification:** Differentiates physical hardware from digital SaaS, software, and apps. Physical goods receive Amazon monetization; software tools (*Notion, YNAB, Hostinger, Duolingo*) route to official homepages or custom affiliate redirects.
- **Built-In Stealth Amazon Scraper (PA-API v5 Equivalent):** A dedicated Node.js microservice powered by Playwright Stealth, hardware fingerprint spoofing, CapSolver, and VPN extensions that bypasses Amazon's Akamai Bot Manager. Extracts verified ASINs, high-resolution 1500px CDN images, customer ratings, review counts, and Prime badges without requiring official Amazon API credentials.
- **Dynamic Product Showcase Cards:** Injects styled, responsive product highlight cards with Editor's Choice badges (*Top Pick, Best Value, Recommended*), official product imagery, and compliant affiliate CTAs.
- **Automatic VRAM Orchestration:** Unloads Ollama from GPU memory before starting ComfyUI to render high-resolution SDXL featured images, then uploads the asset seamlessly with the article.
- **Full SEO & Compliance Hygiene:** Enforces `rel="nofollow sponsored noopener"`, context-aware FTC affiliate disclosures, and clean semantic heading hierarchies.
- **Unified Global CLI (`ejiroinspire`):** A single command (`ejiroinspire start`) that manages the background stealth scraper microservice and Python pipeline together with graceful `Ctrl+C` termination.
- **Batch Remediation Engine:** Includes a standalone migration script (`remediate_posts.py`) that audits and repairs published database archives in-place with automatic revision snapshots.

---

## 📐 Architecture & Pipeline Flow

```mermaid
flowchart TD
    A[Topic Generator] -->|Select Category & Format| B[Duplicate & Trend Check]
    B -->|Query DDG + Crawl4AI| C[Grounded Web Research]
    C -->|Synthesize Insights| D[Structured Outline Generator]
    D -->|Ollama LLM| E[Long-Form Article Generation]
    E -->|Structural Validation| F[Article Validator]
    F -->|Extract Products & Software| G[Entity Extractor]
    G --> H{Is Physical Product?}
    H -->|Yes| I[Stealth Amazon Scraper API]
    H -->|No| J[Curated Software URL Router]
    I -->|Fetch ASINs, 1500px CDN Images, Ratings| K[Inject Product Showcase Cards]
    J -->|Attach Official Redirects| K
    K -->|Generate SDXL Hero Image| L[ComfyUI Generator]
    L -->|Sanitize & Convert to HTML| M[FTC & SEO Compliance Filter]
    M -->|Push via Admin REST API| N[Headless CMS / Laravel Backend]
    N -->|Instant Cache Purge| O[Next.js Frontend (ISR)]
```

---

## 📦 System Requirements

- **Operating System:** Linux (Arch, Ubuntu/Debian recommended) or macOS.
- **Python:** 3.10 or newer.
- **Node.js:** 18.0 or newer.
- **Ollama:** Installed and running locally (e.g. `qwen3:30b`, `llama3.3`).
- **ComfyUI:** Installed locally for SDXL featured image generation.
- **Chromium:** Installed on system (`/usr/bin/chromium`).

---

## 🚀 Quickstart

### 1. Clone the Repository
```bash
git clone https://github.com/Joshualeexy/Ejiroinspire-blogpost-automation-workflow.git
cd Ejiroinspire-blogpost-automation-workflow
```

### 2. Setup Python Virtual Environment
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 3. Setup Custom Amazon Scraper Microservice
```bash
cd customamazonscraper
npm install
cd ..
```

### 4. Install Global CLI
Make the global controller executable and link it to your `$PATH`:
```bash
chmod +x ejiroinspire
ln -sf $(pwd)/ejiroinspire ~/.local/bin/ejiroinspire
```

---

## ⚙️ Configuration (`.env`)

Create a `.env` file in the root directory:

```env
# Ollama LLM Configuration
OLLAMA_MODEL=qwen3:30b

# Headless CMS / Admin REST API
API_URL=https://api.yourdomain.com/api/admin
API_TOKEN=your_bearer_token_here

# Amazon Associates Tag
AMAZON_AFFILIATE_TAG=yourtag-20

# ComfyUI Image Generation
COMFY_URL=http://127.0.0.1:8188
COMFY_START_CMD=cd ~/comfyui/ComfyUI && source venv/bin/activate && python main.py

# Custom Stealth Scraper API Microservice
CUSTOM_SCRAPER_API_URL=http://127.0.0.1:4000
```

Inside `customamazonscraper/.env` (optional, for anti-captcha/VPN integration):
```env
CAPSOLVER_API_KEY=your_capsolver_key_here
SCRAPER_PORT=4000
AMAZON_AFFILIATE_TAG=yourtag-20
```

---

## 💻 Usage

### Running the Entire Engine (One Command)
You can start the full stack from **any terminal, anywhere on your system**:

```bash
# Starts Node.js Scraper API + Python Pipeline
ejiroinspire start

# Start fresh and clear saved pipeline state:
ejiroinspire start --clear-state
```

- When running, pressing **`Ctrl+C`** will gracefully shut down both the Python pipeline and the background Node.js scraper microservice.

### Monitoring & Status
```bash
# View active service statuses
ejiroinspire status

# Stop all background services
ejiroinspire stop
```

### Running the Scraper Standalone
```bash
cd customamazonscraper

# Search products (PA-API SearchItems style)
node scraper.js search "Sony WH-1000XM5"

# Fetch deep item metadata (PA-API GetItems style)
node scraper.js get "B0B11LJ69K"

# Run HTTP API microservice
npm start
```

### Batch Archive Remediation
If you have an existing blog database that needs structural heading fixes, orphaned paragraph wrapping, or Amazon compliance enforcement:

```bash
# Preview changes without modifying database
./venv/bin/python remediate_posts.py --dry-run

# Run live remediation across entire database
./venv/bin/python remediate_posts.py --yes
```

---

## 📁 Repository Structure

```
.
├── main.py                     # Main orchestrator pipeline loop
├── ejiroinspire                # Global CLI bash controller
├── remediate_posts.py          # Batch database audit & repair engine
├── pipeline_state.json         # Resumable stage execution state
├── generated_topics.json       # Topic history & duplicate prevention
├── config.py                   # Local overrides and configuration
├── prompts/                    # Editorial persona templates (Reviews, Guides, etc.)
├── generators/
│   ├── topic_generator.py      # Category selection & SEO topic ideation
│   ├── outline_generator.py    # Structured JSON outline synthesizer
│   ├── article_generator.py    # LLM article writer
│   ├── entity_extractor.py     # Physical vs. digital entity classification
│   ├── content_sanitizer.py    # Heading repair, link hygiene, product card injection
│   └── internal_link_injector.py # Semantic internal cross-linking
├── services/
│   ├── image_fetcher.py        # Microservice client with DDGS fallback
│   ├── markdown.py             # Markdown-to-HTML converter & disclosure logic
│   ├── comfy.py                # ComfyUI SDXL image client & VRAM manager
│   └── api.py                  # Headless CMS REST API client
└── customamazonscraper/         # Standalone Node.js Stealth Scraper Microservice
    ├── server.js               # Express API microservice (http://127.0.0.1:4000)
    ├── scraper.js              # PA-API equivalent SearchItems & GetItems
    ├── lib/browser.js          # Playwright Stealth + Fingerprint spoofing launcher
    ├── extensions/             # CapSolver & VPN extension packages
    └── package.json            # Node.js dependencies
```

---

## 🤝 Open Source Contributing

Contributions, issues, and feature requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for more information.
