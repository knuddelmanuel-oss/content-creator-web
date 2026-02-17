import streamlit as st
from PIL import Image
import io
import time
from core import WebDataManager, ImageGenerator
from streamlit_paste_button import paste_image_button as pbutton

# --- CONFIG ---
st.set_page_config(page_title="CC Pro", layout="wide", initial_sidebar_state="collapsed")

# --- CSS HACKS ---
st.markdown("""
<style>
    header {visibility: hidden;}
    footer {visibility: hidden;}
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    div.row-widget.stRadio > div {
        flex-direction: row;
        justify-content: flex-start;
        overflow-x: auto;
        gap: 0.5rem;
        padding-bottom: 5px;
    }
    div.row-widget.stRadio > div > label {
        background-color: #262730;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: 1px solid #444;
        cursor: pointer;
        font-weight: bold;
        white-space: nowrap;
    }
    div.row-widget.stRadio > div > label:hover { border-color: #FF4B4B; }
    div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    
    /* Grid für Batch */
    .batch-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
</style>
""", unsafe_allow_html=True)

# --- STATE ---
if 'dm' not in st.session_state:
    st.session_state.dm = WebDataManager()
    st.session_state.ig = ImageGenerator(st.session_state.dm)

dm = st.session_state.dm
ig = st.session_state.ig

# --- CALLBACKS ---
def on_cat_change():
    cat = st.session_state.sel_cat
    st.session_state.cur_text = dm.get_next_text(cat)
    st.session_state.bg_list = dm.get_backgrounds(cat)
    st.session_state.bg_idx = 0
    # Batch-Texte vorladen (optional)
    st.session_state.batch_texts = [dm.get_next_text(cat) for _ in range(6)]

def on_new_text():
    cat = st.session_state.sel_cat
    st.session_state.cur_text = dm.get_next_text(cat)

# --- UI ---

# 1. Kategorien
cats = dm.get_categories()
if not cats: st.error("Keine Kategorien!"); st.stop()

if 'sel_cat' not in st.session_state:
    st.session_state.sel_cat = cats[0]
    on_cat_change()

st.radio("Kategorie", cats, key="sel_cat", horizontal=True, label_visibility="collapsed", on_change=on_cat_change)

# 2. Tabs für verschiedene Modi
tab_create, tab_batch, tab_import = st.tabs(["🎨 Einzel-Post", "🚀 Batch-Grid (6x)", "📥 Inspiration & Import"])

# --- TAB 1: EINZEL-POST (Dein Haupt-Arbeitsbereich) ---
with tab_create:
    col_ctrl, col_prev = st.columns([1, 1.3])
    
    with col_ctrl:
        st.markdown("**Inhalt & Design**")
        txt_input = st.text_area("Text", value=st.session_state.cur_text, height=140, label_visibility="collapsed")
        
        c1, c2 = st.columns(2)
        c1.button("🎲 Neuer Spruch", on_click=on_new_text, use_container_width=True)
        
        bgs = st.session_state.bg_list
        if bgs:
            bg_idx = st.slider(f"Hintergrund ({len(bgs)})", 0, len(bgs)-1, key="bg_idx")
            cur_bg_path = bgs[bg_idx]
        else:
            st.warning("Keine BG Bilder")
            cur_bg_path = None
            
        st.markdown("---")
        c_s1, c_s2 = st.columns(2)
        scale = c_s1.slider("Größe", 0.5, 2.5, 1.0, 0.1)
        pos_y = c_s2.slider("Pos Y", 0.0, 1.0, 0.5, 0.05)
        
        c_o1, c_o2 = st.columns(2)
        shadow = c_o1.checkbox("Schatten", True)
        bw = c_o2.checkbox("B&W", False)
        
    with col_prev:
        # LIVE RENDER
        final_img = ig.render(
            st.session_state.sel_cat, txt_input, cur_bg_path,
            scale=scale, pos_y=pos_y, pos_x=0.5,
            shadow=shadow, bw=bw
        )
        st.image(final_img, use_column_width=True)
        
        buf = io.BytesIO()
        final_img.save(buf, format="PNG")
        st.download_button("💾 Speichern", data=buf.getvalue(), 
                           file_name=f"Post_{int(time.time())}.png", 
                           mime="image/png", type="primary", use_container_width=True)

# --- TAB 2: BATCH GRID (Masse machen) ---
with tab_batch:
    st.markdown("### 🚀 6 Posts auf einen Streich")
    if st.button("🔄 Neue 6er Ladung generieren"):
        st.session_state.batch_texts = [dm.get_next_text(st.session_state.sel_cat) for _ in range(6)]
    
    if 'batch_texts' in st.session_state:
        # Wir bauen 2 Spalten mit je 3 Bildern
        b_cols = st.columns(3)
        for i, t in enumerate(st.session_state.batch_texts):
            # Zufalls-Hintergrund für jeden Post
            bg_p = bgs[i % len(bgs)] if bgs else None
            
            img = ig.render(st.session_state.sel_cat, t, bg_p, scale=1.0, pos_y=0.5, shadow=True)
            
            with b_cols[i % 3]:
                st.image(img, use_column_width=True)
                st.caption(f"{t[:30]}...")

# --- TAB 3: IMPORT & INSPIRATION (Clipboard) ---
with tab_import:
    st.markdown("### 📋 Bild aus Zwischenablage einfügen")
    st.info("Kopiere ein Bild (Rechtsklick -> Kopieren) und drücke den Button unten.")
    
    paste_result = pbutton(label="📋 BILD EINFÜGEN", background_color="#FF4B4B")
    
    if paste_result.image_data is not None:
        st.success("Bild empfangen!")
        st.image(paste_result.image_data, caption="Inspiration aus Clipboard", width=300)
        
        st.text_area("✍️ Spruch hier abtippen / umformulieren:", height=100)
        st.button("Diesen Text für Post verwenden (Coming Soon)")
    else:
        st.write("Noch kein Bild eingefügt.")
