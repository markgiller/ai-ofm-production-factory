# LoRA Training — Chroma 1 HD + OneTrainer on RunPod

Complete SOP for training a character LoRA on Chroma 1 HD using OneTrainer on a RunPod GPU pod.

---

## 1. Pod Configuration

**Template:** PyTorch (NOT ComfyUI — ComfyUI is PID1, killing it kills SSH)

| Setting | Value |
|---------|-------|
| GPU | RTX 5090 (32GB VRAM) — preferred; RTX 4090 (24GB) works at batch_size=1 |
| Container image | `runpod/pytorch:2.8.0-py3.11-cuda12.8.1-cudnn-devel-ubuntu22.04` |
| Container disk | **100GB** — all training writes go here (no MFS quota issues) |
| Network volume | `ofm_staging_volume` — attach for dataset + model access |

**Critical:** RTX 5090 requires PyTorch 2.8+. Use the image above exactly.

**Critical:** Container disk must be 100GB+. The 30GB container disk causes `OSError: [Errno 122] Disk quota exceeded` on MFS writes (TensorBoard, HF cache). Even though `df -h` shows free space, the MFS network volume has per-operation quota limits for large sequential writes.

---

## 2. Network Volume Structure

Dataset and models live on network volume (`/workspace`). All training writes go to container disk (`/root/`).

```
/workspace/
├── lora_training/
│   └── lily_v001/
│       ├── img/           ← dataset images + captions (READ ONLY during training)
│       ├── config.json    ← OneTrainer config
│       ├── concepts.json  ← dataset concept definition
│       └── samples.json   ← sample prompts
├── models/
│   ├── unet/              ← Chroma fp8 for ComfyUI inference
│   ├── loras/             ← output LoRA saved here after training
│   └── ...
└── OneTrainer/            ← DO NOT install here (MFS write issues)
```

---

## 3. OneTrainer Installation

Install on container disk (not network volume):

```bash
cd /root && git clone https://github.com/Nerogar/OneTrainer.git && cd OneTrainer
chmod +x install.sh && ./install.sh
```

Installation takes ~5-10 minutes. Verify:
```bash
ls /root/OneTrainer/venv/bin/python
```

---

## 4. Install tmux

**Always run `apt-get update` first** — package index is stale on fresh containers:

```bash
apt-get update && apt-get install -y tmux
```

---

## 5. Patch Config Paths

The config.json was generated on previous pod with `/workspace` paths for workspace_dir and cache_dir.
These must be redirected to container disk (`/root/`) to avoid MFS quota errors:

```bash
python3 -c "
import json
config_path = '/workspace/lora_training/lily_v001/config.json'
with open(config_path, 'r') as f:
    cfg = json.load(f)
cfg['workspace_dir'] = '/root/lora_workspace'
cfg['cache_dir'] = '/root/lora_cache'
cfg['output_model_destination'] = '/workspace/models/loras/lora_lily_chroma_v001.safetensors'
with open(config_path, 'w') as f:
    json.dump(cfg, f, indent=2)
print('Done:', cfg['workspace_dir'], cfg['cache_dir'], cfg['output_model_destination'])
"
```

---

## 6. Launch Training in tmux

```bash
tmux new-session -s training
```

Inside tmux:
```bash
HF_HOME=/root/hf_cache /root/OneTrainer/run-cmd.sh train --config-path /workspace/lora_training/lily_v001/config.json
```

**HF_HOME=/root/hf_cache** is mandatory — without it HuggingFace downloads ~33GB to container root overlay which has quota limits.

Detach from tmux (leave training running): `Ctrl+B` then `D`

Reattach: `tmux attach -t training`

---

## 7. Training Parameters (lora_lily_chroma_v001)

| Parameter | Value | Reason |
|-----------|-------|--------|
| base_model | `lodestones/Chroma1-HD` (HF diffusers) | MUST be diffusers format — single safetensors NOT supported |
| model_type | `CHROMA_1` | |
| lora_rank | 32 | Standard for character identity |
| resolution | 1024 | Dataset images are 824×1024 |
| batch_size | 2 | 32GB VRAM allows it; use 1 for 24GB |
| epochs | 150 | = ~2700 steps (36 imgs / batch 2 = 18 steps/epoch) |
| learning_rate | **6e-5** | Chroma is MORE sensitive than FLUX — preset 0.0003 breaks it |
| lr_scheduler | COSINE | Community consensus |
| lr_warmup_steps | 100 | |
| timestep_distribution | INVERTED_PARABOLA | |
| noising_weight | 7.7 | |
| layer_filter | `attn,ff.net` | attn-mlp preset |
| transformer | train=True, BF16 | |
| text_encoder | train=False | |
| save_every | 500 steps | |
| output_dtype | BFLOAT_16 | |

**Step math:** 36 images / batch_size 2 = 18 steps/epoch × 150 epochs = 2700 steps total.
Community sweet spot for character LoRA: 2500–3500 steps at batch=2.

---

## 8. What Gets Downloaded (HF_HOME)

`lodestones/Chroma1-HD` downloads ~33GB total:
- transformer: ~10GB + ~8GB (two shards)
- text_encoder: ~10GB + ~8GB (two shards)
- vae: ~168MB

First training run takes ~3 minutes just to download. Subsequent runs on same pod use cache.

---

## 9. Monitoring

Check progress from outside tmux:
```bash
tmux attach -t training
```

Or if logging to file (nohup variant):
```bash
tail -f /root/training.log
```

First checkpoint saved at step 500 to `/workspace/models/loras/lora_lily_chroma_v001.safetensors`.
Intermediate checkpoints: same location with step suffix (configurable).

---

## 10. Network Volume Cleanup (before new training pod)

Items safe to delete:
```bash
rm -rf /workspace/hf_cache          # re-downloads to /root/hf_cache on new pod
rm -rf /workspace/OneTrainer        # reinstall on /root/ on new pod
rm -rf /workspace/ai-toolkit        # not needed for OneTrainer workflow
```

Items to KEEP:
- `/workspace/models/` — Chroma fp8 (ComfyUI inference), LoRAs, eval checkpoints
- `/workspace/lora_training/` — dataset, configs, concepts, samples
- `/workspace/ai-ofm-production-factory/` — repo

---

## 11. After Training

1. Verify LoRA saved to network volume:
   ```bash
   ls -lh /workspace/models/loras/lora_lily_chroma_v001.safetensors
   ```
2. Copy to ComfyUI inference pod's loras folder
3. Test with FaceSim evaluation

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `OSError: [Errno 122] Disk quota exceeded` | MFS network volume write quota | Redirect workspace_dir, cache_dir, HF_HOME to /root/ |
| `E: Unable to locate package tmux` | Stale apt index | Run `apt-get update` first |
| `NotImplementedError: Loading of single file Chroma models not supported` | Wrong model format | Use `lodestones/Chroma1-HD` (HF diffusers), not local fp8 safetensors |
| `install.sh exited early` | Script permissions | `chmod +x install.sh && ./install.sh` |
| Training hung on first run | Samples file missing | Generate with `./run-cmd.sh create_train_files --samples-output-destination ...` |
