#!/usr/bin/env python3
"""Quick test: submit embedded workflow to ComfyUI API and print error."""
import json, urllib.request, urllib.error

wf = {
    "58": {"class_type": "LoadImage", "inputs": {"image": "05.png"}},
    "172": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
    "178": {"class_type": "SaveImage", "inputs": {"filename_prefix": "test_debug", "images": ["477", 0]}},
    "204": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_2s"}},
    "206": {"class_type": "CFGGuider", "inputs": {"cfg": 3.2, "model": ["429", 0], "positive": ["425", 0], "negative": ["370", 0]}},
    "207": {"class_type": "RandomNoise", "inputs": {"noise_seed": 100500}},
    "208": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["207", 0], "guider": ["433", 0], "sampler": ["204", 0], "sigmas": ["484", 0], "latent_image": ["479", 0]}},
    "251": {"class_type": "ttN text", "inputs": {"text": "A photo of lily smiling"}},
    "364": {"class_type": "CLIPTextEncode", "inputs": {"text": ["251", 0], "clip": ["367", 0]}},
    "366": {"class_type": "CLIPLoader", "inputs": {"clip_name": "t5xxl_fp8_e4m3fn.safetensors", "type": "chroma", "device": "default"}},
    "367": {"class_type": "T5TokenizerOptions", "inputs": {"min_padding": 1, "min_length": 0, "clip": ["366", 0]}},
    "370": {"class_type": "CLIPTextEncode", "inputs": {"text": ["468", 0], "clip": ["367", 0]}},
    "385": {"class_type": "ApplyPulidFlux", "inputs": {"weight": 1, "start_at": 0, "end_at": 0.55, "fusion": "train_weight", "fusion_weight_max": 1, "fusion_weight_min": 0, "train_step": 8000, "use_gray": True, "model": ["482", 0], "pulid_flux": ["386", 0], "eva_clip": ["391", 0], "face_analysis": ["392", 0], "image": ["58", 0], "prior_image": ["58", 0]}},
    "386": {"class_type": "PulidFluxModelLoader", "inputs": {"pulid_file": "pulid_flux_v0.9.0.safetensors"}},
    "391": {"class_type": "PulidFluxEvaClipLoader", "inputs": {}},
    "392": {"class_type": "PulidFluxInsightFaceLoader", "inputs": {"provider": "CPU"}},
    "425": {"class_type": "unCLIPConditioning", "inputs": {"strength": 10, "noise_augmentation": 0, "conditioning": ["364", 0], "clip_vision_output": ["426", 0]}},
    "426": {"class_type": "CLIPVisionEncode", "inputs": {"crop": "none", "clip_vision": ["436", 0], "image": ["439", 0]}},
    "429": {"class_type": "ModelSamplingFlux", "inputs": {"max_shift": 1, "base_shift": 0.5, "width": 768, "height": 1024, "model": ["385", 0]}},
    "433": {"class_type": "easy cleanGpuUsed", "inputs": {"anything": ["206", 0]}},
    "436": {"class_type": "AdvancedVisionLoader", "inputs": {"clip_name": "siglip2-so400m-patch16-512.safetensors"}},
    "437": {"class_type": "easy imageRemBg", "inputs": {"rem_mode": "RMBG-1.4", "image_output": "Preview", "save_prefix": "ComfyUI", "torchscript_jit": False, "add_background": "none", "refine_foreground": False, "images": ["58", 0]}},
    "439": {"class_type": "PrepImageForClipVisionV2", "inputs": {"interpolation": "LANCZOS", "crop_position": "center", "sharpening": 0, "image": ["437", 0]}},
    "441": {"class_type": "PreviewImage", "inputs": {"images": ["439", 0]}},
    "468": {"class_type": "ttN text", "inputs": {"text": "low quality ugly blurry"}},
    "469": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "Hyper-Chroma-low-step-LoRA.safetensors", "strength_model": 1.0, "model": ["481", 0]}},
    "477": {"class_type": "VAEDecode", "inputs": {"samples": ["208", 0], "vae": ["172", 0]}},
    "479": {"class_type": "EmptyLatentImage", "inputs": {"width": 768, "height": 1024, "batch_size": 1}},
    "481": {"class_type": "UNETLoader", "inputs": {"unet_name": "Chroma1-HD.safetensors", "weight_dtype": "fp8_e4m3fn"}},
    "482": {"class_type": "LoraLoaderModelOnly", "inputs": {"lora_name": "lora_lily_chroma_v001.safetensors", "strength_model": 1.5, "model": ["469", 0]}},
    "484": {"class_type": "SigmoidOffsetScheduler", "inputs": {"steps": 20, "square_k": 1, "base_c": 0.5, "model": ["429", 0]}}
}

payload = json.dumps({"prompt": wf}).encode()
req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=payload, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req)
    print("SUCCESS:", resp.read().decode()[:500])
except urllib.error.HTTPError as e:
    print(f"ERROR {e.code}:", e.read().decode()[:2000])
except Exception as e:
    print("EXCEPTION:", e)
