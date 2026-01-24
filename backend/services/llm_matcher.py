"""
LLM-based matching через Google Gemini (via Cloudflare Relay).
Заменяет локальный embedding matcher (экономит ~500 МБ RAM).
Полностью бесплатно, ключ не требуется (вшит в релей).
"""

import json
import logging
import time
import asyncio
from backend.services.llm_router import llm_router

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

Ответь ТОЛЬКО JSON объектом со следующими полями:
{
  "sku": "артикул (string или null)",
  "name": "название (string или null)",
  "confidence": число от 0 до 100
}

Если товар НЕ найден, верни:
{"sku": null, "name": null, "confidence": 0}
"""


class LLMMatcher:
    """Matching товаров через Google Gemini (via Cloudflare Relay)"""

    def __init__(self):
        self.products_cache: str | None = None
        self._products_list: list[dict] = []
        self.router = llm_router
        logger.info("✅ LLMMatcher configured (via Cloud Router: Gemini/Groq)")

    def set_products(self, products: list[dict]) -> None:
        """
        Кэшировать каталог для промпта.
        """
        self._products_list = products
        # Формируем компактный список для промпта (лимит увеличен до 3000)
        lines = []
        for p in products[:3000]:
            sku = p.get("sku", "")
            name = p.get("name", "")
            if sku and name:
                lines.append(f"{sku} - {name}")
        self.products_cache = "\n".join(lines)
        logger.info(f"✅ LLMMatcher: загружено {len(lines)} товаров")

    def match(self, query: str, candidates: list[dict] = None) -> dict | None:
        """
        Найти товар через LLM.
        :param query: Запрос пользователя
        :param candidates: Опциональный список кандидатов (RAG) для промпта
        """
        if not candidates and not self.products_cache:
            logger.warning("LLMMatcher: каталог не загружен и кандидаты не переданы")
            return None

        if not query or len(query.strip()) < 2:
            return None

        # Prepare Context
        context_str = ""
        if candidates:
            # Use provided RAG candidates
            lines = []
            for p in candidates:
                sku = p.get("sku", "")
                name = p.get("name", "")
                if sku and name:
                    lines.append(f"{sku} - {name}")
            context_str = "\n".join(lines)
        else:
            # Fallback to full cache (legacy)
            context_str = self.products_cache

        # Формируем полный промпт
        full_user_prompt = (
            f"КАТАЛОГ ТОВАРОВ:\n{context_str}\n\n"
            f"ЗАПРОС КЛИЕНТА: {query}\n"
            f"Найди лучший товар из каталога."
        )

        try:
            start_time = time.time()

            # BRIDGE: Call async router from sync method
            # Since this is likely running in a thread pool (FastAPI sync route), asyncio.run works.
            # If running in a loop, we might need a different approach, but simplistic for now.
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we are already in a loop, we can't use run_until_complete easily without nesting issues.
                    # However, MatchingService is usually sync.
                    text_content = asyncio.run_coroutine_threadsafe(
                        self.router.completion(
                            full_user_prompt, system_prompt=DEFAULT_SYSTEM_PROMPT
                        ),
                        loop,
                    ).result(timeout=15)
                else:

                    async def run_with_timeout():
                        return await asyncio.wait_for(
                            self.router.completion(
                                full_user_prompt, system_prompt=DEFAULT_SYSTEM_PROMPT
                            ),
                            timeout=15,
                        )

                    text_content = asyncio.run(run_with_timeout())
            except RuntimeError:
                # No loop running
                async def run_with_timeout():
                    return await asyncio.wait_for(
                        self.router.completion(
                            full_user_prompt, system_prompt=DEFAULT_SYSTEM_PROMPT
                        ),
                        timeout=15,
                    )

                text_content = asyncio.run(run_with_timeout())
            except Exception as e:
                logger.warning(f"LLM Execution Timeout or Error: {e}")
                text_content = None

            duration = time.time() - start_time

            if not text_content:
                logger.warning("LLM Router returned no content")
                return None

            # Helper to clean JSON
            def clean_json(text):
                text = text.replace("```json", "").replace("```", "").strip()
                # Attempt to find JSON structure if there is extra text
                start = text.find("{")
                end = text.rfind("}")
                if start != -1 and end != -1:
                    return text[start : end + 1]
                return text

            # Parse JSON
            try:
                result = json.loads(text_content)
            except json.JSONDecodeError:
                # Cleanup markdown
                clean_text = clean_json(text_content)
                try:
                    result = json.loads(clean_text)
                except json.JSONDecodeError:
                    logger.error(
                        f"LLM JSON Parse Error. Content: {text_content[:100]}..."
                    )
                    return None

            # Валидация
            sku = result.get("sku")
            name = result.get("name")
            confidence = result.get("confidence", 0)

            try:
                confidence = float(confidence) if confidence else 0
            except (TypeError, ValueError):
                confidence = 0

            confidence = max(0, min(100, confidence))

            validated = {
                "sku": sku if sku else None,
                "name": name if name else None,
                "confidence": confidence,
            }

            logger.info(
                f"LLM match ({duration:.2f}s): '{query}' → {validated.get('sku')} ({validated.get('confidence')}%)"
            )
            return validated

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
        _llm_matcher = LLMMatcher()
    return _llm_matcher
