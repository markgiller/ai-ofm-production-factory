#!/usr/bin/env python3
"""
Stage A Bridge: batch generation with IP-Adapter + reference photo.
Generates 20 portraits on FLUX.1 Dev to find dev-native canonical face.
"""
import json
import urllib.request
import time

BASE_URL = "http://localhost:8188"

PROMPTS = [
    "A candid raw photo of a young woman, close-up portrait, soft natural window light, shot on Canon EOS R5 85mm f/1.8",
    "A candid raw photo of a young woman, 3/4 portrait, golden hour sunlight, shot on Sony A7IV 50mm f/1.4",
    "A candid raw photo of a young woman, close-up portrait, overcast soft light, shot on Fujifilm X-T5 56mm f/1.2",
    "A candid raw photo of a young woman, medium portrait, cafe interior warm light, shot on Leica Q2",
    "A candid raw photo of a young woman, close-up portrait, studio soft light, neutral background, shot on Canon EOS R5",
    "A candid raw photo of a young woman, 3/4 portrait, blue hour outdoor light, shot on Nikon Z8 85mm f/1.8",
    "A candid raw photo of a young woman, close-up portrait, dappled forest light, shot on Sony A7IV 35mm f/1.4",
    "A candid raw photo of a young woman, medium portrait, urban street daylight, shot on iPhone 15 Pro",
]

SEEDS = [42, 137, 256, 512, 1024, 2048, 7777, 9999, 11111, 31337, 54321, 77777, 88888, 99999, 12345, 23456, 34567, 45678, 56789, 67890]

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
        "17": {"class_type": "ApplyIPAdapterFlux",    "inputs": {"model": ["1", 0], "ip_adapter_flux": ["16", 0], "image": ["15", 0], "weight": IPA_WEIGHT, "start_percent": 0.0, "end_percent": 1.0}},
        "6":  {"class_type": "BasicGuider",           "inputs": {"model": ["17", 0], "conditioning": ["5", 0]}},
        "7":  {"class_type": "EmptyLatentImage",      "inputs": {"width": 576, "height": 1024, "batch_size": 1}},
        "8":  {"class_type": "BasicScheduler",        "inputs": {"model": ["17", 0], "scheduler": "simple", "steps": 20, "denoise": 1.0}},
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

    # Queue all jobs
    jobs = []
    for i, seed in enumerate(SEEDS):
        prompt = PROMPTS[i % len(PROMPTS)]
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
                imgs = h[pid]["outputs"]["13"]["images"]
                fname = imgs[0]["filename"]
                done.append(pid)
                print(f"Done {len(done)}/{len(SEEDS)}: {fname}")

    print("\nBATCH COMPLETE")
    print(f"Images saved to /workspace/outputs/")


if __name__ == "__main__":
    main()
