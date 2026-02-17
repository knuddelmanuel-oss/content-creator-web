import random
import time
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

# ---------- Hilfsfunktionen ----------

def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", name)

def get_readable_name(filename: str) -> str:
    """Macht aus 'zieh_ab_arschloch.txt' -> 'Zieh Ab Arschloch'."""
    stem = Path(filename).stem
    readable = stem.replace("_", " ").replace("-", " ")
    return readable.title()

def load_json(path: Path, default):
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path: Path, data):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

# ---------- Daten-Manager ----------

class WebDataManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent / "data_content_creator"
        self.base_dir.mkdir(exist_ok=True)
        self.final_image_dir = Path(__file__).parent / "generated_posts"
        self.final_image_dir.mkdir(exist_ok=True)

        self.used_texts_file = self.base_dir / "used_texts_web.json"
        self.used_texts: Dict[str, float] = load_json(self.used_texts_file, {})
        self.lock_duration_minutes = 10

        # Scannt ALLE .txt Dateien, egal wie sie heißen
        self.txt_files = sorted(self.base_dir.glob("*.txt"))
        self.categories: Dict[str, Path] = {}
        
        for f in self.txt_files:
            # Kategorie-Name wird hübsch gemacht
            cat_name = get_readable_name(f.name)
            self.categories[cat_name] = f

        # Fallback, falls leer
        if not self.categories:
            dummy = self.base_dir / "Demo_Kategorie.txt"
            if not dummy.exists():
                with dummy.open("w", encoding="utf-8") as f:
                    f.write("Dies ist ein Beispieltext.\nFüge deine .txt Dateien hinzu.\n")
            self.categories["Demo Kategorie"] = dummy

    def get_categories(self) -> List[str]:
        return sorted(list(self.categories.keys()))

    def get_file_for_category(self, category: str) -> Path:
        return self.categories.get(category, self.base_dir / "Demo_Kategorie.txt")

    def load_texts(self, category: str) -> List[str]:
        path = self.get_file_for_category(category)
        if not path.exists(): return []
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except: return []
        
        # Nur nicht-leere Zeilen, Duplikate entfernen
        return list(dict.fromkeys([l.strip() for l in lines if l.strip()]))

    def get_next_text(self, category: str) -> str:
        # Rotation bereinigen
        now = time.time()
        lock = self.lock_duration_minutes * 60
        self.used_texts = {t: ts for t, ts in self.used_texts.items() if (now - ts) < lock}
        
        texts = self.load_texts(category)
        if not texts: return "Keine Texte gefunden."

        available = [t for t in texts if t not in self.used_texts]
        if not available:
            self.used_texts = {} # Reset wenn alle durch
            available = texts
            
        chosen = random.choice(available)
        self.used_texts[chosen] = time.time()
        save_json(self.used_texts_file, self.used_texts)
        return chosen

    def list_backgrounds(self, category: str) -> List[Path]:
        # Intelligente Suche nach dem Ordner
        txt_stem = self.get_file_for_category(category).stem.lower() # z.B. "motivation"
        cat_clean = category.lower().replace(" ", "_")

        found_dir = None
        # 1. Exakter Match auf Stem (motivation_backgrounds)
        for d in self.base_dir.iterdir():
            if not d.is_dir(): continue
            d_lower = d.name.lower()
            if f"{txt_stem}_backgrounds" in d_lower: found_dir = d; break
            if f"{cat_clean}_backgrounds" in d_lower: found_dir = d; break
            # 2. Fuzzy Match: Wenn "motivation" und "background" drin vorkommt
            if txt_stem in d_lower and "background" in d_lower: found_dir = d; break

        if not found_dir: return []
        
        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            files.extend(sorted(found_dir.glob(ext)))
            files.extend(sorted(found_dir.glob(ext.upper())))
        return files

# ---------- Bildgenerator (Pro-Version) ----------

class ImageGenerator:
    def __init__(self, data_manager: WebDataManager):
        self.dm = data_manager
        self.image_size = (1080, 1350)

    def get_font(self, font_name: str, size: int):
        if not font_name: font_name = "Helvetica"
        # Suche in lokalen Fonts
        fonts_dir = self.dm.base_dir / "fonts"
        candidates = [
            fonts_dir / font_name,
            fonts_dir / f"{font_name}.ttf",
            fonts_dir / f"{font_name}.otf",
            Path("/Library/Fonts") / f"{font_name}.ttf",
            Path("/System/Library/Fonts") / f"{font_name}.ttc"
        ]
        for p in candidates:
            if p.exists():
                try: return ImageFont.truetype(str(p), size=size)
                except: continue
        try: return ImageFont.truetype(font_name, size=size)
        except: return ImageFont.load_default()

    def create_image(self, category: str, text: str, bg_image: Optional[Image.Image], 
                     scale=1.0, pos_x=0.5, pos_y=0.5, 
                     stroke=0.0, blur=0.0, shadow=True, bw=False, vignette=False, 
                     custom_color=None, bg_color="#000000"):
        
        # 1. Format bestimmen
        cat_lower = category.lower()
        # Quadratisch für diese speziellen Kategorien
        if any(x in cat_lower for x in ["krasser", "miststück", "zieh ab", "arschloch"]):
            self.image_size = (960, 960)
        else:
            self.image_size = (1080, 1350)
            
        W, H = self.image_size

        # 2. Hintergrund
        if bg_image:
            # Smart Crop (Center)
            img = bg_image.copy()
            img_ratio = img.width / img.height
            target_ratio = W / H
            if img_ratio > target_ratio:
                new_h = H
                new_w = int(new_h * img_ratio)
            else:
                new_w = W
                new_h = int(new_w / img_ratio)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - W)/2
            top = (new_h - H)/2
            img = img.crop((left, top, left+W, top+H))
        else:
            img = Image.new("RGB", (W, H), bg_color)

        # 3. Effekte
        if bw: img = ImageOps.grayscale(img).convert("RGB")
        if blur > 0: img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        if vignette:
            overlay = Image.new("RGBA", (W, H), (0,0,0,0))
            d = ImageDraw.Draw(overlay)
            d.rectangle([(0,0), (W,H)], fill=(0,0,0,90)) # Leichte Abdunklung
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(img)

        # 4. Farben & Fonts
        if custom_color: text_col = custom_color
        else:
            # Auto-Color
            thumb = img.resize((1,1))
            c = thumb.getpixel((0,0))
            bright = (c[0]*299 + c[1]*587 + c[2]*114)/1000
            text_col = "#FFFFFF" if bright < 120 else "#000000"
        
        stroke_col = "#000000" if text_col == "#FFFFFF" else "#FFFFFF"
        
        # --- SCHRIFTGRÖSSE BOOSTEN ---
        # Standard war 60/80 -> Jetzt 110/140 für bessere Lesbarkeit
        base_s = 130 if W == 960 else 110 
        font = self.get_font("Helvetica", int(base_s * scale))

        if W == 960: text = text.upper()

        # 5. Text-Wrapping & Layout
        # Margin: 1.5cm bei 300dpi sind ca 170px. Wir nehmen 120px für Web.
        margin = 120 
        max_w = W - (2 * margin)
        
        lines = []
        for line in text.split('\n'):
            words = line.split()
            curr = ""
            for w in words:
                test = f"{curr} {w}".strip()
                bbox = draw.textbbox((0,0), test, font=font)
                if (bbox[2]-bbox[0]) <= max_w: curr = test
                else:
                    if curr: lines.append(curr)
                    curr = w
            if curr: lines.append(curr)

        # Höhe berechnen
        line_heights = []
        for l in lines:
            bb = draw.textbbox((0,0), l, font=font)
            line_heights.append(bb[3]-bb[1])
        
        spacing = 15
        total_h = sum(line_heights) + (len(lines)-1)*spacing
        
        # Vertikale Positionierung (Safe Zones)
        top_safe = int(H * 0.25) # Obere 25% heilig
        bottom_safe = int(H * 0.90)
        
        # Verfügbarer Raum
        avail_h = bottom_safe - top_safe
        
        # Zentrierung erzwingen? -> pos_y=0.5 ist exakte Mitte des Safe-Bereichs
        # Wir mappen pos_y (0.0 - 1.0) auf (top_safe ... bottom_safe - total_h)
        min_y = top_safe
        max_y = bottom_safe - total_h
        if max_y < min_y: max_y = min_y # Text zu lang, fängt oben an
        
        start_y = min_y + (max_y - min_y) * pos_y

        # Helper zum Zeichnen (ZENTRIERT)
        def draw_text_lines(painter, fill, s_w=0, s_fill=None):
            y = start_y
            for i, l in enumerate(lines):
                bb = draw.textbbox((0,0), l, font=font)
                lw = bb[2]-bb[0]
                lh = line_heights[i]
                
                # Horizontale Position:
                # Verfügbarer Platz: W - (2*margin)
                # Textbreite: lw
                # pos_x=0.5 -> Zentriert im verfügbaren Platz
                
                # Bereich links/rechts
                area_l = margin
                area_w = W - 2*margin
                
                # Exakte X-Position basierend auf Slider
                # x = Startbereich + (Freiraum * pos)
                freiraum = area_w - lw
                x = area_l + (freiraum * pos_x)
                
                if s_w > 0:
                    painter.text((x, y), l, font=font, fill=fill, stroke_width=s_w, stroke_fill=s_fill)
                else:
                    painter.text((x, y), l, font=font, fill=fill)
                y += lh + spacing

        # Schatten
        if shadow:
            s_layer = Image.new("RGBA", (W,H), (0,0,0,0))
            s_draw = ImageDraw.Draw(s_layer)
            s_col = (0,0,0,160) if text_col == "#FFFFFF" else (255,255,255,160)
            
            # Schatten leicht versetzt
            orig_y = start_y
            start_y += 4 # Offset Y
            draw_text_lines(s_draw, s_col)
            start_y = orig_y # Reset
            
            s_layer = s_layer.filter(ImageFilter.GaussianBlur(radius=5))
            img = Image.alpha_composite(img.convert("RGBA"), s_layer).convert("RGB")
            draw = ImageDraw.Draw(img)

        # Haupttext
        draw_text_lines(draw, text_col, int(stroke), stroke_col)

        # Wasserzeichen
        wm = None
        if "narzissmus" in cat_lower: wm = "Isaak Öztürk"
        elif "herz" in cat_lower or "umfragen" in cat_lower: wm = "Herzwelt"
        
        if wm:
            f_wm = self.get_font("Noteworthy", 45) # Größeres WM
            bb = draw.textbbox((0,0), wm, font=f_wm)
            wx = (W - (bb[2]-bb[0])) / 2
            wy = H - 100
            draw.text((wx, wy), wm, font=f_wm, fill=text_col)

        return img
