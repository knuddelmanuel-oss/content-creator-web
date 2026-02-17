import io
from pathlib import Path

import streamlit as st
from PIL import Image

from core import WebDataManager, ImageGenerator


# ---------- Grundlayout kompakt halten ----------

st.set_page_config(
    page_title="Content Creator Pro",
    layout="wide",
    page_icon="🎨",
)

# Weniger Außenabstand, damit alles auf einen Screen passt
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 0.6rem;
        padding-bottom: 0.6rem;
        padding-left: 1.5rem;
        padding-right: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

dm = WebDataManager()
ig = ImageGenerator(dm)

categories = dm.get_categories()
if not categories:
    st.error("Keine Kategorien gefunden. Prüfe den Ordner `data_content_creator`.")
    st.stop()

# ---------- Kopfzeile & Kategorien (horizontal) ----------

top_left, top_right = st.columns([2, 3])

with top_left:
    st.markdown("### 🎨 Content Creator Pro – Web")
    st.caption("Kategorien, Texte & Hintergründe · Rotation aktiv")

with top_right:
    category = st.radio(
        "Kategorie",
        categories,
        horizontal=True,   # alle Kategorien in einer Zeile
    )

# ---------- Sidebar: Hintergründe & Basis ----------

with st.sidebar:
    st.header("📂 Daten & Hintergründe")

    font_name = st.text_input("Schriftart (Name/Datei)", value="Helvetica")

    bgs = dm.list_backgrounds(category)
    use_bg = st.checkbox("Hintergründe nutzen", value=bool(bgs))
    bg_file = None

    if use_bg and bgs:
        idx = st.number_input(
            "Hintergrund-Index",
            min_value=1,
            max_value=len(bgs),
            value=1,
            step=1,
        )
        bg_file = bgs[idx - 1]
        st.image(str(bg_file), caption=f"BG {idx}/{len(bgs)}", use_column_width=True)
    elif use_bg and not bgs:
        st.warning("Keine Hintergründe für diese Kategorie vorhanden.")

    with st.expander("Datenüberblick", expanded=False):
        st.text(f"Basis: {dm.base_dir.name}")
        for p in sorted(dm.base_dir.glob("*.txt")):
            st.text(f"• {p.name}")

# ---------- Hauptbereich: 3 Spalten ohne Tabs ----------

col_text, col_look, col_prev = st.columns([1.2, 1.0, 1.5])


# ===== Spalte 1: Text & Batch =====

with col_text:
    st.markdown("#### 📝 Text")

    use_auto_text = st.checkbox(
        "Auto: nächsten Text aus Datei (Rotation)",
        value=True,
        help="Nimmt automatisch den nächsten Spruch aus der passenden .txt-Datei.",
    )

    if use_auto_text:
        if st.button("🔄 Nächsten Text laden", use_container_width=True):
            txt = dm.get_next_text(category)
            if txt:
                st.session_state["body_text"] = txt
            else:
                st.warning("Keine Texte für diese Kategorie gefunden.")

    default_text = st.session_state.get("body_text", "")

    headline = st.text_input("Headline (optional)", value="", label_visibility="visible")
    body_text = st.text_area(
        "Haupttext",
        height=130,  # bewusst klein, damit alles auf den Screen passt
        value=default_text,
    )

    # Einfache Batch-Funktion komprimiert
    st.markdown("---")
    st.markdown("##### 🔁 Batch (kompakt)")

    batch_count = st.slider("Anzahl", 1, 10, 4, 1)
    run_batch = st.button("🚀 Batch generieren", use_container_width=True)


# ===== Spalte 2: Look & Feel =====

with col_look:
    st.markdown("#### 🎛 Look & Position")

    text_scale = st.slider("Textgröße", 0.5, 2.5, 1.0, 0.1)
    pos_y = st.slider("Vertikal", 0.0, 1.0, 0.5, 0.05)
    pos_x = st.slider("Horizontal", 0.0, 1.0, 0.5, 0.05)

    stroke = st.slider("Rand (Stroke)", 0.0, 5.0, 0.0, 0.1)
    blur = st.slider("BG-Blur", 0.0, 20.0, 0.0, 0.5)

    st.markdown("---")
    st.markdown("#### 🎨 Farben & Effekte")

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
        custom_color = st.color_picker("Textfarbe", "#FFFFFF")

    st.markdown("---")
    generate = st.button("🎨 Einzel-Bild generieren", type="primary", use_container_width=True)


# ===== Spalte 3: Vorschau & Downloads =====

with col_prev:
    st.markdown("#### 👁️ Vorschau")

    img_single = None

    if generate:
        bg_image = None
        if bg_file is not None:
            try:
                bg_image = Image.open(bg_file).convert("RGB")
            except Exception:
                st.warning("Konnte Hintergrundbild nicht laden, verwende BG-Farbe.")
                bg_image = None

        if not body_text.strip():
            st.error("Bitte Haupttext eingeben oder automatisch laden.")
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
            "💾 Bild herunterladen",
            data=buf.getvalue(),
            file_name=f"post_{category}_{int(__import__('time').time())}.png",
            mime="image/png",
            use_container_width=True,
        )
    else:
        st.info("Links alles einstellen und auf „Einzel-Bild generieren“ klicken.")

    # Batch-Ausgabe direkt unter der Einzel-Vorschau
    if run_batch:
        texts = []
        for _ in range(batch_count):
            t = dm.get_next_text(category)
            if t:
                texts.append(t)

        if not texts:
            st.warning("Keine Texte für diese Kategorie gefunden.")
        else:
            st.markdown("---")
            st.markdown("##### Batch-Vorschau")

            cols = st.columns(2)
            for i, txt in enumerate(texts):
                col = cols[i % 2]

                # Background je nach Modus
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
