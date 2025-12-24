"""
Скрипт для генерации embeddings для всех товаров в БД.
Использует модель paraphrase-multilingual-MiniLM-L12-v2 (384 измерения).

Запуск: PYTHONPATH=. python3 scripts/generate_embeddings.py
"""
import os
import sys
import logging
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.database import get_supabase_client
from backend.utils.normalizers import normalize_name
from backend.services.matching import extract_product_type

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

MODEL_NAME = 'paraphrase-multilingual-MiniLM-L12-v2'
BATCH_SIZE = 50


def prepare_embedding_text(name: str) -> str:
    """
    Подготовка текста для embedding с усилением типа товара.
    Тип товара добавляется дважды в начало для повышения его веса.
    """
    norm = normalize_name(name)
    product_type = extract_product_type(name)
    if product_type:
        # Добавляем тип товара дважды для усиления
        return f"{product_type} {product_type} {norm}"
    return norm


def main():
    logger.info("🔧 Загрузка модели sentence-transformers...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    logger.info(f"✅ Модель загружена: {MODEL_NAME}")

    db = get_supabase_client()

    # Получаем ВСЕ товары сразу (без проверки каждого)
    response = db.table('products').select('id, name, sku').execute()
    products = response.data or []
    logger.info(f"📦 Всего товаров: {len(products)}")

    # Генерируем embeddings батчами
    updated = 0
    for i in tqdm(range(0, len(products), BATCH_SIZE), desc="Generating"):
        batch = products[i:i + BATCH_SIZE]

        # Подготовка текста с усилением типа товара
        names = [prepare_embedding_text(p.get('name', '') or p.get('sku', '')) for p in batch]

        # Генерируем embeddings
        embeddings = model.encode(
            names,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        # Обновляем в БД батчами
        for j, product in enumerate(batch):
            embedding_list = embeddings[j].tolist()
            try:
                db.table('products').update({
                    'embedding': embedding_list
                }).eq('id', product['id']).execute()
                updated += 1
            except Exception as e:
                logger.error(f"❌ Ошибка {product['id']}: {e}")

    logger.info(f"✅ Готово! Обновлено: {updated}/{len(products)}")


if __name__ == '__main__':
    main()
