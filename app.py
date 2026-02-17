import io
from pathlib import Path

import streamlit as st
from PIL import Image

from core import WebDataManager, ImageGenerator


# ---------- Setup ----------

st.set_page_config(
    page_title="Content Creator Pro",
    layout="wide",
    page_icon="🎨",
)

dm = WebDataManager()
ig = ImageGenerator(dm)

st.title("🎨 Content Creator Pro – Web Dashboard")
st.caption("Web-Version deiner Desktop-App mit Kategorien, Rotation & Hintergründen")


# ---------- Sidebar: Globale Einstellungen ----------

with st.sidebar:
    st.header("⚙️ Globale Einstellungen")

    categories = dm.get_categories()
    if not categories:
        st.error("Keine Kategorien gefunden. Prüfe den Ordner `data_content_creator`.")
        st.stop()

    category = st.selectbox("Kategorie", categories)

    font_name = st.text_input("Schriftart (Name / Datei, optional)", value="Helvetica")

    with st.expander("Erweitert", expanded=False):
        lock_minutes = st.number_input(
            "Rotations-Lock (Minuten)",
            min_value=1,
            max_value=1440,
            value=dm.lock_duration_minutes,
            step=1,
            help="Solange bleibt ein Text 'gesperrt', nachdem er verwendet wurde.",
        )
        dm.lock_duration_minutes = int(lock_minutes)

    st.markdown("---")
    st.markdown("**Hintergründe**")

    bgs = dm.list_backgrounds(category)
    use_bg = st.checkbox(f"Hintergründe für {category} nutzen", value=bool(bgs))

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
        st.image(str(bg_file), caption=f"Hintergrund {idx}/{len(bgs)}", use_column_width=True)
    elif use_bg and not bgs:
        st.warning("Für diese Kategorie wurden noch keine Hintergründe importiert.")


# ---------- Tabs ----------

tab_single, tab_batch, tab_settings = st.tabs(["Einzel-Post", "Batch-Vorschau", "Einstellungen"])


# ---------- Tab 1: Einzel-Post ----------

with tab_single:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("📝 Text")

        use_auto_text = st.checkbox(
            "Automatisch nächsten Text aus Datei ziehen (Rotation)",
            value=True,
            help="Nimmt automatisch den nächsten Spruch aus der passenden .txt-Datei.",
        )

        if use_auto_text:
            if st.button("🔄 Nächsten Text laden", type="primary"):
                txt = dm.get_next_text(category)
                if txt:
                    st.session_state["body_text"] = txt
                else:
                    st.warning("Keine Texte für diese Kategorie gefunden.")
        default_text = st.session_state.get("body_text", "")

        headline = st.text_input("Headline (optional)", value="")
        body_text = st.text_area("Haupttext", height=6, value=default_text)

        st.subheader("🎛 Look & Position")

        col_controls1, col_controls2 = st.columns(2)

        with col_controls1:
            text_scale = st.slider("Textgröße", 0.5, 2.5, 1.0, 0.1)
            pos_y = st.slider("Vertikale Position", 0.0, 1.0, 0.5, 0.05)
            pos_x = st.slider("Horizontale Position", 0.0, 1.0, 0.5, 0.05)

        with col_controls2:
            stroke = st.slider("Rand (Stroke)", 0.0, 5.0, 0.0, 0.1)
            blur = st.slider("Hintergrund-Blur", 0.0, 20.0, 0.0, 0.5)
            use_shadow = st.checkbox("Soft-Schatten", value=True)
            use_vignette = st.checkbox("Vignette", value=False)
            use_bw = st.checkbox("Schwarz-Weiß", value=False)

        st.subheader("🎨 Farben")

        col_color1, col_color2 = st.columns(2)
        with col_color1:
            bg_color = st.color_picker("Fallback-Hintergrundfarbe", "#000000")
        with col_color2:
            use_custom_color = st.checkbox("Eigene Textfarbe setzen", value=False)
            if use_custom_color:
                custom_color = st.color_picker("Textfarbe", "#FFFFFF")
            else:
                custom_color = None

        generate = st.button("🎨 Bild generieren", type="primary")

    with col_right:
        st.subheader("👁️ Live-Vorschau")

        if generate:
            # Hintergrundbild laden (falls vorhanden)
            bg_image = None
            if bg_file is not None:
                try:
                    bg_image = Image.open(bg_file).convert("RGB")
                except Exception:
                    st.warning("Konnte Hintergrundbild nicht laden, verwende Fallback-Farbe.")
                    bg_image = None

            if not body_text.strip():
                st.error("Bitte Haupttext eingeben oder automatisch laden.")
            else:
                img = ig.create_image(
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
                st.session_state["last_image"] = img

        if "last_image" in st.session_state:
            img = st.session_state["last_image"]
            st.image(img, use_column_width=True)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            st.download_button(
                "💾 Bild herunterladen",
                data=buf.getvalue(),
                file_name=f"post_{category}_{int(__import__('time').time())}.png",
                mime="image/png",
            )
        else:
            st.info("Noch kein Bild generiert. Stelle links alles ein und klicke auf „Bild generieren“.")


# ---------- Tab 2: Batch-Vorschau (vereinfachte Variante) ----------

with tab_batch:
    st.subheader("🔁 Batch-Vorschau (einfach)")

    st.write(
        "Hier kannst du mehrere Posts auf einmal generieren. "
        "Die Web-Version erzeugt eine Liste von Vorschaubildern für schnelles Durchklicken."
    )

    batch_count = st.slider("Anzahl Posts", 1, 12, 6, 1)

    if st.button("🚀 Batch generieren"):
        texts = []
        for _ in range(batch_count):
            t = dm.get_next_text(category)
            if t:
                texts.append(t)

        if not texts:
            st.warning("Keine Texte gefunden.")
        else:
            cols = st.columns(3)
            images = []

            # Hintergrund ggf. zufällig pro Bild
            all_bgs = dm.list_backgrounds(category) if use_bg else []

            for i, txt in enumerate(texts):
                if all_bgs:
                    chosen_bg = Image.open(all_bgs[i % len(all_bgs)]).convert("RGB")
                elif bg_file is not None:
                    chosen_bg = Image.open(bg_file).convert("RGB")
                else:
                    chosen_bg = None

                img = ig.create_image(
                    category=category,
                    headline="",
                    body=txt,
                    background_image=chosen_bg,
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
                images.append((txt, img))

            # Anzeige im Grid
            for i, (txt, img) in enumerate(images):
                with cols[i % 3]:
                    st.image(img, use_column_width=True)
                    st.caption(f"#{i+1}")
                    with st.expander("Text"):
                        st.write(txt)

            # Download als ZIP wäre möglich, aber dazu müssten wir BytesIO + zipfile nutzen.
            # Das können wir später ergänzen, wenn du möchtest.


# ---------- Tab 3: Einstellungen & Debug ----------

with tab_settings:
    st.subheader("📁 Datenpfade")

    st.code(f"Basisordner: {dm.base_dir}", language="bash")
    st.code(f"Fertige Posts (Web): {dm.final_image_dir}", language="bash")

    st.subheader("📂 Dateien in data_content_creator")

    files = sorted([p.relative_to(dm.base_dir) for p in dm.base_dir.glob("**/*")])
    for p in files:
        st.text(str(p))

    st.subheader("ℹ️ Hinweise")

    st.markdown(
        "- Diese Web-Version nutzt eine Kopie deiner Texte & Hintergründe aus `data_content_creator`.\n"
        "- Rotations-Status wird in `used_texts_web.json` im selben Ordner gespeichert.\n"
        "- OCR (Tesseract) ist in Streamlit Cloud aktuell nicht aktiviert, weil dafür Systempakete nötig wären."
    )
