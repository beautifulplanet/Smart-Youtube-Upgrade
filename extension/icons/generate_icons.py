"""
Generate YouTube Safety Inspector extension icons.
Shield with checkmark design in the extension's dark theme colors.
"""
from PIL import Image, ImageDraw, ImageFont
import math
import os

# Color palette
SHIELD_OUTER = (30, 215, 96)     # Green (#1ed760) - safe/chill accent
SHIELD_INNER = (20, 20, 40)      # Dark navy background
CHECK_COLOR  = (30, 215, 96)     # Green checkmark
SHIELD_EDGE  = (50, 200, 100)    # Slightly lighter green for edge highlight
BG_COLOR     = (0, 0, 0, 0)      # Transparent background


def draw_shield(draw, cx, cy, w, h, fill, outline, outline_width=1):
    """Draw a shield shape centered at (cx, cy) with given width and height."""
    # Shield is composed of:
    # - Top: rounded rectangle (top half)
    # - Bottom: pointed triangle / curved taper

    hw = w / 2
    top_h = h * 0.5     # top rectangular section height
    bot_h = h * 0.5     # bottom pointed section height

    top_y = cy - h / 2
    mid_y = top_y + top_h
    bot_y = cy + h / 2

    # Corner radius for top
    r = hw * 0.35

    # Build shield polygon points (clockwise from top-left)
    points = []
    steps = 12

    # Top-left corner arc
    for i in range(steps + 1):
        angle = math.pi + (math.pi / 2) * (i / steps)
        px = (cx - hw + r) + r * math.cos(angle)
        py = (top_y + r) + r * math.sin(angle)
        points.append((px, py))

    # Top-right corner arc
    for i in range(steps + 1):
        angle = -math.pi / 2 + (math.pi / 2) * (i / steps)
        px = (cx + hw - r) + r * math.cos(angle)
        py = (top_y + r) + r * math.sin(angle)
        points.append((px, py))

    # Right side down to mid
    points.append((cx + hw, mid_y))

    # Bottom point - curved taper
    taper_steps = 16
    for i in range(taper_steps + 1):
        t = i / taper_steps
        # Quadratic bezier from (cx+hw, mid_y) through (cx+hw*0.3, bot_y-bot_h*0.1) to (cx, bot_y)
        x = (1-t)**2 * (cx + hw) + 2*(1-t)*t * (cx + hw*0.15) + t**2 * cx
        y = (1-t)**2 * mid_y + 2*(1-t)*t * (bot_y - bot_h*0.05) + t**2 * bot_y
        points.append((x, y))

    # Left taper back up
    for i in range(taper_steps + 1):
        t = i / taper_steps
        x = (1-t)**2 * cx + 2*(1-t)*t * (cx - hw*0.15) + t**2 * (cx - hw)
        y = (1-t)**2 * bot_y + 2*(1-t)*t * (bot_y - bot_h*0.05) + t**2 * mid_y
        points.append((x, y))

    # Close back to top-left
    points.append((cx - hw, mid_y))

    # Draw filled shield
    draw.polygon(points, fill=fill, outline=outline, width=outline_width)
    return points


def draw_checkmark(draw, cx, cy, size, color, width):
    """Draw a checkmark centered at (cx, cy)."""
    # Checkmark proportions
    s = size / 2
    # Three points of the check: left, bottom, right-top
    p1 = (cx - s * 0.55, cy + s * 0.05)   # left
    p2 = (cx - s * 0.10, cy + s * 0.50)   # bottom vertex
    p3 = (cx + s * 0.60, cy - s * 0.40)   # right top
    
    draw.line([p1, p2, p3], fill=color, width=width, joint="curve")


def generate_icon(size: int, output_path: str):
    """Generate a single icon at the given size."""
    # Use 4x supersampling for anti-aliasing
    ss = 4
    ss_size = size * ss
    
    img = Image.new('RGBA', (ss_size, ss_size), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    cx = ss_size / 2
    cy = ss_size / 2
    
    # Shield dimensions relative to canvas
    shield_w = ss_size * 0.72
    shield_h = ss_size * 0.82
    
    # Drop shadow (subtle)
    shadow_offset = ss_size * 0.02
    draw_shield(draw, cx + shadow_offset, cy + shadow_offset, 
                shield_w, shield_h, 
                fill=(0, 0, 0, 60), outline=None)
    
    # Outer shield (green border)
    border = ss_size * 0.06
    draw_shield(draw, cx, cy, shield_w, shield_h,
                fill=SHIELD_OUTER, outline=None)
    
    # Inner shield (dark fill)
    draw_shield(draw, cx, cy, shield_w - border*2, shield_h - border*2,
                fill=SHIELD_INNER + (255,), outline=None)
    
    # Checkmark
    check_size = shield_w * 0.65
    check_width = max(int(ss_size * 0.06), 2)
    draw_checkmark(draw, cx, cy - ss_size * 0.02, check_size, 
                   CHECK_COLOR + (255,), check_width)
    
    # Downsample with LANCZOS for clean anti-aliasing
    img = img.resize((size, size), Image.LANCZOS)
    img.save(output_path, 'PNG')
    
    file_size = os.path.getsize(output_path)
    print(f"  Created {output_path} ({size}x{size}, {file_size:,} bytes)")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("Generating YouTube Safety Inspector icons...")
    for size in [16, 48, 128]:
        output = os.path.join(script_dir, f"icon{size}.png")
        generate_icon(size, output)
    
    print("Done!")


if __name__ == "__main__":
    main()
