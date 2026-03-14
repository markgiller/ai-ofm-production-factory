#!/usr/bin/env python3
"""Convert VAE from Diffusers format to BFL format for musubi-tuner."""
import re
from safetensors.torch import load_file, save_file
sd = load_file("/workspace/models/vae/flux2-vae.safetensors")
new_sd = {}
for k, v in sd.items():
    n = k
    if n.startswith("post_quant_conv."):
        n = "decoder." + n
    elif n.startswith("quant_conv."):
        n = "encoder." + n
    n = n.replace(".conv_norm_out.", ".norm_out.")
    n = n.replace(".conv_shortcut.", ".nin_shortcut.")
    n = re.sub(r'encoder\.down_blocks\.(\d+)\.resnets\.(\d+)', r'encoder.down.\1.block.\2', n)
    n = re.sub(r'encoder\.down_blocks\.(\d+)\.downsamplers\.0\.conv', r'encoder.down.\1.downsample.conv', n)
    n = re.sub(r'decoder\.up_blocks\.(\d+)\.resnets\.(\d+)', lambda m: f'decoder.up.{3-int(m.group(1))}.block.{m.group(2)}', n)
    n = re.sub(r'decoder\.up_blocks\.(\d+)\.upsamplers\.0\.conv', lambda m: f'decoder.up.{3-int(m.group(1))}.upsample.conv', n)
    n = re.sub(r'(encoder|decoder)\.mid_block\.resnets\.(\d+)', lambda m: f'{m.group(1)}.mid.block_{int(m.group(2))+1}', n)
    n = re.sub(r'(encoder|decoder)\.mid_block\.attentions\.0\.group_norm', r'\1.mid.attn_1.norm', n)
    n = re.sub(r'(encoder|decoder)\.mid_block\.attentions\.0\.to_q', r'\1.mid.attn_1.q', n)
    n = re.sub(r'(encoder|decoder)\.mid_block\.attentions\.0\.to_k', r'\1.mid.attn_1.k', n)
    n = re.sub(r'(encoder|decoder)\.mid_block\.attentions\.0\.to_v', r'\1.mid.attn_1.v', n)
    n = re.sub(r'(encoder|decoder)\.mid_block\.attentions\.0\.to_out\.0', r'\1.mid.attn_1.proj_out', n)
    # Attention weights: Linear [512,512] → Conv2d [512,512,1,1]
    if "attn_1" in n and n.endswith(".weight") and v.dim() == 2:
        v = v.unsqueeze(-1).unsqueeze(-1)
    new_sd[n] = v
save_file(new_sd, "/workspace/models/vae/flux2-vae-bfl.safetensors")
print(f"Done: {len(new_sd)} keys")
