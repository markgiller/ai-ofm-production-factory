#!/usr/bin/env python3
"""
Batch generate 500 everyday lifestyle photos using LoRA v004_best (step 660).
100 prompts × 5 seeds = 500 images.
Ultra-realistic phone-camera aesthetic, imperfect lighting, candid feel.
Face descriptor embedded in every prompt for high ArcFace FaceSim.

Usage:
    python scripts/batch_everyday_v004.py \
        --comfyui-url http://localhost:8188 \
        --count-per-prompt 5
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from run_explore import run_explore
from pathlib import Path
import random

# ── Photorealism anchors for FLUX.2 Klein ──────────────────────────────────
# FLUX responds to filename trick (IMG_XXXX.HEIC = iPhone snapshot aesthetic)
# and camera/lens references. "ultrarealistic" etc. are SD-era noise — don't use.
# Prose > keyword lists. CFG should stay low (1.0-2.5) for photorealism.

# Face descriptor — keeps trigger word "chara" early, adds face features for FaceSim
FACE = "chara, young woman with soft brown eyes and warm brunette hair"

# Camera suffixes — randomly appended to each prompt for photo style anchoring
CAMERAS = [
    "shot on iPhone 14, natural skin texture",       # casual phone
    "shot on iPhone 14, natural skin texture",       # casual phone (weight)
    "shot on iPhone 14, natural skin texture",       # casual phone (weight)
    "shot on Canon EOS R5, 85mm f/1.8, shallow depth of field",  # portrait
    "shot on Fujifilm X-T5, 35mm f/1.4, natural color grading",  # street
]

# ── 100 ultra-realistic prompts ─────────────────────────────────────────────
# FACE is embedded via f-string. Filename trick + camera added in main loop.
EVERYDAY_PROMPTS = [

    # ── MORNING / WAKING UP (10) ──────────────────────────────────────────
    f"{FACE}, just woke up, messy hair plastered to cheek, squinting in harsh morning light, oversized faded t-shirt, lying in unmade bed with phone screen on, no makeup, slightly puffy eyes, candid phone photo from above",
    f"{FACE}, sitting on edge of bed in morning, elbows on knees, staring at floor, messy bedroom, harsh window light cutting across half her face, wearing oversized sweatpants and tank top, totally zoned out",
    f"{FACE}, brushing teeth at bathroom mirror, phone balanced on sink edge, slightly annoyed expression because alarm went off, harsh fluorescent bathroom light, half-awake, pajama top, messy bun",
    f"{FACE}, making coffee in small apartment kitchen at 7am, wearing boyfriend's hoodie and underwear, winter light barely coming through window, steam from mug, scrolling phone with one hand, slightly messy counter",
    f"{FACE}, sitting in bed eating toast with phone in other hand, morning sunlight streaming through cheap blinds making stripes across the sheets, wearing bralette and shorts, hair half in face",
    f"{FACE}, blurry morning selfie in bathroom mirror, just stepped out of shower, hair wet and dripping, wrapped in towel, no makeup, fresh skin, tiny bit of steam on mirror edges, phone visible in reflection",
    f"{FACE}, standing at kitchen counter eating cereal straight from bowl without spoon, leaning over to not drip, wearing oversized night shirt, morning hair, light through dirty window, authentic low-effort morning",
    f"{FACE}, lying face-down on bed after alarm, one arm over face blocking light, phone on pillow next to head showing missed calls, wearing wrinkled clothes from last night, total chaos energy",
    f"{FACE}, early morning getting ready at bathroom counter, one eye done with mascara, other bare, mid-process, bright bathroom vanity light, collection of products spread out, focused but rushed",
    f"{FACE}, walking out of apartment building in morning, tote bag and coffee cup, slightly squinting at bright morning sun, casual outfit — jeans and puffer jacket, motion blur on background, authentic commute photo",

    # ── STUDY / UNIVERSITY (10) ──────────────────────────────────────────
    f"{FACE}, at university library, surrounded by open textbooks and highlighters, wearing reading glasses, knit cardigan, head resting on hand looking tired, fluorescent library lighting, candid mid-study shot",
    f"{FACE}, laptop open in cafe, multiple browser tabs open, notes with arrows and circles everywhere, slightly stressed expression, half-eaten croissant next to coffee, natural window light, cozy but chaotic desk",
    f"{FACE}, sitting in lecture hall row, pen twirling between fingers not paying full attention, notebook with doodles in margins, wearing hoodie, fluorescent overhead lighting, slightly bored expression",
    f"{FACE}, studying in bed late at night, laptop glowing, notes spread all around, wearing oversized tee, blanket pulled up, one AirPod in, empty tea mug on nightstand, concentrated but tired",
    f"{FACE}, taking a study break in dorm hallway, back against wall, knees up, phone in hand, slightly glazed expression, vending machine light in background, tired 2am energy",
    f"{FACE}, library study room, whiteboard behind her full of diagrams and arrows, marker in hand mid-explanation, casual sweater, natural enthusiasm, candid shot taken by friend through glass",
    f"{FACE}, sitting on campus steps eating lunch from plastic container, earbuds in, watching something on phone propped against bag, casual jeans and jacket, autumn leaves on ground",
    f"{FACE}, in university bathroom between classes, reapplying lip gloss at mirror, backpack on floor, slightly tired, fluorescent light overhead, candid mid-touch-up photo by friend",
    f"{FACE}, waiting for lecture to start, sitting sideways in seat talking to someone off-frame, laughing, casual outfit, lecture hall overhead lighting, notebook open but empty, first day energy",
    f"{FACE}, closing laptop at end of study session, stretching arms above head, coffee cup empty, late evening cafe, warm amber light, relieved expression, papers being stacked together",

    # ── CAFE / COFFEE (10) ──────────────────────────────────────────────
    f"{FACE}, sitting alone at corner cafe table, latte art in ceramic cup, looking out rainy window, cream knit sweater, chin resting on hand, soft overcast light, pensieve and unbothered",
    f"{FACE}, ordering at cafe counter, pointing at pastry display, casual outfit, slightly leaning forward squinting at options, warm indoor cafe light, genuine indecision face",
    f"{FACE}, phone call at cafe table, one hand gesturing, other holding coffee, animated expression, outdoor terrace, afternoon sun, other tables blurred in background",
    f"{FACE}, barista behind espresso machine, black apron, hair tied back with a few strands loose, steam from machine, focused on pulling shot, warm cafe lighting, genuine concentration",
    f"{FACE}, reading book in window seat of cafe, tea on table, rain on glass behind, wearing chunky knit jumper, feet tucked under, soft grey light, peaceful and absorbed",
    f"{FACE}, laughing at something on phone at cafe table, covering mouth with hand, coffee mid-sip almost spilled it, warm daylight from window, totally caught off guard candid",
    f"{FACE}, sharing dessert at cafe, fork mid-bite, looking up at someone off-frame smiling, small table with two cups, warm indoor light, relaxed hangout energy",
    f"{FACE}, doing homework at cafe, three windows open on laptop, AirPods in, ignoring the fact that it's 6pm and cafe is filling up, hoodie, tired but grinding",
    f"{FACE}, iced coffee and laptop at outdoor cafe table, squinting slightly in afternoon sun, sunglasses pushed up on head, tank top, working remotely vibe",
    f"{FACE}, trying first sip of new coffee order, uncertain expression, small paper cup, cafe counter, slight grimace or pleasant surprise — not sure yet",

    # ── MIRROR SELFIES / GETTING READY (10) ────────────────────────────
    f"{FACE}, full length mirror selfie in bedroom, casual fit — jeans and tucked in tee, messy room behind, soft window light, not posed just checking the outfit",
    f"{FACE}, bathroom mirror selfie, phone partially covering face, fresh out of shower, slightly dewy skin, wearing oversized shirt, damp hair, casual and unbothered",
    f"{FACE}, getting ready to go out, in process — one shoe on, holding other, sitting on bed edge, cute going-out outfit, bedroom light on, rushing energy",
    f"{FACE}, doing eyeliner in compact mirror, tip of tongue out concentrating, sitting in car, sunlight coming through window, other hand holding compact steady",
    f"{FACE}, changing room selfie, holding up two different top options against herself, looking in mirror unsure, store lighting, being realistic about what looks good",
    f"{FACE}, lying on bathroom floor after shower, wrapped in towel, phone above her face, wet hair spread out, too tired to move, warm bathroom light, genuine exhaustion",
    f"{FACE}, mirror selfie at pre-drinks, night out outfit, good lighting, someone else visible in mirror behind her getting ready too, excited energy",
    f"{FACE}, checking her makeup in phone front camera before leaving, slight lipstick fix with pinky finger, standing in hallway, coat already on, last second check",
    f"{FACE}, morning mirror selfie catching herself looking surprisingly good, unbothered expression, simple outfit, natural light from window behind, no plan just vibes",
    f"{FACE}, gym changing room mirror selfie post-workout, sports bra and leggings, flushed face, no makeup, sweaty, actually proud of the workout",

    # ── FITNESS / GYM / SPORT (10) ────────────────────────────────────
    f"{FACE}, running on pavement in early morning, earbuds in, ponytail swinging, light sweat on face, wearing running shorts and long sleeve, slightly motion-blurred background",
    f"{FACE}, sitting on gym floor after leg day, back against mirror, water bottle between knees, red cheeks, slightly dead expression, gym bag next to her, fluorescent gym lighting",
    f"{FACE}, stretching on yoga mat in living room, morning light through window, wearing leggings and sports bra, focused inward, phone propped showing YouTube yoga video",
    f"{FACE}, lifting weights at gym, mid-rep, focused expression, gym lighting, casual gym fit, other equipment blurred in background, genuine effort not performance",
    f"{FACE}, on exercise bike at gym scrolling phone, not particularly trying hard, headphones in, gym clothes, slightly bored but showing up, late evening empty gym",
    f"{FACE}, hiking trail, slightly out of breath, looking back at camera with tired smile, backpack straps over shoulders, sunlight filtering through trees, natural outdoor setting",
    f"{FACE}, after swim at pool, hair wet and chlorine smell implied, wrapped in towel on pool deck, no makeup, summer afternoon, squinting slightly in bright light",
    f"{FACE}, at outdoor tennis or basketball court in park, mid-action or resting, athletic wear, golden hour light, summer afternoon, friend taking photo",
    f"{FACE}, foam rolling on living room floor, grimacing slightly at the discomfort, phone showing Netflix paused, evening light, bottle of water nearby",
    f"{FACE}, walking home from gym, gym bag over shoulder, hair in messy bun, wearing hoodie over gym clothes, tired but satisfied face, urban residential street, evening light",

    # ── SOCIAL LIFE / NIGHTS OUT (10) ────────────────────────────────
    f"{FACE}, at bar with friends, leaning against bar counter, holding drink, warm dim bar lighting, slightly flushed cheeks from laughing, casual going-out outfit, candid mid-conversation",
    f"{FACE}, house party, sitting on kitchen counter, red cup in hand, talking to someone, overhead kitchen light, party in background, totally in her element",
    f"{FACE}, club or bar dance floor, caught mid-dance by friend with phone, blurry colored lights behind, hair a bit wild, genuinely having fun not posing",
    f"{FACE}, restaurant dinner, laughing at something said across table, wine glass near hand, warm restaurant candle light, nice casual dress, relaxed dinner energy",
    f"{FACE}, rooftop with friends, city lights behind, holding drink, summer night, warm ambient light, slightly windswept hair, genuine smile not for camera",
    f"{FACE}, taxi or uber back home late, window reflection showing city lights streaking, tired but happy face, slightly smudged makeup, coat on, phone in hand",
    f"{FACE}, fast food run at midnight with friends, holding paper bag from drive-through window, laughing, car interior lit by dashboard and street lights",
    f"{FACE}, at concert, phone up taking video, slightly pushed by crowd, sweaty and happy, stage lights in background, screaming along to music",
    f"{FACE}, pregaming at friend's place, sitting cross-legged on carpet, cheap wine bottle nearby, everyone in early stages of getting ready, casual vibe before the night starts",
    f"{FACE}, end of night, sitting on steps of venue or outside bar, heels off next to her, bare feet on cool pavement, phone in hand, exhausted but happy",

    # ── HOME / DOMESTIC (10) ─────────────────────────────────────────
    f"{FACE}, cooking pasta, standing at stove stirring, steam rising, wearing apron thrown over casual clothes, messy counter with olive oil splatter, warm kitchen light, focused",
    f"{FACE}, doing laundry, holding pile of clothes trying to figure out which way round a shirt goes, slightly confused face, laundry room fluorescent light, Sunday vibe",
    f"{FACE}, flat on couch at end of long day, legs over armrest, phone on chest, eyes half open watching something, dim living room, oversized sweatshirt, totally done",
    f"{FACE}, cleaning apartment, hair in messy bun, wearing old t-shirt and shorts, mop or vacuum in hand, looking at phone while cleaning, weekend catch-up chores",
    f"{FACE}, ordering food delivery on phone, lying on couch, looking slightly too excited about the 45 minute wait, comfortable clothes, dim evening light",
    f"{FACE}, eating takeout straight from container, standing at kitchen counter, not even going to make this a proper sit-down meal, soy sauce packet on counter, happy about it",
    f"{FACE}, video call on laptop, waving at screen, sitting at desk, messy background with clothes on chair, laptop light illuminating face, evening at home",
    f"{FACE}, doing skincare routine at bathroom mirror, applying moisturizer with focused expression, wet hair from shower, bathroom light, products lined up on counter",
    f"{FACE}, sitting on bathroom floor doing face mask, phone in hand watching youtube, towel on shoulders, waiting for it to dry, quiet evening alone ritual",
    f"{FACE}, watering houseplants by window, morning light, oversized pyjama shirt, messy hair, little watering can, genuine care for her plants, soft morning atmosphere",

    # ── OUTDOORS / URBAN (10) ─────────────────────────────────────────
    f"{FACE}, walking through city on overcast day, headphones around neck, tote bag, slightly hunched against cold, moving through busy street, candid from behind then turned",
    f"{FACE}, waiting at bus stop, looking at phone, earbuds in, morning commute outfit, slight drizzle making her slightly damp, totally in her own world",
    f"{FACE}, sitting on park bench in autumn, fallen leaves around feet, scarf and coat, holding takeaway coffee, looking up slightly from phone, soft grey sky light",
    f"{FACE}, street market or farmer's market, looking at something on a stall, weekend morning, sunglasses on, canvas bag already slightly full, casual weekend outfit",
    f"{FACE}, caught in sudden rain, laughing and covering head with bag running to shelter, denim jacket getting wet, mascara slightly running, total chaos but funny",
    f"{FACE}, sitting on steps outside friend's house after hangout, not ready to leave yet, knees up, talking, late afternoon golden light catching her hair",
    f"{FACE}, at outdoor restaurant terrace, summer afternoon, white wine on table, sunglasses on head, oversized shirt, relaxed lunch that turned into three hours",
    f"{FACE}, night street shot, city lights reflected in puddle, wearing long coat, walking home, slightly mysterious but completely normal situation, phone camera night mode",
    f"{FACE}, flower market or plant shop, holding up small potted plant or bunch of flowers, deciding if she needs it (she does), morning light, genuine delight",
    f"{FACE}, rooftop of building or fire escape, city view behind, sitting with legs dangling, golden hour, casual outfit, phone for camera, no occasion needed",

    # ── TRAVEL / TRANSIT (10) ──────────────────────────────────────
    f"{FACE}, on train looking out window, headphones on, countryside or city blurring past, soft overcast natural light through train window, contemplative expression",
    f"{FACE}, airport departures hall, sitting on floor charging phone at wall socket, backpack between knees, tired pre-flight face, departure board in background",
    f"{FACE}, in airplane window seat, blanket over legs, neck pillow, looking out window during flight, soft cabin light, slightly pale and tired, overnight flight energy",
    f"{FACE}, lost in unfamiliar city, squinting at maps on phone, pulling small suitcase, slightly frustrated but managing, daylight, tourist but make it realistic",
    f"{FACE}, hostel or hotel room at end of travel day, sitting on bed with shoes still on, backpack dropped on floor, exhausted face, overhead room light, just needs five minutes",
    f"{FACE}, solo travel cafe in foreign city, journaling or writing postcards, coffee next to her, looking up thoughtfully, beautiful window light, peaceful and free",
    f"{FACE}, bus or metro in foreign city, trying to figure out the ticket machine, slightly puzzled face, other commuters around, candid moment of travel confusion",
    f"{FACE}, beach but make it realistic — overcast day, sitting on towel with book, eating chips from bag, windswept hair, not the glossy version just actual beach afternoon",
    f"{FACE}, at train station or bus terminal, giant backpack, sitting on top of it because chairs are taken, tired but okay, just waiting it out",
    f"{FACE}, road trip in passenger seat, feet up on dashboard, window open, hair blowing everywhere, music playing, singing slightly badly, golden hour through windshield",

    # ── EMOTIONAL / PERSONAL MOMENTS (10) ────────────────────────────
    f"{FACE}, deep in phone call, sitting by window, serious or emotional expression, one hand holding mug she forgot was there, soft afternoon light, clearly important conversation",
    f"{FACE}, journaling in bed, pen moving fast like catching up with thoughts, messy pages, warm lamp light, legs crossed, focused and private moment",
    f"{FACE}, watching sad movie, wet eyes, blanket pulled up to chin, dark room with screen light, tissue on armrest, totally absorbed and feeling it",
    f"{FACE}, venting to friend in cafe, leaning forward, hands moving, very animated face, friend's hands visible across table, warm cafe light, necessary catch-up",
    f"{FACE}, frustrated at laptop, head in hands or staring blankly at screen, messy desk, cold coffee, afternoon that went wrong, genuine stress face",
    f"{FACE}, genuine laugh, head thrown back, eyes crinkled shut, whatever was said was actually funny, caught by friend's phone in living room or street, natural light",
    f"{FACE}, proud little smile after finishing something hard — gym, exam, project, just sitting quietly with it, warm light, small private satisfaction moment",
    f"{FACE}, lying on floor of apartment staring at ceiling, not sad just need a moment, wearing comfortable clothes, afternoon light, phone face-down beside her",
    f"{FACE}, reading something on phone with very intense expression, completely absorbed, oblivious to surroundings, coffee getting cold, public place, candid shot",
    f"{FACE}, sitting outside after hard day, back against wall, knees up, exhaling, soft evening light, not looking at camera, just a quiet moment",

]

LORA_NAME = "lora_chara_v004_best.safetensors"
LORA_STRENGTH = 1.0
FORMAT = "4:5"
OUTPUT_DIR = Path("./explore_output/batch_v005_candidates")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch 500 photos for v005 dataset candidates")
    parser.add_argument("--comfyui-url", type=str, required=True)
    parser.add_argument("--count-per-prompt", type=int, default=5,
                        help="Seeds per prompt (default: 5, total = 100 x 5 = 500 images)")
    parser.add_argument("--lora-strength", type=float, default=1.0)
    parser.add_argument("--start-prompt", type=int, default=0,
                        help="Skip first N prompts (for resuming interrupted runs)")
    args = parser.parse_args()

    prompts = EVERYDAY_PROMPTS[args.start_prompt:]
    total = len(prompts) * args.count_per_prompt
    print(f"[batch] {len(prompts)} prompts x {args.count_per_prompt} seeds = {total} images")
    print(f"[batch] LoRA: {LORA_NAME} @ {args.lora_strength}")
    print(f"[batch] Output: {OUTPUT_DIR}\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for i, prompt in enumerate(prompts):
        prompt_idx = i + args.start_prompt
        seed_start = random.randint(100000, 999999)

        # Wrap prompt with FLUX photorealism anchors:
        # IMG_XXXX.HEIC filename trick + random camera/lens reference
        img_num = random.randint(1000, 9999)
        cam = random.choice(CAMERAS)
        full_prompt = f"IMG_{img_num}.HEIC. A candid raw photo, {prompt}, {cam}"

        short = prompt[20:70].replace(",", "").strip()
        print(f"\n{'='*60}")
        print(f"[batch] Prompt {prompt_idx+1}/{len(EVERYDAY_PROMPTS)}: {short}...")
        print(f"{'='*60}")

        try:
            run_explore(
                prompt=full_prompt,
                count=args.count_per_prompt,
                fmt=FORMAT,
                seed_start=seed_start,
                base_url=args.comfyui_url.rstrip("/"),
                output_dir=OUTPUT_DIR,
                lora=LORA_NAME,
                lora_strength=args.lora_strength,
            )
        except KeyboardInterrupt:
            print(f"\n[batch] Stopped at prompt {prompt_idx+1}. Resume with --start-prompt {prompt_idx}")
            sys.exit(0)
        except Exception as e:
            print(f"[batch] ERROR on prompt {prompt_idx+1}: {e}")
            continue

    print(f"\n[batch] DONE. {len(EVERYDAY_PROMPTS) * args.count_per_prompt} images in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
