База документа: one-GPU/self-hosted factory на 4090, Dockerized ComfyUI, image/video
workflows, S3, Postgres, manifests, review gates, staging/prod, KPI и phased rollout.
Отдельно: из BHW с июля 2025 по март 2026 повторяются одни и те же сигналы —
качество и консистентность важнее массового AI-спама, органика и дистрибуция решают
не меньше, чем генерация, Instagram чаще всего называли главным источником органики,
Threads у части людей давал старт, но был нестабилен и баноопасен, а promotion
называли самой сложной частью. Поэтому я добавляю в систему отдельный блок
promo/growth asset line, которого в техдокументе не хватало как явного production-модуля.
Это не “теория”, а рыночный сигнал с форума.

Compute-ядро
Что это: облачная 4090 как стартовая production GPU.
Что входит: Runpod/Vast, один основной worker.
Зачем: без этого нет фабрики, только эксперименты.
Готово, когда: можно стабильно гонять image/video jobs без ручного UI-бардака.
Runtime-слой
Что это: self-hosted ComfyUI в Docker.
Что входит: headless API, отдельные staging/prod окружения.
Зачем: inference должен быть сервисом, а не “рисовалкой в браузере”.
Готово, когда: workflow запускается JSON’ом, а не руками.
Model layer
Что это: набор базовых моделей и finishing-инструментов.
Что входит: FLUX.1 Dev 12B (fp8) для image-side, Wan 2.2 для image-to-video,
upscale/interpolation/encode для финала.
Зачем: это мотор генерации still + motion.
Готово, когда: есть repeatable output для explore, hero, repair, video, finish.
Storage layer
Что это: S3-compatible object storage.
Что входит: refs, raw outputs, final outputs, workflow snapshots, thumbs, audio, captions.
Зачем: все assets и lineage должны жить централизованно.
Готово, когда: raw/final разнесены, а каждый output можно найти по job/manfiest.
Metadata layer
Что это: Postgres + manifests.
Что входит: jobs, assets, characters, workflows, optional review_scores.
Зачем: это “память фабрики” — кто, что, когда, на чем, с каким seed, с каким результатом.
Готово, когда: любой winner можно воспроизвести.

Naming discipline
Что это: единый стандарт имен.
Что входит: workflow naming, job naming, hero still naming, video master naming, LoRA
naming.
Зачем: без этого система сгнивает в хаосе за 2 недели.
Готово, когда: нет файлов вида final_new_real_v2_last.json.
Repo / file structure
Что это: production repository, а не папка “разное”.
Что входит: /infra, /services, /models, /refs, /creative, /workflows, /manifests, /docs.
Зачем: это каркас всей системы.
Готово, когда: любой новый оператор понимает, где лежит что.
Creative memory
Что это: библиотека творческих входов.
Что входит: briefs, character bibles, style bibles, shot library, wardrobe/location/background
packs, platform specs.
Зачем: без этого модель каждый раз “придумывает заново”, а не производит брендовый
контент.
Готово, когда: каждый asset стартует не с пустого промпта, а из structured input.
Character system
Что это: система фиксации идентичности персонажа.
Что входит: character LoRA, ref packs, character bible, forbidden drift, approved shot families,
voice intent.
Зачем: главный актив — не картинка, а узнаваемый персонаж.
Готово, когда: персонаж стабилен из поста в пост и не “плавает”.
House aesthetic
Что это: слой фирменной эстетики поверх персонажа.
Что входит: style LoRA, skin finish, lens behavior, light logic, color mood, editorial polish.
Зачем: одна фабрика должна выглядеть как одна фабрика.
Готово, когда: разные сцены ощущаются как один бренд.
Shot grammar library
Что это: библиотека рабочих типов кадров.
Что входит: hero close-up, medium conversational, mirror composition, entrance/walking,
seated idle, over-shoulder, reaction shot, CTA end frame.
Зачем: люди проигрывают не в модели, а в режиссуре.
Готово, когда: у каждого shot type есть prompt block, refs, preferred ratios, failure modes,
repair rules и примеры winners.

Workflow library
Что это: versioned ComfyUI JSON-графы.
Что входит: 5 обязательных workflow: IMG_explore, IMG_hero, IMG_repair, VID_i2v,
VID_finish.
Зачем: не 20 хаотичных графов, а 5 production-proven путей.
Готово, когда: workflow versionируется, имеет changelog и snapshot при запуске job.
Orchestrator / job runner
Что это: сервис поверх ComfyUI.
Что входит: intake job, parameter injection, /prompt, tracking /queue и /history, сохранение
outputs, manifests, запись в DB.
Зачем: убирает ручной бардак и делает трассируемость.
Готово, когда: оператор запускает job через panel/API, а не собирает пайплайн руками.
Internal panel
Что это: операторская точка входа.
Что входит: выбор lane, character, workflow, refs, params, publish target, notes.
Зачем: это интерфейс фабрики для человека.
Готово, когда: оператор может без техдолга запускать production jobs.
Brief intake
Что это: точка начала production loop.
Что входит: персонаж, сюжет, эмоциональный тон, shot type, канал, цель поста.
Зачем: плохой brief убивает всю цепочку дальше.
Готово, когда: brief полный, однозначный и пригоден для explore.
Explore line
Что это: линия дешевого поиска winners.
Что входит: 10–50 вариаций на brief, contact sheet, shortlist JSON, seeds лучших кадров.
Зачем: найти hook, композицию и mood до дорогого hero-pass.
Готово, когда: из explore выходят 1–3 кандидата, которых реально стоит доводить.

Select layer
Что это: точка человеческого отбора.
Что входит: фиксация seed, notes, shortlist decision.
Зачем: winner выбирается человеком, а не “авось модель сама знает”.
Готово, когда: selected frame уже ощущается дорогим, а не generic.
Hero line
Что это: high-quality still production.
Что входит: ref injection, character/style LoRA, pose/control, two-pass generation, local inpaint,
upscale.
Зачем: превратить candidate в publish-grade master still.
Готово, когда: лицо, руки, свет, одежда и фон проходят базовый QC.
Repair line
Что это: локальная правка дефектов без полной регенерации.
Что входит: repair_face, repair_hands, repair_clothing, repair_background,
repair_identity_preserve.
Зачем: дешевле и быстрее чинить, чем пересобирать все заново.
Готово, когда: нет заметных артефактов и drift.
Video line
Что это: motion-layer поверх уже стабилизированного still.
Что входит: Wan 2.2, short controllable clips, subtle motion, 720p/24fps source.
Зачем: видео должно быть надстройкой над сильным кадром, а не заменой character lock.
Готово, когда: движение естественное, без morphing/stutter.
Finish line
Что это: publish-ready packaging.
Что входит: interpolation, video upscale, encode, caption/audio flags, platform variants.
Зачем: сырой clip не публикуется.
Готово, когда: есть 1080p master + channel variants + preview thumb + final manifest.
Review gates
Что это: денежный фильтр фабрики.
Что входит: identity gate, polish gate, shot gate, motion gate, thumbnail gate, channel gate.
Зачем: публикуются только winners.
Готово, когда: у каждого reject есть конкретная причина, а “нормально” в прод не уходит.

Policy / lane separation
Что это: две output-линии поверх одного ядра.
Что входит: SFW lane и lawful adult lane с разными packs, approval rules, storage flags,
review flags и publishing rules.
Зачем: ядро одно, правила выпуска разные.
Готово, когда: sensitive assets и brand-safe assets не смешиваются ни по storage, ни по
review, ни по publish.
Staging / production discipline
Что это: слой стабильности.
Что входит: отдельный staging pod, отдельный production pod, allowlist nodes, pinned
versions, snapshots, hash discipline.
Зачем: иначе фабрика ломается от каждого “интересного GitHub-нода”.
Готово, когда: прод не трогают для R&D.
Promo / growth asset line
Что это: обязательный дополнительный модуль, который прямо нужен для твоей цели
“контент, который тянет людей”.
Что входит: не только hero masters, а отдельные наборы под рост — carousels, reels,
thumbnail-first кадры, CTA end frames, hook-first variants, platform-native crops и post
packages.
Зачем: BHW очень явно показывает, что генерация без дистрибуции не решает, promotion
называют hardest part, Instagram чаще всего считают основным органическим каналом,
Threads иногда дает хороший старт, но нестабилен, а “mass generated content” не
конвертит как качественный контент с консистентной подачей.
Готово, когда: на каждый hero asset фабрика выпускает еще и growth-pack для соцсетей, а
не только “основной файл”.
Publishing system
Что это: связка production → distribution.
Что входит: publish presets по каналам, asset ID, связь с performance tracking.
Зачем: контент должен замыкаться на метрики канала, а не исчезать после экспорта.
Готово, когда: каждый опубликованный asset имеет канал, дату, вариант и результат.
KPI / analytics layer
Что это: управленческий слой.
Что входит: keeper rate, rework count, time-to-final, character drift incidents, cost per accepted
asset, accepted assets per GPU hour, video completion success rate, channel metrics.
Зачем: без этого вы не фабрика, а студия догадок.
Готово, когда: видно, какой workflow реально делает winners, а какой просто жжет GPU.

Voice module v
Что это: отдельный аудио-модуль после стабилизации image/video.
Что входит: TTS/voice cloning, lip sync, breathing/ambience/pauses, final audio mix.
Зачем: голос должен быть независимой итерационной надстройкой, а не частью
генерации видео.
Готово, когда: можно менять текст, темп, эмоцию и язык без перегенерации клипа.
Partial automation layer
Что это: автоматизация поверх уже доказанного manual lane.
Что входит: scoring, batch scheduling, top-N selection, auto-routing в repair.
Зачем: автоматизация должна ускорять дисциплину, а не заменять ее.
Готово, когда: вы уже умеете руками стабильно выпускать winners.
Non-goals / anti-chaos rules
Что это: список того, что не делать в v1.
Что входит: не строить multi-GPU cluster, не собирать тонну кастомных нод, не делать
свою foundation model, не насиловать native 1080p/30 на одной 4090, не запускать fully
autonomous agent до доказанной repeatability.
Зачем: фокус держит скорость.
Готово, когда: команда не расползается в “интересные эксперименты”.
⸻
В каком порядке реально собирать
Не по красоте, а по уму:
Этап 1 — каркас
Compute
Runtime
Storage
Metadata
Repo structure
Naming discipline
Staging/prod discipline
Этап 2 — creative OS

Creative memory
Character system
House aesthetic
Shot grammar
Workflow library
Этап 3 — production loop
Orchestrator
Internal panel
Brief intake
Explore
Select
Hero
Repair
Video
Finish
Review
Этап 4 — то, что реально тянет людей и деньги
Policy lanes
Promo/growth asset line
Publishing system
KPI/analytics
Этап 5 — только потом
Voice v
Partial automation
⸻
Система на самом деле состоит не из “генерации картинок”, а из 5 больших машин:
Production core — GPU, runtime, storage, DB, orchestrator.
Creative OS — character lock, style, shot grammar, briefs, refs.
Content engine — explore → hero → repair → video → finish.
Money filter — review gates, scoring, ruthless curation.
Growth engine — promo variants, thumbnails, reels/carousels, publish presets, KPI feedback.