# YouTube Safety Inspector - Extension Icons

Since SVG icons need to be PNG for Chrome extensions, generate PNG icons from these specs:

## Icon Specifications

**Design**: Shield emoji (🛡️) on dark gradient background
**Colors**: 
- Background gradient: #1a1a2e to #16213e
- Border radius: 20% of size

**Sizes needed**:
- icon16.png (16x16)
- icon48.png (48x48) 
- icon128.png (128x128)

## Quick Generation

You can use any image editor or online tool to create these. 

### Option 1: Use placeholder colored squares
Create solid color PNG files:
- 16x16, 48x48, 128x128 pixels
- Color: #1a1a2e (dark blue)

### Option 2: Use an emoji-to-PNG converter
Search for "emoji to PNG" online and download 🛡️ in required sizes.

### Option 3: Generate programmatically
```python
from PIL import Image, ImageDraw, ImageFont

sizes = [16, 48, 128]
for size in sizes:
    img = Image.new('RGBA', (size, size), '#1a1a2e')
    img.save(f'icon{size}.png')
```

For now, the extension will work without icons (just show default puzzle piece).
