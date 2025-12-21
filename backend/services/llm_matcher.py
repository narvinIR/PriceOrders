"""
LLM-based matching через OpenRouter API.
Заменяет локальный embedding matcher (экономит ~500 МБ RAM).
"""
import json
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты помощник по сопоставлению товаров Jakko (канализация, ППР, водопровод).
Тебе дан каталог товаров и запрос клиента. Найди ЛУЧШЕЕ совпадение.

КРИТИЧНЫЕ ПРАВИЛА:
1. РАЗМЕРЫ (110, 50, 32, 40 мм) - ВСЕГДА должны совпадать!
2. "канализационная/серая" = ПП труба (артикул 202...)
3. "малошумная/белая канализация/Prestige" = артикул 403...
4. "наружная/рыжая" = артикул 303...
5. "колено/угол/угольник" = отвод
6. "переход" = переходник
7. Учитывай углы: 45°, 67°, 87°, 90°
8. Если НЕ уверен или размер не совпадает - верни confidence < 70

Ответь ТОЛЬКО JSON (без markdown, без ```):
{"sku": "артикул", "name": "название", "confidence": 0-100}

Если товар НЕ найден:
{"sku": null, "name": null, "confidence": 0}
"""


class LLMMatcher:
    """Matching товаров через LLM API (OpenRouter)"""

    def __init__(self, api_key: str, model: str = "x-ai/grok-4.1-fast"):
        self.api_key = api_key
        self.model = model
        self.products_cache: Optional[str] = None
        self._products_list: list[dict] = []

    def set_products(self, products: list[dict]) -> None:
        """
        Кэшировать каталог для промпта.
        Формируем компактный список SKU - название.
        """
        self._products_list = products
        # Формируем компактный список для промпта (лимит ~800 товаров для контекста)
        lines = []
        for p in products[:800]:
            sku = p.get('sku', '')
            name = p.get('name', '')
            if sku and name:
                lines.append(f"{sku} - {name}")
        self.products_cache = "\n".join(lines)
        logger.info(f"✅ LLMMatcher: загружено {len(lines)} товаров")

    def match(self, query: str) -> Optional[dict]:
        """
        Найти товар через LLM.

        Args:
            query: Запрос клиента (название/артикул)

        Returns:
            {"sku": "...", "name": "...", "confidence": 0-100} или None
        """
        if not self.products_cache:
            logger.warning("LLMMatcher: каталог не загружен")
            return None

        if not query or len(query.strip()) < 2:
            return None

        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"{SYSTEM_PROMPT}\n\nКаталог товаров:\n{self.products_cache}"
                        },
                        {
                            "role": "user",
                            "content": f"Найди товар: {query}"
                        }
                    ],
                    "temperature": 0,
                    "max_tokens": 200,
                },
                timeout=30.0
            )

            if response.status_code != 200:
                logger.error(f"LLM API error: {response.status_code} - {response.text[:200]}")
                return None

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Парсим JSON из ответа
            # Убираем возможные markdown блоки
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            result = json.loads(content)
            logger.info(f"LLM match: '{query}' → {result.get('sku')} ({result.get('confidence')}%)")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"LLM JSON parse error: {e}, content: {content[:100]}")
            return None
        except httpx.TimeoutException:
            logger.error("LLM API timeout (30s)")
            return None
        except Exception as e:
            logger.error(f"LLM match error: {e}")
            return None

    def get_product_by_sku(self, sku: str) -> Optional[dict]:
        """Найти товар в кэше по SKU"""
        for p in self._products_list:
            if p.get('sku') == sku:
                return p
        return None

    @property
    def is_ready(self) -> bool:
        """Проверка готовности"""
        return self.products_cache is not None and len(self.products_cache) > 0


# Singleton
_llm_matcher: Optional[LLMMatcher] = None


def get_llm_matcher() -> Optional[LLMMatcher]:
    """Получить глобальный экземпляр LLMMatcher"""
    global _llm_matcher
    if _llm_matcher is None:
        from backend.config import settings
        if settings.openrouter_api_key:
            _llm_matcher = LLMMatcher(
                api_key=settings.openrouter_api_key,
                model=settings.llm_model
            )
            logger.info(f"✅ LLMMatcher инициализирован (модель: {settings.llm_model})")
        else:
            logger.warning("⚠️ OPENROUTER_API_KEY не установлен - LLM matching отключен")
    return _llm_matcher
