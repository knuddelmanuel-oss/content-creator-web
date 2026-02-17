import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import random
from pathlib import Path
import time

st.set_page_config(page_title="Content Creator Pro", layout="wide")

# Titel
st.title("🎨 Content Creator Pro - Web Version")
st.markdown("### Erstelle professionelle Social Media Posts im Browser")

# Sidebar für Einstellungen
with st.sidebar:
    st.header("⚙️ Einstellungen")
    
    category = st.selectbox(
        "Kategorie",
        ["Motivation", "Zieh ab, Arschloch", "Krasser Strass", 
         "Miststück aus Prinzip", "Herzwelt"]
    )
    
    text_size = st.slider("Textgröße", 0.5, 2.5, 1.0, 0.1)
    pos_y = st.slider("Vertikale Position", 0.0, 1.0, 0.5, 0.05)
    
    use_shadow = st.checkbox("Schatten", value=True)
    use_bw = st.checkbox("Schwarz-Weiß", value=False)

# Hauptbereich
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📝 Text eingeben")
    headline = st.text_input("Headline (optional)")
    body_text = st.text_area("Haupttext", height=200, 
                              placeholder="Dein Spruch kommt hier rein...")
    
    bg_color = st.color_picker("Hintergrundfarbe", "#000000")
    text_color = st.color_picker("Textfarbe", "#FFFFFF")
    
    if st.button("🎨 Bild generieren", type="primary"):
        if body_text:
            # Bild erstellen
            img_size = (1080, 1350)
            img = Image.new("RGB", img_size, bg_color)
            draw = ImageDraw.Draw(img)
            
            # Einfache Textpositionierung
            font_size = int(60 * text_size)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except:
                font = ImageFont.load_default()
            
            # Text zentrieren
            y_position = int(img_size[1] * pos_y)
            
            # Schatten
            if use_shadow:
                draw.text((img_size[0]//2 + 3, y_position + 3), body_text, 
                         font=font, fill="#000000", anchor="mm")
            
            # Haupttext
            draw.text((img_size[0]//2, y_position), body_text, 
                     font=font, fill=text_color, anchor="mm")
            
            # Schwarz-Weiß
            if use_bw:
                img = img.convert("L").convert("RGB")
            
            st.session_state['generated_image'] = img
            st.success("✅ Bild erstellt!")
        else:
            st.error("Bitte Text eingeben!")

with col2:
    st.subheader("👁️ Vorschau")
    if 'generated_image' in st.session_state:
        st.image(st.session_state['generated_image'], 
                use_column_width=True)
        
        # Download-Button
        from io import BytesIO
        buf = BytesIO()
        st.session_state['generated_image'].save(buf, format="PNG")
        st.download_button(
            label="💾 Bild herunterladen",
            data=buf.getvalue(),
            file_name=f"post_{int(time.time())}.png",
            mime="image/png"
        )
    else:
        st.info("Erstelle ein Bild um es hier zu sehen")

# Footer
st.markdown("---")
st.markdown("*Content Creator Pro | Powered by Streamlit*")
