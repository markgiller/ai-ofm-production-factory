# NSFW Generation — FLUX.1 Dev + LoRA Stack

Standard operating procedure for adult lane content generation on **FLUX.1 Dev 12B + character LoRA**,
based on testing conducted 2026-03-16 during lily_v001 checkpoint evaluation.

---

## Key Finding: FLUX.1 Dev Has Soft Alignment, Not Hard Filter

FLUX.1 Dev self-hosted has **no content filter** — but it was trained with alignment that makes it
resist explicit poses. It will generate:

| Content | Result |
|---------|--------|
| Topless, bare chest | ✅ Works without NSFW LoRA |
| Full nudity, bare back/ass | ✅ Works without NSFW LoRA |
| Explicit poses (spread legs, doggy) | ❌ Fails without NSFW LoRA — model "softens" composition |
| Detailed genital anatomy | ❌ Requires uncensored base model |

The model doesn't throw an error — it just quietly generates a tamer version of the prompt.

---

## Two-Lane Architecture

### Lane 1: SFW / Implied Nude (Instagram, Threads)
- Character LoRA only, strength 1.0
- No NSFW LoRA needed
- Identity lock: FaceSim 0.77 (excellent)
- Results: portrait, fashion, boudoir, artistic nude

### Lane 2: Explicit Adult (Fanvue)
- Character LoRA (strength 1.0) + NSFW LoRA (strength 0.3-0.5) stacked
- Identity: slightly degraded (~0.70-0.74 estimated) due to LoRA interference
- Results: explicit poses work, anatomy realistic but genitalia "smoothed"

---

## NSFW LoRA Stack — ComfyUI Implementation

Workflow uses two chained `LoraLoaderModelOnly` nodes:

```
UNETLoader(1) → LoraLoaderModelOnly[lily, 1.0](14) → LoraLoaderModelOnly[nsfw, 0.45](15) → BasicGuider(6)
                                                                                            → BasicScheduler(8)
```

Node 6 (BasicGuider) and Node 8 (BasicScheduler) must reference Node 15 output, not Node 14.

### Tested LoRA: NSFW FLUX LoRA V1 (CivitAI - Ai_Art_Vision)
- **Source:** civitai.com/models/655753
- **File:** `nsfw_flux_lora_v1.safetensors` (656MB)
- **Base:** FLUX.1 Dev
- **Training:** 18,000 steps, 600 images, A6000
- **Trigger word:** `AiArtV` (include at start of prompt)
- **Reviews:** 1,805 overwhelmingly positive — confirmed stacking with character LoRAs on fp8
- **Install path:** `/app/comfyui/models/loras/nsfw_flux_lora_v1.safetensors`

### Strength Tuning Results

| lily strength | NSFW strength | Identity | Pose explicitness | Notes |
|---------------|---------------|----------|-------------------|-------|
| 1.0 | 0.5 | ~70% | High | Pose works great, face drifts |
| 1.0 | 0.3 | ~80% | Medium | Face closer, poses softer |
| 1.0 | 0.45 | ~75% | High | Best compromise |

**Rule:** suммарный strength обеих LoRA не превышать ~1.5 во избежание артефактов.

---

## Prompt Structure for Adult Lane

```
AiArtV [explicit action/pose], lily, young woman with hazel eyes and freckles on nose and cheeks,
[body description], [scene/setting], [lighting], [camera/lens], photorealistic
```

- `AiArtV` trigger word **обязательно** в начале
- Упоминать freckles явно — иначе NSFW LoRA "перебивает" характерные черты
- `hazel eyes` держит цвет глаз
- Детали освещения и камеры (35mm f/1.4) улучшают фотореализм

---

## Known Limitations of Current Stack

### 1. Genital anatomy unrealistic
FLUX.1 Dev + NSFW LoRA генерирует "сглаженную" анатомию — не детализированную.
Причина: модель не видела explicit контент при тренировке.

**Решение (v002):** заменить base model на uncensored checkpoint:
- **Fluxed Up v7.1** (CivitAI 847101) — fp8 вариант, drop-in замена, 500+ отзывов
- **Vision Realistic** (CivitAI — Ai_Art_Vision) — тот же автор что NSFW LoRA

### 2. Identity drift at explicit poses
При higher NSFW strength лицо отклоняется от lily референса.
Причина: NSFW LoRA натренирована на 600 изображениях с конкретным лицом — интерференция.

**Решение (v002):** тренировать character LoRA на uncensored base model. Тогда одна LoRA
держит identity И не конфликтует с explicit контентом.

### 3. Face-heavy dataset = weak body shots
Датасет lily_v001 (36 фото) в основном портреты/face. LoRA плохо держит identity
при full body / explicit позах где лицо маленькое.

**Решение (v002):** добавить в датасет full body shots разных поз (не upscale, а разнообразие).

---

## Workflow File

Eval workflow с поддержкой LoRA стека:
`workflows/eval/IMG_eval_lora_v001.json`

Для production нужен отдельный `IMG_hero_nsfw_v001.json` с двумя LoRA нодами.

---

## Checkpoint Evaluation Results (lily_v001, 2026-03-16)

ArcFace scoring: 9 checkpoints × 3 prompts × 3 seeds = 80 images

| Rank | Step | Mean FaceSim | Max | Notes |
|------|------|-------------|-----|-------|
| #1 | **1750** | **0.7727** | 0.8037 | **WINNER — deployed to ComfyUI** |
| #2 | 2000 | 0.7712 | 0.8156 | почти идентичен |
| #3 | 2250 | 0.7668 | 0.8043 | лёгкий спад |
| #4 | 2500 | 0.7653 | 0.8088 | финальный — чуть хуже |
| #9 | 0 | 0.5160 | 0.5883 | baseline без LoRA |

Sweet spot: **step 1750** — после него лёгкий overfitting, identity начинает падать.
Baseline jump: 0.516 → 0.773 = +49% — LoRA работает.

### Deploy command
```bash
cp /workspace/lora_training/lily_v001/output/lora_lily_v001/lora_lily_v001_000001750.safetensors \
   /app/comfyui/models/loras/lora_lily_v001.safetensors
```

---

## Next Steps (обновлено 2026-03-16)

### Immediate (текущий стек)
1. **IMG_hero_nsfw_v001.json** — построить inpainting workflow в ComfyUI:
   - Шаг 1: txt2img с lily LoRA 1.0 (без NSFW LoRA)
   - Шаг 2: inpainting маска на анатомическую зону, lily 0.5 + NSFW 1.0, denoise 0.90-0.95
2. **Шипиться** — генерировать SFW + implied nude + boudoir, публиковать, строить аудиторию

### v002 Dataset & Training
3. **v002 dataset** — расширить до 100+ фото: full body shots, разные позы/ракурсы, разные дистанции от камеры (не upscale существующих)
4. **v002 training** — rank 16, resolution [1024, 1536], те же параметры

### Исследовать позже
5. **Chroma** — единственная по-настоящему uncensored модель по данным комьюнити. Проверить совместимость с FLUX-trained LoRA когда будет время
6. **Z-Image base model** — ждать релиза + NSFW community finetune (минимум 6-12 месяцев)

---

## Model Landscape Research (2026-03-16)

Источник: Reddit r/StableDiffusion + CivitAI. Критический анализ альтернатив нашему стеку.

### Z-Image Turbo — МЁРТВЫЙ ПУТЬ для нас

Z-Image Turbo (ZiT) — новая архитектура, не FLUX. Хорошая анатомия женщин, но:

**Критичная проблема — сам автор модели подтвердил:**
> *"Training and merging models with ZiT can break when using multiple LoRAs"*

Комьюнити подтверждает: character LoRA на Z-Image работает плохо или не работает совсем.
Наша lily LoRA тренирована на FLUX.1 Dev — на Z-Image она несовместима по архитектуре.

**Вывод: Z-Image не рассматривать.** Даже Z-Image Turbo NSFW (CivitAI 2237711) — мимо.

### Chroma — полностью uncensored, требует исследования

Несколько независимых источников в треде называют Chroma единственной **по-настоящему uncensored** моделью:
> *"If you want fully uncensored, you have to use Chroma"*

Один пользователь строит гибридный workflow:
```
Chroma (генерация 512px, без ограничений) → Z-Image img2img (upscale до 2048px)
```

**Что неизвестно:** совместима ли Chroma с нашей FLUX-trained lily LoRA.
Требует отдельного исследования перед v002.

### Fluxed Up — детальный анализ (CivitAI 847101, автор 6tZ)

FLUX.1 Dev base + NSFW LoRA вмёрженная в checkpoint. Та же архитектура что наш base model.
Наша lily LoRA совместима по архитектуре. Но есть нюансы.

**Технические параметры:**
- Формат: safetensors, **VAE и CLIP не вшиты** — нужно грузить отдельно
- Наш ComfyUI workflow уже делает это правильно (DualCLIPLoader + VAELoader отдельно) ✅
- Рекомендованный sampler: `dpmpp_2m` (DPM++ 2M) + scheduler `beta`
- Серый output = забыл подключить VAE (не баг модели)
- Версии: FP16 (лучшее качество), Q8/Q4 (меньше VRAM). fp8 официально не выпущен.

**Как создан:** LoRA тренировка → merge в checkpoint. Автор сам подтвердил что LoRAs работают поверх.

**Плюсы:**
- NSFW контент без стека LoRA — одна lily LoRA, никакой интерференции
- Совместим с нашим ComfyUI workflow
- Фотореализм кожи и тела высокий

**Критические минусы (автор сам признаёт):**
> *"It's certainly overfit and has extremely strong biases, to a point where prompt adherence is hurt"*

Конкретно:
- **Composition randomness** — если просишь определённую позу, можешь получить другую. Датасет без нормального каптионинга.
- Nipple/genital anatomy — всё ещё "flux static" look, автор знает и работает над этим
- Сильный bias к nude изображениям — SFW контент тоже может выйти с nudity

**Вывод по Fluxed Up для нас:**
Совместимость с lily LoRA — да. Но composition randomness — серьёзная проблема для production pipeline где нам нужны конкретные позы. Требует тестирования. Не гарантированная замена.

**Гибридный workflow (из комментов):**
Несколько пользователей используют схему:
```
Pony/SDXL (генерация с правильной композицией) → img2img denoise 0.4 в Fluxed Up (текстура/кожа)
```
Это решает проблему рандомной композиции но добавляет сложность.

### Общий инсайт из комьюнити (подтверждает нашу проблему)

> *"Training a person is a LoRA, and if I stack it with additional LoRAs, the person LoRA may become distorted"*

Это не наша ошибка — это фундаментальное ограничение стека LoRA, известное всему комьюнити.
Решение одно: uncensored base model + одна character LoRA без стека.

### Community Training Insights (Reddit r/StableDiffusion, март 2026)

Источник: "The Z-Image Turbo Lora-Training Townhall" (212 upvotes, 107 комментов) + CivitAI.
Хотя данные по Z-Image Turbo, многие принципы универсальны для LoRA тренировки.

**Двойная LoRA для одного персонажа (The_Monitorr, 33 upvotes):**
> *"Train two loras for a single person — one on AI generated images (cherry picked),
> the other on real images. Use together and the results are amazing."*

Адаптация для нас: тренировать вторую LoRA на лучших генерациях v001, использовать
вместе с основной. Первая = identity, вторая = стиль/качество.

**Синтетические данные нужно обрабатывать перед ретрейном:**
> YMIR_THE_FROSTY: *"Resize with other diffusion model, add gentle noise.
> This breaks unique model pattern inside the picture."*

Если v002 из генераций v001 — сломать AI-паттерн: resize через другую модель,
добавить шум, уменьшить обратно. Иначе модель учит свои же артефакты.

**Rank 8-16 подтверждён как оптимум:**
> *"8 and 16 works best and gives exceptional quality with realism.
> 64 took a lot longer and lacked skin texture."*

Наш rank 16 = правильный выбор. Confirmed across Z-Image and FLUX.

**Больше данных = стабильнее identity:**
> *"100 images = 90% likeness. 1000 images = every single image with same likeness
> + better prompt adherence."*

Наш датасет 36 фото — работает, но минимум. Для v002: расширить до 100+
(разнообразие поз/ракурсов, не upscale).

**LoRA стек ломается — универсальная проблема:**
> Mystic XXX (57K downloads, ZIT NSFW LoRA): *"Having big trouble using it with
> a character lora. Seems like both loras are on same layers. Combining them is doomed."*

Подтверждает наш опыт. Решение: uncensored base model + одна character LoRA.

**Block weight analysis — инструмент для стека:**
> *"Do a post training block analysis and save your lora so it won't destroy base quality."*
> Tool: `comfyUI-Realtime-Lora` (github.com/shootthesound/comfyUI-Realtime-Lora)

Анализ какие слои LoRA отвечают за что + отключение конфликтующих слоев.
Может помочь при стеке character + NSFW LoRA.

**Больше steps = лучше при стеке:**
> *"Higher steps retains knowledge better at low weights and performs much better
> when used in combination with other loras."*

Для стека с NSFW LoRA: возможно лучше checkpoint 2000-2500 вместо 1750.

**Resolution 1536 > 1024 для тренировки:**
> *"Training at 1536 resolution does seem to produce noticeably better results than 1024."*

Мы тренировали на [768, 1024]. Для v002 попробовать [1024, 1536].

**Каптионы: спорный вопрос, но большинство за:**
> *"Without captions works fine, but flexibility and prompt adherence is way better
> when you caption."* (Nyao)
> *"I retrained without captions — worsened prompt following and likeness."* (tom-dixon)

Наш подход (простые captions с trigger word) — validated.

### Сравнительная таблица моделей (обновлено 2026-03-16)

| Модель | Архитектура | Фотореализм | Character LoRA | Explicit анатомия | Для нас |
|--------|-------------|-------------|----------------|-------------------|---------|
| FLUX.1 Dev (текущий) | FLUX | ✅ лучший | ✅ отлично (0.77 FaceSim) | ❌ "flux static" | база — SFW + inpainting NSFW |
| FLUX.1 Dev + NSFW LoRA стек | FLUX | ✅ | ✅ с drift (~0.75) | ⚠️ позы работают, гениталии сглажены | текущий стек для explicit поз |
| FLUX + NSFW LoRA inpainting | FLUX | ✅ | ✅ без drift | ✅ зона перегенерируется | **следующий шаг — строить workflow** |
| Fluxed Up v7.1 FP16 | FLUX uncensored | ✅ | ✅ совместима | ❌ всё равно "flux static" | не тестировать — не решает анатомию |
| Z-Image Turbo | Z-Image | ✅ хороший | ✅ лица отлично | ❌ explicit не работает даже с 100 фото | мёртвый путь для NSFW |
| Pony V6 XL | SDXL | ⚠️ ~90%, не фото | ✅ mature eco | ✅ лучший для аниме/stylized | не наш таргет — не фотореализм |
| Pony V7 (AuraFlow) | AuraFlow | ❌ хуже V6 | ❌ незрелый | ❌ официально отфильтрован | мёртвый путь |
| SDXL (Juggernaut XL) | SDXL | ⚠️ хороший | ✅ | ✅ работает | запасной вариант |
| Chroma | Chroma | ❓ | ❓ совместимость неизвестна | ✅ полностью | исследовать в будущем |

---

## Gap Analysis: Что отделяет нас от успешных создателей (2026-03-16)

Изучили комьюнити, рынок и технический стек. Вот реальные gaps:

### Gap 1: Мы стакаем LoRA вместо одного решения
Успешные создатели не кладут NSFW LoRA поверх character LoRA — они используют либо uncensored base (одна LoRA), либо inpainting для проблемных зон. LoRA стек = identity drift + конфликт слоёв. Это подтверждено комьюнити повсеместно.

### Gap 2: Датасет — 36 портретов
100 изображений = 90% likeness. 1000 = каждое изображение с одинаковым сходством.
Наши 36 фото — работают, но минимум. v002: 100+ с разнообразием поз и ракурсов.

### Gap 3: Один проход txt2img
Профессиональные создатели: generate → inpaint проблемные зоны → upscale.
Мы делаем один проход и получаем что получаем.

### Gap 4: Нет inpainting pipeline для NSFW
Даже если анатомия "smoothed" — inpainting решает. Маска на зону, перегенерация с NSFW LoRA 1.0. Лицо за пределами маски = лицо не меняется.

### Gap 5: Ничего не зашипили
Те ребята прогнали тысячи генераций, нашли формулы эмпирически. Мы в фазе research.

---

## Market Intelligence: Fanvue Earnings (2026)

Источник: Sacra, Fanvue публичные данные, Quasa.io.

- **Platform ARR:** $100M в 2025 (150% YoY рост)
- **Документированные кейсы:** $30k–60k/месяц в первые 30-60 дней
- **Top performers:** $20k+/месяц sustained
- **Whale spending:** одиночные пользователи тратят $13k за 30 дней
- **AI как % дохода платформы:** ~15%

**Что реально продаётся:** подписка + PPV + custom requests + чат. Explicit PPV = ~80% дохода.
Платят за персонажа, fantasy, relationship — не только за анатомию.

**Успешный контент-план:** 60-100 изображений/неделю, 3-5 themed outfits, 1-2 wall posts/день, 1 PPV blast/неделю, teasers на Twitter/Reddit 3-5x/неделю.

---

## Z-Image Turbo: Окончательный вердикт по explicit анатомии

Дополнение к разделу выше — прямые тесты из комьюнити (Reddit, 2 месяца назад):

**Что РАБОТАЕТ на Z-Image Turbo LoRA:**
- Лица: высокое сходство от ~2750 шагов при 40-50 изображениях
- Грудь: работает при наличии примеров в датасете
- Общая likeness: лучше чем SDXL при интерполяции между дистанциями от камеры

**Что НЕ РАБОТАЕТ даже с 100 изображениями в датасете:**
- Vagina/vulva: *"Terrible with front lady parts. No amount of examples (within 100 image dataset) gave good likeness"*
- Penis: подтверждено комьюнити — не работает
- Tattoos: рандомизируются по телу, не поддаются обучению

**Почему это не цензура — это gap обучения:**
> *"It just has almost no experience of NSFW anatomy. It's not been trained on vulva or anus or similar."*

Character LoRA не может научить модель тому, чего в ней нет как базовые знания.
Решение — масштабный NSFW retrain базовой модели. Требует огромных ресурсов, доступных единицам.

> *"It really makes you appreciate how great SDXL is, even today."*

Ещё одна проблема Z-Image Turbo: модель **fixates on faces**. Если в body-only датасете случайно оказалось одно фото с лицом — каждая генерация воспроизводит layout этой фотографии.

**Вывод: Z-Image Turbo — мёртвый путь для full explicit.** Ждать base model + NSFW community finetune. Минимум 6-12 месяцев.

---

## Fluxed Up 7.1 FP16: Окончательный вердикт

**Технический вопрос с VRAM решён:**
FP16 файл ~24GB, но ComfyUI кастует на лету:
```
UNETLoader → weight_dtype: "fp8_e4m3fn"
```
Загружает fp16, кастует в fp8 (~12GB в VRAM). Технически запустить можно.

**Но community feedback от реальных пользователей (CivitAI, февраль 2026):**
- *"Still lacks natural nipples and ****s, it's still cursed by the Flux static look"* (Learning2025)
- *"Random results and little control over composition... no good image captioning"* (mad_rooky — подробный review)
- *"Complete garbage"* (True_Warrior)
- *"Loves it for realistic faces"* (Doctor_Nothing)

**Composition randomness** — серьёзная проблема: просишь стоять → получаешь лежать.
Датасет без нормального каптионинга = модель не понимает запрошенную позу.

**Вывод: не тестировать.** Fluxed Up не решает анатомию ("flux static" confirmed) и добавляет проблему composition randomness. Нет evidence что это лучше нашего текущего стека.

---

## Pony V6 XL: Анализ для нашего юзкейса

**Статус:** Лучшая модель для NSFW — но для аниме/stylized, не фотореализм.

Community consensus (Reddit, 1+ год данных):
- *"Pony is best for anything NSFW. Issue is photorealism — 90% there."*
- *"Body part proportions bizarre — wide legs too short, oddly-sized heads"*
- *"Pony realistic always has unrealistic feeling, super big eyes, plastic skin"*
- *"SDXL for 'spicy' is ass"* — Pony лучше SDXL для explicit, но всё равно не фото

**Для нас:** не подходит. Требование — indistinguishable from real photos. Pony = stylized.

---

## Pony V7 (AuraFlow): МЁРТВЫЙ ПУТЬ

Вышел октябрь 2025, CivitAI model ID: 1901521.

**Это не SDXL — это AuraFlow (7B параметров, другая архитектура).**

**Explicit контент официально отфильтрован** — дословно из документации:
> *"Any inappropriate explicit content has been filtered out."*
> *"Dataset balanced to be slightly less NSFW compared to previous versions."*

Дополнительные проблемы:
- 24GB VRAM только на генерацию — весь RTX 4090, LoRA не поместится
- LoRA экосистема нулевая (другая архитектура)
- Нет ControlNet
- Хуже V6 из коробки по качеству
- Лица деградируют в зависимости от стиля
- Промптинг стал сложнее (новая система тегов без документации)

Community: разочарование. V7 с AuraFlow = предательство core-аудитории (NSFW).

**История:** "V7 выйдет через пару недель" ждали месяцами → вышел с фильтрацией explicit.

**Вывод: полностью исключить из рассмотрения.**

---

## Реальное решение: FLUX + Inpainting Workflow

Ключевой инсайт от реального создателя NSFW контента (Reddit):

> *"I've been mostly creating 'spicy' images, and now I use FLUX almost exclusively. My workflow relies heavily on inpainting and FLUX is so much better than SDXL in that aspect. Although inpainting itself is fine with SDXL, it tends to lose overall image consistency as you repeat the process."*

> *"There's no reason why you can't go back and forth between FLUX and SDXL/Pony while working on a single image."*

**Вывод: проблема не в модели. Проблема в workflow.**

FLUX.1 Dev — правильный выбор для фотореализма. Gap не в модели, а в отсутствии multi-stage workflow с inpainting.

### Inpainting для NSFW анатомии — техническая схема

```
Шаг 1: txt2img (основная генерация)
  FLUX.1 Dev + lily LoRA 1.0 (без NSFW LoRA)
  Результат: лицо идеальное, тело реалистичное, анатомия "smoothed"

Шаг 2: inpainting (только проблемная зона)
  Маска = ТОЛЬКО гениталии / грудь (конкретная зона)
  Модель: FLUX.1 Dev + lily LoRA 0.5 + NSFW LoRA 1.0
  Denoise: 0.90-0.95 (полная перегенерация зоны)
  Результат: зона перегенерирована правильно
  Лицо: не в маске → не меняется физически
```

**Почему это работает:**
- Маска изолирует зону — всё за пределами маски нетронуто
- FLUX видит контекст (поза, тон кожи, освещение) и генерирует анатомию органично
- lily LoRA в inpainting можно снизить — лицо уже нарисовано
- NSFW LoRA на 1.0 только в inpainting зоне — нет interference с лицом
- FLUX inpainting держит consistency изображения лучше SDXL

**ComfyUI nodes для inpainting:**
- `VAEEncodeForInpaint`
- Маска: ручная (рисуем в ComfyUI) или SAM (автосегментация)
- Два `LoraLoaderModelOnly`: lily 0.5 + nsfw 1.0

**Это следующий workflow для построения: `IMG_hero_nsfw_v001.json`**
