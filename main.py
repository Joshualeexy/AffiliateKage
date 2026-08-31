import argparse
import json
import time
import traceback
import subprocess
import warnings
from pathlib import Path

# Suppress unclosed sqlite3 ResourceWarnings from Crawl4AI and other libs
warnings.filterwarnings("ignore", category=ResourceWarning)

from generators.topic_generator import TopicGenerator
from generators.article_generator import ArticleGenerator
from generators.image_prompt_generator import ImagePromptGenerator
from generators.classifier import Classifier, ArticleType, article_type_from_topic_format
from generators.outline_generator import OutlineGenerator
from generators.entity_extractor import EntityExtractor
from generators.content_sanitizer import ContentSanitizer
from generators.internal_link_injector import InternalLinkInjector
from generators.affiliate_link_injector import AffiliateLinkInjector
from validation.article_validator import ArticleValidator
from research.crawl4ai_provider import Crawl4AiProvider
from research.duckduckgo import DuckDuckGoProvider

from services.api import ApiClient
from services.image_generator import ImageGenerator
from services.comfy import ComfyClient
from services.markdown import to_html
from services.image_fetcher import ImageFetcher
from services.terminal_ui import ui
from config import OLLAMA_MODEL, IMAGE_PROVIDER, AMAZON_AFFILIATE_TAG

STATE_PATH = Path("pipeline_state.json")
MAX_VALIDATION_RETRIES = 3

def save_state(state: dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")

def load_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"Failed to load saved state: {e}")
        return None

def clear_state() -> None:
    STATE_PATH.unlink(missing_ok=True)

def run_pipeline(
    api: ApiClient, 
    image_generator: ImageGenerator, 
    topic_generator: TopicGenerator, 
    article_generator: ArticleGenerator, 
    image_prompt_generator: ImagePromptGenerator,
    classifier: Classifier,
    researcher: Crawl4AiProvider,
    outline_generator: OutlineGenerator,
    validator: ArticleValidator,
    entity_extractor: EntityExtractor,
    content_sanitizer: ContentSanitizer,
    internal_link_injector: InternalLinkInjector,
    affiliate_link_injector: AffiliateLinkInjector,
) -> None:
    state = load_state() or {"stage": "start", "status": "running"}

    if STATE_PATH.exists():
        print(f"Resuming saved pipeline state from stage: {state.get('stage')}")

    try:
        # 1. Topic Generation
        topic = state.get("topic")
        if state["stage"] in {"start", "topic_generated"}:
            if not topic:
                ui.start_step(1, "Generating topic")
                try:
                    topic = topic_generator.generate(api_client=api)
                except ValueError as e:
                    print(f"Topic generation failed after all retries: {e}")
                    clear_state()
                    return
                ui.complete_step(1, "Generating topic", topic['title'])
                state.update({"stage": "topic_generated", "topic": topic})
                save_state(state)
            else:
                ui.complete_step(1, "Resumed topic", topic['title'])
                # On resume, perform sanity check since it wasn't generated in this process
                if api.topic_exists(topic["title"]):
                    print("Topic already exists on resumption. Skipping.")
                    clear_state()
                    return

            state["stage"] = "topic_checked"
            save_state(state)

        # 2. Topic Classification
        article_type_val = state.get("article_type")
        if state["stage"] in {"topic_checked", "topic_classified"}:
            if not article_type_val:
                article_type = article_type_from_topic_format(topic.get("type"))
                if not article_type:
                    article_type = classifier.classify(topic["title"])
                state.update({"stage": "topic_classified", "article_type": article_type.value})
                save_state(state)

        # 3. Research
        research_dict = state.get("research_report")
        if state["stage"] in {"topic_classified", "research_completed"}:
            if not research_dict:
                ui.start_step(2, "Researching")
                # Try the highly specific query first
                query = f"{topic['primary_keyword']} {topic['title']}"
                report = researcher.search(query)
                
                # Fallback 1: Just the title
                if not report.results:
                    report = researcher.search(topic['title'])
                    
                # Fallback 2: Just the primary keyword
                if not report.results:
                    report = researcher.search(topic['primary_keyword'])
                    
                ui.complete_step(2, "Researching", f"{len(report.results)} competitor sources analyzed")
                # Convert dataclass to dict for JSON serialization
                report_dict = {
                    "query": report.query,
                    "results": [{"url": r.url, "title": r.title, "content": r.content, "snippet": r.snippet} for r in report.results]
                }
                state.update({"stage": "research_completed", "research_report": report_dict})
                save_state(state)

        # Reconstruct research report object if exists
        from research.base import ResearchReport, SearchResult
        research_report = None
        if state.get("research_report"):
            rd = state["research_report"]
            results = [SearchResult(**r) for r in rd.get("results", [])]
            research_report = ResearchReport(query=rd["query"], results=results)

        # 4. Outline Generation
        outline = state.get("outline")
        if state["stage"] in {"research_completed", "outline_generated"}:
            if not outline:
                ui.start_step(3, "Building outline")
                article_type_enum = ArticleType(state["article_type"])
                outline = outline_generator.generate(topic, article_type_enum, research_report)
                ui.complete_step(3, "Building outline", "Structured outline synthesized")
                state.update({"stage": "outline_generated", "outline": outline})
                save_state(state)

        # 5. Article Generation
        article = state.get("article")
        if state["stage"] in {"outline_generated", "article_generated"}:
            if not article:
                ui.start_step(4, "Writing article")
                article_type_enum = ArticleType(state["article_type"])
                article = article_generator.generate(topic, article_type_enum, outline, research_report)

                # Sanitize Article (code-only, instant)
                article["content"] = content_sanitizer.sanitize(article["content"], article_type_enum)
                article["title"] = content_sanitizer.sanitize_plain_text(article["title"])
                article["seo_title"] = content_sanitizer.sanitize_plain_text(article["seo_title"])
                
                word_count = len(article.get("content", "").split())
                ui.complete_step(4, "Writing article", f"{word_count:,} words generated")

                state.update({"stage": "article_generated", "article": article})
                save_state(state)

        # 6. Article Validation
        if state["stage"] == "article_generated":
            print("Starting stage: Validate Article")
            article_type_enum = ArticleType(state["article_type"])
            ui.start_step(7, "Validating & sanitizing")
            report = validator.validate(state["article"]["content"], article_type_enum)
            if not report.passed:
                print("Validation failed! Looping back to article generation.")
                for issue in report.issues:
                    print(f"[{issue.severity.upper()}] {issue.check}: {issue.message}")

                failures = int(state.get("validation_failures", 0)) + 1
                if failures >= MAX_VALIDATION_RETRIES:
                    state["status"] = "failed"
                    state["validation_failures"] = failures
                    save_state(state)
                    print(
                        f"Article validation failed {failures} times. "
                        "Saved state for inspection."
                    )
                    return

                # Reset state to generate article again
                state["stage"] = "outline_generated"
                state["article"] = None
                state["validation_failures"] = failures
                save_state(state)
                return # Break out and let loop restart
            else:
                ui.complete_step(7, "Validating & sanitizing", "Passed quality & compliance checks")
                state["stage"] = "article_validated"
                state["validation_failures"] = 0
                save_state(state)

        # 7. Entity Extraction
        entities = state.get("entities")
        if state["stage"] in {"article_validated", "entities_extracted"}:
            if not entities:
                entities = entity_extractor.extract(state["article"]["content"])
                state["article"]["entities"] = entities
                state["article"]["article_type"] = state["article_type"]
                state["article"]["category"] = topic.get("category", "") if topic else ""
                state.update({"stage": "entities_extracted", "entities": entities})
                save_state(state)

        # 7.5 Fetch Product Images & Direct URLs (code-only, instant)
        product_images = state.get("product_images", {})
        product_urls = state.get("product_urls", {})
        if state["stage"] == "entities_extracted" and (not product_images or not product_urls):
            ui.start_step(5, "Extracting products")
            try:
                category = topic.get("category", "") if topic else ""
                product_data = ImageFetcher.fetch_product_data(
                    state.get("entities", []),
                    max_items=10
                )
                product_images = {k: v.get("image", "") for k, v in product_data.items() if v.get("image")}
                product_urls = {k: v.get("url", "") for k, v in product_data.items() if v.get("url")}
                state["product_images"] = product_images
                state["product_urls"] = product_urls
                ui.complete_step(5, "Extracting products", f"{len(product_images)} items mapped with Amazon CDN photos & direct links")
            except Exception as e:
                print(f"Warning: Image/link fetching failed: {e}. Continuing without product metadata.")
                state["product_images"] = {}
                state["product_urls"] = {}

        # 7.6 Enforce Smart Entity Links (code-only, instant)
        if state["stage"] == "entities_extracted":
            print("Starting stage: Enforce Smart Entity Links")
            category = topic.get("category", "") if topic else ""
            state["article"]["content"] = content_sanitizer.enforce_amazon_links(
                state["article"]["content"],
                state.get("entities", []),
                category=category,
            )
            print("Completed stage: Enforce Smart Entity Links")

            # 7.6b Enforce Software/Digital Entity Links (code-only, instant)
            print("Starting stage: Enforce Software Entity Links")
            try:
                affiliate_links = api.get_affiliate_links() or []
            except Exception:
                affiliate_links = []
            state["article"]["content"] = content_sanitizer.enforce_software_links(
                state["article"]["content"],
                state.get("entities", []),
                category=category,
                affiliate_links=affiliate_links,
            )
            print("Completed stage: Enforce Software Entity Links")

            # 7.7 Inject Visual Product Cards with Direct Links (code-only, instant)
            print("Starting stage: Inject Product Cards")
            state["article"]["content"] = content_sanitizer.inject_product_cards(
                state["article"]["content"],
                state.get("entities", []),
                product_images=state.get("product_images", {}),
                product_urls=state.get("product_urls", {}),
                category=category,
            )
            print("Completed stage: Inject Product Cards")

            state["stage"] = "amazon_links_enforced"
            save_state(state)

        # 8. Internal Link Injection (code + LLM)
        if state["stage"] == "amazon_links_enforced":
            print("Starting stage: Inject Internal Links")
            state["article"]["content"] = internal_link_injector.inject(
                state["article"]["content"],
                state.get("topic", {}),
                state.get("entities", []),
                api,
            )
            print("Completed stage: Inject Internal Links")
            state["stage"] = "internal_links_injected"
            save_state(state)

        # 9. Markdown Conversion
        if state["stage"] == "internal_links_injected":
            print("Starting stage: Convert Markdown -> HTML")
            html_content = to_html(state["article"]["content"])
            print("Applying affiliate links...")
            try:
                affiliate_links = api.get_affiliate_links()
                if affiliate_links:
                    html_content = affiliate_link_injector.inject(html_content, affiliate_links)
                    print(f"Applied affiliate link patterns. Total: {len(affiliate_links)}")
                else:
                    print("No affiliate links configured on backend.")
            except Exception as e:
                print(f"Warning: Failed to fetch or inject affiliate links: {e}")
            state["article"]["content"] = html_content
            print("Completed stage: Convert Markdown -> HTML")
            state["stage"] = "markdown_converted"
            save_state(state)

        # 9. Image Prompt Generation
        image_prompt = state.get("image_prompt")
        if state["stage"] in {"markdown_converted", "image_prompt_generated"}:
            if not image_prompt:
                print("Starting stage: Generate Image Prompt")
                image_prompt = image_prompt_generator.generate(topic, state["article"])
                print("Completed stage: Generate Image Prompt")
                state.update({"stage": "image_prompt_generated", "image_prompt": image_prompt})
                save_state(state)

        # 10. Unload Ollama
        if state["stage"] == "image_prompt_generated":
            try:
                print("Unloading Ollama model...")
                image_prompt_generator.unload()
                print("Ollama model unloaded.")
            except Exception as e:
                print(f"Warning: failed to unload Ollama model: {e}")
            state["stage"] = "image_generated"
            save_state(state)

        # 11. Image Generation with Process Management
        image_path = state.get("image_path")
        if state["stage"] in {"image_generated", "publish_ready"}:
            if not image_path:
                ui.start_step(6, "Generating hero image")
                try:
                    image_path = image_generator.generate(image_prompt)
                    ui.complete_step(6, "Generating hero image", "Featured image ready")
                    state.update({"stage": "publish_ready", "image_path": image_path})
                    save_state(state)
                except Exception as e:
                    print(f"Failed to generate image: {e}")
                    raise

        # 12. Publish
        if state["stage"] == "publish_ready":
            ui.start_step(8, "Publishing")
            api.publish(state["article"], image_path)
            ui.complete_step(8, "Publishing", "Live on CMS")
            ui.render_publish_card(topic['title'])
            clear_state()

    except KeyboardInterrupt:
        print("\nStopping automation...")
        state["status"] = "interrupted"
        save_state(state)
        raise

    except Exception as e:
        traceback.print_exc()
        state["status"] = "failed"
        save_state(state)
        print("Pipeline failed and state was saved. Restart the process to resume.")
        return


def main(clear_saved_state: bool = False):
    if clear_saved_state:
        print("Clearing saved pipeline state before starting.")
        clear_state()

    try:
        api = ApiClient()
        image_generator = ImageGenerator()

        topic_generator = TopicGenerator()
        article_generator = ArticleGenerator()
        image_prompt_generator = ImagePromptGenerator()
        
        # Initialize modules
        classifier = Classifier()
        researcher = Crawl4AiProvider()
        outline_generator = OutlineGenerator()
        validator = ArticleValidator()
        entity_extractor = EntityExtractor()
        content_sanitizer = ContentSanitizer(affiliate_tag=AMAZON_AFFILIATE_TAG)
        internal_link_injector = InternalLinkInjector()
        affiliate_link_injector = AffiliateLinkInjector()

        # Render stylish AFFILIATEKAGE WORKER status card
        ui.render_worker_card(
            model=OLLAMA_MODEL,
            mode="Production",
            target="Ejiro Inspire",
            images=IMAGE_PROVIDER
        )

        while True:
            run_pipeline(
                api, image_generator, topic_generator, article_generator, image_prompt_generator,
                classifier, researcher, outline_generator, validator, entity_extractor,
                content_sanitizer, internal_link_injector, affiliate_link_injector,
            )

            if STATE_PATH.exists():
                state = load_state() or {}
                should_retry_article = (
                    state.get("stage") == "outline_generated"
                    and state.get("article") is None
                    and state.get("status") != "failed"
                    and int(state.get("validation_failures", 0)) < MAX_VALIDATION_RETRIES
                )
                if should_retry_article:
                    print("Retrying article generation after validation failure...")
                    continue

                print("Saved state exists. Exiting to avoid overwriting incomplete session.")
                break

            print("Sleeping before next session...")
            time.sleep(10)
            
    except Exception as e:
        print(f"Pipeline error: {e}")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Ejiro Inspire automation pipeline.")
    parser.add_argument(
        "--clear-state",
        action="store_true",
        help="Clear saved pipeline state before starting a new run.",
    )
    args = parser.parse_args()
    main(clear_saved_state=args.clear_state)
