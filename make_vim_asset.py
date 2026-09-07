#!/usr/bin/env python3
from PIL import Image, ImageOps
import argparse
from pathlib import Path

VARIANTS = [
    ("vim_32x100", 100, 32),
    ("vim_32x128", 128, 32),
    ("vim_68x160", 160, 68),
    ("vim_68x69", 69, 68),
]

def crop_art(img):
    gray = img.convert("L")
    mask = gray.point(lambda p: 255 if p > 20 else 0)
    bbox = mask.getbbox()
    if bbox:
        gray = gray.crop(bbox)
    pad = max(2, int(max(gray.size) * 0.04))
    return ImageOps.expand(gray, border=pad, fill=0)

def make_variant(src, w, h, rotate):
    art = crop_art(src)

    if rotate == "cw":
        art = art.rotate(-90, expand=True)
    elif rotate == "ccw":
        art = art.rotate(90, expand=True)

    canvas = Image.new("L", (w, h), 0)
    fitted = ImageOps.contain(
        art,
        (max(1, w - 2), max(1, h - 2)),
        method=Image.Resampling.LANCZOS,
    )
    fitted = fitted.point(lambda p: 255 if p >= 128 else 0)
    canvas.paste(fitted, ((w - fitted.width)//2, (h - fitted.height)//2))
    return canvas

def packed_pixels(img):
    px = img.load()
    w, h = img.size
    out = []
    for y in range(h):
        for x0 in range(0, w, 8):
            byte = 0
            for bit in range(8):
                x = x0 + bit
                idx = 1
                if x < w and px[x, y] >= 128:
                    idx = 0
                byte |= idx << (7 - bit)
            out.append(byte)
    return out

def c_bytes(data, indent="  ", per_line=16):
    lines = []
    for i in range(0, len(data), per_line):
        part = data[i:i+per_line]
        lines.append(indent + ", ".join(f"0x{x:02x}" for x in part) + ",")
    return "\n".join(lines)

def macro_name(name):
    return "LV_ATTRIBUTE_IMG_" + name.upper()

def emit_map(name, img):
    macro = macro_name(name)
    pixels = packed_pixels(img)
    return f'''#ifndef {macro}
#define {macro}
#endif

static const LV_ATTRIBUTE_MEM_ALIGN {macro} uint8_t {name}_map[] = {{
#if CONFIG_NICE_OLED_WIDGET_INVERTED
  0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff,
#else
  0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0xff,
#endif
{c_bytes(pixels)}
}};
'''

def emit_desc(name, w, h):
    size = 8 + ((w + 7)//8) * h
    return f'''const lv_img_dsc_t {name} = {{
  .header.cf = LV_IMG_CF_INDEXED_1BIT,
  .header.always_zero = 0,
  .header.reserved = 0,
  .header.w = {w},
  .header.h = {h},
  .data_size = {size},
  .data = {name}_map,
}};
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--output", default="vim.c")
    ap.add_argument(
        "--rotate",
        choices=("cw", "ccw"),
        default="cw",
        help="If the OLED image is upside-down, regenerate with --rotate ccw",
    )
    ap.add_argument("--preview-dir", default=None)
    args = ap.parse_args()

    src = Image.open(args.image)
    rendered = {}

    for name, w, h in VARIANTS:
        rendered[name] = make_variant(src, w, h, args.rotate)

    if args.preview_dir:
        p = Path(args.preview_dir)
        p.mkdir(parents=True, exist_ok=True)
        for name, img in rendered.items():
            img.save(p / f"{name}.png")

    pieces = [
        "/* Custom retro C++ image generated for zmk-nice-oled. */\n",
        "#include <lvgl.h>\n\n",
        "#ifndef LV_ATTRIBUTE_MEM_ALIGN\n#define LV_ATTRIBUTE_MEM_ALIGN\n#endif\n\n",
    ]

    for name, _, _ in VARIANTS:
        pieces.append(emit_map(name, rendered[name]))
        pieces.append("\n")

    for name, w, h in VARIANTS:
        pieces.append(emit_desc(name, w, h))
        pieces.append("\n")

    pieces.append('''const lv_img_dsc_t vim = {
  .header.cf = LV_IMG_CF_INDEXED_1BIT,
  .header.always_zero = 0,
  .header.reserved = 0,
  .header.w = 160,
  .header.h = 68,
  .data_size = 1368,
  .data = vim_68x160_map,
};
''')

    Path(args.output).write_text("".join(pieces), encoding="utf-8")
    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
