#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import re
import sys

ROOT = Path.cwd()
VIM_C = ROOT / "boards/shields/nice_oled/assets/vim.c"
PNG = ROOT / "retro_cpp_exact_32x128.png"

if not VIM_C.exists():
    sys.exit(f"Nie znaleziono: {VIM_C}")
if not PNG.exists():
    sys.exit(f"Nie znaleziono: {PNG}")

src = Image.open(PNG).convert("1")
if src.size != (32, 128):
    sys.exit(f"Obraz musi mieć dokładnie 32x128 px, ma {src.size}")

# Asset dla OLED-a jest zapisany w module jako obrócone 128x32.
img = src.rotate(-90, expand=True)
if img.size != (128, 32):
    sys.exit(f"Błąd obrotu: oczekiwano 128x32, otrzymano {img.size}")

px = img.load()
data = []
for y in range(32):
    for x0 in range(0, 128, 8):
        byte = 0
        for bit in range(8):
            x = x0 + bit
            is_white = px[x, y] != 0
            idx = 0 if is_white else 1
            byte |= idx << (7 - bit)
        data.append(byte)

def c_bytes(vals, per_line=16):
    out = []
    for i in range(0, len(vals), per_line):
        part = vals[i:i+per_line]
        out.append("  " + ", ".join(f"0x{v:02x}" for v in part) + ",")
    return "\n".join(out)

new_map = f"""#ifndef LV_ATTRIBUTE_IMG_VIM_32X128
#define LV_ATTRIBUTE_IMG_VIM_32X128
#endif

static const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_IMG_VIM_32X128 uint8_t vim_32x128_map[] = {{
#if CONFIG_NICE_OLED_WIDGET_INVERTED
  /* Palette: index 0 = black, index 1 = white */
  0x00, 0x00, 0x00, 0xff, 0xff, 0xff, 0xff, 0xff,
#else
  /* Palette: index 0 = white, index 1 = black */
  0xff, 0xff, 0xff, 0xff, 0x00, 0x00, 0x00, 0xff,
#endif
{c_bytes(data)}
}};
"""

text = VIM_C.read_text(encoding="utf-8")

map_pattern = re.compile(
    r'#ifndef LV_ATTRIBUTE_IMG_VIM_32X128\s*'
    r'#define LV_ATTRIBUTE_IMG_VIM_32X128\s*'
    r'#endif\s*'
    r'static const LV_ATTRIBUTE_MEM_ALIGN LV_ATTRIBUTE_IMG_VIM_32X128 '
    r'uint8_t vim_32x128_map\[\] = \{.*?^\};',
    flags=re.S | re.M,
)

text, map_count = map_pattern.subn(new_map.rstrip(), text, count=1)
if map_count != 1:
    sys.exit(f"Nie udało się znaleźć vim_32x128_map (trafień: {map_count})")

vim_pattern = re.compile(
    r'const lv_img_dsc_t vim = \{.*?^\};',
    flags=re.S | re.M,
)
new_vim = """const lv_img_dsc_t vim = {
  .header.cf = LV_IMG_CF_INDEXED_1BIT,
  .header.always_zero = 0,
  .header.reserved = 0,
  .header.w = 128,
  .header.h = 32,
  .data_size = 520,
  .data = vim_32x128_map,
};"""

matches = list(vim_pattern.finditer(text))
if not matches:
    sys.exit("Nie znaleziono deskryptora: const lv_img_dsc_t vim")
m = matches[-1]
text = text[:m.start()] + new_vim + text[m.end():]

VIM_C.write_text(text, encoding="utf-8")
print("OK: podmieniono vim_32x128_map.")
print("OK: domyślny symbol vim wskazuje na 128x32 / vim_32x128_map.")
print("Przy CONFIG_NICE_OLED_WIDGET_INVERTED=y tło będzie czarne, grafika biała.")
