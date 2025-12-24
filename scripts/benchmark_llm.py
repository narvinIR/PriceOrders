"""
Бенчмарк LLM моделей для matching товаров.
Тестируем: скорость, качество JSON, точность SKU.

Запуск: PYTHONPATH=. python3 scripts/benchmark_llm.py
"""
import os
import sys
import json
import time
import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.database import get_supabase_client

# Модели для теста (OpenRouter) - дешёвые и быстрые
MODELS = [
    "anthropic/claude-3-5-haiku",
    "openai/gpt-4o-mini",
    "mistralai/mistral-small-3.1-24b-instruct",
    "deepseek/deepseek-chat-v3-0324",
    "moonshotai/kimi-k2",  # Kimi K2 (без thinking)
    "meta-llama/llama-3.3-70b-instruct",
    "qwen/qwen-2.5-72b-instruct",
]

# Тестовые запросы с ожидаемыми SKU (проверены по базе!)
TEST_CASES = [
    ("Труба канализационная 110-2000", "202051110R"),
    ("Отвод 110/45 серый", "202107110R"),
    ("Муфта компрессионная 32", "704051032T"),
    ("Тройник 45 серый 110-110", "202148110R"),
    ("Кран шаровый компресс 20-20", "704014202T"),
    ("Заглушка компрессионная 32", "704009032T"),
    ("Муфта переходник ППР 32-25", "101099320K"),
    ("Труба ППР PN20 25", "101020025R"),
]

SYSTEM_PROMPT = """Ты помощник по сопоставлению товаров Jakko.
Найди ЛУЧШЕЕ совпадение из каталога.

КРИТИЧНЫЕ ПРАВИЛА:
1. РАЗМЕРЫ должны совпадать!
2. Тип товара должен совпадать (труба≠муфта)

Ответь ТОЛЬКО JSON:
{"sku": "артикул", "name": "название", "confidence": 0-100}

Если НЕ найден:
{"sku": null, "name": null, "confidence": 0}
"""


def load_catalog():
    """Загрузить каталог товаров"""
    db = get_supabase_client()
    result = db.table('products').select('sku, name').limit(800).execute()
    lines = [f"{p['sku']} - {p['name']}" for p in result.data if p.get('sku')]
    return "\n".join(lines)


def test_model(model: str, catalog: str, api_key: str) -> dict:
    """Тестировать одну модель"""
    results = {
        "model": model,
        "total_time": 0,
        "correct": 0,
        "json_errors": 0,
        "details": []
    }

    for query, expected_sku in TEST_CASES:
        start = time.time()
        try:
            response = httpx.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\nКаталог:\n{catalog}"},
                        {"role": "user", "content": f"Найди: {query}\n\nТолько JSON."}
                    ],
                    "temperature": 0,
                    "max_tokens": 150,
                },
                timeout=30.0
            )
            elapsed = time.time() - start
            results["total_time"] += elapsed

            if response.status_code != 200:
                results["details"].append({
                    "query": query,
                    "error": f"HTTP {response.status_code}",
                    "time": elapsed
                })
                continue

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse JSON
            try:
                # Clean markdown
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()

                import re
                json_match = re.search(r'\{[^{}]*\}', content)
                if json_match:
                    content = json_match.group(0)

                result = json.loads(content)
                got_sku = result.get("sku")

                correct = (got_sku == expected_sku) or (got_sku is None and expected_sku is None)
                if correct:
                    results["correct"] += 1

                results["details"].append({
                    "query": query,
                    "expected": expected_sku,
                    "got": got_sku,
                    "correct": correct,
                    "time": elapsed,
                    "confidence": result.get("confidence")
                })

            except json.JSONDecodeError:
                results["json_errors"] += 1
                results["details"].append({
                    "query": query,
                    "error": "JSON parse error",
                    "content": content[:100],
                    "time": elapsed
                })

        except Exception as e:
            results["details"].append({
                "query": query,
                "error": str(e),
                "time": time.time() - start
            })

    return results


def main():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY not set")
        return

    print("📦 Загрузка каталога...")
    catalog = load_catalog()
    print(f"✅ Загружено {len(catalog.split(chr(10)))} товаров\n")

    all_results = []

    for model in MODELS:
        print(f"🔄 Тестирую: {model}")
        result = test_model(model, catalog, api_key)
        all_results.append(result)

        accuracy = result["correct"] / len(TEST_CASES) * 100
        avg_time = result["total_time"] / len(TEST_CASES)

        print(f"   ✅ Точность: {accuracy:.0f}% ({result['correct']}/{len(TEST_CASES)})")
        print(f"   ⏱️  Среднее время: {avg_time:.2f}s")
        print(f"   ❌ JSON ошибок: {result['json_errors']}")
        print()

    # Summary
    print("\n" + "="*60)
    print("📊 ИТОГИ БЕНЧМАРКА")
    print("="*60)
    print(f"{'Модель':<40} {'Точность':<10} {'Время':<10} {'JSON err'}")
    print("-"*60)

    for r in sorted(all_results, key=lambda x: (-x["correct"], x["total_time"])):
        acc = r["correct"] / len(TEST_CASES) * 100
        avg = r["total_time"] / len(TEST_CASES)
        print(f"{r['model']:<40} {acc:>6.0f}%    {avg:>6.2f}s    {r['json_errors']}")

    # Best model
    best = max(all_results, key=lambda x: (x["correct"], -x["total_time"]))
    print(f"\n🏆 Лучшая модель: {best['model']}")

    # Детали ответов
    print("\n\n📋 ДЕТАЛИ ОТВЕТОВ (лучшая модель):")
    print("-"*60)
    for d in best["details"]:
        status = "✅" if d.get("correct") else "❌"
        print(f"{status} {d['query']}")
        print(f"   Ожидали: {d.get('expected')}")
        print(f"   Получили: {d.get('got')} (conf: {d.get('confidence')})")
        if d.get("error"):
            print(f"   ⚠️ Ошибка: {d.get('error')}")
        print()


if __name__ == "__main__":
    main()
