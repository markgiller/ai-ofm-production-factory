#!/usr/bin/env python3
"""
Generate 150 diverse Chroma-format prompts for Lily v002 dataset via Gemini API.

Output: prompts saved to /creative/prompts/lily_v002_dataset_prompts.json
Each prompt follows Chroma prompting guide: natural language, IMG_XXXX.HEIC anchor,
descriptive sentences, explicit lighting, 75-150 T5 tokens.
"""

import json
import os
import random
import time
import requests
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY = "AIzaSyDVduTR1GHXYFCU4QWVoexlBFvqt4v_biY"
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

OUTPUT_DIR = Path(__file__).parent.parent / "creative" / "prompts"
OUTPUT_FILE = OUTPUT_DIR / "lily_v002_dataset_prompts.json"

# ─── Chroma Prompting System Knowledge ────────────────────────────────────────

SYSTEM_INSTRUCTION = """You are a professional prompt engineer for an AI image generation model called Chroma 1 HD.
Your job is to write prompts that produce images INDISTINGUISHABLE from real photographs.

CHARACTER — "lily":
- Young woman, early-mid 20s
- Medium brown wavy hair, shoulder length to just past shoulders
- Natural freckles across nose and cheeks
- Brown/hazel eyes, warm tone
- Slim/petite natural build, small-medium natural breasts
- Natural beauty — no heavy makeup, no plastic surgery look
- Her vibe: confident, warm, natural sex appeal — "girl next door who knows she's attractive"

CHROMA PROMPT FORMAT (strict):
Line 1: IMG_XXXX.HEIC (random 4-digit number, different each time)
Line 2: blank
Line 3+: Natural language paragraph, 75-150 T5 tokens. Full sentences only. NO comma-separated tags. NO SD-era keywords (masterpiece, best quality, ultrarealistic, etc).

STRUCTURE of the paragraph:
"An image of lily [action/pose]. [Body details, expression, hair, clothing]. [Scene: location, lighting, background]. [Camera angle/framing]."

MANDATORY RULES:
1. ALWAYS describe lighting explicitly (golden hour, warm lamp, soft window light, etc)
2. ALWAYS describe what she is wearing or not wearing — be specific about fabrics, colors, fit
3. ALWAYS include camera/shot description (phone snapshot, slightly above, POV, eye level, etc)
4. Include natural imperfections: slightly messy hair, a wrinkle in fabric, overexposed highlights
5. Use "phone snapshot", "casual selfie", "candid" language for amateur realism
6. NEVER use: masterpiece, best quality, ultrarealistic, extremely detailed, 4k, 8k, HDR
7. NEVER use comma-separated tag lists — full natural sentences only
8. Each prompt must be UNIQUE — different pose, setting, outfit, lighting, mood, angle
9. Keep between 80-140 words per prompt (not counting the IMG line)

EXPRESSION & ENERGY:
- Vary expressions: relaxed smile, seductive gaze, laughing, looking away thoughtfully,
  slightly parted lips, biting lower lip, confident stare, playful smirk, sleepy/morning eyes
- For intimate/NSFW: "bedroom eyes", "intimate gaze into camera", "she knows she's being watched"
- Avoid dead/neutral expressions — every shot needs emotional energy

PHOTOREALISM TRICKS (use naturally, don't force all into every prompt):
- IMG_XXXX.HEIC filename anchor (already required)
- "phone propped on [surface]" for self-filmed
- "screenshot quality — like a frame captured from a vertical video"
- "slightly overexposed highlights from [light source]"
- "shallow depth of field" / "background slightly out of focus"
- Mention specific real-world details: brand names, specific locations, time of day

OUTPUT FORMAT:
Return ONLY a JSON array of prompt strings. No explanations, no numbering, no markdown.
Each string is the COMPLETE prompt including the IMG_XXXX.HEIC line.
Example element:
"IMG_3291.HEIC\\n\\nAn image of lily looking directly into the camera with a relaxed half-smile. Her medium brown wavy hair falls past her shoulders, a few strands catching the light. Natural freckles visible across her nose and cheeks. She is wearing a simple white cotton t-shirt with a round neckline. Warm golden hour sunlight coming from a window to the left, casting soft shadows on the right side of her face. Shallow depth of field, the background is a blurred out living room with warm tones. Casual phone snapshot aesthetic, slightly overexposed highlights from the window."
"""

# ─── Category Definitions ─────────────────────────────────────────────────────
# Distribution designed for v002 LoRA training + OFM commercial viability

CATEGORIES = [
    {
        "name": "close_up_portrait",
        "count": 12,
        "lane": "sfw",
        "instruction": """Generate {count} CLOSE-UP PORTRAIT prompts (face, neck, shoulders only).
Focus on: varied expressions (smile, thoughtful, laughing, seductive gaze, sleepy morning face),
varied lighting (golden hour, overcast, indoor lamp, bathroom mirror light, ring light selfie),
varied hair states (messy morning hair, wet after shower, pulled back, loose and windblown).
Clothing visible: t-shirt necklines, tank tops, off-shoulder, bare shoulders with blanket/towel.
Settings: bedroom, bathroom, living room, car, balcony, café.
Camera: selfie angle, phone held slightly above, mirror reflection, someone across table."""
    },
    {
        "name": "upper_body_casual",
        "count": 15,
        "lane": "sfw",
        "instruction": """Generate {count} UPPER BODY CASUAL prompts (head to waist/hips).
Everyday life scenes: coffee shop, kitchen cooking, reading on couch, working on laptop,
sitting on bed with phone, walking through market, eating ice cream, riding in car passenger seat.
Outfits: oversized hoodie, crop top and jeans, sundress, denim jacket, band tee, workout top.
Show natural body language: leaning forward, stretching, tucking hair behind ear, holding coffee cup.
Mix of looking at camera and candid/caught-off-guard moments."""
    },
    {
        "name": "upper_body_fashion",
        "count": 10,
        "lane": "sfw",
        "instruction": """Generate {count} UPPER BODY FASHION/EDITORIAL prompts.
More styled than casual: date night outfit, elegant dinner, rooftop bar, gallery opening.
Outfits: fitted dress, silk camisole, blazer over bra, backless top, off-shoulder sweater.
Accessories: delicate gold jewelry, sunglasses pushed up on head, small earrings.
Lighting: restaurant ambient, sunset rooftop, neon reflections, candlelight.
Confident energy: she's dressed up and knows she looks good. Subtle sex appeal through styling."""
    },
    {
        "name": "full_body_street",
        "count": 12,
        "lane": "sfw",
        "instruction": """Generate {count} FULL BODY STREET/TRAVEL prompts.
Settings: European cobblestone streets, NYC sidewalk, beach boardwalk, park path, metro station.
Outfits: high-waisted jeans + crop top, mini skirt + boots, summer dress, athleisure.
Poses: walking toward camera, leaning against wall, sitting on steps, standing at railing.
Include environmental details: café tables, bicycles, street signs, potted plants, puddles.
Natural movement energy — not stiff posing. Shot by friend with phone aesthetic."""
    },
    {
        "name": "full_body_lifestyle",
        "count": 8,
        "lane": "sfw",
        "instruction": """Generate {count} FULL BODY LIFESTYLE/ACTIVITY prompts.
Activities: yoga on balcony, stretching in park, dancing in kitchen, surfing/beach walk,
hiking trail, farmers market shopping, riding bicycle.
Athletic/casual outfits: bikini top + shorts, yoga pants + sports bra, swimsuit, short shorts.
These show body in motion/activity context — natural and aspirational.
Golden hour and natural outdoor lighting preferred. Candid energy."""
    },
    {
        "name": "selfie_mirror",
        "count": 8,
        "lane": "sfw",
        "instruction": """Generate {count} SELFIE / MIRROR SHOT prompts.
Classic Instagram content: bathroom mirror selfie, gym mirror, fitting room, bedroom full-length mirror.
Phone visible in hand or propped up. Screen glow on face for night selfies.
Outfits range from casual (gym clothes, pajamas) to going-out (mini dress, heels visible).
Include mirror-specific details: slightly steamy mirror, bathroom tiles, ring light reflection.
Caption-ready energy — these are "posting on stories" moments."""
    },
    {
        "name": "lingerie_intimate",
        "count": 20,
        "lane": "nsfw",
        "instruction": """Generate {count} LINGERIE / INTIMATE APPAREL prompts.
Lingerie types: black lace bralette, white cotton underwear set, silk chemise, sheer bodysuit,
matching set with garter belt, oversized men's shirt unbuttoned, lace thong + cropped tank.
Settings: bedroom (rumpled white sheets, warm lamp), hotel room, bathroom after shower.
Poses: sitting on edge of bed, lying on stomach looking back, standing by window, kneeling on bed.
Expression: seductive but natural — "just woke up", "getting ready for bed", "lazy Sunday morning".
Lighting: warm bedside lamp, morning window light through sheer curtains, golden hour bedroom.
Show natural body — subtle cleavage, visible waist/hips, bare legs. NOT plastic or exaggerated.
Camera: phone propped on nightstand, selfie angle, shot from slightly above."""
    },
    {
        "name": "boudoir_bedroom",
        "count": 18,
        "lane": "nsfw",
        "instruction": """Generate {count} BOUDOIR / BEDROOM prompts.
More intimate than lingerie — partially undressed, implied nudity, teasing.
Scenarios: tangled in sheets with bare shoulders visible, pulling off t-shirt, towel dropping,
wearing only underwear bottom and covering chest with arm/hand, lying in bed with sheet
draped over hips, sitting up in bed bare-shouldered with messy hair.
Expression: intimate gaze into camera, slightly parted lips, sleepy seductive, post-shower glow.
Lighting: ALWAYS warm — bedside lamp, candles, golden morning light, sunset through blinds.
These are "private moment" shots — intimate, personal, real girlfriend aesthetic.
Camera: POV angle (as if partner is looking at her), phone selfie in bed, slightly below eye level."""
    },
    {
        "name": "topless_artistic",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} TOPLESS / ARTISTIC NUDE prompts.
Natural, tasteful but explicitly showing breasts. Small-medium natural breasts, no implant look.
Scenarios: standing by window in morning light topless in just underwear, lying on bed completely
topless, sitting cross-legged on floor topless, shower scene with wet skin and hair,
getting dressed — caught between outfits, poolside/beach topless.
Hair states: wet from shower, messy bed hair, blown by breeze, tucked behind ears.
Expression: confident and comfortable with her body, natural smile, direct eye contact,
looking away candidly, laughing.
Lighting: emphasize skin texture and natural shadows — side lighting, rim light, dappled sun.
Camera: medium shot, slightly above, eye level, profile view, three-quarter angle.
Keep it REAL — visible freckles on chest/shoulders, natural skin texture, no airbrushed look."""
    },
    {
        "name": "suggestive_teasing",
        "count": 15,
        "lane": "nsfw",
        "instruction": """Generate {count} SUGGESTIVE / TEASING prompts.
The "almost showing" category — maximum anticipation, strategic coverage.
Scenarios: pulling down jeans showing hip bones and underwear band, shirt lifted showing underboob,
looking over shoulder with bare back visible, lying face down on bed with side of breast visible,
wearing boyfriend's oversized shirt that barely covers, wet white t-shirt, hand inside underwear
(implied), biting lip while looking at camera, arching back on bed.
Clothing: oversized shirts, barely-there crop tops, low-rise everything, sheer fabrics.
Expression: playful, teasing, "come here" energy, knowing smirk, biting lower lip.
Camera: POV, slightly below (looking up at her), close crop on torso/hips.
This category is about TENSION and ANTICIPATION — not full reveal."""
    },
    {
        "name": "explicit_fanvue",
        "count": 17,
        "lane": "nsfw",
        "instruction": """Generate {count} EXPLICIT / FANVUE-TIER prompts.
Full nudity, explicit poses — this is premium paywall content.
Scenarios: completely naked on bed in various poses, nude selfie in bathroom mirror,
naked lying on stomach with legs up behind her, spread on bed with nothing hidden,
sitting naked on kitchen counter, nude by pool/bath, straddling position on bed.
Full body visibility: breasts, stomach, hips, thighs all visible. Natural small-medium breasts.
Expression: direct sexual energy — bedroom eyes, parted lips, intense gaze, orgasmic expression,
biting lip, head tilted back.
Lighting: warm intimate lighting always — lamp, candles, window. Never harsh/clinical.
Camera: phone selfie, POV (partner perspective), propped phone angle from below,
mirror reflection showing full body.
Keep REAL: natural body, visible freckles, real skin texture, no plastic perfection.
These must feel like real private photos shared with a partner — NOT studio pornography."""
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

            # Parse JSON response
            prompts = json.loads(text)

            # Handle nested structure if Gemini wraps in an object
            if isinstance(prompts, dict):
                # Find the array in the dict
                for v in prompts.values():
                    if isinstance(v, list):
                        prompts = v
                        break

            if not isinstance(prompts, list):
                print(f"  WARNING: unexpected response type: {type(prompts)}, retrying...")
                continue

            # Validate each prompt
            valid = []
            for p in prompts:
                if isinstance(p, str) and "lily" in p.lower():
                    # Ensure IMG_ prefix exists
                    if not p.startswith("IMG_"):
                        img_num = random.randint(1000, 9999)
                        p = f"IMG_{img_num}.HEIC\n\n{p}"
                    valid.append(p)
                elif isinstance(p, dict):
                    # Sometimes Gemini returns objects with prompt field
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("LILY V002 DATASET PROMPT GENERATOR")
    print("=" * 70)

    total_expected = sum(c["count"] for c in CATEGORIES)
    print(f"\nTarget: {total_expected} prompts across {len(CATEGORIES)} categories")
    print(f"Model: {GEMINI_MODEL}")
    print(f"Output: {OUTPUT_FILE}\n")

    # Print distribution
    print("Distribution:")
    sfw_count = sum(c["count"] for c in CATEGORIES if c["lane"] == "sfw")
    nsfw_count = sum(c["count"] for c in CATEGORIES if c["lane"] == "nsfw")
    print(f"  SFW:  {sfw_count} ({sfw_count/total_expected*100:.0f}%)")
    print(f"  NSFW: {nsfw_count} ({nsfw_count/total_expected*100:.0f}%)")
    print()

    for cat in CATEGORIES:
        print(f"  [{cat['lane'].upper():4s}] {cat['name']:25s} → {cat['count']} prompts")
    print()

    # Generate
    all_prompts = []
    metadata = {
        "version": "v002",
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

        # Tag each prompt with metadata
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

        # Rate limit — be nice to the API
        if i < len(CATEGORIES) - 1:
            time.sleep(2)

    # Deduplicate by IMG number (regenerate if collision)
    used_img_nums = set()
    for item in all_prompts:
        # Extract IMG number
        prompt = item["prompt"]
        if prompt.startswith("IMG_"):
            num_str = prompt[4:8]
            if num_str in used_img_nums:
                # Regenerate unique number
                new_num = random.randint(1000, 9999)
                while str(new_num) in used_img_nums:
                    new_num = random.randint(1000, 9999)
                item["prompt"] = f"IMG_{new_num}" + prompt[8:]
                num_str = str(new_num)
            used_img_nums.add(num_str)

    # Shuffle to mix categories
    random.shuffle(all_prompts)

    # Add index
    for i, item in enumerate(all_prompts):
        item["index"] = i

    metadata["total_generated"] = len(all_prompts)

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
            "scheduler": "beta",
            "scheduler_alpha": 0.45,
            "scheduler_beta": 0.45,
            "lora_strength_model": 1.5,
            "lora_strength_clip": 1.0,
            "pulid_strength": 0.8,
        },
        "prompts": all_prompts,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print()
    print("=" * 70)
    print(f"DONE — {len(all_prompts)}/{total_expected} prompts generated")
    print(f"Saved to: {OUTPUT_FILE}")
    print("=" * 70)

    # Print sample
    print("\n--- Sample prompts ---\n")
    samples = random.sample(all_prompts, min(3, len(all_prompts)))
    for s in samples:
        print(f"[{s['category']} / {s['lane']}]")
        print(s["prompt"])
        print()


if __name__ == "__main__":
    main()
