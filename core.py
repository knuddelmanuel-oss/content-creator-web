import io
import time

import streamlit as st
from PIL import Image

from core import WebDataManager, ImageGenerator


# ---------- Grundlayout maximal kompakt ----------

st.set_page_config(
    page_title="Content Creator Pro",
    layout="wide",
    page_icon="🎨",
)

# Weniger Padding & White-Space im Hauptbereich
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.2rem;
        padding-bottom: 0.2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    .stVerticalBlock { gap: 0.3rem !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

dm = WebDataManager()
ig = ImageGenerator(dm)

categories = dm.get_categories()
if not categories:
    st.error("Keine Kategorien gefunden. Prüfe `data_content_creator` im Projektordner.")
    st.stop()


# ---------- Kopfzeile & Kategorie (oben, kompakt) ----------

head_left, head_right = st.columns([2, 3])

with head_left:
    st.markdown("#### 🎨 Content Creator Pro – Web")
    st.caption("Kategorien, Texte, Hintergründe & Rotation (Web-Version)")

with head_right:
    category = st.radio(
        "Kategorie wählen",
        categories,
        horizontal=True,
        label_visibility="collapsed",
    )

# Aktuelle Kategorie im Preview-Bereich deutlich anzeigen
st.markdown(
    f"<div style='text-align:right; font-size:0.9rem; color:#888;'>Aktuelle Kategorie: "
    f"<span style='font-weight:600; color:#fff;'>{category}</span></div>",
    unsafe_allow_html=True,
)


# ---------- Sidebar: Daten & Hintergründe ----------

with st.sidebar:
    st.markdown("#### 📂 Daten & Hintergründe")

    font_name = st.text_input("Schriftart", value="Helvetica")

    bgs = dm.list_backgrounds(category)
    use_bg = st.checkbox("BG nutzen", value=bool(bgs))
    bg_file = None

    if use_bg and bgs:
        idx = st.number_input(
            "BG-Index",
            min_value=1,
            max_value=len(bgs),
            value=1,
            step=1,
        )
        bg_file = bgs[idx - 1]
        st.image(str(bg_file), caption=f"{idx}/{len(bgs)}", use_column_width=True)
    elif use_bg and not bgs:
        st.warning("Keine Hintergründe gefunden.")

    st.markdown("---")
    st.caption("Textdateien in `data_content_creator`:")
    for p in sorted(dm.base_dir.glob("*.txt")):
        st.text(f"• {p.name}")


# ---------- Hauptbereich: 3 Spalten, alles sichtbar ----------

col_text, col_look, col_prev = st.columns([1.1, 0.9, 1.5])


# ===== Spalte 1: Text & einfache Batch-Auswahl =====

with col_text:
    st.markdown("##### Text")

    use_auto_text = st.checkbox(
        "Auto-Text (Rotation)",
        value=True,
        help="Nimmt automatisch den nächsten Spruch aus der .txt-Datei der Kategorie.",
    )

    if use_auto_text and st.button("🔄 Nächsten Text", use_container_width=True):
        txt = dm.get_next_text(category)
        if txt:
            st.session_state["body_text"] = txt
        else:
            st.warning("Keine Texte für diese Kategorie gefunden.")

    default_text = st.session_state.get("body_text", "")

    headline = st.text_input("Headline", value="", label_visibility="visible")
    body_text = st.text_area(
        "Haupttext",
        height=110,
        value=default_text,
    )

    st.markdown("---")
    st.markdown("##### Batch")

    batch_count = st.slider("Anzahl Posts", 1, 8, 4, 1)
    auto_batch_preview = st.checkbox("Batch-Vorschau direkt unter Bild anzeigen", value=False)


# ===== Spalte 2: Look & Feel =====

with col_look:
    st.markdown("##### Look & Position")

    text_scale = st.slider("Größe", 0.5, 2.5, 1.2, 0.1)
    pos_y = st.slider("Vertikal", 0.0, 1.0, 0.5, 0.05)
    pos_x = st.slider("Horizontal", 0.0, 1.0, 0.5, 0.05)

    stroke = st.slider("Rand", 0.0, 5.0, 0.0, 0.1)
    blur = st.slider("BG-Blur", 0.0, 20.0, 0.0, 0.5)

    st.markdown("---")
    st.markdown("##### Farben & Effekte")

    col_fx1, col_fx2 = st.columns(2)

    with col_fx1:
        bg_color = st.color_picker("BG-Farbe", "#000000")
        use_bw = st.checkbox("B&W", value=False)

    with col_fx2:
        use_shadow = st.checkbox("Schatten", value=True)
        use_vignette = st.checkbox("Vignette", value=False)
        use_custom_color = st.checkbox("Eigene Textfarbe", value=False)

    custom_color = None
    if use_custom_color:
        custom_color = st.color_picker("Text", "#FFFFFF")

    st.markdown("---")
    manual_render = st.checkbox("Nur auf Klick rendern", value=False)
    if manual_render:
        render_click = st.button("🎨 Bild aktualisieren", use_container_width=True)
    else:
        render_click = True  # immer automatisch (Live-Vorschau)


# ===== Spalte 3: Vorschau & Batch-Ausgabe =====

with col_prev:
    st.markdown("##### Vorschau")

    img_single = None

    # Sofort-Vorschau: immer rendern, wenn Einstellungen/Text sich ändern
    if render_click:
        bg_image = None
        if bg_file is not None:
            try:
                bg_image = Image.open(bg_file).convert("RGB")
            except Exception:
                bg_image = None

        if not body_text.strip():
            st.info("Haupttext eingeben oder Auto-Text laden.")
        else:
            img_single = ig.create_image(
                category=category,
                headline=headline,
                body=body_text,
                background_image=bg_image,
                font_name=font_name.strip() or None,
                scale=text_scale,
                pos_x=pos_x,
                pos_y=pos_y,
                stroke=stroke,
                blur=blur,
                use_shadow=use_shadow,
                use_bw=use_bw,
                use_vignette=use_vignette,
                custom_color=custom_color,
                bg_color=bg_color,
            )
            st.session_state["last_image"] = img_single

    if "last_image" in st.session_state:
        img_single = st.session_state["last_image"]

    if img_single is not None:
        st.image(img_single, use_column_width=True)

        buf = io.BytesIO()
        img_single.save(buf, format="PNG")
        st.download_button(
            "💾 Download",
            data=buf.getvalue(),
            file_name=f"post_{category}_{int(time.time())}.png",
            mime="image/png",
            use_container_width=True,
        )

    # Optionale Batch-Vorschau direkt unter dem Einzel-Bild
    if auto_batch_preview and body_text.strip():
        st.markdown("---")
        st.markdown("##### Batch-Vorschau")

        texts = []
        for _ in range(batch_count):
            t = dm.get_next_text(category)
            if t:
                texts.append(t)

        if not texts:
            st.warning("Keine Texte für Batch gefunden.")
        else:
            cols = st.columns(2)
            for i, txt in enumerate(texts):
                col = cols[i % 2]

                bg_for_post = None
                if use_bg and bgs:
                    try:
                        bg_for_post = Image.open(bgs[i % len(bgs)]).convert("RGB")
                    except Exception:
                        bg_for_post = None
                elif bg_file is not None:
                    try:
                        bg_for_post = Image.open(bg_file).convert("RGB")
                    except Exception:
                        bg_for_post = None

                img = ig.create_image(
                    category=category,
                    headline="",
                    body=txt,
                    background_image=bg_for_post,
                    font_name=font_name.strip() or None,
                    scale=text_scale,
                    pos_x=pos_x,
                    pos_y=pos_y,
                    stroke=stroke,
                    blur=blur,
                    use_shadow=use_shadow,
                    use_bw=use_bw,
                    use_vignette=use_vignette,
                    custom_color=custom_color,
                    bg_color=bg_color,
                )

                with col:
                    st.image(img, use_column_width=True, caption=f"#{i+1}")
                    st.write(txt)
