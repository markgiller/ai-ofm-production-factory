AI OFM PRODUCTION PIPELINE v
Полный технический план production stack для стабильной генерации image/video assets,
управляемой оркестрации и масштабируемой фабрики контента
Назначение
Собрать один рабочий документ, который задаёт архитектуру,
storage, workflow library, SOP оператора, review gates и rollout-
план.
Техническое ядро
Runpod/Vast 4090 → Dockerized ComfyUI → FLUX.2 [klein] 4B → LoRA
+ refs + ControlNet + repair + upscale → Wan 2.2 → interpolation + video
upscale → orchestrator → S3 + Postgres + manifests.
North star
Не просто генерировать картинки, а воспроизводимо выпускать
winners: стабильный персонаж, дорогой visual finish, контролируемое
short-form video и контент, который воспринимается как живой личный
контакт.
Ключевая идея
Одна фабрика, две output-линии: SFW и lawful adult живут на одном техническом ядре, но с разными
policy packs, review gates и distribution rules.
Главный актив — не модель сама по себе, а character lock + house aesthetic + ruthless curation + полная
воспроизводимость результата.
1. Что именно строим
Это не «рисовалка» и не набор случайных нод. Это production system, в которой любой asset
проходит через формализованный путь: brief → explore → select → hero → repair → video → finish →
review → publish.
Система обязана решать четыре задачи одновременно:
давать стабильного персонажа из поста в пост;
позволять быстро получать дорогой photorealistic still и короткий controllable clip;
сохранять все inputs, версии, seed, workflow и lineage без ручного бардака;
быть готовой к постепенной автоматизации без переписывания ядра.
Операционный принцип
Manual-first, system-first: сначала собирается ручной, но дисциплинированный pipeline.
Automation приходит сверху как routing/scoring/job-running layer, а не вместо нормальной production
discipline.
Сырым генеративным output не публикуем: finishing — обязательная часть фабрики.
2. Цели результата
Технический pipeline должен выпускать assets, которые визуально ощущаются как «дорогой
персональный контент», а не как generic AI render. Для этого система работает не только на
качество кадра, но и на восприятие зрителем.
Практическая цель контента:
стабильная идентичность персонажа;
правильная eye-line и ощущение прямого контакта со зрителем;
микро-движение, паузы, дыхание и voice layer, которые убирают ощущение пластиковой
генерации;
shot templates, которые выглядят как повторяемый фирменный стиль, а не случайный
визуальный шум.
3. Базовый стек v
Ниже — конкретный стек, на котором имеет смысл строить v1, потому что он достаточно сильный,
контролируемый и пригодный для масштабирования из одной GPU в worker-layer.
Слой Инструмент / выбор Роль Правило использования
Compute 1× RTX 4090 24 GB (облако) Стартовая production GPU Сначала аренда, не покупка железа.
Runtime SelfDocker-hosted ComfyUI в Inference engine + queueable workflows Headless API format JSON, staging и prod раздельно.
Image
backbone FLUX.2 [klein] 4B^
Explore, hero, repair,
editing
Основа для T2I/I2I и
house-layer через LoRA +
refs.
Video
backbone
Wan 2.2 TI2V-5B /
control-line
Image-to-video,
controllable short clips
Source clip генерируем как
720p/24fps, не насилуем
систему native 1080p/30.
Finishing Upscale + interpolation + encode Publish-ready master Любой clip проходит through finish stage.
Слой Инструмент / выбор Роль Правило использования
Storage S3storage-compatible object Refs, outputs, snapshots, review assets Raw и final разнесены, lineage сохраняется.
Metadata Postgres Jobs, assets, workflows, character lineage Все решения логируются через manifest + DB.
Orchestration FastAPI service + internal panel Job intake, parameter injection, queue tracking Сначала job runner, не «магический агент».
Runpod/Vast 4090
↓
Dockerized ComfyUI (headless)
↓
FLUX.2 [klein] 4B + LoRA + refs + ControlNet + repair
↓
Wan 2.2 TI2V-5B
↓
Interpolation + upscale + encode
↓
S3 + Postgres + manifests
↓
Review / scoring / publish
4. Целевая архитектура: 7 слоёв
Слой Что хранит / делает Почему это важно
Creative inputs
briefs, character bibles, style bibles, reference
packs, shot library, wardrobe/location/background
packs, platform specs
Без этого у системы нет
управляемого creative
memory.
Workflow library versioned ComfyUI JSON graphs: explore, hero, repair, video, finish Repeatability и быстрый rollback.
Inference GPU pod с headless ComfyUI Исполняет jobs, а не живёт как playground.
Orchestrator
принимает job, подставляет параметры,
отправляет в /prompt, читает /queue и /history,
сохраняет outputs
Убирает ручной бардак и
создаёт трассируемость.
Storage refs, raw outputs, final outputs, workflow snapshots, review assets Asset lineage и повторяемость.
Metadata jobs, assets, characters, workflows, scores, review status, hashes, seeds
Machine memory для
анализа и
масштабирования.
Review &
analytics
human selection, acceptance/reject, routing в
repair, KPI и позже scoring
Именно здесь winners
отделяются от «нормально».
5. Где что должно лежать
Система хранится как production repository + object storage, а не как хаотичная папка «разное». Ниже
— минимальная структура, которую не придётся переделывать через месяц.

/infra/
docker/
compose/
env/
deploy/
/services/
orchestrator/
internal_panel/
workers/
/models/
image/base/
video/base/
loras/character/
loras/style/
/refs/
characters/<character_id>/
face/
body/
hair_makeup/
wardrobe/
signature_poses/
styles/<style_id>/
locations/
backgrounds/
/creative/
briefs/
character_bibles/
style_bibles/
shot_library/
platform_specs/
/workflows/
explore/
hero/
repair/
video/
finish/
/manifests/jobs/
/exports/contact_sheets/
/docs/sops/
/docs/review_rules/
В object storage храним assets и snapshots по дате и типу:

s3://ofm-prod/
refs/
outputs/raw/YYYY/MM/DD/
outputs/final/YYYY/MM/DD/
workflow_snapshots/
review_assets/
thumbs/
audio/
voice/
captions/
Naming discipline обязательна. Никаких «workflow_final_real_new2».

Сущность Пример naming
Workflow hero_flux2k4b_chara_editorial_v003.json
Сущность Пример naming
Job job_2026_03_09_chara_sfw_hero_00421

Manifest job_2026_03_09_chara_sfw_hero_00421.json

Hero still chara_sfw_hero_mirror_9x16_v012_seed483829.png

Video master chara_sfw_walkin_9x16_master_v004.mp4

LoRA lora_chara_v006.safetensors / lora_house_editorial_v003.safetensors

6. Workflow library: пять обязательных графов
В v1 не нужно двадцать workflow. Нужно пять production-proven графов. Каждый должен жить как
versioned JSON и проходить через change log.
Workflow A — IMG_explore_v
Назначение: Быстро получить веер сцен, композиций и visual hooks при низкой цене ошибки.
Inputs: brief, lane, character pack, style pack, aspect ratio, seed range, explore prompt block
Проход: FLUX.2 [klein] 4B, fast preview settings, 10–50 вариаций на один brief, сохранение seed и shortlist
contact sheet.
Outputs: preview batch, contact sheet, shortlist JSON, seeds для лучших кадров.
Workflow B — IMG_hero_v
Назначение: Довести выбранный candidate до дорогого production still.
Inputs: selected explore frame, character LoRA, style LoRA, refs, pose/control inputs, repair rules
Проход: reference injection → character/style LoRA → pose/structure control → two-pass generation →
локальный inpaint → upscale.
Outputs: hero still master, crop variants, thumbnail candidate, manifest linkage.
Workflow C — IMG_repair_v
Назначение: Исправлять типовые дефекты без полной регенерации.
Inputs: hero image, repair subtype, mask/inpaint zone, identity-preserve refs
Проход: отдельные режимы repair_face / repair_hands / repair_clothing / repair_background /
repair_identity_preserve.
Outputs: исправленный asset, repair note, count rework cycles.
Workflow D — VID_i2v_v
Назначение: Делать короткий controllable clip из стабилизированного hero still.
Inputs: hero still, motion brief, camera behavior, duration, fps, output ratio
Проход: Wan 2.2 TI2V-5B, subtle head/eye/body motion, limited duration, source clip 720p/24fps.
Outputs: source clip, frame set, motion manifest, candidate covers.
Workflow E — VID_finish_v
Назначение: Превратить source clip в publishable master.
Inputs: source clip, publish preset, caption/audio flags
Проход: frame interpolation → video upscale → encode → optional caption layer → output packaging per
channel.
Outputs: 1080p publish master, platform variants, preview thumb, final manifest.
Главное правило video-side
Видео используется как motion layer поверх уже стабилизированного image-side результата.
Стартовый target — 1080p publish master через 720p/24fps source + interpolation + upscale.
Не строим систему вокруг native 1080p/30 generation на одной 4090.
7. Полный production loop: один asset от brief до publish
Шаг Что делает оператор / система Артефакт на выходе Критерий перехода
Brief
Выбор персонажа, сюжета,
эмоционального тона, shot type, канала,
цели поста.
brief record brief полный и однозначный.
Explore Генерация батча preview для поиска hook, композиции и mood. contact sheet + shortlist
есть 1–3 winners,
которые стоит
доводить.
Select Оператор выбирает кандидатов, фиксирует seed и notes. selected candidate кадр already feels expensive, не generic.
Hero Highи upscale.-quality still workflow с refs, LoRA, control hero still master
лицо, руки, свет,
одежда и фон
проходят базовый QC.
Repair Локальная правка дефектов без полной регенерации. repair pass нет заметных артефактов и drift.
Video Imagemotion brief.-to-video из hero still c ограниченным source clip
движение
естественное, без
странного morphing.
Finish Interpolation, upscale, encode, packaging. publish master файл технически готов для канала.
Review Human accept/reject, score, notes, routing в repair или approve. review decision принят только winner.
Publish Asset уходит в distribution system и получает performance tracking. published asset id контент связан с метриками канала.
8. Character system: как держать персонажа живым и узнаваемым
Самый ценный актив фабрики — не backbone сам по себе, а house layer поверх него. Character lock
строится из трёх уровней.
Уровень Содержимое Правило
A. Character LoRA одна LoRA на персонажа или tightly related family Не смешивать разные character identities в одном asset.
B. Style LoRA свет, skin finish, lens behavior, color mood, editorial polish
Это house aesthetic; одна
фабрика должна выглядеть как
одна фабрика.
C. Reference packs face, body proportions, hair/makeup, wardrobe, room tone, signature poses
Reference set фиксируется и
versionируется, а не гуляет от
сессии к сессии.
На каждого персонажа должен существовать character bible, в котором зафиксированы:
identity core: лицо, возрастной диапазон, телосложение, волосы, skin tone, мимика, базовые
пропорции;
signature look: тип света, макияж, любимые ракурсы, фирменные wardrobe anchors;
forbidden drift: что нельзя менять без отдельной версии персонажа;
approved shot families: где персонаж выглядит strongest;
voice intent: темп речи, breathiness, эмоциональная температура, словарь.
9. Shot grammar и perceptual design контента
Большинство проигрывает не на модели, а на режиссуре. Контент должен строиться на production-
proven shot templates. Ниже — минимальная библиотека для v1.
Shot type Что продаёт кадр Технический фокус Failure mode
Hero close-up ощущение личного контакта eyeasymmetry, clean background-line, skin detail, subtle plastic skin, dead eyes, over-smoothing
Medium
conversational
ощущение «она
говорит со мной»
natural hand placement, torso
framing, realistic posture
stiff body, awkward
hands
Mirror
composition
editorial tease и visual
depth
reflections, environment
consistency, silhouette broken reflection logic^
Entrance /
walking frame динамика и anticipation^
motion from still into clip,
posture, clothing flow morphing legs, weird gait^
Seated idle спокойная интимность и pause micro movement, breathing, fabric realism frozen mannequin feel
Over-shoulder
tease
curiosity and reveal
control
camera angle, spine line, hair
behavior
distorted shoulders /
neck
Reaction shot эмоциональная живость microblink logic-expression, gaze shift, empty expression
CTA end frame конверсия без грязного визуального шума clean composition, space for text, thumbnail readability too busy, unreadable framing
Каждый shot template хранится как пакет из четырёх частей:
prompt block и negative constraints;
reference pack и preferred aspect ratios;
known failure modes + repair rules;
пример winners, на которые можно равняться при отборе.
Что создаёт ощущение флирта на уровне production
правильная eye-line: зрителю должно казаться, что внимание направлено в него, а не в пустоту;
micro-expressions вместо гиперэмоций: лёгкая улыбка, пауза перед взглядом, небольшое движение плеч
и головы;
controlled reveal: кадр должен намекать и удерживать внимание, а не сразу отдавать весь визуальный
объём;
ритм: still, motion, voice и audio ambience должны ощущаться как одна сцена, а не четыре независимых
слоя.
10. Оркестратор: что пишет сервис поверх ComfyUI
Поверх ComfyUI нужен маленький job runner. На старте это не агент и не «авто-гений». Это сервис,
который делает шесть скучных, но критических вещей.
Принимает job из internal panel или API.
Подставляет параметры в versioned workflow JSON.
Отправляет JSON в ComfyUI /prompt.
Следит за /queue и /history до завершения.
Складывает outputs в storage и создаёт preview/review assets.
Пишет manifest и метаданные в Postgres.
POST /jobs
{
"lane": "sfw",
"character_id": "chara",
"workflow": "IMG_hero_v1",
"workflow_version": "v003",
"brief_id": "brief_2026_03_09_0021",
"refs": ["chara_face_v004", "lora_house_editorial_v003"],
"params": {
"aspect_ratio": "9:16",
"shot_type": "hero_closeup",
"seed": 483829,
"publish_target": "short_vertical"
}
}
Оркестратор также должен уметь хранить workflow snapshot на момент запуска job, чтобы later
reproduction не зависел от того, что кто-то поменял JSON в репозитории.

11. Минимальная схема данных
На старте достаточно четырёх core tables и manifests в JSON. Этого хватит, чтобы контролировать
производство и потом нарастить scoring layer.

Таблица Поля v1 Зачем
jobs id, lane, brief_id, workflow_id, status, created_at, finished_at, operator, cost_estimate, notes Жизненный цикл каждого запуска.
assets asset_id, job_id, type, path, width, height, fps, score_human, accepted Что именно было произведено и принято.
characters character_id, name, lane, lora_version, ref_pack_version, style_bible_version Состояние персонажей как production entities.
workflows workflow_id, name, version, file_hash, changelog Контроль версий графов.
optional
review_scores
job_id, hook_score, identity_score, polish_score,
publish_readiness, notes
Ускоряет сравнение
winners.
На каждый job создаётся manifest. Это фактически машинная память системы.

Поле manifest Содержимое
job_id уникальный идентификатор job
date / operator / lane кто запускал и для какой линии
workflow_version конкретный JSON-граф и его hash
model_version / hash какая модель реально была использована
Поле manifest Содержимое
LoRA versions character/style LoRA версии

references_used точный набор refs

seed seed или seed range

notes операторские заметки и review flags

accepted / rejected статус принятия

final_asset_paths пути до финальных outputs

12. Review gates и acceptance criteria
Контент в топ выходит не потому, что был сгенерирован, а потому что был отфильтрован. Review —
это не косметика, а денежный фильтр.
Gate Проверка Reject, если...
Identity gate персонаж узнаётся, ref drift минимален лицо, волосы, пропорции или signature look плавают
Polish gate кожа, руки, ткань, фон, свет и рефлексы выглядят цельно видны AI artifacts или дешёвый render feel
Shot gate композиция продаёт именно этот shot type кадр скучный, нечитабельный или не несёт hook
Motion gate движение естественное, без morphing и stutter странные деформации, мёртвые паузы, ненужная суета
Thumbnail gate кадр работает в маленьком размере силуэт, лицо или композиция теряются
Channel gate формат, длительность, encode и safe areas соответствуют каналу мастер не готов технически
Правило фабрики
Публикуются только winners. «Нормально» не публикуется.
Каждый reject должен иметь понятную причину: shot weak, drift, polish fail, motion fail, channel fail.
Именно ruthless curation превращает техсистему в money system.
13. Staging / production и дисциплина стабильности
ComfyUI в production должен жить как закрытый appliance, а не как playground. Иначе система
расползается, и никакая автоматизация уже не спасает.
Отдельный staging pod и отдельный production pod.
Custom nodes ставятся только в staging.
В production — allowlist, pinned versions, snapshots, hash discipline.
Никаких random GitHub installs на живую систему.
Model verification, version pinning и reproducibility важнее любопытства.
Контур Что разрешено Что запрещено
Staging тест новых нод, workflow tuning, R&D открывать наружу или смешивать с живым продом
Production только проверенный стек, job execution, review-ready outputs
ручные installs,
неподтверждённые nodes,
uncontrolled config drift
14. Две output-линии поверх одного ядра
Технически фабрика одна. Разделяются не инфраструктуры, а policy-конфигурации.
Компонент SFW lane Lawful adult lane
Character packs fashion/editorial/lifestyle variants отдельные packs и flags
Компонент SFW lane Lawful adult lane
Style bible brand-safe aesthetics тот же house polish, но отдельные approval rules
Storage общие core buckets отдельные subpolicy для sensitive assets-buckets и access
Review flags thumbnail / brand / platform safety extra compliance flags, rights log, age-gating where applicable
Publishing rules broad distribution presets separate publishing policy and manual check
Важно: взрослую линию ведём только в рамках применимых правил площадок и юрисдикций;
compliance log, rights log и age-gating rules должны быть заложены в систему с первого дня, а не
после проблем.

15. Voice pipeline как v
Голос не встраивается внутрь генерации видео. Это отдельный модуль, который подключается
после того, как image-side и video-side уже стабильны.

Hero image
↓
Video generation
↓
Voice synthesis
↓
Lip-sync
↓
Audio mix (breathing / ambience / pauses)
↓
Final encode
Почему так: текст, эмоцию, язык и темп речи можно менять без перегенерации видео. Это резко
повышает контроль и удешевляет итерации.

Подслой Инструменты v2 Задача
TTS / voice cloning ElevenLabs / XTTS / PlayHT / Cartesia реалистичный голос и вариативность под персонажа
Lip sync Wav2Lip / SadTalker / MuseTalk синхронизация рта и мимики
Audio mix breath layer, room ambience, micro pauses убрать ощущение стерильного синтеза
16. KPI, без которых фабрика неуправляема
KPI Что показывает Почему важен
Keeper rate доля explore outputs, которые доходят до hero показывает, насколько explore действительно находит winners
Rework count сколько repair cycles требуется на asset показывает качество базовых workflow и ref discipline
Time-to-final время от brief до publishable still/video управление скоростью фабрики
KPI Что показывает Почему важен
Character drift incidents частота потери идентичности главный враг бренда персонажа
Cost per accepted
asset реальная стоимость winner^ основа для экономики^
Accepted assets per
GPU hour
производительность железа в
полезных результатах
отделяет реальную
эффективность от самообмана
Video completion
success rate
сколько clip jobs завершается
без критического брака здоровье video lane^
Channel metrics CTR, watch time, conversion связывает production с деньгами
17. План запуска по фазам
Фаза Срок Что делаем Результат
Skeleton 3 – 5 дней
Runpod 4090 pod, Docker, ComfyUI, S3-
compatible storage, Postgres, git repo,
staging/prod convention
правильный пустой
каркас
Image
lane 7 – 10 дней^
собрать и стабилизировать Explore, Hero,
Repair
production-grade still
images
Video
lane 7 – 10 дней^
Wan 2.2 I2V/TI2V, interpolation, video
upscale, publish presets
короткие publishable
clips
3.
Character
system
1 – 2
недели
2 – 3 персонажа, их LoRA, ref packs, style
bibles, shot libraries узнаваемость и бренд^
4.
Orchestrati
on
1 неделя internal panel, job runner, manifests, review screen
работа через систему,
а не руками из
браузера
Partial
automation
после
стабилиза
ции
scoring, batch scheduling, top-N selection,
auto-routing into repair предагентная стадия^
18. Что сознательно не делать в v
multi-GPU cluster и сложную serverless orchestration;
тонну кастомных нод без жёсткой проверки;
свою foundation model;
native 1080p/30 generation как обязательную цель;
fully autonomous agent до того, как manual lane доказал repeatability;
хаотичное смешивание персонажей, стилей и refs без version control.
Финальная операционная формула
Character lock + house aesthetic + production discipline + ruthless curation.
Именно эта связка даёт внимание зрителя, а не поиск «секретной ноды» или «магической модели».
Система должна быть настолько чистой, чтобы лучший результат можно было воспроизвести, сравнить и
улучшить.
19. Итог
Если кратко: правильный старт — это one-GPU, self-hosted, repeatable factory. Image-side
стабилизирует идентичность и дорогой кадр; video-side добавляет motion; finishing превращает
генерацию в publish-ready asset; orchestrator, storage и manifests превращают хаос в систему; review
и KPI отделяют winners от мусора. На таком фундаменте можно строить как сильный ручной
production loop, так и последующую автоматизацию.

Этот документ — базовая техническая спецификация v1. Следующие полезные слои поверх
него: детальные SOP на каждый workflow, шаблоны briefs, review scorecards, publish presets по
каналам и internal dashboard.