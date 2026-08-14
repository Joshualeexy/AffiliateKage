import re
import time
import requests

from config import API_URL, API_TOKEN


class ApiClient:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {API_TOKEN}",
            "Accept": "application/json",
        })

    def topic_exists(self, title: str, max_retries: int = 3, backoff_seconds: int = 3) -> bool:
        url = f"{API_URL}/automation/check-topic"

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.post(
                    url,
                    json={"title": title},
                )
                response.raise_for_status()
                return response.json()["exists"]
            except requests.RequestException as e:
                if attempt == max_retries:
                    raise
                print(
                    f"Topic existence check attempt {attempt} failed: {e}. "
                    f"Retrying in {backoff_seconds * attempt} seconds..."
                )
                time.sleep(backoff_seconds * attempt)

    def get_published_posts(self, max_retries: int = 3, backoff_seconds: int = 3) -> list | None:
        """Fetch all published posts from the blog API.
        
        Returns a list of dicts with 'title' and 'slug' keys,
        or None if the endpoint is not available yet.
        """
        url = f"{API_URL}/automation/published-posts"

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url)
                if response.status_code == 404:
                    # Endpoint not created yet; caller should use fallback
                    return None
                response.raise_for_status()
                return response.json()
            except requests.RequestException as e:
                if attempt == max_retries:
                    print(f"Failed to fetch published posts: {e}")
                    return None
                print(
                    f"Published posts fetch attempt {attempt} failed: {e}. "
                    f"Retrying in {backoff_seconds * attempt} seconds..."
                )
                time.sleep(backoff_seconds * attempt)

    def get_categories(self, max_retries: int = 3, backoff_seconds: int = 3) -> list | None:
        url = f"{API_URL}/categories"

        for attempt in range(1, max_retries + 1):
            try:
                response = self.session.get(url)
                response.raise_for_status()
                return response.json().get("data", [])
            except requests.RequestException as e:
                if attempt == max_retries:
                    print(f"Failed to fetch categories: {e}")
                    return None
                print(
                    f"Categories fetch attempt {attempt} failed: {e}. "
                    f"Retrying in {backoff_seconds * attempt} seconds..."
                )
                time.sleep(backoff_seconds * attempt)

    def map_category(self, category_name: str = None, article_type: str = None) -> int | None:
        """Map the topic category name or article type to a backend category ID."""
        categories = self.get_categories()
        if not categories:
            return None

        def normalize(s: str) -> str:
            return re.sub(r'\s+', '', s.lower().strip())

        # 1. Match the category name/slug directly
        if category_name:
            norm_name = normalize(category_name)
            for cat in categories:
                if normalize(cat.get("name", "")) == norm_name or normalize(cat.get("slug", "")) == norm_name:
                    return cat["id"]

        # 2. Map based on article type
        if article_type:
            mapping = {
                "review": ["review", "reviews"],
                "comparison": ["comparison", "comparisons"],
                "buying_guide": ["comparison", "comparisons", "buyingguide", "buyingguides"],
                "listicle": ["comparison", "comparisons", "lists", "listicle", "listicles"],
                "tutorial": ["insights", "insight", "tutorial", "tutorials", "guides", "guide"],
                "informational": ["analysys", "analysis", "insights", "insight", "informational"],
            }
            
            allowed_names = mapping.get(article_type.lower())
            if allowed_names:
                for target in allowed_names:
                    norm_target = normalize(target)
                    for cat in categories:
                        if normalize(cat.get("name", "")) == norm_target or normalize(cat.get("slug", "")) == norm_target:
                            return cat["id"]

        # 3. Fallback to first available category
        return categories[0]["id"] if categories else None

    def publish(self, article: dict, image_path: str, max_retries: int = 3, backoff_seconds: int = 5):
        url = f"{API_URL}/automation/publish"
        response = None

        for attempt in range(1, max_retries + 1):
            try:
                with open(image_path, "rb") as image:
                    files = {
                        "featured_image": image,
                    }

                    excerpt = article.get("excerpt", "")
                    if len(excerpt) > 500:
                        print(f"Warning: Excerpt is too long ({len(excerpt)} characters). Truncating to 500 characters.")
                        excerpt = excerpt[:497].rstrip() + "..."

                    data = {
                        "title": article["title"],
                        "slug": article.get("slug", ""),
                        "excerpt": excerpt,
                        "content": article["content"],
                    }

                    category_id = article.get("category_id")
                    if not category_id:
                        category_id = self.map_category(
                            category_name=article.get("category"),
                            article_type=article.get("article_type")
                        )

                    if category_id:
                        data["category_id"] = category_id

                    response = self.session.post(
                        url,
                        data=data,
                        files=files,
                    )

                response.raise_for_status()
                return response.json()

            except requests.RequestException as e:
                body = response.text if response is not None else None
                if attempt == max_retries:
                    print(f"Publish failed after {attempt} attempts: {e}")
                    if body:
                        print(f"Publish response body: {body}")
                    raise

                wait = backoff_seconds * attempt
                print(
                    f"Publish attempt {attempt} failed: {e}. "
                    f"Retrying in {wait} seconds..."
                )
                if body:
                    print(f"Last response body: {body}")
                time.sleep(wait)