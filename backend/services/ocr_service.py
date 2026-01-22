"""
OCR сервис для распознавания рукописных заказов.
Использует Vision LLM через OpenRouter API.
"""
import base64
import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

DEFAULT_OCR_PROMPT = """Ты OCR для рукописных заказов сантехники.

ДОПУСТИМЫЕ ТОВАРЫ:
труба, отвод, тройник, переход, муфта, заглушка, аэратор, ревизия, крестовина, хомут, патрубок, кран

ИГНОРИРУЙ (НЕ товары):
корпус, эмульсия, задерживающий, непонятный текст

ОПРЕДЕЛИ КАТЕГОРИЮ:
1. ПНД/HDPE/компрессионный (фитинги) → "ПНД комп." (краны, муфты, отводы)
2. ПЭ/HDPE/SDR/PN10/PN12.5/PN16 + вода → "ПЭ" (водопроводные трубы)
3. ППР/армированная/PN20/PN25 → "ППР" (белые трубы)
4. Рыжая/наружная/SN4/SN8/110+ рыж → "наруж. кан."
5. Серая/ПП/канализация → "кан." (внутренняя канализация)

ФОРМАТ НАЗВАНИЙ:
- "Труба 50" (серая) → "Труба кан. 50"
- "Муфта 25" → "Муфта кан. 25"
- "Кран ПНД 20" → "Кран ПНД комп. 20"
- "Муфта компресс. 32" → "Муфта ПНД комп. 32"
- "Труба ПЭ 32 SDR11" → "Труба ПЭ 32"

ФОРМАТ ОТВОДА:
"Отвод 110×45" → "Отвод кан. 110 45°"
Второе число = УГОЛ (45, 67, 87, 90)

ФОРМАТ ТРОЙНИКА:
"Тройник 110×110×45" → "Тройник кан. 110 45°"
Последнее число = УГОЛ

РАЗМЕРЫ ВАЖНЫ:
- Точно переписывай размеры: 20, 25, 32, 40, 50, 110...
- НЕ меняй размер! "Муфта 25" ≠ "Муфта 50"

КОЛИЧЕСТВО:
- "?" = qty: 1
- Нечитаемо = qty: 1
- Больше 1000 и странно = qty: 1

JSON: [{"name": "...", "qty": N}, ...]
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
            logger.warning(f"OCR JSON parse warning: {e}, trying text fallback...")
            # Fallback: пробуем извлечь позиции из текстового формата
            if content:
                result = []
                lines = content.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith(('#', '//', '-')):
                        continue
                    # Паттерн: "название qty" или "название - qty"
                    match = re.match(r'^(.+?)[-:\s]+(\d{1,3})\s*$', line)
                    if match:
                        name = match.group(1).strip()
                        if name and any(c.isalpha() for c in name):
                            result.append({"name": name, "qty": int(match.group(2)), "sku": ""})
                    elif any(c.isalpha() for c in line):
                        result.append({"name": line, "qty": 1, "sku": ""})
                if result:
                    logger.info(f"OCR fallback: извлечено {len(result)} позиций из текста")
                    return result
            logger.error(f"OCR fallback failed, content: {content[:200] if content else 'empty'}")
            return []
        except httpx.TimeoutException:
            logger.error("OCR API timeout (60s)")
            return []
        except Exception as e:
            logger.error(f"OCR error: {e}")
            return []


# Singleton
_ocr_service: OCRService | None = None


def get_ocr_service() -> OCRService | None:
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
