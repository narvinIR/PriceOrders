"""
LLM-based matching через OpenRouter API.
Заменяет локальный embedding matcher (экономит ~500 МБ RAM).
Промпт загружается из Supabase (таблица settings).
"""

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

# Fallback промпт (если БД недоступна)
DEFAULT_SYSTEM_PROMPT = """Ты помощник по сопоставлению товаров Jakko (канализация, ППР, водопровод).
Найди ЛУЧШЕЕ совпадение из каталога для запроса клиента.

СОКРАЩЕНИЯ КЛИЕНТОВ:
- "ПП" / "ППР" = полипропилен
- "арм." = армированная (труба армированная стекловолокном)
- "ред." = ПЕРЕХОДНИК (тройник ред. 40*25*40 = тройник переходник 40-25-40)
- "НР" = наружная резьба, "ВР" = внутренняя резьба
- "американка" = муфта разъемная
- "90*40*90" = размеры через * (вместо ×)
- "PN25 40*6,7" = труба PN25 диаметр 40 толщина стенки 6.7
- "компенсирующая петля" = компенсатор

СИНОНИМЫ (одно и то же):
- колено/угол/угольник = отвод
- американка = муфта разъемная
- ред./ред = переходник
- опора/держатель/стойка для труб = клипсы (крепёж)
- хомут с защёлкой = клипсы

ФОРМАТЫ КАТАЛОГА (ВАЖНО!):
- "Муфта разъемная ППР ЭКО с нар. рез. белый 32x1" Jakko" = Муфта НР 32×1" (американка с наружной резьбой)
- "Муфта разъемная ППР ЭКО с вн. рез. белый 32x1" Jakko" = Муфта ВР 32×1" (американка с внутренней резьбой)
- "Тройник переходник ППР белый 40-25-40 Jakko" = Тройник ред. 40*25*40
- "Муфта переходник ППР ВН/ВН белый 40-32 Jakko" = Муфта ред. 40*32

РАЗМЕРЫ С РЕЗЬБОЙ (КРИТИЧНО!):
- "32*1" = 32мм × 1 дюйм резьбы (НЕ два размера фитинга!)
- "25*3/4" = 25мм × 3/4 дюйма резьбы
- "20*1/2" = 20мм × 1/2 дюйма резьбы
Если клиент пишет "Муфта НР 32*1" - ищи "Муфта разъемная с нар. рез. 32x1""!

КАТЕГОРИИ ТРУБ:
- "канализационная/серая" = артикул 202...
- "малошумная/белая/Prestige" = артикул 403...
- "наружная/рыжая" = артикул 303...
- "ППР/водопроводная" = артикул 101...

КРИТИЧНЫЕ ПРАВИЛА:
1. РАЗМЕРЫ (110, 50, 32, 40 мм) - ВСЕГДА должны совпадать!
2. "колено/угол" = отвод
3. "переход" = переходник
4. "ред." = переходник (НЕ обычный фитинг!)
5. Углы: 45°, 67°, 87°, 90°
6. "НР/ВР" с размером через * = комбинированная муфта с резьбой
7. Если размер НЕ совпадает - confidence < 70
8. СТРОГО РАЗЛИЧАЙ: "Муфта" != "Отвод" (Confidence 0 если перепутал!)
9. СТРОГО РАЗЛИЧАЙ: "Наружная" (НР) != "Внутренняя" (ВР) резьба!
10. "Отвод 90" и "Отвод 45" - разные товары!

Ответь ТОЛЬКО JSON (без markdown):
{"sku": "артикул", "name": "название", "confidence": 0-100}

Если НЕ найден:
{"sku": null, "name": null, "confidence": 0}
"""

# Кэш промпта (TTL 10 минут)
_prompt_cache: dict[str, tuple[str, float]] = {}
_PROMPT_CACHE_TTL = 600  # 10 минут


def _get_system_prompt() -> str:
    """Загрузить промпт из Supabase с кэшированием 10 минут."""
    # FORCE OVERRIDE: Игнорируем БД, так как там старый промпт, который ломает логику.
    # Используем только жестко заданный строгий промпт.
    return DEFAULT_SYSTEM_PROMPT

    # --- DB Loading Disabled for stability ---
    # cache_key = "llm_system_prompt"
    # now = time.time()
    # if cache_key in _prompt_cache: ...
    # try:
    #     result = supabase.table("settings").select("value").eq("key", cache_key).single().execute()
    #     ...
    # except ...


class LLMMatcher:
    """Matching товаров через LLM API (OpenRouter)"""

    def __init__(
        self, api_key: str, model: str = "meta-llama/llama-3.3-70b-instruct:free"
    ):
        self.api_key = api_key
        # Log masked key for debugging
        if api_key:
            masked = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else "***"
            logger.info(f"LLMMatcher init with key: {masked}")
        else:
            logger.warning("LLMMatcher init with EMPTY key")

        self.model = model
        self.products_cache: str | None = None
        self._products_list: list[dict] = []

    def set_products(self, products: list[dict]) -> None:
        """
        Кэшировать каталог для промпта.
        Формируем компактный список SKU - название.
        """
        self._products_list = products
        # Формируем компактный список для промпта (лимит увеличен до 3000, т.к. каталог ~840 товаров)
        lines = []
        for p in products[:3000]:
            sku = p.get("sku", "")
            name = p.get("name", "")
            if sku and name:
                lines.append(f"{sku} - {name}")
        self.products_cache = "\n".join(lines)
        logger.info(f"✅ LLMMatcher: загружено {len(lines)} товаров")

    def match(self, query: str) -> dict | None:
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

        content = ""  # Инициализация до try блока
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/Antigravity",
                    "X-Title": "Antigravity PriceOrders",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": f"{_get_system_prompt()}\n\nКаталог товаров:\n{self.products_cache}",
                        },
                        {
                            "role": "user",
                            "content": f"Найди товар: {query}\n\nВерни ТОЛЬКО JSON без пояснений.",
                        },
                    ],
                    "temperature": 0,
                    "max_tokens": 200,
                    "response_format": {"type": "json_object"},
                },
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(
                    f"LLM API error: {response.status_code} - {response.text[:200]}"
                )
                return None

            data = response.json()
            # Kimi K2 Thinking возвращает ответ в reasoning, другие модели в content
            message = data.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "") or message.get("reasoning", "")

            # Парсим JSON из ответа
            # Убираем возможные markdown блоки
            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            # Извлекаем только JSON объект (игнорируем текст после него)
            # Kimi K2 иногда добавляет пояснения после JSON
            json_match = re.search(r"\{[^{}]*\}", content)
            if json_match:
                content = json_match.group(0)

            result = json.loads(content)

            # Валидация обязательных полей
            if not isinstance(result, dict):
                logger.error(f"LLM вернул не dict: {type(result)}")
                return None

            # Нормализация полей (могут быть None или отсутствовать)
            sku = result.get("sku")
            name = result.get("name")
            confidence = result.get("confidence", 0)

            # Проверяем что confidence - число
            try:
                confidence = float(confidence) if confidence else 0
            except (TypeError, ValueError):
                confidence = 0

            # Ограничиваем confidence диапазоном 0-100
            confidence = max(0, min(100, confidence))

            validated_result = {
                "sku": sku if sku else None,
                "name": name if name else None,
                "confidence": confidence,
            }

            logger.info(
                f"LLM match: '{query}' → {validated_result.get('sku')} ({validated_result.get('confidence')}%)"
            )
            return validated_result

        except json.JSONDecodeError as e:
            logger.error(
                f"LLM JSON parse error: {e}, content: {content[:100] if content else 'empty'}"
            )
            return {"sku": None, "name": None, "confidence": 0}
        except httpx.TimeoutException:
            logger.error("LLM API timeout (30s)")
            return None
        except Exception as e:
            logger.error(f"LLM match error: {e}")
            return None

    def get_product_by_sku(self, sku: str) -> dict | None:
        """Найти товар в кэше по SKU"""
        for p in self._products_list:
            if p.get("sku") == sku:
                return p
        return None

    @property
    def is_ready(self) -> bool:
        """Проверка готовности"""
        return self.products_cache is not None and len(self.products_cache) > 0


# Singleton
_llm_matcher: LLMMatcher | None = None


def get_llm_matcher() -> LLMMatcher | None:
    """Получить глобальный экземпляр LLMMatcher"""
    global _llm_matcher
    if _llm_matcher is None:
        from backend.config import settings

        if settings.openrouter_api_key:
            _llm_matcher = LLMMatcher(
                api_key=settings.openrouter_api_key, model=settings.llm_model
            )
            logger.info(f"✅ LLMMatcher инициализирован (модель: {settings.llm_model})")
        else:
            logger.warning("⚠️ OPENROUTER_API_KEY не установлен - LLM matching отключен")
    return _llm_matcher
