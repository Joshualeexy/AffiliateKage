#!/usr/bin/env python3
"""
AffiliateKage Asset Generator
Generates:
1. assets/social-preview.png (1280x640 GitHub Social Preview Card)
2. assets/worker_demo.gif (Animated Terminal Execution)
3. assets/worker_terminal.png (High-Res Static Terminal Snapshot)
4. assets/production_showcase.png (Live Production Blog & Article Collage)
"""

import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

ASSETS_DIR = Path("assets")
ASSETS_DIR.mkdir(exist_ok=True)


def generate_social_preview(page):
    """Render 1280x640 GitHub Social Preview Banner."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">
      <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
          width: 1280px;
          height: 640px;
          background: #080b12;
          font-family: 'Inter', sans-serif;
          color: #f8fafc;
          position: relative;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 44px 56px;
        }

        /* Subtle ambient glow & grid */
        .grid-bg {
          position: absolute;
          inset: 0;
          background-image: 
            radial-gradient(ellipse 60% 40% at 50% 10%, rgba(56, 189, 248, 0.12) 0%, transparent 70%),
            radial-gradient(ellipse 50% 50% at 85% 60%, rgba(168, 85, 247, 0.10) 0%, transparent 60%),
            radial-gradient(ellipse 40% 40% at 15% 70%, rgba(34, 197, 94, 0.08) 0%, transparent 60%),
            linear-gradient(to right, rgba(255, 255, 255, 0.02) 1px, transparent 1px),
            linear-gradient(to bottom, rgba(255, 255, 255, 0.02) 1px, transparent 1px);
          background-size: 100% 100%, 100% 100%, 100% 100%, 40px 40px, 40px 40px;
          pointer-events: none;
        }

        .border-glow {
          position: absolute;
          inset: 16px;
          border-radius: 20px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          box-shadow: inset 0 0 40px rgba(56, 189, 248, 0.03);
          pointer-events: none;
        }

        .top-row {
          position: relative;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .repo-badge {
          display: inline-flex;
          align-items: center;
          gap: 10px;
          padding: 7px 16px;
          border-radius: 9999px;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.1);
          font-family: 'JetBrains Mono', monospace;
          font-size: 13px;
          font-weight: 500;
          color: #94a3b8;
          backdrop-filter: blur(8px);
        }

        .repo-badge svg {
          width: 16px;
          height: 16px;
          fill: #f8fafc;
        }

        .live-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 6px 14px;
          border-radius: 9999px;
          background: rgba(34, 197, 94, 0.12);
          border: 1px solid rgba(34, 197, 94, 0.3);
          font-size: 12px;
          font-weight: 600;
          color: #4ade80;
          letter-spacing: 0.5px;
          text-transform: uppercase;
        }
        .live-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #22c55e;
          box-shadow: 0 0 10px #22c55e;
        }

        /* Hero text */
        .hero {
          position: relative;
          z-index: 10;
          margin-top: 6px;
        }

        .brand-title {
          font-size: 58px;
          font-weight: 900;
          letter-spacing: -1.5px;
          line-height: 1;
          display: flex;
          align-items: center;
          gap: 16px;
          background: linear-gradient(135deg, #ffffff 30%, #38bdf8 70%, #a855f7 100%);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .brand-kanji {
          font-size: 42px;
          font-weight: 700;
          background: linear-gradient(135deg, #38bdf8, #818cf8);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          border: 1px solid rgba(56, 189, 248, 0.3);
          padding: 2px 14px;
          border-radius: 12px;
          background-color: rgba(56, 189, 248, 0.05);
        }

        .tagline {
          font-size: 20px;
          font-weight: 500;
          color: #94a3b8;
          margin-top: 14px;
          max-width: 950px;
          line-height: 1.4;
        }
        .tagline strong {
          color: #f1f5f9;
          font-weight: 700;
        }

        /* Pipeline cards */
        .pipeline-container {
          position: relative;
          z-index: 10;
          margin-top: 14px;
        }

        .pipeline-label {
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 2px;
          color: #38bdf8;
          text-transform: uppercase;
          margin-bottom: 12px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .pipeline-label::after {
          content: '';
          flex: 1;
          height: 1px;
          background: linear-gradient(to right, rgba(56, 189, 248, 0.3), transparent);
        }

        .pipeline-grid {
          display: grid;
          grid-template-columns: repeat(6, 1fr);
          gap: 12px;
          position: relative;
        }

        .step-card {
          background: rgba(15, 23, 42, 0.7);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 14px;
          padding: 16px 14px;
          display: flex;
          flex-direction: column;
          position: relative;
          transition: all 0.3s ease;
          backdrop-filter: blur(10px);
        }
        .step-card:hover {
          border-color: rgba(56, 189, 248, 0.4);
          transform: translateY(-2px);
        }

        .step-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 10px;
        }

        .step-num {
          font-family: 'JetBrains Mono', monospace;
          font-size: 10px;
          font-weight: 700;
          color: #38bdf8;
          background: rgba(56, 189, 248, 0.1);
          padding: 2px 7px;
          border-radius: 6px;
        }

        .step-icon {
          font-size: 15px;
        }

        .step-name {
          font-size: 17px;
          font-weight: 800;
          color: #f8fafc;
          margin-bottom: 4px;
        }

        .step-desc {
          font-size: 11px;
          font-weight: 500;
          color: #64748b;
          line-height: 1.3;
        }

        .arrow {
          position: absolute;
          right: -9px;
          top: 50%;
          transform: translateY(-50%);
          width: 16px;
          height: 16px;
          z-index: 20;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #38bdf8;
          font-size: 12px;
          font-weight: 900;
        }

        /* Bottom pill badges */
        .bottom-row {
          position: relative;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: 14px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
        }

        .tech-pills {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .pill {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px 12px;
          border-radius: 8px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          font-family: 'JetBrains Mono', monospace;
          font-size: 11px;
          font-weight: 500;
          color: #94a3b8;
        }
        .pill-dot {
          width: 6px;
          height: 6px;
          border-radius: 50%;
        }

        .showcase-link {
          font-size: 12px;
          font-weight: 600;
          color: #94a3b8;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .showcase-link span {
          color: #38bdf8;
        }
      </style>
    </head>
    <body>
      <div class="grid-bg"></div>
      <div class="border-glow"></div>

      <!-- Header Row -->
      <div class="top-row">
        <div class="repo-badge">
          <svg viewBox="0 0 16 16"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>
          github.com / AffiliateKage
        </div>
        <div class="live-badge">
          <div class="live-dot"></div>
          Production Verified &bull; ejiroinspire.com
        </div>
      </div>

      <!-- Hero Title -->
      <div class="hero">
        <div class="brand-title">
          AffiliateKage <span class="brand-kanji">影</span>
        </div>
        <div class="tagline">
          An <strong>autonomous AI engine</strong> that researches products, generates SEO content, enriches it with affiliate data, creates images, validates the result, and publishes it.
        </div>
      </div>

      <!-- 6-Stage Pipeline Flow -->
      <div class="pipeline-container">
        <div class="pipeline-label">End-to-End Autonomous Pipeline</div>
        <div class="pipeline-grid">
          <div class="step-card">
            <div class="step-header">
              <span class="step-num">01</span>
              <span class="step-icon">🔍</span>
            </div>
            <div class="step-name">Research</div>
            <div class="step-desc">SERP scraping & competitor source analysis</div>
            <div class="arrow">→</div>
          </div>

          <div class="step-card">
            <div class="step-header">
              <span class="step-num">02</span>
              <span class="step-icon">⚡</span>
            </div>
            <div class="step-name">Generate</div>
            <div class="step-desc">Local / Cloud LLM multi-stage generation</div>
            <div class="arrow">→</div>
          </div>

          <div class="step-card">
            <div class="step-header">
              <span class="step-num">03</span>
              <span class="step-icon">💎</span>
            </div>
            <div class="step-name">Enrich</div>
            <div class="step-desc">Stealth Amazon scraper, CDN photos & tags</div>
            <div class="arrow">→</div>
          </div>

          <div class="step-card">
            <div class="step-header">
              <span class="step-num">04</span>
              <span class="step-icon">🎨</span>
            </div>
            <div class="step-name">Render</div>
            <div class="step-desc">ComfyUI SDXL & Cloud photorealistic hero art</div>
            <div class="arrow">→</div>
          </div>

          <div class="step-card">
            <div class="step-header">
              <span class="step-num">05</span>
              <span class="step-icon">🛡️</span>
            </div>
            <div class="step-name">Validate</div>
            <div class="step-desc">Compliance, SEO & structural guardrails</div>
            <div class="arrow">→</div>
          </div>

          <div class="step-card" style="border-color: rgba(34, 197, 94, 0.4); background: rgba(34, 197, 94, 0.05);">
            <div class="step-header">
              <span class="step-num" style="color: #4ade80; background: rgba(34, 197, 94, 0.15);">06</span>
              <span class="step-icon">🚀</span>
            </div>
            <div class="step-name" style="color: #4ade80;">Publish</div>
            <div class="step-desc">Headless CMS REST API + Next.js frontend</div>
          </div>
        </div>
      </div>

      <!-- Bottom Tech Pills -->
      <div class="bottom-row">
        <div class="tech-pills">
          <div class="pill"><span class="pill-dot" style="background:#38bdf8;"></span>Python 3.10+</div>
          <div class="pill"><span class="pill-dot" style="background:#a855f7;"></span>Ollama / OpenAI / DeepSeek</div>
          <div class="pill"><span class="pill-dot" style="background:#f59e0b;"></span>ComfyUI SDXL</div>
          <div class="pill"><span class="pill-dot" style="background:#22c55e;"></span>Playwright Stealth Pool</div>
          <div class="pill"><span class="pill-dot" style="background:#06b6d4;"></span>Zero-Touch Automation</div>
        </div>
        <div class="showcase-link">
          Live Showcase: <span>ejiroinspire.com/blog</span>
        </div>
      </div>
    </body>
    </html>
    """

    page.set_viewport_size({"width": 1280, "height": 640})
    page.set_content(html_content)
    page.wait_for_timeout(1000)
    out_path = ASSETS_DIR / "social-preview.png"
    page.screenshot(path=str(out_path))
    print(f"✓ Saved social preview to {out_path}")


def generate_worker_terminal_frames(page):
    """Render high-res terminal frames and compile into animated GIF + static image."""
    steps_data = [
        ("start", []),
        ("step1", [("[01]", "Generating topic...", "[01] ✓ Generating topic: Best Car Phone Mounts for Safe Driving (1m 12s)")]),
        ("step2", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching...", "[02] ✓ Researching: 4 competitor sources analyzed (19s)")
        ]),
        ("step3", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline...", "[03] ✓ Building outline: Structured outline synthesized (1m 20s)")
        ]),
        ("step4", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline: Structured outline synthesized", "(1m 20s)"),
            ("[04]", "Writing article...", "[04] ✓ Writing article: 1,886 words generated (2m 35s)")
        ]),
        ("step5", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline: Structured outline synthesized", "(1m 20s)"),
            ("[04]", "Writing article: 1,886 words generated", "(2m 35s)"),
            ("[05]", "Extracting products...", "[05] ✓ Extracting products: 5 items mapped with Amazon CDN photos & direct links (11s)")
        ]),
        ("step6", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline: Structured outline synthesized", "(1m 20s)"),
            ("[04]", "Writing article: 1,886 words generated", "(2m 35s)"),
            ("[05]", "Extracting products: 5 items mapped with Amazon CDN photos & direct links", "(11s)"),
            ("[06]", "Generating hero image...", "[06] ✓ Generating hero image: Featured image ready (39s)")
        ]),
        ("step7", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline: Structured outline synthesized", "(1m 20s)"),
            ("[04]", "Writing article: 1,886 words generated", "(2m 35s)"),
            ("[05]", "Extracting products: 5 items mapped with Amazon CDN photos & direct links", "(11s)"),
            ("[06]", "Generating hero image: Featured image ready", "(39s)"),
            ("[07]", "Validating & sanitizing...", "[07] ✓ Validating & sanitizing: Passed quality & compliance checks (0s)")
        ]),
        ("step8", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline: Structured outline synthesized", "(1m 20s)"),
            ("[04]", "Writing article: 1,886 words generated", "(2m 35s)"),
            ("[05]", "Extracting products: 5 items mapped with Amazon CDN photos & direct links", "(11s)"),
            ("[06]", "Generating hero image: Featured image ready", "(39s)"),
            ("[07]", "Validating & sanitizing: Passed quality & compliance checks", "(0s)"),
            ("[08]", "Publishing...", "[08] ✓ Publishing: Live on CMS (3s)")
        ]),
        ("published", [
            ("[01]", "Generating topic: Best Car Phone Mounts for Safe Driving", "(1m 12s)"),
            ("[02]", "Researching: 4 competitor sources analyzed", "(19s)"),
            ("[03]", "Building outline: Structured outline synthesized", "(1m 20s)"),
            ("[04]", "Writing article: 1,886 words generated", "(2m 35s)"),
            ("[05]", "Extracting products: 5 items mapped with Amazon CDN photos & direct links", "(11s)"),
            ("[06]", "Generating hero image: Featured image ready", "(39s)"),
            ("[07]", "Validating & sanitizing: Passed quality & compliance checks", "(0s)"),
            ("[08]", "Publishing: Live on CMS", "(3s)")
        ])
    ]

    def render_terminal_html(lines, is_published=False):
        lines_html = ""
        for item in lines:
            if len(item) == 3 and item[2].startswith("["):
                # Done line
                text = item[2]
                num = item[0]
                lines_html += f"""
                <div class="line done">
                    <span class="num">{num}</span>
                    <span class="check">✓</span>
                    <span class="content">{text.split('✓')[1].strip()}</span>
                </div>
                """
            elif len(item) == 3:
                # Finished line with elapsed time
                num, label, elapsed = item
                lines_html += f"""
                <div class="line done">
                    <span class="num">{num}</span>
                    <span class="check">✓</span>
                    <span class="content">{label} <span class="dim">{elapsed}</span></span>
                </div>
                """
            else:
                num, label = item
                lines_html += f"""
                <div class="line active">
                    <span class="num active-num">{num}</span>
                    <span class="content">{label}</span>
                </div>
                """

        published_box_html = ""
        if is_published:
            published_box_html = """
            <div class="publish-card">
                <div class="publish-title">✓ Published:</div>
                <div class="publish-article">Best Car Phone Mounts for Safe Driving</div>
                <div class="publish-time">Total: 6m 59s</div>
            </div>
            """

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="UTF-8">
          <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
          <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{
              width: 900px;
              height: 620px;
              background: #0d1117;
              font-family: 'JetBrains Mono', monospace;
              padding: 24px;
              display: flex;
              align-items: center;
              justify-content: center;
            }}
            .window {{
              width: 100%;
              height: 100%;
              background: #090d13;
              border-radius: 12px;
              border: 1px solid #30363d;
              box-shadow: 0 20px 50px rgba(0, 0, 0, 0.7), 0 0 30px rgba(56, 189, 248, 0.08);
              display: flex;
              flex-direction: column;
              overflow: hidden;
            }}
            .titlebar {{
              height: 38px;
              background: #161b22;
              border-bottom: 1px solid #30363d;
              display: flex;
              align-items: center;
              padding: 0 16px;
              position: relative;
            }}
            .dots {{
              display: flex;
              gap: 8px;
            }}
            .dot {{
              width: 12px;
              height: 12px;
              border-radius: 50%;
            }}
            .dot.red {{ background: #ff5f56; }}
            .dot.yellow {{ background: #ffbd2e; }}
            .dot.green {{ background: #27c93f; }}
            .title {{
              position: absolute;
              left: 50%;
              transform: translateX(-50%);
              font-size: 12px;
              color: #8b949e;
              font-weight: 500;
              display: flex;
              align-items: center;
              gap: 6px;
            }}
            .terminal-body {{
              flex: 1;
              padding: 20px 24px;
              overflow: hidden;
              display: flex;
              flex-direction: column;
              gap: 8px;
              color: #c9d1d9;
              font-size: 13.5px;
              line-height: 1.45;
            }}
            .worker-card {{
              border: 1px solid #38bdf8;
              border-radius: 8px;
              padding: 10px 16px;
              width: 440px;
              background: rgba(56, 189, 248, 0.03);
              margin-bottom: 8px;
            }}
            .worker-header {{
              text-align: center;
              font-weight: 700;
              color: #38bdf8;
              letter-spacing: 1px;
              margin-bottom: 6px;
              padding-bottom: 6px;
              border-bottom: 1px dashed rgba(56, 189, 248, 0.3);
            }}
            .worker-row {{
              display: flex;
              font-size: 12px;
              margin-bottom: 3px;
            }}
            .worker-label {{
              width: 90px;
              color: #38bdf8;
              font-weight: 600;
            }}
            .worker-val {{
              color: #f0f6fc;
              font-weight: 500;
            }}

            .line {{
              display: flex;
              align-items: center;
              gap: 8px;
              font-size: 13.5px;
            }}
            .num {{
              color: #38bdf8;
              font-weight: 600;
            }}
            .check {{
              color: #3fb950;
              font-weight: 700;
            }}
            .active-num {{
              color: #38bdf8;
            }}
            .dim {{
              color: #6e7681;
              font-size: 12px;
              margin-left: 6px;
            }}

            .publish-card {{
              border: 1px solid #3fb950;
              border-radius: 8px;
              padding: 12px 18px;
              background: rgba(63, 185, 80, 0.05);
              width: 580px;
              margin-top: 10px;
            }}
            .publish-title {{
              color: #3fb950;
              font-weight: 700;
              margin-bottom: 4px;
            }}
            .publish-article {{
              color: #f0f6fc;
              font-size: 15px;
              font-weight: 700;
              margin-bottom: 8px;
              padding-left: 12px;
            }}
            .publish-time {{
              color: #38bdf8;
              font-size: 12px;
              font-weight: 600;
            }}
          </style>
        </head>
        <body>
          <div class="window">
            <div class="titlebar">
              <div class="dots">
                <div class="dot red"></div>
                <div class="dot yellow"></div>
                <div class="dot green"></div>
              </div>
              <div class="title">affiliatekage worker &mdash; zsh &mdash; 110x35</div>
            </div>
            <div class="terminal-body">
              <div class="worker-card">
                <div class="worker-header">AFFILIATEKAGE WORKER</div>
                <div class="worker-row"><span class="worker-label">Model:</span><span class="worker-val">qwen3-coder:30b (Ollama)</span></div>
                <div class="worker-row"><span class="worker-label">Mode:</span><span class="worker-val">Production (Autonomous)</span></div>
                <div class="worker-row"><span class="worker-label">Target:</span><span class="worker-val">ejiroinspire.com</span></div>
                <div class="worker-row"><span class="worker-label">Images:</span><span class="worker-val">COMFYUI (SDXL Local GPU)</span></div>
              </div>

              {lines_html}

              {published_box_html}
            </div>
          </div>
        </body>
        </html>
        """

    frame_images = []
    page.set_viewport_size({"width": 900, "height": 620})

    temp_dir = Path("/tmp/term_frames")
    temp_dir.mkdir(exist_ok=True)

    for idx, (name, lines) in enumerate(steps_data):
        is_pub = (name == "published")
        html = render_terminal_html(lines, is_published=is_pub)
        page.set_content(html)
        page.wait_for_timeout(300)
        frame_path = temp_dir / f"frame_{idx:02d}.png"
        page.screenshot(path=str(frame_path))

        img = Image.open(frame_path)
        frame_images.append(img)

        # Also save the final published state as a crisp static snapshot
        if is_pub:
            static_out = ASSETS_DIR / "worker_terminal.png"
            img.save(static_out)
            print(f"✓ Saved static terminal screenshot to {static_out}")

    # Create smooth looping animated GIF
    # Frame durations: 700ms per step, 3500ms on final published card
    durations = [700] * (len(frame_images) - 1) + [3500]
    gif_out = ASSETS_DIR / "worker_demo.gif"
    frame_images[0].save(
        gif_out,
        save_all=True,
        append_images=frame_images[1:],
        duration=durations,
        loop=0,
        optimize=True
    )
    print(f"✓ Saved animated worker GIF to {gif_out} ({os.path.getsize(gif_out) // 1024} KB)")


def generate_production_showcase(page):
    """Combine live screenshots into a sleek showcase mockup."""
    import base64
    
    blog_img_path = ASSETS_DIR / "production_blog.png"
    article_img_path = ASSETS_DIR / "article_hero.png"
    
    with open(blog_img_path, "rb") as f:
        blog_b64 = base64.b64encode(f.read()).decode("utf-8")
    with open(article_img_path, "rb") as f:
        article_b64 = base64.b64encode(f.read()).decode("utf-8")

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
      <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
          width: 1280px;
          height: 720px;
          background: #080c14;
          font-family: 'Inter', sans-serif;
          color: #f8fafc;
          padding: 32px 48px;
          position: relative;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
        }}

        .ambient {{
          position: absolute;
          inset: 0;
          background: radial-gradient(circle at 80% 20%, rgba(56, 189, 248, 0.12) 0%, transparent 50%),
                      radial-gradient(circle at 15% 85%, rgba(34, 197, 94, 0.1) 0%, transparent 50%);
          pointer-events: none;
        }}

        .header {{
          display: flex;
          align-items: center;
          justify-content: space-between;
          position: relative;
          z-index: 10;
        }}

        .title-group h2 {{
          font-size: 28px;
          font-weight: 800;
          letter-spacing: -0.5px;
          display: flex;
          align-items: center;
          gap: 12px;
        }}
        .title-group p {{
          color: #94a3b8;
          font-size: 14px;
          margin-top: 4px;
        }}

        .live-tag {{
          background: rgba(34, 197, 94, 0.12);
          border: 1px solid rgba(34, 197, 94, 0.35);
          color: #4ade80;
          font-size: 12.5px;
          font-weight: 700;
          padding: 6px 16px;
          border-radius: 9999px;
          display: flex;
          align-items: center;
          gap: 8px;
        }}
        .live-dot {{
          width: 8px;
          height: 8px;
          border-radius: 50%;
          background: #22c55e;
          box-shadow: 0 0 10px #22c55e;
        }}

        .mockup-grid {{
          display: grid;
          grid-template-columns: 1.15fr 1fr;
          gap: 24px;
          position: relative;
          z-index: 10;
          margin: 16px 0;
          flex: 1;
        }}

        .card-frame {{
          background: #0f172a;
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 14px;
          overflow: hidden;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
          display: flex;
          flex-direction: column;
        }}

        .frame-top {{
          height: 34px;
          background: #162032;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          align-items: center;
          padding: 0 14px;
          gap: 6px;
        }}
        .fd {{ width: 10px; height: 10px; border-radius: 50%; }}
        .fd-r {{ background: #ef4444; }}
        .fd-y {{ background: #f59e0b; }}
        .fd-g {{ background: #10b981; }}
        .frame-url {{
          margin-left: 12px;
          background: rgba(0, 0, 0, 0.35);
          border-radius: 4px;
          padding: 3px 12px;
          font-size: 11px;
          color: #94a3b8;
          font-family: 'JetBrains Mono', monospace;
        }}

        .frame-img {{
          flex: 1;
          width: 100%;
          height: 480px;
          object-fit: cover;
          object-position: top;
        }}

        .footer-note {{
          position: relative;
          z-index: 10;
          display: flex;
          justify-content: space-between;
          align-items: center;
          color: #64748b;
          font-size: 12px;
          padding-top: 10px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
        }}
        .footer-note strong {{
          color: #94a3b8;
        }}
      </style>
    </head>
    <body>
      <div class="ambient"></div>

      <div class="header">
        <div class="title-group">
          <h2>Production Proven &bull; Live CMS Publishing Showcase</h2>
          <p>Autonomous AI engine running 24/7 &mdash; researching, generating, enriching, and publishing without human intervention.</p>
        </div>
        <div class="live-tag">
          <div class="live-dot"></div>
          ejiroinspire.com/blog
        </div>
      </div>

      <div class="mockup-grid">
        <div class="card-frame">
          <div class="frame-top">
            <div class="fd fd-r"></div>
            <div class="fd fd-y"></div>
            <div class="fd fd-g"></div>
            <div class="frame-url">https://ejiroinspire.com/blog</div>
          </div>
          <img class="frame-img" src="data:image/png;base64,{blog_b64}" alt="Live Blog Index">
        </div>

        <div class="card-frame">
          <div class="frame-top">
            <div class="fd fd-r"></div>
            <div class="fd fd-y"></div>
            <div class="fd fd-g"></div>
            <div class="frame-url">https://ejiroinspire.com/blog/foam-rollers-...</div>
          </div>
          <img class="frame-img" src="data:image/png;base64,{article_b64}" alt="Live Article & ComfyUI SDXL Hero Image">
        </div>
      </div>

      <div class="footer-note">
        <span>Stack: <strong>Linux</strong> &bull; <strong>Qwen 30B (Ollama)</strong> &bull; <strong>ComfyUI SDXL</strong> &bull; <strong>Stealth Amazon Scraper</strong> &bull; <strong>Next.js</strong></span>
        <span>Verified Production Output &bull; <a href="https://ejiroinspire.com/blog" style="color: #38bdf8; text-decoration: none;">ejiroinspire.com</a></span>
      </div>
    </body>
    </html>
    """

    page.set_viewport_size({"width": 1280, "height": 720})
    page.set_content(html)
    page.wait_for_timeout(1000)
    out_path = ASSETS_DIR / "production_showcase.png"
    page.screenshot(path=str(out_path))
    print(f"✓ Saved production showcase to {out_path}")


def main():
    print("🎨 Generating AffiliateKage Visual Media Assets...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(device_scale_factor=2)  # Retina 2x scale
        page = context.new_page()

        # 1. Social Preview
        generate_social_preview(page)

        # 2. Worker Terminal & GIF
        generate_worker_terminal_frames(page)

        # 3. Production Showcase
        generate_production_showcase(page)

        browser.close()

    print("\n🎉 All visual assets generated successfully in assets/!")


if __name__ == "__main__":
    main()
