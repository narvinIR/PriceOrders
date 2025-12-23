"""
OCR сервис для распознавания рукописных заказов.
Использует Vision LLM через OpenRouter API.
"""
import base64
import json
import logging
import re
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_OCR_PROMPT = """Ты OCR система для рукописных заказов КАНАЛИЗАЦИИ и ППР труб.

ТИПЫ ТОВАРОВ (распознавай ВНИМАТЕЛЬНО!):
- Труба канализационная (серая) - размер×длина, толщина в скобках (2.2, 2.7, 3.2, 1.5 мм)
- Труба ППР (полипропилен) - армированная, PN20, PN25
- Отвод (НЕ "отбой"!) - углы 45°, 87°, 90°
- Тройник - размеры через × (110×110×45)
- Муфта ремонтная
- Муфта двухраструбная
- Заглушка ПП (ВАЖНО - часто в начале списка!)
- Крестовина
- Переход эксцентрический (НЕ "короб"!)
- Переход концентрический
- Ревизия
- Хомут
- Аэратор (вентиляционный клапан)

ЕДИНИЦЫ ИЗМЕРЕНИЯ:
- Канализация (серая труба) → ШТУКИ (шт)
- ППР/полипропилен (белая труба) → МЕТРЫ (м, м.)
- Фитинги (отводы, тройники, муфты) → ШТУКИ

ФОРМАТ ЗАПИСИ НА ФОТО:
"Товар размер - количество" или "размер×размер - количество"

ПРИМЕРЫ:
- "Заглушка ПП 110 - 1000шт" → name: "Заглушка ПП 110", qty: 1000
- "Аэратор 50 - ?" → name: "Аэратор 50", qty: 1
- "Труба 110×2000 (3.2) - 30" → name: "Труба кан. 110×2000 3.2мм", qty: 30
- "Труба арм. 32 - 100м" → name: "Труба ППР арм. 32", qty: 100
- "Отвод 50×87 - 1500" → name: "Отвод 50 87°", qty: 1500 (НЕ труба!)

КРИТИЧНО:
- 50×45, 50×87, 50×90 после "Отвод" = это УГЛЫ, не размеры трубы!
- Заглушки обычно в НАЧАЛЕ списка - не пропускай!
- "?" в количестве = qty: 1

Ответ - ТОЛЬКО JSON массив:
[{"name": "полное название", "qty": число}, ...]
"""


class OCRService:
    """Распознавание рукописных заказов через Vision LLM"""

    def __init__(self, api_key: str, model: str = "qwen/qwen3-vl-32b-instruct"):
        self.api_key = api_key
        self.model = model

    def recognize_order(self, image_bytes: bytes) -> list[dict]:
        """
        Распознать рукописный заказ с фото.

        Args:
            image_bytes: Байты изображения (JPEG/PNG)

        Returns:
            Список позиций: [{"name": "...", "qty": N}, ...]
        """
        if not image_bytes:
            logger.warning("OCR: пустое изображение")
            return []

        content = ""
        try:
            # Кодируем в base64
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')

            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": DEFAULT_OCR_PROMPT},
                            {"type": "image_url", "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            }}
                        ]
                    }],
                    "temperature": 0,
                    "max_tokens": 2000,
                },
                timeout=60.0  # Vision модели медленнее
            )

            if response.status_code != 200:
                logger.error(f"OCR API error: {response.status_code} - {response.text[:300]}")
                return []

            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "")

            # Парсим JSON из ответа
            content = content.strip()

            # Убираем markdown блоки
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            # Извлекаем JSON массив
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)

            items = json.loads(content)

            # Валидируем и нормализуем
            result = []
            for item in items:
                if isinstance(item, dict) and item.get("name"):
                    name = str(item.get("name", "")).strip()
                    try:
                        qty = int(item.get("qty", 1))
                    except (ValueError, TypeError):
                        qty = 1

                    if name:
                        result.append({"name": name, "qty": max(1, qty), "sku": ""})

            logger.info(f"OCR: распознано {len(result)} позиций")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"OCR JSON parse error: {e}, content: {content[:200] if content else 'empty'}")
            return []
        except httpx.TimeoutException:
            logger.error("OCR API timeout (60s)")
            return []
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return []


# Singleton
_ocr_service: Optional[OCRService] = None


def get_ocr_service() -> Optional[OCRService]:
    """Получить глобальный экземпляр OCRService"""
    global _ocr_service
    if _ocr_service is None:
        from backend.config import settings
        if settings.openrouter_api_key:
            _ocr_service = OCRService(
                api_key=settings.openrouter_api_key,
                model=settings.ocr_model
            )
            logger.info(f"OCRService инициализирован (модель: {settings.ocr_model})")
        else:
            logger.warning("OPENROUTER_API_KEY не установлен - OCR отключен")
    return _ocr_service
