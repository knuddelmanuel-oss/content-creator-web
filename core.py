import random
import time
import json
import re
import zipfile
import io
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# --- DYNAMIC DATA MANAGER ---
class WebDataManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent / "data_content_creator"
        self.base_dir.mkdir(exist_ok=True)
        self.used_texts_file = self.base_dir / "used_texts_web.json"
        
        try:
            with self.used_texts_file.open("r", encoding="utf-8") as f:
                self.used_texts = json.load(f)
        except: self.used_texts = {}

        self.categories = {}
        # Scan for txt files
        for f in sorted(self.base_dir.glob("*.txt")):
            clean_name = f.stem.replace("_", " ").title()
            self.categories[clean_name] = f

        # Fallback if empty
        if not self.categories:
            dummy = self.base_dir / "Demo.txt"
            if not dummy.exists():
                with dummy.open("w") as f: f.write("Beispieltext.")
            self.categories["Demo"] = dummy

    def get_categories(self): return sorted(list(self.categories.keys()))

    def get_next_text(self, category):
        fpath = self.categories.get(category)
        if not fpath: return "Fehler: Kategorie nicht gefunden"
        try:
            with fpath.open("r", encoding="utf-8", errors="ignore") as f:
                lines = [l.strip() for l in f if l.strip()]
        except: return "Fehler beim Lesen"
        if not lines: return "Datei ist leer"

        # Rotation Logic
        now = time.time()
        self.used_texts = {k:v for k,v in self.used_texts.items() if (now-v) < 900}
        
        avail = [t for t in lines if t not in self.used_texts]
        if not avail: 
            avail = lines 
            self.used_texts = {}
        
        chosen = random.choice(avail)
        self.used_texts[chosen] = now
        try:
            with self.used_texts_file.open("w", encoding="utf-8") as f: 
                json.dump(self.used_texts, f)
        except: pass
        
        return chosen

    def get_backgrounds(self, category):
        if category not in self.categories: return []
        stem = self.categories[category].stem.lower()
        
        found = None
        for d in self.base_dir.iterdir():
            if d.is_dir():
                d_name = d.name.lower()
                if stem in d_name and "background" in d_name:
                    found = d
                    break
        
        if not found: return []
        exts = {".jpg", ".jpeg", ".png", ".webp"}
        return sorted([f for f in found.glob("*") if f.suffix.lower() in exts])


# --- PRO IMAGE GENERATOR (FIXED FONT) ---
class ImageGenerator:
    def __init__(self, dm):
        self.dm = dm

    def get_font(self, size):
        """
        Robust font loading that works on Mac, Linux (Streamlit Cloud), and Windows.
        """
        # 1. Look in project 'fonts' folder first
        project_fonts = self.dm.base_dir / "fonts"
        if project_fonts.exists():
            for f in project_fonts.glob("*.[to]tf"):
                try: return ImageFont.truetype(str(f), size)
                except: continue

        # 2. Common System Fonts (Linux/Mac)
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", # Linux Standard
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", # Linux
            "arial.ttf", "Arial.ttf",
            "/Library/Fonts/Arial Bold.ttf", # Mac
            "/System/Library/Fonts/Helvetica.ttc" # Mac
        ]
        
        for c in candidates:
            try: return ImageFont.truetype(c, size)
            except: continue
            
        # 3. Absolute Fallback (Default PIL font)
        # Note: load_default() returns a font that might NOT support size parameter in older PIL
        # But in newer Pillow it does. We try-except.
        try:
            return ImageFont.load_default()
        except:
            return ImageFont.load_default()

    def render(self, category, text, bg_path=None, scale=1.0, pos_y=0.5, pos_x=0.5, 
               shadow=True, bw=False, blur=0, vignette=False, custom_col=None,
               draw_overlay=False): 
        
        is_square = any(x in category.lower() for x in ["krasser", "miststück", "zieh ab"])
        W, H = (960, 960) if is_square else (1080, 1350)
        
        # Background
        if bg_path:
            try:
                img = Image.open(bg_path).convert("RGB")
                r_img, r_can = img.width/img.height, W/H
                if r_img > r_can: nh, nw = H, int(H*r_img)
                else: nw, nh = W, int(W/r_img)
                img = img.resize((nw, nh), Image.Resampling.LANCZOS)
                l, t = (nw-W)//2, (nh-H)//2
                img = img.crop((l, t, l+W, t+H))
            except: img = Image.new("RGB", (W,H), "#111")
        else: img = Image.new("RGB", (W,H), "#111")

        if bw: img = ImageOps.grayscale(img).convert("RGB")
        if blur > 0: img = img.filter(ImageFilter.GaussianBlur(blur))
        if vignette:
            ov = Image.new("RGBA", (W,H), (0,0,0,0))
            d = ImageDraw.Draw(ov)
            d.rectangle([0,0,W,H], fill=(0,0,0,80))
            img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

        draw = ImageDraw.Draw(img)
        
        # Colors
        if custom_col: fill = custom_col
        else:
            s = ImageOps.grayscale(img.resize((1,1))).getpixel((0,0))
            fill = "#FFFFFF" if s < 130 else "#000000"
        
        base_s = 120 if is_square else 105
        font = self.get_font(int(base_s * scale))
        if is_square: text = text.upper()

        # Layout
        mx = 140
        top_s, bot_s = int(H*0.25), H-120
        max_w = W - 2*mx
        
        lines = []
        # Safer wrapping logic
        try:
            for par in text.split('\n'):
                words, cur = par.split(), ""
                for w in words:
                    test = (cur + " " + w).strip()
                    # Check text length
                    if draw.textlength(test, font=font) <= max_w: 
                        cur = test
                    else: 
                        if cur: lines.append(cur)
                        cur = w
                if cur: lines.append(cur)
        except Exception:
            # Fallback for old PIL or font issues
            lines = [text]

        # Calculate heights safely
        line_h = []
        for l in lines:
            try:
                bbox = draw.textbbox((0,0), l, font=font)
                line_h.append(bbox[3] - bbox[1])
            except:
                line_h.append(40) # Fallback height

        space = 20
        tot_h = sum(line_h) + (len(lines)-1)*space
        
        min_y, max_y = top_s, max(top_s, bot_s - tot_h)
        start_y = min_y + (max_y - min_y) * pos_y

        def paint(ptr, col, off=0, strk=0, scol=None):
            y = start_y + off
            for i, l in enumerate(lines):
                try:
                    lw = ptr.textlength(l, font=font)
                except:
                    bbox = ptr.textbbox((0,0), l, font=font)
                    lw = bbox[2] - bbox[0]

                x = mx + ((W - 2*mx - lw) * pos_x)
                
                # FIXED: Ensure color is valid tuple/string
                if strk: 
                    ptr.text((x, y), l, font, fill=col, stroke_width=strk, stroke_fill=scol)
                else: 
                    ptr.text((x, y), l, font, fill=col)
                y += line_h[i] + space

        if shadow:
            s_im = Image.new("RGBA", (W,H), (0,0,0,0))
            # Fix color tuple for shadow
            shad_col = (0,0,0,160) if fill=="#FFFFFF" else (255,255,255,160)
            paint(ImageDraw.Draw(s_im), shad_col, off=8)
            img = Image.alpha_composite(img.convert("RGBA"), s_im.filter(ImageFilter.GaussianBlur(5))).convert("RGB")
            draw = ImageDraw.Draw(img)

        paint(draw, fill, strk=int(bw), scol="#000000" if fill=="#FFFFFF" else "#FFFFFF")

        # Watermark
        wm = None
        cat_low = category.lower()
        if "narzissmus" in cat_low: wm = "Isaak Öztürk"
        elif "herz" in cat_low or "umfragen" in cat_low: wm = "Herzwelt"
        if wm:
            try: fwm = ImageFont.truetype("Noteworthy.ttc", 45)
            except: fwm = ImageFont.load_default()
            wbb = draw.textbbox((0,0), wm, font=fwm)
            draw.text(((W-(wbb[2]-wbb[0]))/2, H-90), wm, font=fwm, fill=fill)

        # Overlay
        if draw_overlay:
            ov = Image.new("RGBA", (W,H), (0,0,0,0))
            d = ImageDraw.Draw(ov)
            ui_col = (255,255,255,200)
            d.text((40, 60), "< Zurück", font=self.get_font(40), fill=ui_col)
            rx, ry = W-100, H-400
            for i in range(3):
                d.ellipse([rx, ry, rx+70, ry+70], outline=ui_col, width=4)
                ry += 160
            img = Image.alpha_composite(img.convert("RGBA"), ov).convert("RGB")

        return img

    def create_batch_zip(self, category, texts, bg_list):
        mem_zip = io.BytesIO()
        with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for i, txt in enumerate(texts):
                bg = bg_list[i % len(bg_list)] if bg_list else None
                img = self.render(category, txt, bg, scale=1.0, shadow=True)
                img_byte = io.BytesIO()
                img.save(img_byte, format="PNG")
                safe_txt = re.sub(r'\W+', '_', txt[:20])
                zf.writestr(f"Post_{i+1}_{safe_txt}.png", img_byte.getvalue())
        return mem_zip.getvalue()
