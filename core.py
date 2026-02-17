import random
import time
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps


# ---------- Hilfsfunktionen ----------

def sanitize_filename(name: str) -> str:
    """Bereinigt Dateinamen für URL/System (nur zur Sicherheit)."""
    return re.sub(r'[\\/*?:"<>|]', "", name)

def get_readable_name(filename: str) -> str:
    """Macht aus 'zieh_ab_arschloch.txt' -> 'Zieh Ab Arschloch'."""
    stem = Path(filename).stem
    # Unterstriche zu Leerzeichen
    readable = stem.replace("_", " ").replace("-", " ")
    # Optional: Wörter kapitalisieren
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


# ---------- Daten-Management (Auto-Discovery) ----------

class WebDataManager:
    """
    Scannt automatisch data_content_creator nach .txt-Dateien und *_backgrounds Ordnern.
    Erstellt daraus dynamisch Kategorien.
    """

    def __init__(self):
        self.base_dir = Path(__file__).parent / "data_content_creator"
        self.base_dir.mkdir(exist_ok=True)

        self.final_image_dir = Path(__file__).parent / "generated_posts"
        self.final_image_dir.mkdir(exist_ok=True)

        self.used_texts_file = self.base_dir / "used_texts_web.json"
        self.used_texts: Dict[str, float] = load_json(self.used_texts_file, {})

        # Rotation-Lock (Minuten)
        self.lock_duration_minutes = 10

        # Auto-Discovery: Alle .txt Dateien finden
        self.txt_files = sorted(self.base_dir.glob("*.txt"))
        
        # Mapping: Kategorie-Name -> Dateipfad
        self.categories: Dict[str, Path] = {}
        for f in self.txt_files:
            cat_name = get_readable_name(f.name)
            self.categories[cat_name] = f

        # Falls gar keine .txt da sind, Dummy-Eintrag (damit App nicht crasht)
        if not self.categories:
            dummy = self.base_dir / "demo.txt"
            if not dummy.exists():
                with dummy.open("w", encoding="utf-8") as f:
                    f.write("Dies ist ein Beispieltext.\n")
            self.categories["Demo"] = dummy

    # ----- Kategorien -----

    def get_categories(self) -> List[str]:
        return sorted(list(self.categories.keys()))

    def get_file_for_category(self, category: str) -> Path:
        return self.categories.get(category, self.base_dir / "demo.txt")

    # ----- Texte -----

    def load_texts(self, category: str) -> List[str]:
        path = self.get_file_for_category(category)
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except Exception:
            return []

        texts = [l.strip() for l in lines if l.strip()]
        # Duplikate entfernen, Reihenfolge behalten
        seen = set()
        clean = []
        for t in texts:
            if t not in seen:
                seen.add(t)
                clean.append(t)
        return clean

    def _clean_old_used_texts(self):
        now = time.time()
        lock = self.lock_duration_minutes * 60
        new_used = {t: ts for t, ts in self.used_texts.items() if (now - ts) < lock}
        if len(new_used) != len(self.used_texts):
            self.used_texts = new_used
            save_json(self.used_texts_file, self.used_texts)

    def get_next_text(self, category: str) -> Optional[str]:
        self._clean_old_used_texts()
        texts = self.load_texts(category)
        if not texts:
            return None

        available = [t for t in texts if t not in self.used_texts]
        if not available:
            # Reset, wenn alle durch sind
            self.used_texts = {}
            save_json(self.used_texts_file, self.used_texts)
            available = texts

        chosen = random.choice(available)
        self.used_texts[chosen] = time.time()
        save_json(self.used_texts_file, self.used_texts)
        return chosen

    # ----- Hintergründe (Intelligent Matching) -----

    def get_background_folder_path(self, category: str) -> Optional[Path]:
        """
        Versucht, einen passenden Ordner zu finden.
        Strategie:
        1. Suche nach exaktem Match 'Category Name_backgrounds'
        2. Suche nach 'filename_backgrounds' (basierend auf .txt)
        3. Suche nach ähnlichem Namen (fuzzy match)
        """
        # 1. Basis-Name aus der Textdatei (z.B. 'motivation' aus 'motivation.txt')
        txt_path = self.get_file_for_category(category)
        stem = txt_path.stem  # 'motivation'

        # Kandidaten-Namen
        candidates = [
            f"{stem}_backgrounds",
            f"{category}_backgrounds",
            f"{stem}_background",
            f"{category} backgrounds",
        ]

        # Check exakt
        for c in candidates:
            p = self.base_dir / c
            if p.exists() and p.is_dir():
                return p

        # Fuzzy Search: Suche Ordner, der den Stem enthält und 'background' heißt
        for d in self.base_dir.iterdir():
            if d.is_dir() and "background" in d.name.lower():
                # Wenn der Stem (z.B. 'motivation') im Ordnernamen vorkommt
                if stem.lower() in d.name.lower():
                    return d
                # Oder Teile des Kategorie-Namens
                parts = category.lower().split()
                if any(p in d.name.lower() for p in parts if len(p) > 3):
                    return d
        
        return None

    def list_backgrounds(self, category: str) -> List[Path]:
        folder = self.get_background_folder_path(category)
        if not folder or not folder.exists():
            return []
        
        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            files.extend(folder.glob(ext))
            files.extend(folder.glob(ext.upper())) # Case insensitive
        return sorted(files)


# ---------- Bildgenerator ----------

class ImageGenerator:
    """
    Web-tauglicher Bildgenerator mit:
    - Live-Vorschau Optimierung
    - Wasserzeichen für spezifische Kategorien
    - Großem Text & sauberen Rändern
    """

    def __init__(self, data_manager: WebDataManager):
        self.dm = data_manager
        self.image_size = (1080, 1350)

    # -- Fonts --
    def get_font(self, font_name: Optional[str], size: int) -> ImageFont.FreeTypeFont:
        if not font_name:
            font_name = "Helvetica"

        # Priorität: Projekt-Fonts -> System-Fonts -> Fallback
        fonts_dir = self.dm.base_dir / "fonts"
        candidates = [
            fonts_dir / font_name,
            fonts_dir / f"{font_name}.ttf",
            fonts_dir / f"{font_name}.otf",
            Path("/Library/Fonts") / f"{font_name}.ttf",
            Path("/System/Library/Fonts") / f"{font_name}.ttc",
        ]
        
        for p in candidates:
            if p.exists():
                try: return ImageFont.truetype(str(p), size=size)
                except: continue
        
        try: return ImageFont.truetype(font_name, size=size)
        except: return ImageFont.load_default()

    def calculate_auto_color(self, image: Image.Image) -> str:
        if not image: return "#FFFFFF"
        thumb = image.resize((1, 1))
        color = thumb.getpixel((0, 0))
        if isinstance(color, int): b = color
        else: b = (color[0]*299 + color[1]*587 + color[2]*114) / 1000
        return "#FFFFFF" if b < 120 else "#000000"

    def prepare_background(self, img_source: Optional[Image.Image]) -> Image.Image:
        target_w, target_h = self.image_size
        if not img_source:
            return Image.new("RGB", self.image_size, "#000000")

        img_ratio = img_source.width / img_source.height
        target_ratio = target_w / target_h

        if img_ratio > target_ratio:
            new_height = target_h
            new_width = int(new_height * img_ratio)
        else:
            new_width = target_w
            new_height = int(new_width / img_ratio)

        img_resized = img_source.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Center Crop
        left = (new_width - target_w) / 2
        top = (new_height - target_h) / 2
        right = (new_width + target_w) / 2
        bottom = (new_height + target_h) / 2
        return img_resized.crop((left, top, right, bottom))

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
        lines, words = [], text.split()
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                if current_line: lines.append(current_line)
                current_line = word
        if current_line: lines.append(current_line)
        return lines

    def create_image(
        self,
        category: str,
        headline: str,
        body: str,
        *,
        background_image: Optional[Image.Image],
        font_name: Optional[str],
        scale: float,
        pos_x: float,
        pos_y: float,
        stroke: float,
        blur: float,
        use_shadow: bool,
        use_bw: bool,
        use_vignette: bool,
        custom_color: Optional[str],
        bg_color: str = "#000000",
    ) -> Image.Image:
        
        # Quadratisch für bestimmte Kategorien (Fuzzy Match auf Namen)
        cat_lower = category.lower()
        if any(x in cat_lower for x in ["krasser", "miststück", "zieh ab", "arschloch"]):
            self.image_size = (960, 960)
        else:
            self.image_size = (1080, 1350)

        # Background
        if background_image:
            img = self.prepare_background(background_image)
        else:
            img = Image.new("RGB", self.image_size, bg_color)

        # Filter
        if use_bw:
            img = ImageOps.grayscale(img).convert("RGB")
            img = ImageEnhance.Contrast(img).enhance(1.2)
        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))
        if use_vignette:
            overlay = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            draw.rectangle([(0, 0), self.image_size], fill=(0, 0, 0, 100))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(img)

        # Farben
        if custom_color: text_color = custom_color
        else: text_color = self.calculate_auto_color(img)
        
        stroke_color = "#000000" if text_color == "#FFFFFF" else "#FFFFFF"

        # Fonts & Größe (Großzügig berechnet)
        base_size = 100 if self.image_size == (960, 960) else 80
        font_head = self.get_font(font_name, int(base_size * scale * 1.2))
        font_body = self.get_font(font_name, int(base_size * scale))

        if self.image_size == (960, 960):
            headline = (headline or "").upper()
            body = (body or "").upper()

        # Layout-Constraints
        margin_side = 150 # ~1.5cm
        top_safe = int(self.image_size[1] * 0.25) # Obere 25% frei
        bottom_safe = int(self.image_size[1] * 0.95)
        max_width = self.image_size[0] - (2 * margin_side)

        lines_head = self.wrap_text(headline, font_head, max_width, draw) if headline else []
        lines_body = self.wrap_text(body, font_body, max_width, draw) if body else []

        def get_h(lines, f):
            return sum([draw.textbbox((0,0), l, font=f)[3] - draw.textbbox((0,0), l, font=f)[1] for l in lines])

        h_head = get_h(lines_head, font_head)
        h_body = get_h(lines_body, font_body)
        
        spacing = 10
        block_gap = 40
        
        total_h = 0
        if lines_head: total_h += h_head + (len(lines_head)-1)*spacing
        if lines_body: total_h += h_body + (len(lines_body)-1)*spacing
        if lines_head and lines_body: total_h += block_gap

        # Vertikale Positionierung im erlaubten Bereich
        min_y = top_safe
        max_y = bottom_safe - total_h
        if max_y < min_y: max_y = min_y # Fallback wenn Text zu lang
        
        start_y = min_y + (max_y - min_y) * pos_y

        # Helper Drawing
        def draw_block(lines, font, y_start, painter, fill, s_width=0, s_fill=None):
            y = y_start
            for l in lines:
                bbox = draw.textbbox((0,0), l, font=font)
                w = bbox[2]-bbox[0]
                h = bbox[3]-bbox[1]
                
                # Horizontal Positionierung (mit Margin)
                avail_w = self.image_size[0] - w - (2 * margin_side)
                x = margin_side + (avail_w * pos_x)
                
                if s_width > 0:
                    painter.text((x, y), l, font=font, fill=fill, stroke_width=s_width, stroke_fill=s_fill)
                else:
                    painter.text((x, y), l, font=font, fill=fill)
                
                y += h + spacing
            return y

        # Schatten
        if use_shadow:
            shadow_layer = Image.new("RGBA", img.size, (0,0,0,0))
            s_draw = ImageDraw.Draw(shadow_layer)
            
            # Schattenfarbe ermitteln
            if text_color == "#FFFFFF": s_rgba = (0,0,0,180)
            else: s_rgba = (255,255,255,180)
            
            sy = start_y + 3 # Offset
            sy = draw_block(lines_head, font_head, sy, s_draw, s_rgba)
            if lines_head and lines_body: sy += block_gap
            draw_block(lines_body, font_body, sy, s_draw, s_rgba)
            
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=4))
            img = Image.alpha_composite(img.convert("RGBA"), shadow_layer).convert("RGB")
            draw = ImageDraw.Draw(img)

        # Haupttext
        ty = start_y
        s_w = int(stroke)
        ty = draw_block(lines_head, font_head, ty, draw, text_color, s_w, stroke_color)
        if lines_head and lines_body: ty += block_gap
        end_y = draw_block(lines_body, font_body, ty, draw, text_color, s_w, stroke_color)

        # Wasserzeichen
        # Mapping: Keyword im Kategorienamen -> Wasserzeichentext
        wm_text = None
        if "narzissmus" in cat_lower: wm_text = "Isaak Öztürk"
        elif "herz" in cat_lower or "umfragen" in cat_lower: wm_text = "Herzwelt"
        
        if wm_text:
            wm_font = self.get_font("Noteworthy", 40)
            wm_bbox = draw.textbbox((0,0), wm_text, font=wm_font)
            wm_w = wm_bbox[2]-wm_bbox[0]
            wm_x = (self.image_size[0] - wm_w) / 2
            wm_y = end_y + 50
            draw.text((wm_x, wm_y), wm_text, font=wm_font, fill=text_color)

        return img
