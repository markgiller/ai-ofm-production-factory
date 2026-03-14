# Pod File Transfer — SOP

How to download explore sessions and other files from the Runpod pod.

## Download last explore session as archive

**On pod:**
```bash
# Find latest session
LATEST=$(ls -t /workspace/ai-ofm-production-factory/explore_output/ | head -1)
echo "Latest session: $LATEST"

# Pack into archive
tar czf /workspace/outputs/explore_latest.tar.gz \
  -C /workspace/ai-ofm-production-factory/explore_output "$LATEST"
```

**On mac (browser):**
```
https://<pod-id>-8188.proxy.runpod.net/view?filename=explore_latest.tar.gz&type=output
```

Replace `<pod-id>` with your pod ID (e.g. `xve3vkwv9je132`).

## Download specific file

**On pod:**
```bash
cp /path/to/file.png /workspace/outputs/
```

**On mac (browser):**
```
https://<pod-id>-8188.proxy.runpod.net/view?filename=file.png&type=output
```

## Download contact sheet only

**On pod:**
```bash
LATEST=$(ls -t /workspace/ai-ofm-production-factory/explore_output/ | head -1)
cp /workspace/ai-ofm-production-factory/explore_output/$LATEST/contact_sheet.png /workspace/outputs/
```

**On mac (browser):**
```
https://<pod-id>-8188.proxy.runpod.net/view?filename=contact_sheet.png&type=output
```

## How it works

ComfyUI serves files from `/workspace/outputs/` via the `/view` endpoint on port 8188.
Port 8188 is already exposed through Runpod proxy. No extra setup needed.

## Cleanup after download

```bash
rm /workspace/outputs/explore_latest.tar.gz
rm /workspace/outputs/contact_sheet.png
```

Don't leave large archives in outputs — they waste space and clutter ComfyUI history.
