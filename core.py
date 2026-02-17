import random
import time
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps


# ---------- Hilfsfunktionen ----------

def sanitize_category_name(name: str) -> str:
    """Wie in deiner Desktop-App: Kategorienamen in Ordnernamen umwandeln."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
        .replace("'", "")
        .replace(",", "")
    )


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


# ---------- Kategorien & Daten-Management ----------

DEFAULT_CATEGORIES_TO_FILES: Dict[str, str] = {
    "Motivation": "motivation.txt",
    "Zieh ab, Arschloch": "zieh_ab.txt",
    "Krasser Strass": "krasser_strass.txt",
    "Miststück aus Prinzip": "miststueck.txt",
    "Dein Sternzeichen": "sternzeichen.txt",
    "Narzissmus": "narzissmus.txt",
    "Umfragen": "umfragen.txt",
    "Herzwelt": "herzwelt.txt",
}


class WebDataManager:
    """
    Vereinfachte, web-taugliche Version deines DataManager:
    - arbeitet nur im Projektordner (kein Desktop-Pfad)
    - nutzt deinen kopierten Folder `data_content_creator`
    - verwaltet Rotation über used_texts_web.json
    """

    def __init__(self):
        self.base_dir = Path(__file__).parent / "data_content_creator"
        self.base_dir.mkdir(exist_ok=True)

        self.final_image_dir = Path(__file__).parent / "generated_posts"
        self.final_image_dir.mkdir(exist_ok=True)

        self.categories_to_files = DEFAULT_CATEGORIES_TO_FILES.copy()

        self.used_texts_file = self.base_dir / "used_texts_web.json"
        self.used_texts: Dict[str, float] = load_json(self.used_texts_file, {})

        # Lock-Dauer in Minuten (ähnlich wie Desktop)
        self.lock_duration_minutes = 10

    # ----- Texte -----

    def get_categories(self) -> List[str]:
        return list(self.categories_to_files.keys())

    def _get_file_for_category(self, category: str) -> Path:
        fname = self.categories_to_files.get(category)
        if not fname:
            # Fallback: Name selbst verwenden
            fname = f"{sanitize_category_name(category)}.txt"
        return self.base_dir / fname

    def load_texts(self, category: str) -> List[str]:
        path = self._get_file_for_category(category)
        if not path.exists():
            return []

        try:
            with path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with path.open("r", encoding="latin-1") as f:
                lines = f.readlines()

        texts = [l.strip() for l in lines if l.strip()]
        # Duplikate entfernen, Reihenfolge stabil halten
        seen = set()
        clean_list = []
        for t in texts:
            if t not in seen:
                seen.add(t)
                clean_list.append(t)
        return clean_list

    def _clean_old_used_texts(self):
        now = time.time()
        lock = self.lock_duration_minutes * 60
        new_used = {t: ts for t, ts in self.used_texts.items() if (now - ts) < lock}
        if len(new_used) != len(self.used_texts):
            self.used_texts = new_used
            save_json(self.used_texts_file, self.used_texts)

    def get_next_text(self, category: str) -> Optional[str]:
        """
        Liefert den nächsten Text für eine Kategorie mit einfacher Rotation:
        - nimmt bevorzugt Texte, die in den letzten X Minuten nicht benutzt wurden
        """
        self._clean_old_used_texts()
        texts = self.load_texts(category)
        if not texts:
            return None

        # verfügbare Texte = alle, die nicht gelockt sind
        available = [t for t in texts if t not in self.used_texts]

        if not available:
            # Wenn alle gesperrt sind, Lock zurücksetzen
            self.used_texts = {}
            save_json(self.used_texts_file, self.used_texts)
            available = texts

        chosen = random.choice(available)
        self.used_texts[chosen] = time.time()
        save_json(self.used_texts_file, self.used_texts)
        return chosen

    # ----- Hintergründe -----

    def get_background_folder_path(self, category: str) -> Path:
        return self.base_dir / f"{sanitize_category_name(category)}_backgrounds"

    def list_backgrounds(self, category: str) -> List[Path]:
        folder = self.get_background_folder_path(category)
        if not folder.exists():
            return []
        files = []
        for ext in ("*.jpg", "*.jpeg", "*.png", "*.webp"):
            files.extend(folder.glob(ext))
        return sorted(files)

    def get_random_background(self, category: str) -> Optional[Path]:
        bgs = self.list_backgrounds(category)
        if not bgs:
            return None
        return random.choice(bgs)

    # ----- Speichern -----

    def get_final_image_save_path(self, category: str) -> Path:
        cat_folder = self.final_image_dir / sanitize_category_name(category)
        cat_folder.mkdir(parents=True, exist_ok=True)
        return cat_folder / f"Finales_Bild_{int(time.time())}_{random.randint(100,999)}.png"


# ---------- Bildgenerator ----------

class ImageGenerator:
    """
    Web-tauglicher Bildgenerator, angelehnt an deine Desktop-Version:
    - Kategorieabhängige Bildgrößen
    - Text-Schatten, Stroke, B&W, Vignette
    - Position & Skalierung steuerbar
    """

    def __init__(self, data_manager: WebDataManager):
        self.dm = data_manager
        self.image_size = (1080, 1350)

    # -- Font-Handling wie in deiner App --

    def get_font(self, font_name: Optional[str], size: int) -> ImageFont.FreeTypeFont:
        if not font_name:
            font_name = "Helvetica"

        # 1. Projekt-Fonts
        fonts_dir = self.dm.base_dir / "fonts"
        candidates = [
            fonts_dir / font_name,
            fonts_dir / f"{font_name}.ttf",
            fonts_dir / f"{font_name}.otf",
        ]

        # 2. System-Fonts (macOS / Linux)
        system_candidates = [
            Path("/Library/Fonts") / f"{font_name}.ttf",
            Path("/Library/Fonts") / f"{font_name}.ttc",
            Path("/System/Library/Fonts") / f"{font_name}.ttc",
            Path("/System/Library/Fonts/Supplemental") / f"{font_name}.ttf",
        ]
        candidates.extend(system_candidates)

        for p in candidates:
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size=size)
                except Exception:
                    continue

        # Fallbacks
        try:
            return ImageFont.truetype(font_name, size=size)
        except Exception:
            pass
        try:
            return ImageFont.truetype("Arial", size=size)
        except Exception:
            return ImageFont.load_default()

    def calculate_auto_color(self, image: Image.Image) -> str:
        if not image:
            return "#FFFFFF"
        thumb = image.resize((1, 1))
        color = thumb.getpixel((0, 0))
        if isinstance(color, int):
            brightness = color
        else:
            r, g, b = color[:3]
            brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "#FFFFFF" if brightness < 120 else "#000000"

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
        left = (new_width - target_w) / 2
        top = (new_height - target_h) / 2
        right = (new_width + target_w) / 2
        bottom = (new_height + target_h) / 2
        return img_resized.crop((left, top, right, bottom))

    def wrap_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
        lines, words, current_line = [], text.split(), ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
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
        # Kategorieabhängige Größe wie in deiner App
        if category in ["Krasser Strass", "Miststück aus Prinzip", "Zieh ab, Arschloch"]:
            self.image_size = (960, 960)
        else:
            self.image_size = (1080, 1350)

        # Hintergrund vorbereiten
        if background_image is not None:
            img = self.prepare_background(background_image)
        else:
            img = Image.new("RGB", self.image_size, bg_color)

        # B&W & Blur & Vignette
        if use_bw:
            img = ImageOps.grayscale(img).convert("RGB")
            img = ImageEnhance.Contrast(img).enhance(1.2)

        if blur > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=blur))

        if use_vignette:
            overlay = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            draw_overlay.rectangle([(0, 0), self.image_size], fill=(0, 0, 0, 100))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(img)

        # Textfarbe
        if custom_color:
            text_color = custom_color
        else:
            text_color = self.calculate_auto_color(img)

        stroke_color = "#000000" if text_color == "#FFFFFF" else "#FFFFFF"

          # Grundgröße etwas größer wählen, damit Standard nicht zu klein ist
        base_size = 100 if category in ["Zieh ab, Arschloch", "Krasser Strass"] else 80
        font_head = self.get_font(font_name, int(base_size * scale * 1.2))
        font_body = self.get_font(font_name, int(base_size * scale))


        if category in ["Zieh ab, Arschloch", "Krasser Strass"]:
            headline = (headline or "").upper()
            body = (body or "").upper()

               # Innenabstände:
        # links/rechts ca. 1.5cm -> je nach Auflösung ca. 140–160px, wir nehmen 150px
        margin_side = 150
        # oben soll die obere 25%-Zone frei bleiben
        top_safe_ratio = 0.25
        top_safe = int(self.image_size[1] * top_safe_ratio)
        max_width = self.image_size[0] - (2 * margin_side)


        lines_head = self.wrap_text(headline, font_head, max_width, draw) if headline else []
        lines_body = self.wrap_text(body, font_body, max_width, draw) if body else []

        def lines_height(lines, font):
            h_sum = 0
            for l in lines:
                bbox = draw.textbbox((0, 0), l, font=font)
                h_sum += bbox[3] - bbox[1]
            return h_sum

        h_head = lines_height(lines_head, font_head)
        h_body = lines_height(lines_body, font_body)

        line_spacing = 10
        block_spacing = 40

                total_content_height = 0
        if lines_head:
            total_content_height += h_head + (len(lines_head) - 1) * line_spacing
        if lines_body:
            total_content_height += h_body + (len(lines_body) - 1) * line_spacing
        if lines_head and lines_body:
            total_content_height += block_spacing

        # Vertikaler Bereich, in dem Text liegen darf:
        # oben 25% frei, unten 5% Reserve
        bottom_safe = int(self.image_size[1] * 0.95)
        min_y = top_safe
        max_y = bottom_safe - total_content_height
        if max_y < min_y:
            max_y = min_y

        # pos_y steuert jetzt nur noch innerhalb dieses erlaubten Bereichs
        current_y = min_y + (max_y - min_y) * pos_y


        s_width = int(stroke)

        # Schatten-Layer
        if use_shadow:
            shadow_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
            draw_shadow = ImageDraw.Draw(shadow_layer)

            # Helligkeit ermitteln
            if text_color.startswith("#"):
                h = text_color.lstrip("#")
                rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            else:
                rgb = (255, 255, 255)
            brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000

            if brightness > 128:
                shadow_rgba = (0, 0, 0, 200)
            else:
                shadow_rgba = (255, 255, 255, 180)

            def draw_lines(lines, font, start_y, painter):
                y = start_y
                for l in lines:
                    bbox = draw.textbbox((0, 0), l, font=font)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                                        avail = self.image_size[0] - w - (2 * margin_side)
                    x = margin_side + (avail * pos_x)

                    painter.text((x+3, y+3), l, font=font, fill=shadow_rgba)
                    y += h + line_spacing
                return y

            sy = current_y
            sy = draw_lines(lines_head, font_head, sy, draw_shadow)
            if lines_head and lines_body:
                sy += (block_spacing - line_spacing)
            draw_lines(lines_body, font_body, sy, draw_shadow)

            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=4))
            img = Image.alpha_composite(img.convert("RGBA"), shadow_layer).convert("RGB")
            draw = ImageDraw.Draw(img)

        # Haupt-Text
        def draw_main(lines, font, start_y):
            y = start_y
            for l in lines:
                bbox = draw.textbbox((0, 0), l, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                avail = self.image_size[0] - w - (2 * margin_px)
                x = margin_px + (avail * pos_x)
                draw.text((x, y), l, font=font, fill=text_color,
                          stroke_width=s_width, stroke_fill=stroke_color)
                y += h + line_spacing
            return y

        ty = current_y
        ty = draw_main(lines_head, font_head, ty)
        if lines_head and lines_body:
            ty += (block_spacing - line_spacing)
        end_y = draw_main(lines_body, font_body, ty)

        # Optional: Wasserzeichen für bestimmte Kategorien
        if category in ["Narzissmus", "Umfragen", "Herzwelt"]:
            if category == "Narzissmus":
                watermark = "Isaak Öztürk"
            else:
                watermark = "Herzwelt"

            wm_font = self.get_font("Noteworthy", 40)
            wm_bbox = draw.textbbox((0, 0), watermark, font=wm_font)
            wm_w = wm_bbox[2] - wm_bbox[0]
            wm_x = (self.image_size[0] - wm_w) / 2
            wm_y = end_y + 40
            draw.text((wm_x, wm_y), watermark, font=wm_font,
                      fill=text_color, stroke_width=1, stroke_fill=stroke_color)

        return img
