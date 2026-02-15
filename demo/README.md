# VSM Demo Recording

## Quick Record (Recommended)

Use asciinema + agg to create a compact GIF:

```bash
# Install tools (one-time)
pip install asciinema
cargo install --git https://github.com/asciinema/agg

# Record the demo
cd /home/mike/projects/vsm/main
asciinema rec demo/vsm-demo.cast --command "./demo/record-demo.sh"

# Convert to GIF
agg demo/vsm-demo.cast demo/vsm-demo.gif --speed 1.5 --cols 100 --rows 30

# Check file size
ls -lh demo/vsm-demo.gif
```

## Alternative: Manual Recording

If tools aren't available, record manually:

1. Open terminal, set size to 100x30
2. Run: `./demo/record-demo.sh`
3. Screen record the terminal (QuickTime, OBS, etc.)
4. Convert to GIF with ffmpeg:
   ```bash
   ffmpeg -i demo.mov -vf "fps=10,scale=800:-1:flags=lanczos" -c:v gif demo/vsm-demo.gif
   ```

## Alternative: Terminalizer (npm-based)

```bash
npm install -g terminalizer
terminalizer record vsm-demo --config demo/terminalizer.yml
terminalizer render vsm-demo -o demo/vsm-demo.gif
```

## File Size Optimization

Target: < 5MB for GitHub embedding

```bash
# Optimize GIF
gifsicle -O3 --colors 256 demo/vsm-demo.gif -o demo/vsm-demo-optimized.gif

# Or convert to WebP (better compression)
ffmpeg -i demo/vsm-demo.gif -c:v libwebp -qscale 50 demo/vsm-demo.webp
```

## Embedding in README

Once generated, add to README.md:

```markdown
## Demo

![VSM Demo](demo/vsm-demo.gif)

*Watch VSM autonomously complete a task*
```

## Files

- `record-demo.sh` - Automated demo script
- `vsm-demo.svg` - Static SVG animation (can be embedded directly)
- `vsm-demo.gif` - Animated GIF (generated from recording)
