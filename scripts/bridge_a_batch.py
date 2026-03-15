#!/usr/bin/env python3
"""
Stage A Bridge: batch generation with IP-Adapter + reference photo.
Generates 20 portraits on FLUX.1 Dev to find dev-native canonical face.
"""
import json
import urllib.request
import time

BASE_URL = "http://localhost:8188"

# Shot distribution per plan: 40% close-up, 30% 3/4, 20% medium, 10% varied
# 20 images: 8 close-up, 6 three-quarter, 4 medium, 2 varied lighting
# HEIC filename trick: strongest photorealism anchor for FLUX (trained on camera filenames)
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

SEEDS = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000]

REF_IMAGE = "reference.png"
IPA_WEIGHT = 0.6


def build_workflow(prompt_text, seed):
    return {
        "1":  {"class_type": "UNETLoader",           "inputs": {"unet_name": "flux1-dev-fp8.safetensors", "weight_dtype": "default"}},
        "2":  {"class_type": "DualCLIPLoader",        "inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}},
        "3":  {"class_type": "VAELoader",             "inputs": {"vae_name": "ae.safetensors"}},
        "4":  {"class_type": "CLIPTextEncode",        "inputs": {"text": prompt_text, "clip": ["2", 0]}},
        "5":  {"class_type": "FluxGuidance",          "inputs": {"conditioning": ["4", 0], "guidance": 3.5}},
        "15": {"class_type": "LoadImage",             "inputs": {"image": REF_IMAGE}},
        "16": {"class_type": "IPAdapterFluxLoader",   "inputs": {"ipadapter": "ip-adapter.bin", "clip_vision": "google/siglip-so400m-patch14-384", "provider": "cuda"}},
        "17": {"class_type": "ApplyIPAdapterFlux",    "inputs": {"model": ["1", 0], "ipadapter_flux": ["16", 0], "image": ["15", 0], "weight": IPA_WEIGHT, "start_percent": 0.0, "end_percent": 1.0}},
        "6":  {"class_type": "BasicGuider",           "inputs": {"model": ["17", 0], "conditioning": ["5", 0]}},
        "7":  {"class_type": "EmptyLatentImage",      "inputs": {"width": 576, "height": 1024, "batch_size": 1}},
        "8":  {"class_type": "BasicScheduler",        "inputs": {"model": ["17", 0], "scheduler": "simple", "steps": 25, "denoise": 1.0}},
        "9":  {"class_type": "KSamplerSelect",        "inputs": {"sampler_name": "euler"}},
        "10": {"class_type": "RandomNoise",           "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["6", 0], "sampler": ["9", 0], "sigmas": ["8", 0], "latent_image": ["7", 0]}},
        "12": {"class_type": "VAEDecode",             "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage",             "inputs": {"images": ["12", 0], "filename_prefix": "bridge_a"}},
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
    # Copy reference to ComfyUI input if needed
    import shutil, os
    ref_src = "/workspace/refs/characters/chara/reference.png"
    ref_dst = "/workspace/input/reference.png"
    if not os.path.exists(ref_dst):
        shutil.copy(ref_src, ref_dst)
        print(f"Copied reference to {ref_dst}")

    # Queue all jobs — each seed maps to its own prompt (1:1, no cycling)
    jobs = []
    for i, seed in enumerate(SEEDS):
        prompt = PROMPTS[i]
        wf = build_workflow(prompt, seed)
        pid = queue_job(wf)
        jobs.append(pid)
        print(f"Queued {i+1}/{len(SEEDS)}: seed={seed}")

    print(f"\nAll {len(SEEDS)} jobs queued. Waiting for results...\n")

    # Wait for completion
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
    print(f"Images saved to /workspace/outputs/")


if __name__ == "__main__":
    main()
