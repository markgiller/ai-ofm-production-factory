#!/usr/bin/env python3
"""
Stage A Bridge (v4): batch generation with PuLID-FLUX + reference photo.
Generates 20 portraits on FLUX.1 Dev — PuLID provides face identity injection.
"""
import json
import urllib.request
import time

BASE_URL = "http://localhost:8188"

# Shot distribution: 40% close-up, 30% 3/4, 20% medium, 10% varied
PROMPTS = [
    # 8 close-up portraits (40%)
    "IMG_0142.HEIC, a candid raw photo of a young woman, extreme close-up portrait, face fills frame, soft natural window light, shallow depth of field, shot on Canon EOS R5 85mm f/1.8",
    "IMG_0317.HEIC, a candid raw photo of a young woman, close-up portrait, warm golden hour light from the side, skin texture visible, shot on Sony A7IV 85mm f/1.4",
    "IMG_0521.HEIC, a candid raw photo of a young woman, close-up portrait, overcast diffused light, neutral expression, shot on Fujifilm X-T5 56mm f/1.2",
    "IMG_0634.HEIC, a candid raw photo of a young woman, close-up portrait, soft studio light, white background, shot on Canon EOS R5 50mm f/1.2",
    "IMG_0789.HEIC, a candid raw photo of a young woman, close-up portrait, dappled natural light, outdoors, shot on Sony A7IV 35mm f/1.4",
    "IMG_0901.HEIC, a candid raw photo of a young woman, close-up portrait, blue hour soft light, slight bokeh, shot on Nikon Z8 85mm f/1.8",
    "IMG_1023.HEIC, a candid raw photo of a young woman, close-up portrait, warm cafe interior light, slightly low angle, shot on Leica Q2",
    "IMG_1156.HEIC, a candid raw photo of a young woman, close-up portrait, bright overcast outdoor light, looking slightly off camera, shot on Fujifilm X-T5",
    # 6 three-quarter portraits (30%)
    "IMG_1204.HEIC, a candid raw photo of a young woman, 3/4 portrait, head and shoulders, golden hour backlight, shot on Canon EOS R5 85mm f/1.8",
    "IMG_1388.HEIC, a candid raw photo of a young woman, 3/4 portrait, natural window light from left, indoor setting, shot on Sony A7IV 50mm f/1.4",
    "IMG_1452.HEIC, a candid raw photo of a young woman, 3/4 portrait, soft overcast outdoor light, relaxed pose, shot on Nikon Z8 85mm f/1.8",
    "IMG_1567.HEIC, a candid raw photo of a young woman, 3/4 portrait, warm afternoon light, slight smile, shot on Fujifilm X-T5 56mm f/1.2",
    "IMG_1623.HEIC, a candid raw photo of a young woman, 3/4 portrait, studio softbox light, clean background, shot on Canon EOS R5",
    "IMG_1744.HEIC, a candid raw photo of a young woman, 3/4 portrait, blue hour outdoor, city background slightly blurred, shot on Sony A7IV",
    # 4 medium shots (20%)
    "IMG_1812.HEIC, a candid raw photo of a young woman, medium shot waist up, sitting at a cafe table, warm indoor light, shot on Leica Q2",
    "IMG_1934.HEIC, a candid raw photo of a young woman, medium shot, standing outdoors, urban background, natural daylight, shot on iPhone 15 Pro",
    "IMG_2001.HEIC, a candid raw photo of a young woman, medium shot, leaning against a wall, soft overcast light, shot on Canon EOS R5 35mm f/1.8",
    "IMG_2087.HEIC, a candid raw photo of a young woman, medium shot, sitting on steps, golden hour light, relaxed pose, shot on Sony A7IV",
    # 2 varied lighting/expression (10%)
    "IMG_2134.HEIC, a candid raw photo of a young woman, close-up portrait, dramatic side lighting, one side of face lit, shot on Canon EOS R5 85mm f/1.4",
    "IMG_2256.HEIC, a candid raw photo of a young woman, 3/4 portrait, overcast soft light, laughing expression, natural moment, shot on Fujifilm X-T5",
]

SEEDS = [5000, 5100, 5200, 5300, 5400, 5500, 5600, 5700, 5800, 5900,
         6000, 6100, 6200, 6300, 6400, 6500, 6600, 6700, 6800, 6900]

REF_IMAGE = "reference.png"
PULID_WEIGHT = 0.9  # 0.9 = strong identity, still allows scene/lighting diversity


def build_workflow(prompt_text, seed):
    return {
        "1":  {"class_type": "UNETLoader",           "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}},
        "2":  {"class_type": "DualCLIPLoader",        "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3":  {"class_type": "VAELoader",             "inputs": {"vae_name": "ae.safetensors"}},
        "4":  {"class_type": "CLIPTextEncode",        "inputs": {"text": prompt_text, "clip": ["2", 0]}},
        "5":  {"class_type": "FluxGuidance",          "inputs": {"conditioning": ["4", 0], "guidance": 3.5}},
        "14": {"class_type": "PulidFluxModelLoader",  "inputs": {"pulid_file": "pulid_flux_v0.9.1.safetensors"}},
        "15": {"class_type": "LoadImage",             "inputs": {"image": REF_IMAGE}},
        "16": {"class_type": "PulidFluxEvaClipLoader","inputs": {}},
        "17": {"class_type": "PulidFluxFaceNetLoader","inputs": {"provider": "CUDA"}},
        "18": {"class_type": "ApplyPulidFlux",        "inputs": {"model": ["1", 0], "pulid_flux": ["14", 0], "eva_clip": ["16", 0], "face_analysis": ["17", 0], "image": ["15", 0], "weight": PULID_WEIGHT, "start_at": 0.0, "end_at": 1.0}},
        "6":  {"class_type": "BasicGuider",           "inputs": {"model": ["18", 0], "conditioning": ["5", 0]}},
        "7":  {"class_type": "EmptyLatentImage",      "inputs": {"width": 576, "height": 1024, "batch_size": 1}},
        "8":  {"class_type": "BasicScheduler",        "inputs": {"model": ["18", 0], "scheduler": "simple", "steps": 25, "denoise": 1.0}},
        "9":  {"class_type": "KSamplerSelect",        "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise",           "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["6", 0], "sampler": ["9", 0], "sigmas": ["8", 0], "latent_image": ["7", 0]}},
        "12": {"class_type": "VAEDecode",             "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",             "inputs": {"images": ["12", 0], "filename_prefix": "bridge_d"}},
    }


def queue_job(workflow):
    data = json.dumps({"prompt": workflow}).encode()
    req = urllib.request.Request(BASE_URL + "/prompt", data=data, headers={"Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req).read())
    except urllib.error.HTTPError as e:
        print("ERROR:", e.read().decode())
        raise
    return resp["prompt_id"]


def main():
    import shutil, os
    ref_src = "/workspace/refs/characters/chara/reference.png"
    ref_dst = "/workspace/input/reference.png"
    if not os.path.exists(ref_dst):
        shutil.copy(ref_src, ref_dst)
        print(f"Copied reference to {ref_dst}")

    print(f"PuLID weight: {PULID_WEIGHT} | Reference: {REF_IMAGE}")

    jobs = []
    for i, seed in enumerate(SEEDS):
        prompt = PROMPTS[i]
        wf = build_workflow(prompt, seed)
        pid = queue_job(wf)
        jobs.append(pid)
        print(f"Queued {i+1}/{len(SEEDS)}: seed={seed}")

    print(f"\nAll {len(SEEDS)} jobs queued. Waiting for results...\n")

    done = []
    while len(done) < len(jobs):
        time.sleep(5)
        for pid in jobs:
            if pid in done:
                continue
            h = json.loads(urllib.request.urlopen(BASE_URL + "/history/" + pid).read())
            if pid in h:
                entry = h[pid]
                if entry.get("status", {}).get("status_str") == "error":
                    msgs = entry["status"].get("messages", [])
                    print(f"ERROR job {pid}: {msgs}")
                    done.append(pid)
                elif "13" in entry.get("outputs", {}):
                    fname = entry["outputs"]["13"]["images"][0]["filename"]
                    done.append(pid)
                    print(f"Done {len(done)}/{len(SEEDS)}: {fname}")

    print("\nBATCH COMPLETE")
    print(f"Images saved to /workspace/outputs/bridge_d_*.png")


if __name__ == "__main__":
    main()
