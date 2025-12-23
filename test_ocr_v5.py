#!/usr/bin/env python3
"""Тест OCR v5"""
import os
import sys
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv()

from backend.services.ocr_service import OCRService

ocr = OCRService(api_key=os.getenv('OPENROUTER_API_KEY'))

with open('photo_5352667885760875323_y.jpg', 'rb') as f:
    img = f.read()

items = ocr.recognize_order(img)
print(f'Распознано: {len(items)} позиций\n')
for i, item in enumerate(items, 1):
    name = item.get('name', '')
    qty = item.get('qty', 1)
    print(f'{i}. {name} — {qty}')
