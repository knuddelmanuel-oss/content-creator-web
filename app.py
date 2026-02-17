import streamlit as st
from PIL import Image
import io
import time
from core import WebDataManager, ImageGenerator
from streamlit_paste_button import paste_image_button as pbutton

# --- CONFIG ---
st.set_page_config(page_title="CC Pro Agency", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header, footer {visibility: hidden;}
    .block-container { padding: 1rem !important; }
    .stButton > button { border-radius: 8px; font-weight: 600; width: 100%; }
</style>
""", unsafe_allow_html=True)

if 'dm' not in st.session_state:
    st.session_state.dm = WebDataManager()
    st.session_state.ig = ImageGenerator(st.session_state.dm)

dm = st.session_state.dm
ig = st.session_state.ig

# --- LOGIC ---
def on_cat_change():
    cat = st.session_state.sel_cat
    st.session_state.cur_text = dm.get_next_text(cat)
    # This matches the method in core.py now!
    st.session_state.bg_list = dm.get_backgrounds(cat)
    st.session_state.bg_idx = 0
    st.session_state.batch_texts = [dm.get_next_text(cat) for _ in range(6)]

def set_bg(idx):
    st.session_state.bg_idx = idx

# --- UI ---
cats = dm.get_categories()
if not cats: st.error("Keine Daten!"); st.stop()

if 'sel_cat' not in st.session_state:
    st.session_state.sel_cat = cats[0]
    on_cat_change() # Init

# Categories
st.radio("Kategorie", cats, key="sel_cat", horizontal=True, label_visibility="collapsed", on_change=on_cat_change)

tab_edit, tab_batch, tab_clip = st.tabs(["✨ Editor", "📦 Batch (Masse)", "📋 Import"])

# === EDITOR ===
with tab_edit:
    c_ctrl, c_view = st.columns([1, 1.4])
    
    with c_ctrl:
        st.caption("CONTENT")
        st.text_area("Text", value=st.session_state.cur_text, key="cur_text", height=100, label_visibility="collapsed")
        st.button("🎲 Neuer Spruch", on_click=lambda: st.session_state.update(cur_text=dm.get_next_text(st.session_state.sel_cat)))
        
        st.markdown("---")
        st.caption(f"HINTERGRUND ({len(st.session_state.bg_list)})")
        
        bgs = st.session_state.bg_list
        if bgs:
            with st.expander("🖼 Hintergrund-Galerie", expanded=False):
                cols = st.columns(5)
                for i, bg_p in enumerate(bgs):
                    with cols[i % 5]:
                        if st.button(f"{i+1}", key=f"bg_{i}"): set_bg(i)
            st.caption(f"Gewählt: {bgs[st.session_state.bg_idx].name}")
        else:
            st.warning("Keine Bilder gefunden.")
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        scale = c1.slider("Größe", 0.5, 2.5, 1.0)
        pos_y = c2.slider("Pos Y", 0.0, 1.0, 0.5)
        show_mockup = st.checkbox("📱 Instagram Overlay", value=False)

    with c_view:
        cur_bg = bgs[st.session_state.bg_idx] if bgs else None
        
        img = ig.render(
            st.session_state.sel_cat, 
            st.session_state.cur_text, 
            cur_bg, 
            scale=scale, pos_y=pos_y, 
            draw_overlay=show_mockup, 
            shadow=True
        )
        st.image(img, use_column_width=True)
        
        # Download clean version logic
        if show_mockup:
            dl_img = ig.render(st.session_state.sel_cat, st.session_state.cur_text, cur_bg, scale=scale, pos_y=pos_y, draw_overlay=False, shadow=True)
        else:
            dl_img = img
            
        buf = io.BytesIO()
        dl_img.save(buf, format="PNG")
        st.download_button("⬇️ Bild speichern", data=buf.getvalue(), file_name="Post.png", mime="image/png", type="primary", use_container_width=True)

# === BATCH ===
with tab_batch:
    c_h, c_a = st.columns([3, 1])
    c_h.markdown("### 🏭 Massenproduktion")
    if c_a.button("🔄 Neue Sprüche"):
        st.session_state.batch_texts = [dm.get_next_text(st.session_state.sel_cat) for _ in range(6)]

    b_cols = st.columns(3)
    bgs = st.session_state.bg_list
    
    for i, txt in enumerate(st.session_state.batch_texts):
        bg = bgs[i % len(bgs)] if bgs else None
        thumb = ig.render(st.session_state.sel_cat, txt, bg, scale=0.8, shadow=True)
        with b_cols[i % 3]:
            st.image(thumb, use_column_width=True)
    
    st.markdown("---")
    zip_data = ig.create_batch_zip(st.session_state.sel_cat, st.session_state.batch_texts, bgs)
    st.download_button("📦 ALLE ALS ZIP LADEN", data=zip_data, file_name="Batch.zip", mime="application/zip", type="primary", use_container_width=True)

# === CLIPBOARD ===
with tab_clip:
    st.info("Kopiere ein Bild und klicke unten.")
    res = pbutton("📋 BILD EINFÜGEN")
    if res.image_data:
        st.image(res.image_data, width=300)
        st.text_area("Abschreiben:", height=100)
