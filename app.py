import io
import time
import streamlit as st
from PIL import Image
from core import WebDataManager, ImageGenerator

st.set_page_config(page_title="Content Creator Pro", layout="wide", page_icon="🎨")

# CSS für kompakten Look & Loading-Spinner weg
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    div[data-testid="stVerticalBlock"] > div { gap: 0.5rem; }
    /* Radio Buttons größer und hübscher */
    div.row-widget.stRadio > div { flex-direction: row; gap: 10px; overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

# 1. Init
if 'dm' not in st.session_state:
    st.session_state.dm = WebDataManager()
    st.session_state.ig = ImageGenerator(st.session_state.dm)

dm = st.session_state.dm
ig = st.session_state.ig

# 2. Callbacks (Das Geheimnis für "Sofort")
def update_category():
    # Wird ausgeführt, sobald Kategorie gewechselt wird
    cat = st.session_state.selected_category
    # Sofort neuen Text laden
    st.session_state.body_text = dm.get_next_text(cat)
    # Sofort neuen Hintergrund laden (zufällig)
    bgs = dm.list_backgrounds(cat)
    if bgs:
        st.session_state.bg_index = 0 # oder random.randint(0, len(bgs)-1)
    else:
        st.session_state.bg_index = 0

def next_text_callback():
    cat = st.session_state.selected_category
    st.session_state.body_text = dm.get_next_text(cat)

# 3. Layout: Kopfbereich
cols = st.columns([1, 4])
with cols[0]:
    st.markdown("### 🎨 CC Pro")
with cols[1]:
    cats = dm.get_categories()
    if not cats: st.error("Keine Kategorien! Bitte Daten pushen.")
    
    # Radio mit Callback
    st.radio("Kategorie", cats, key="selected_category", horizontal=True, 
             on_change=update_category, label_visibility="collapsed")

if "body_text" not in st.session_state:
    update_category() # Initial load

# Aktuelle Daten holen
category = st.session_state.selected_category
bgs = dm.list_backgrounds(category)

# 4. Hauptbereich (3 Spalten)
c1, c2, c3 = st.columns([1.2, 0.8, 1.5])

# --- SPALTE 1: INHALT ---
with c1:
    st.markdown("#### 📝 Inhalt")
    # Textfeld
    txt = st.text_area("Text", value=st.session_state.body_text, height=150, key="input_text")
    # Button für neuen Text
    st.button("🎲 Neuer Text (Rotation)", on_click=next_text_callback, use_container_width=True)
    
    st.markdown("#### 🖼 Hintergrund")
    if bgs:
        # Slider statt Number Input -> schneller
        bg_idx = st.slider("Bild auswählen", 0, len(bgs)-1, key="bg_index", label_visibility="collapsed")
        st.caption(f"Datei: {bgs[bg_idx].name}")
    else:
        st.warning("Keine Bilder für diese Kategorie gefunden.")
        bg_idx = 0

# --- SPALTE 2: LOOK ---
with c2:
    st.markdown("#### 🎛 Design")
    scale = st.slider("Schriftgröße", 0.5, 2.0, 1.0, 0.1)
    # Standard 0.5 = Perfekte Mitte
    pos_y = st.slider("Pos Oben/Unten", 0.0, 1.0, 0.5, 0.05)
    pos_x = st.slider("Pos Links/Rechts", 0.0, 1.0, 0.5, 0.05)
    
    st.markdown("---")
    c2a, c2b = st.columns(2)
    with c2a:
        shadow = st.checkbox("Schatten", True)
        bw = st.checkbox("B&W", False)
    with c2b:
        vignette = st.checkbox("Vignette", False)
        blur = st.checkbox("Blur", False)
        
    blur_val = 5.0 if blur else 0.0
    
    col_pick = st.color_picker("Textfarbe (Auto = Leer)", "")
    custom_col = col_pick if col_pick else None

# --- SPALTE 3: PREVIEW ---
with c3:
    st.markdown(f"#### 👁️ {category}")
    
    # Rendern
    # Hintergrund laden
    bg_img = None
    if bgs:
        try: bg_img = Image.open(bgs[bg_idx]).convert("RGB")
        except: pass
    
    # Das eigentliche Generieren
    final_img = ig.create_image(
        category=category,
        text=txt,
        bg_image=bg_img,
        scale=scale,
        pos_x=pos_x,
        pos_y=pos_y,
        stroke=0,
        blur=blur_val,
        shadow=shadow,
        bw=bw,
        vignette=vignette,
        custom_color=custom_col
    )
    
    # Anzeigen
    st.image(final_img, use_column_width=True)
    
    # Download
    buf = io.BytesIO()
    final_img.save(buf, format="PNG")
    st.download_button("⬇️ Bild speichern", data=buf.getvalue(), 
                       file_name=f"{category}_{int(time.time())}.png", 
                       mime="image/png", type="primary", use_container_width=True)

# Debug Info in Sidebar (damit Main sauber bleibt)
with st.sidebar:
    st.info(f"Geladene Texte: {len(dm.load_texts(category))}")
    st.info(f"Geladene Bilder: {len(bgs)}")
