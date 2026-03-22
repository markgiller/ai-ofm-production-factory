#!/usr/bin/env python3
"""
Generate diverse Chroma-format prompts for Lily v002 dataset (WAVE 2) via Gemini API.

Fixes from wave 1:
  - Forced variety in hair, gaze, lighting, camera angle
  - New categories: bath/pool, getting ready, night out, couple POV, video call, car/travel
  - Anti-repetition: explicit "DO NOT" list + variety matrices
  - More real 22-year-old energy: messy, spontaneous, unpolished

Output: creative/prompts/lily_v002_dataset_prompts_wave2.json
"""

import json
import random
import time
import requests
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyCyVuP2hImfypB93bD6sAuRkFbjaGmrEaA"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

OUTPUT_DIR = Path(__file__).parent.parent / "creative" / "prompts"
OUTPUT_FILE = OUTPUT_DIR / "lily_v002_dataset_prompts_wave2.json"

# ─── Variety Matrices ─────────────────────────────────────────────────────────
# Each prompt MUST pick different combos from these. Included in system instruction.

VARIETY = """
MANDATORY VARIETY — cycle through these, never repeat the same combo twice:

HAIR STATES (use ALL of these across your prompts, not just "medium brown wavy"):
- messy bun with loose strands
- wet hair slicked back
- hair in a claw clip, pieces falling out
- french braids
- low ponytail
- hair tucked into a beanie/cap
- air-dried natural texture, slightly frizzy
- blowout straight (rare occasion)
- wrapped in a towel turban
- windblown, across her face
- bedhead, one side flattened
- hair pushed to one side, undercut of neck visible

GAZE DIRECTIONS (NOT always "looking at camera"):
- looking down at her phone, lit by screen glow
- looking out a window, profile visible
- eyes closed, peaceful/pleasure
- mid-laugh with eyes squeezed shut
- looking at herself in mirror (we see reflection)
- looking over her shoulder
- looking up at the sky
- caught mid-blink, slightly blurry
- staring at something off-frame with curiosity
- eyes hidden by sunglasses
- looking at her own body/outfit
- side profile, nose and jaw silhouette

LIGHTING (be SPECIFIC, no generic "warm light"):
- phone flash in dark room — harsh, red-eye, overblown
- laptop/TV screen glow on face in dark room — blue cast
- bathroom fluorescent — slightly unflattering, real
- golden hour through car windshield — warm streaks on dashboard
- overcast flat daylight — no shadows, very even
- neon bar signs — pink/blue color cast on skin
- ring light — catchlights in eyes, even face illumination
- candle on nightstand — deep orange, heavy shadows
- flash from friend's phone across table — frozen moment
- sunrise, blue-pink sky behind her
- gym overhead fluorescent — slightly green cast
- dappled tree shadow on face/body — light patches

CAMERA/SHOT (NOT always "phone snapshot" or "candid"):
- phone timer propped on stack of books
- selfie arm visible at edge of frame
- mirror reflection with phone flash visible
- screenshot from FaceTime/video call — pixelated, UI visible
- dash cam angle from car
- shot from below looking up (POV lying on bed, she's above)
- over-the-shoulder of someone else (we see her from their perspective)
- photo taken by friend at arm's length
- security cam / webcam aesthetic — wide angle, slight distortion
- macro close-up — pores, individual eyelashes visible
- motion blur — she's moving, slightly ghosted
- taken through a window/glass door — reflections overlaid

NATURAL IMPERFECTIONS (include at least 1 per prompt):
- mascara slightly smudged under eye
- chipped nail polish
- tan lines visible
- pillow crease on cheek
- bra strap showing under shirt
- smudged lipstick
- hair tie on wrist
- phone crack visible in selfie
- slightly red/irritated skin from shaving
- dewy/sweaty forehead
- coffee stain on shirt
- wrinkled/rumpled clothing
"""

# ─── System Instruction ───────────────────────────────────────────────────────

SYSTEM_INSTRUCTION = f"""You are writing prompts as if you ARE lily — a real 22-year-old girl
documenting her actual life through phone photos. These are NOT studio shots.
These are the photos on her actual camera roll — messy, real, sometimes embarrassing,
sometimes hot, always authentic.

CHARACTER — "lily":
- 22, brown wavy hair (shoulder length), freckles, brown/hazel eyes
- Slim/petite, small-medium natural breasts, no plastic surgery
- Natural beauty — minimal or no makeup most of the time
- Confident, flirty, warm — "hot girl next door" who takes nudes for her boyfriend
  and also posts cute outfits on Instagram

CHROMA PROMPT FORMAT (strict):
Line 1: IMG_XXXX.HEIC (random 4-digit number, unique each time)
Line 2: blank
Line 3+: Natural language paragraph, 80-130 words. Full sentences only.
NO comma-separated tags. NO SD keywords (masterpiece, best quality, etc).

STRUCTURE: "An image of lily [action/pose]. [Body, expression, hair, clothing].
[Scene: location, lighting, background]. [Camera angle/framing]."

{VARIETY}

CRITICAL ANTI-REPETITION RULES:
1. NEVER use the phrase "medium brown wavy hair" — describe her hair STATE instead
   (messy, wet, clipped up, braided, etc). We know it's brown.
2. NEVER use "natural freckles across her nose and cheeks" — mention freckles only
   in 30% of prompts, and vary: "faint freckles on her shoulders", "sun freckles
   on her chest", "freckles barely visible under foundation"
3. NEVER use "small-medium natural breasts" — describe shape/visibility contextually
   if relevant, not as a label
4. NEVER use "warm bedside lamp" more than once — use SPECIFIC different light sources
5. NEVER use "candid phone snapshot" — be specific about WHO is shooting and HOW
6. Vary sentence structure — don't start every prompt with the same pattern
7. At least 30% of prompts should have her NOT looking at the camera

OUTPUT FORMAT:
Return ONLY a JSON array of prompt strings. Each string is the complete prompt
including IMG_XXXX.HEIC. No explanations, no numbering.
"""

# ─── Categories (Wave 2 — new + expanded) ────────────────────────────────────

CATEGORIES = [
    # ── NEW categories not in wave 1 ──
    {
        "name": "getting_ready",
        "count": 12,
        "lane": "sfw",
        "instruction": """Generate {count} GETTING READY / MORNING ROUTINE prompts.
The real content of a girl's camera roll — documenting outfits, makeup, hair process.
Scenarios: doing eyeliner in bathroom mirror, trying on 3rd outfit (clothes pile on bed),
blow-drying hair with one hand while holding phone, painting toenails on bathroom floor,
shaving legs in shower (leg propped up), picking outfit from messy closet,
straightening hair — caught by timer, applying body lotion after shower in towel.
Mix of dressed and partially dressed. Real bathroom/bedroom mess visible.
Include: makeup bag clutter, hair ties everywhere, clothing tags still on."""
    },
    {
        "name": "night_out",
        "count": 10,
        "lane": "sfw",
        "instruction": """Generate {count} NIGHT OUT / GOING OUT prompts.
Bar, club, rooftop, house party, restaurant, concert — the "hot" photos she posts.
Scenarios: posing with cocktail at bar (neon lights), dancing with eyes closed (motion blur),
smoking on balcony at party, laughing with drink spilling slightly, uber back seat selfie
with smudged makeup, bathroom selfie at club (harsh light, other girls in background),
sitting on someone's kitchen counter at house party, legs crossed at fancy restaurant.
Outfits: mini dress, leather pants, crop top + low jeans, bodycon, going-out top.
Energy: tipsy, confident, "fuck it" vibes. Slightly sloppy makeup is fine."""
    },
    {
        "name": "bath_pool_water",
        "count": 10,
        "lane": "nsfw",
        "instruction": """Generate {count} BATH / POOL / WATER prompts.
Scenarios: in bathtub with bubbles barely covering, stepping out of pool dripping wet,
shower glass half-steamed (body outline visible), sitting on edge of hot tub at night,
floating in pool on back (bikini), standing under outdoor shower at beach (head tilted back),
wet from rain on balcony in white t-shirt, sitting in shallow bath with knees up.
Water on skin is THE detail — droplets, wet hair clinging to neck, steam.
Lighting: bathroom overhead (slightly harsh), pool underwater lights, sunset at pool.
Camera: phone propped on towel, selfie with wet hand, through steamy glass."""
    },
    {
        "name": "couple_pov",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} COUPLE POV / BOYFRIEND PERSPECTIVE prompts.
The photos she takes FOR someone or that someone takes OF her. Private camera roll energy.
Scenarios: lying on his chest looking up at camera (his hand visible), standing in his
oversized hoodie and nothing else, morning-after lying in his sheets with bedhead,
sitting on his lap (shot from his perspective), leaning against kitchen counter in just
underwear while he cooks, sending a selfie from his bathroom mirror, pulling him toward
the bed by his shirt (phone in her other hand), lying on her stomach on the couch in
just a thong watching TV, stretching on bed — he snaps the photo, she half-notices.
These feel PRIVATE. Not for posting. Personal. Unguarded.
Camera: shot from above (he's standing/sitting up), her selfie for him, caught moment."""
    },
    {
        "name": "video_call_screen",
        "count": 8,
        "lane": "nsfw",
        "instruction": """Generate {count} VIDEO CALL / SCREEN CAPTURE prompts.
FaceTime, screen recording, webcam aesthetic — this is modern intimacy.
Scenarios: FaceTime screenshot — her face close to camera, lying in bed with laptop open
on chest (webcam angle from below), sitting at desk in bra — forgot camera was on,
showing off new lingerie via video call (holds phone at distance), lying on stomach
naked with laptop in front (shot includes laptop frame/UI), sending voice memo with
eyes half-closed and messy hair, ring light reflection in eyes during late-night call.
Include digital artifacts: slight pixelation, timestamp, wifi signal icon, battery %,
notification banner, slight lag blur. The intimacy of digital connection."""
    },
    {
        "name": "car_travel",
        "count": 8,
        "lane": "sfw",
        "instruction": """Generate {count} CAR / TRAVEL / ROAD TRIP prompts.
Scenarios: passenger seat with feet on dashboard, window down — hair blowing everywhere,
drive-through coffee in hand — golden hour on windshield, pumping gas in oversized
sunglasses, sleeping in reclined passenger seat (someone else took the photo), backseat
with pillow and blanket on long drive, rest stop bathroom mirror selfie (harsh light),
standing outside car at scenic overlook — wind in hair, sitting on car hood at sunset.
Travel energy: messy snacks, aux cord, sunglasses. The "on the road" aesthetic.
Camera: dashboard angle, selfie in visor mirror, phone against windshield, from driver seat."""
    },
    {
        "name": "post_workout_gym",
        "count": 8,
        "lane": "sfw",
        "instruction": """Generate {count} POST-WORKOUT / GYM prompts.
Real gym content, not Instagram fitness model posing.
Scenarios: gym mirror selfie — sweaty with AirPods in, sitting on bench catching breath,
lying on yoga mat staring at ceiling (exhausted), walking out of gym into parking lot
sunlight, doing abs on mat (phone propped nearby for form check), stretching hamstring
against wall, red-faced and sweaty selfie with "died" expression, sports bra tan line
visible after outdoor run.
Outfits: matched gym set (leggings + sports bra), baggy shorts + cropped tank, old
college t-shirt cut into crop. Include: water bottle, gym bag, headphones.
Lighting: gym fluorescent, parking lot sun, home workout natural light."""
    },
    # ── Expanded/improved from wave 1 ──
    {
        "name": "bedroom_intimate_v2",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} BEDROOM INTIMATE prompts — DIFFERENT from wave 1.
Wave 1 was too repetitive (all warm lamp, white sheets, looking at camera).
Force variety:
- Locations: hotel room, Airbnb, his apartment, dorm room, childhood bedroom at parents' house
- Surfaces: unmade bed with colorful sheets, floor with rug, window seat, bathroom tile floor
- NOT always lying down: sitting on windowsill naked, standing nude by door, squatting to pick
  something up, bending over dresser, sitting backwards on chair
- Light sources: laptop screen, TV glow, streetlight through blinds, bathroom light with door
  ajar (strip of light across body), morning grey overcast light
- Moods: not always seductive. Sometimes: bored and naked, just woke up grumpy, texting
  someone while undressed, eating takeout in bed nude, casual about nudity
- Camera: phone on nightstand timer, mirror across room, his phone (she's not looking)"""
    },
    {
        "name": "explicit_v2",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} EXPLICIT prompts — DIFFERENT from wave 1.
Wave 1 explicit was all "bed + warm lamp + direct gaze". Break the pattern:
- Locations: bathroom counter, kitchen, car backseat, hotel balcony (risky), shower, floor
- Positions: NOT always on back. On knees, standing, bent over, sitting on edge of counter,
  legs up against wall, straddling a pillow, on all fours looking back
- Context: post-sex hair mess, self-pleasure (hand between legs, not posed), running a bath
  naked, stretching after sleep, fresh out of shower dripping, sending nudes to someone
  (phone angle, she's checking the shot)
- Expression: NOT always "seductive gaze". Sometimes: concentration (self-pleasure), sleepy,
  laughing (caught at wrong moment), looking at own reflection critically, surprised
- IMPORTANT: these should feel like HER content — photos she chose to take. Not things
  happening TO her. She has agency. She thinks she looks hot and she's right."""
    },
    {
        "name": "selfie_variety",
        "count": 10,
        "lane": "sfw",
        "instruction": """Generate {count} SELFIE prompts covering angles NOT in wave 1.
Wave 1 was all bathroom mirrors. Expand:
- Car visor mirror with one eye in frame
- Laptop webcam screenshot — face very close, slight wide-angle distortion
- Phone held high above at concert/event (crowd behind)
- In bed, phone at arm's length, half her face in pillow
- Gym mirror with sweat visible
- Work bathroom during break (lanyard visible, tired eyes)
- Hotel elevator mirror (full body, going-out outfit)
- Photo booth strip aesthetic — 4 expressions in sequence
- In sunglasses — we see phone reflection in lens
- Back camera held over shoulder (shows back/hair from behind)"""
    },
    {
        "name": "cozy_domestic",
        "count": 10,
        "lane": "sfw",
        "instruction": """Generate {count} COZY / DOMESTIC / HOMEBODY prompts.
The "soft" content for Instagram stories — relatable, cute, aspirational.
Scenarios: wrapped in blanket burrito watching laptop, cooking pasta in oversized sweater,
reading in window seat with rain outside, face mask on + messy bun + pajamas,
watering plants in morning light in just a long t-shirt, assembling IKEA furniture
frustrated, eating cereal on kitchen floor (moved in, no table yet), painting nails
on coffee table while watching trash TV, folding laundry on bed, cat/dog in frame.
Energy: soft, domestic, girlfriend material. No trying hard. Sunday energy.
Include home details: candles, throw blankets, mugs, plants, messy but cute."""
    },
    {
        "name": "lingerie_v2",
        "count": 12,
        "lane": "nsfw",
        "instruction": """Generate {count} LINGERIE prompts — DIFFERENT styles from wave 1.
Wave 1 was all lace bralette + white sheets. New variety:
- Lingerie TYPES: strappy harness, garter belt + stockings, silk robe open, mesh bodysuit,
  cotton boy shorts + tank (anti-lingerie), vintage-style high waist + bullet bra,
  sports bra as lingerie (it's how real girls do it), bralette under open flannel
- Scenarios: trying on new set she just bought (tag still on), wearing matching set under
  regular clothes (shirt unbuttoned to reveal), lounging in just underwear + socks,
  lingerie + heels + nothing else, old comfortable underwear — no lace, just real
- Settings: NOT just bedroom. Laundry room, kitchen, hallway, staircase, living room couch
- Energy: mix of intentional (she bought this for a reason) and unintentional (she's just
  in her underwear because it's her house)"""
    },
]

# ─── Gemini API Call ──────────────────────────────────────────────────────────

def call_gemini(category: dict) -> list[str]:
    """Call Gemini to generate prompts for a single category."""

    user_prompt = category["instruction"].format(count=category["count"])
    user_prompt += f"\n\nReturn exactly {category['count']} prompts as a JSON array of strings. Nothing else."

    payload = {
        "system_instruction": {
            "parts": [{"text": SYSTEM_INSTRUCTION}]
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 1.0,
            "topP": 0.95,
            "maxOutputTokens": 16384,
            "responseMimeType": "application/json"
        }
    }

    headers = {"Content-Type": "application/json"}

    for attempt in range(3):
        try:
            resp = requests.post(GEMINI_URL, json=payload, headers=headers, timeout=120)
            resp.raise_for_status()

            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            prompts = json.loads(text)

            if isinstance(prompts, dict):
                for v in prompts.values():
                    if isinstance(v, list):
                        prompts = v
                        break

            if not isinstance(prompts, list):
                print(f"  WARNING: unexpected response type: {type(prompts)}, retrying...")
                continue

            valid = []
            for p in prompts:
                if isinstance(p, str) and "lily" in p.lower():
                    if not p.startswith("IMG_"):
                        img_num = random.randint(1000, 9999)
                        p = f"IMG_{img_num}.HEIC\n\n{p}"
                    valid.append(p)
                elif isinstance(p, dict):
                    prompt_text = p.get("prompt", p.get("text", str(p)))
                    if not prompt_text.startswith("IMG_"):
                        img_num = random.randint(1000, 9999)
                        prompt_text = f"IMG_{img_num}.HEIC\n\n{prompt_text}"
                    valid.append(prompt_text)

            print(f"  Got {len(valid)}/{category['count']} valid prompts")
            return valid

        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(3)

    return []


# ─── Quality Check ────────────────────────────────────────────────────────────

BANNED_PHRASES = [
    "medium brown wavy hair",
    "natural freckles across her nose and cheeks",
    "natural freckles across her nose",
    "small-medium natural breasts",
    "small-medium breasts",
    "candid phone snapshot",
    "masterpiece",
    "best quality",
    "ultrarealistic",
    "extremely detailed",
]

def quality_check(prompts: list[dict]) -> dict:
    """Run quality checks on generated prompts."""
    issues = {"banned_phrases": [], "too_short": [], "too_long": [], "no_img": [], "no_lighting": []}

    for item in prompts:
        p = item["prompt"]
        idx = item["index"]

        for phrase in BANNED_PHRASES:
            if phrase.lower() in p.lower():
                issues["banned_phrases"].append(f"#{idx}: '{phrase}'")

        # Word count (excluding IMG line)
        text = p.split("\n\n", 1)[-1] if "\n\n" in p else p
        wc = len(text.split())
        if wc < 60:
            issues["too_short"].append(f"#{idx}: {wc} words")
        if wc > 160:
            issues["too_long"].append(f"#{idx}: {wc} words")

        if not p.startswith("IMG_"):
            issues["no_img"].append(f"#{idx}")

    return issues


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("LILY V002 DATASET PROMPT GENERATOR — WAVE 2")
    print("=" * 70)

    total_expected = sum(c["count"] for c in CATEGORIES)
    print(f"\nTarget: {total_expected} prompts across {len(CATEGORIES)} categories")
    print(f"Model: {GEMINI_MODEL}")
    print(f"Output: {OUTPUT_FILE}\n")

    sfw_count = sum(c["count"] for c in CATEGORIES if c["lane"] == "sfw")
    nsfw_count = sum(c["count"] for c in CATEGORIES if c["lane"] == "nsfw")
    print(f"Distribution: SFW {sfw_count} ({sfw_count/total_expected*100:.0f}%) | "
          f"NSFW {nsfw_count} ({nsfw_count/total_expected*100:.0f}%)")
    print()

    for cat in CATEGORIES:
        print(f"  [{cat['lane'].upper():4s}] {cat['name']:25s} → {cat['count']} prompts")
    print()

    all_prompts = []
    metadata = {
        "version": "v002_wave2",
        "character": "lily",
        "model": GEMINI_MODEL,
        "total_target": total_expected,
        "categories": {},
    }

    for i, cat in enumerate(CATEGORIES):
        print(f"[{i+1}/{len(CATEGORIES)}] Generating: {cat['name']} ({cat['count']} prompts)...")

        prompts = call_gemini(cat)

        if not prompts:
            print(f"  FAILED — no prompts generated for {cat['name']}")
            continue

        for p in prompts:
            all_prompts.append({
                "prompt": p,
                "category": cat["name"],
                "lane": cat["lane"],
            })

        metadata["categories"][cat["name"]] = {
            "lane": cat["lane"],
            "requested": cat["count"],
            "generated": len(prompts),
        }

        if i < len(CATEGORIES) - 1:
            time.sleep(2)

    # Deduplicate IMG numbers
    used_img_nums = set()
    for item in all_prompts:
        prompt = item["prompt"]
        if prompt.startswith("IMG_"):
            num_str = prompt[4:8]
            if num_str in used_img_nums:
                new_num = random.randint(1000, 9999)
                while str(new_num) in used_img_nums:
                    new_num = random.randint(1000, 9999)
                item["prompt"] = f"IMG_{new_num}" + prompt[8:]
                num_str = str(new_num)
            used_img_nums.add(num_str)

    random.shuffle(all_prompts)

    for i, item in enumerate(all_prompts):
        item["index"] = i

    metadata["total_generated"] = len(all_prompts)

    # Quality check
    issues = quality_check(all_prompts)
    print("\n--- Quality Check ---")
    for k, v in issues.items():
        if v:
            print(f"  {k}: {len(v)} issues")
            for issue in v[:5]:
                print(f"    {issue}")
        else:
            print(f"  {k}: ✓")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "metadata": metadata,
        "negative_prompt": (
            "This greyscale unfinished sketch has bad proportions, is featureless and disfigured. "
            "It is a blurry ugly mess and with excessive gaussian blur. It is riddled with watermarks "
            "and signatures. Everything is smudged with leaking colors and nonsensical orientation of "
            "objects. Messy and abstract image filled with artifacts disrupt the coherency of the "
            "overall composition. The image has extreme chromatic abberations and inconsistent lighting. "
            "Dull, monochrome colors and countless artistic errors."
        ),
        "workflow_params": {
            "resolution": "768x1024",
            "steps": 20,
            "cfg": 3.2,
            "sampler": "res_2s",
            "scheduler": "sigmoid_offset",
            "scheduler_square_k": 1.0,
            "scheduler_base_c": 0.5,
            "lora_strength_model": 1.5,
            "lora_strength_clip": 1.0,
            "pulid_strength": 0.8,
        },
        "prompts": all_prompts,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 70}")
    print(f"DONE — {len(all_prompts)}/{total_expected} prompts generated")
    print(f"Saved to: {OUTPUT_FILE}")
    print(f"{'=' * 70}")

    # Samples
    print("\n--- Sample prompts ---\n")
    samples = random.sample(all_prompts, min(5, len(all_prompts)))
    for s in samples:
        print(f"[{s['category']} / {s['lane']}]")
        print(s["prompt"])
        print()


if __name__ == "__main__":
    main()
