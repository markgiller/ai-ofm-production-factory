# Chroma 1 HD — Introduction Plan

**Цель:** Сделать ALL FW (SFW + NSFW) IMG_Generation workflow, который берёт промпт и доводит
фото от генерации до publishable asset внутри одного workflow.

**Что workflow должен уметь:**
1. Генерировать качественное изображение модели по промпту
2. Доводить любые косяки до уровня publishable asset
3. Post Processing Layer — turning generated image into publishable asset

---

## Фаза 1 — Установка Chroma 1 HD в ComfyUI

| Шаг | Задача | Статус |
|-----|--------|--------|
| 1 | Изучить Chroma 1 HD installation / usage process — сформировать базу знаний в repo | DONE |
| 2 | Установить Chroma 1 HD workflow в ComfyUI, сохранить (persistent при перезагрузке), проверить настройки | TODO |
| 3 | Test Batch Generation — собрать опыт как работает модель | TODO |

---

## Фаза 2 — Тренировка Character LoRA

| Шаг | Задача | Статус |
|-----|--------|--------|
| 4 | Изучить как правильно делать training на Chroma — сформировать базу знаний в repo | TODO |
| 5 | Решить параметры тренировки Character LoRA — понять почему выбираем конкретные значения | TODO |
| 6 | Создать Training Script — залить Dataset, натренировать `lora_lily_chroma_v001.safetensors` | TODO |
| 7 | Test Batch Generation — проверить Character LoRA, включая ALL FW | TODO |

---

## Фаза 3 — Развилка по качеству

| Результат шага 7 | Действие |
|------------------|----------|
| **ДА** — генерирует ALL FW на нужном уровне | Переходим к построению Inpainting → Detailer → Post Processing workflow до publishable asset |
| **НЕТ** — качество недостаточное | Собрать dataset больше + ALL FW фото (использовать модели, вручную снять шикарные фотки, много штук) → перетренировать `lora_lily_chroma_v002.safetensors` → тесты → решить что дальше |

---

## Ресурсы

- `workflows/Chroma1_HD_T2I.json` — официальный базовый workflow
- `workflows/Chroma1-HD_Full_with_res2s.json` — продвинутый workflow с res_2s
- `docs/sops/chroma_1_hd_knowledge_base.md` — база знаний по модели
