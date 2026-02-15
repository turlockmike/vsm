#!/usr/bin/env python3
"""
Generate a demo GIF showing VSM in action
Uses PIL to create animated GIF from terminal frames
"""

from PIL import Image, ImageDraw, ImageFont
import os

# Terminal styling
BG_COLOR = (0, 43, 54)  # Solarized dark
TEXT_COLOR = (147, 161, 161)  # Base0
PROMPT_COLOR = (108, 113, 196)  # Violet
COMMAND_COLOR = (38, 139, 210)  # Blue
SUCCESS_COLOR = (133, 153, 0)  # Green
HIGHLIGHT_COLOR = (42, 161, 152)  # Cyan

WIDTH = 800
HEIGHT = 500
FONT_SIZE = 14
LINE_HEIGHT = 20

# Demo frames
frames = [
    # Frame 0: Header
    {
        "lines": [
            ("", TEXT_COLOR),
            ("VSM — Viable System Machine Demo", TEXT_COLOR, "bold"),
            ("Autonomous AI Computer powered by Claude Code", TEXT_COLOR),
            ("━" * 70, TEXT_COLOR),
            ("", TEXT_COLOR),
        ],
        "duration": 1000
    },
    # Frame 1: vsm status
    {
        "lines": [
            ("", TEXT_COLOR),
            ("VSM — Viable System Machine Demo", TEXT_COLOR, "bold"),
            ("━" * 70, TEXT_COLOR),
            ("", TEXT_COLOR),
            ("$ vsm status", COMMAND_COLOR),
            ("", TEXT_COLOR),
            ("System Status: Healthy", TEXT_COLOR),
            ("✓ Controller running", SUCCESS_COLOR),
            ("✓ Dashboard active (http://localhost:80)", SUCCESS_COLOR),
            ("✓ Cron heartbeat every 5 min", SUCCESS_COLOR),
            ("", TEXT_COLOR),
            ("Active Errors: 0", TEXT_COLOR),
            ("Pending Tasks: 0", TEXT_COLOR),
        ],
        "duration": 2000
    },
    # Frame 2: Create task
    {
        "lines": [
            ("", TEXT_COLOR),
            ("VSM — Viable System Machine Demo", TEXT_COLOR, "bold"),
            ("━" * 70, TEXT_COLOR),
            ("", TEXT_COLOR),
            ("$ vsm status", TEXT_COLOR),
            ("System Status: Healthy ✓", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("$ vsm task add 'Calculate fibonacci(10)'", COMMAND_COLOR),
            ("", TEXT_COLOR),
            ("✓ Task created: task_fibonacci.json", SUCCESS_COLOR),
            ("  Priority: 2 (medium)", HIGHLIGHT_COLOR),
            ("  Status: pending", HIGHLIGHT_COLOR),
        ],
        "duration": 2000
    },
    # Frame 3: Autonomous execution
    {
        "lines": [
            ("", TEXT_COLOR),
            ("VSM — Viable System Machine Demo", TEXT_COLOR, "bold"),
            ("━" * 70, TEXT_COLOR),
            ("", TEXT_COLOR),
            ("$ vsm task add 'Calculate fibonacci(10)'", TEXT_COLOR),
            ("✓ Task created", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("[Autonomous cycle triggered by cron...]", HIGHLIGHT_COLOR),
            ("", TEXT_COLOR),
            ("✓ Heartbeat running", SUCCESS_COLOR),
            ("✓ System 5 analyzing task queue", SUCCESS_COLOR),
            ("✓ Delegating to builder agent", SUCCESS_COLOR),
            ("✓ Task completed: fibonacci(10) = 55", SUCCESS_COLOR),
        ],
        "duration": 2500
    },
    # Frame 4: Final status
    {
        "lines": [
            ("", TEXT_COLOR),
            ("VSM — Viable System Machine Demo", TEXT_COLOR, "bold"),
            ("━" * 70, TEXT_COLOR),
            ("", TEXT_COLOR),
            ("[Autonomous execution complete]", HIGHLIGHT_COLOR),
            ("", TEXT_COLOR),
            ("$ vsm status", COMMAND_COLOR),
            ("", TEXT_COLOR),
            ("System Status: Healthy", TEXT_COLOR),
            ("Completed Tasks (24h): 1", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("Recent Activity:", TEXT_COLOR),
            ("  ✓ fibonacci(10) = 55", SUCCESS_COLOR),
            ("", TEXT_COLOR),
            ("Dashboard: http://localhost:80", HIGHLIGHT_COLOR),
        ],
        "duration": 2500
    },
    # Frame 5: CTA
    {
        "lines": [
            ("", TEXT_COLOR),
            ("VSM — Viable System Machine Demo", TEXT_COLOR, "bold"),
            ("━" * 70, TEXT_COLOR),
            ("", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("✓ VSM is autonomously running on your machine", SUCCESS_COLOR),
            ("", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("Try it:", TEXT_COLOR, "bold"),
            ("  curl -fsSL https://raw.githubusercontent.com/", TEXT_COLOR),
            ("    turlockmike/vsm/main/install.sh | bash", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("", TEXT_COLOR),
            ("━" * 70, TEXT_COLOR),
        ],
        "duration": 3000
    }
]


def create_frame(lines, font_regular, font_bold):
    """Create a single frame image"""
    img = Image.new('RGB', (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = 20
    for line_data in lines:
        if not line_data:
            continue

        text = line_data[0]
        color = line_data[1] if len(line_data) > 1 else TEXT_COLOR
        bold = len(line_data) > 2 and line_data[2] == "bold"

        font = font_bold if bold else font_regular
        draw.text((20, y), text, fill=color, font=font)
        y += LINE_HEIGHT

    return img


def main():
    """Generate the demo GIF"""
    try:
        # Try to load a monospace font
        font_regular = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", FONT_SIZE)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", FONT_SIZE)
    except:
        # Fallback to default
        font_regular = ImageFont.load_default()
        font_bold = ImageFont.load_default()

    # Generate frames
    images = []
    durations = []

    for frame_data in frames:
        img = create_frame(frame_data["lines"], font_regular, font_bold)
        images.append(img)
        durations.append(frame_data["duration"])

    # Save as animated GIF
    output_path = "/home/mike/projects/vsm/main/demo/vsm-demo.gif"
    images[0].save(
        output_path,
        save_all=True,
        append_images=images[1:],
        duration=durations,
        loop=0,  # Loop forever
        optimize=True
    )

    file_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"✓ Demo generated: {output_path}")
    print(f"  File size: {file_size:.2f} MB")

    if file_size > 5:
        print(f"  WARNING: File size exceeds 5MB GitHub limit")
        print(f"  Consider reducing frame count or dimensions")


if __name__ == "__main__":
    main()
