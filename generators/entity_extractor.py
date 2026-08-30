import json
from typing import List, Dict, Any
from services.ollama_client import OllamaClient, extract_json
from services.prompt_loader import load_prompt

class EntityExtractor:
    def __init__(self):
        self.client = OllamaClient()

    def extract(self, content: str) -> List[Dict[str, Any]]:
        """
        Extract entities from article content.
        Returns a list of entity dicts, each with "name", "type", "is_physical", and "context".
        Types are normalized to: "product" (physical), "software", "brand", "company".
        """
        try:
            prompt = load_prompt("entity_extraction", content=content)
        except Exception:
            # Fallback if prompt is missing
            prompt = (
                f"Extract key entities (physical products, software/apps, brands) from this article.\n"
                f"Classify type as 'physical_product', 'software_app', 'brand', or 'company'.\n"
                f"Return ONLY JSON: {{\"entities\": [{{\"name\": \"X\", \"type\": \"physical_product\", \"is_physical\": true}}]}}\n\n"
                f"Article: {content[:3000]}"
            )

        try:
            response = self.client.generate(
                prompt=prompt,
                format="json",
                options={"temperature": 0.2},
            )
            result = extract_json(response["response"])
            entities = result.get("entities", [])
            
            validated: List[Dict[str, Any]] = []
            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                name = entity.get("name", "").strip()
                if not name or len(name) < 2:
                    continue

                raw_type = entity.get("type", "").strip().lower()
                raw_is_physical = entity.get("is_physical")

                # Normalize type and is_physical
                if raw_type in {"physical_product", "hardware", "hardware_product", "device", "gear"}:
                    norm_type = "product"
                    is_physical = True
                elif raw_type in {"software_app", "software", "app", "service", "saas", "website", "platform", "tool"}:
                    norm_type = "software"
                    is_physical = False
                elif raw_type in {"brand", "hardware_brand"}:
                    norm_type = "brand"
                    is_physical = True if raw_is_physical is True else False
                elif raw_type in {"company", "publisher"}:
                    norm_type = "company"
                    is_physical = False
                elif raw_type == "product":
                    # Determine from is_physical flag if provided
                    if raw_is_physical is False:
                        norm_type = "software"
                        is_physical = False
                    else:
                        norm_type = "product"
                        is_physical = True if raw_is_physical is True else True
                else:
                    norm_type = "company"
                    is_physical = False

                validated.append({
                    "name": name,
                    "type": norm_type,
                    "is_physical": is_physical,
                    "context": entity.get("context", "")
                })

            return validated
        except Exception as e:
            print(f"Entity extraction failed: {e}")
            return []
