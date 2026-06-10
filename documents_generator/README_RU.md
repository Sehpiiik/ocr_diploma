# Document generator

[English](./README.md) | [Русский](./README_RU.md)

Генератор синтетических документов.
На основе текстового корпуса создаёт:

- Указанное количество изображений страниц (PNG).
- JSON-аннотацию для каждого изображения, содержащую для каждого предложения текст и его
  **прямоугольные bounding boxes по строкам** в координатах пикселей изображения.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Использование

```bash
python main.py --corpus sample_corpus.txt --num 10 --output out/ --seed 0
```

Полезные флаги:

| флаг | значение по умолчанию | описание |
| --- | --- | --- |
| `--corpus / -n` | 10 | корпус текстовых данных для генерации |
| `--num / -n` | 10 | количество документов |
| `--output / -o` | `out` | выходная директория |
| `--width`, `--height` | 1240, 1754 | размер страницы в пикселях |
| `--margin` | 100 | отступ от полей страницы в пикселях |
| `--font-size` | 24 | размер шрифта в пикселях |
| `--line-spacing` | 1.35 | множитель пространства между строками |
| `--font` | auto | путь к `.ttf` шрифту |
| `--min-sentences` / `--max-sentences` | 20 / 60 | min/max предложений на документ |
| `--seed` | None | воспроизводимость результатов |
| `--debug-boxes` | off | отрисовка bounding boxes на сгенерированном изображении |

## Структура выходных данных

```
out/
├── images/
│   ├── doc_00001.png
│   ├── doc_00002.png
│   └── ...
└── annotations/
    ├── doc_00001.json
    ├── doc_00002.json
    └── ...
```

## Формат аннотации

```json
{
  "image": "doc_00001.png",
  "width": 1240,
  "height": 1754,
  "sentences": [
    {
      "id": 0,
      "text": "Optical character recognition has long been a foundational task in document understanding.",
      "lines": [
        {
          "text": "Optical character recognition has long been a foundational",
          "bbox": [100, 100, 920, 33]
        },
        {
          "text": "task in document understanding.",
          "bbox": [100, 133, 470, 33]
        }
      ]
    }
  ]
}
```

`bbox` имеет формат `[x, y, width, height]` в пикселях, начало координат в верхнем левом углу.
Каждая запись в `lines` представляет одну визуальную строку, поэтому
многострочные предложения естественным образом создают несколько bounding boxes вместо одного
общего.

## Использование в качестве библиотеки

```python
from doc_generator import DocumentGenerator, PageConfig, load_sentences

sents = load_sentences("sample_corpus.txt")
gen = DocumentGenerator(PageConfig(font_size=22))
img, ann = gen.render(sents[:30], image_name="example.png", draw_debug_boxes=True)
img.save("example.png")
print(ann.to_dict())
```
