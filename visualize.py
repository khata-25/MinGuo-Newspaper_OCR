import streamlit as st
import os
import glob
import json
import base64
from io import BytesIO
import pandas as pd
import zipfile

# Try importing PIL, handle if missing
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    st.error("PIL (Pillow) library not found. Please install it.")

# --- Config & Setup ---
st.set_page_config(layout="wide", page_title="民国报纸 OCR 校对平台", initial_sidebar_state="expanded")

# --- Styles ---
st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        .stButton button { width: 100%; border-radius: 4px; }
        .success-box { padding: 10px; background-color: #d4edda; color: #155724; border-radius: 4px; margin-bottom: 10px;}
        /* Make data editor taller */
        div[data-testid="stDataEditor"] > div { height: 100%; min-height: 600px; } 
    </style>
""", unsafe_allow_html=True)

# --- Helper Functions ---

@st.cache_data
def load_file_pairs(image_dir, output_dir):
    """Scan directories and pair images with their OCR results."""
    if not os.path.exists(image_dir) or not os.path.exists(output_dir): 
        return []
    
    # Recursively find all layout.json files
    layout_files = glob.glob(os.path.join(output_dir, "**", "layout.json"), recursive=True)
    
    pairs = []
    supported_exts = ['.jpg', '.jpeg', '.png', '.bmp']
    
    for layout_path in layout_files:
        subdir = os.path.dirname(layout_path)
        dirname = os.path.basename(subdir)
        
        # Determine paths
        md_path = os.path.join(subdir, f"{dirname}.md")
        
        # Find matching image
        img_path = None
        # Try finding image with same name in image_dir
        for ext in supported_exts:
            potential = os.path.join(image_dir, dirname + ext)
            if os.path.exists(potential):
                img_path = potential
                break
        
        if img_path:
            pairs.append({
                "name": dirname,
                "image_path": img_path,
                "layout_path": layout_path,
                "markdown_path": md_path,
                "display_name": f"📄 {dirname}"
            })
            
    # Sort by name
    pairs.sort(key=lambda x: x["name"])
    return pairs

def load_data(layout_path):
    """Load regions from JSON."""
    try:
        with open(layout_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('regions', [])
    except Exception as e:
        st.error(f"Error loading JSON: {e}")
        return []

def save_data(layout_path, markdown_path, regions):
    """Save updated regions to JSON and regenerate Markdown."""
    try:
        # 1. Save JSON
        # Load original to keep other fields (version, etc.) if any
        with open(layout_path, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
        
        full_data['regions'] = regions
        
        with open(layout_path, 'w', encoding='utf-8') as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)
            
        # 2. Update Markdown (Simple regeneration)
        # Sort regions by order or top-to-bottom
        regions_sorted = sorted(regions, key=lambda x: x.get('order', x.get('id', 0)))
        
        md_content = f"# {os.path.basename(os.path.dirname(markdown_path))}\n\n"
        for r in regions_sorted:
            text = r.get('text', '').strip()
            if text:
                md_content += f"{text}\n\n"
        
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
            
        return True
    except Exception as e:
        st.error(f"Save Failed: {e}")
        return False

def draw_annotations(image_path, regions, selected_id=None):
    """Draw bounding boxes on image using PIL."""
    try:
        img = Image.open(image_path).convert("RGBA")
        overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        try:
            # Try to load a font, otherwise default
            # Linux path often: /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size=30)
        except:
            font = None 
            
        for r in regions:
            bbox = r.get('bbox')
            if not bbox or len(bbox) != 4: continue
            
            rid = r.get('id')
            is_selected = (str(rid) == str(selected_id))
            
            # Color scheme
            # Unselected: Blue, semi-transparent
            # Selected: Red, solid outline, brighter fill
            if is_selected:
                fill_color = (255, 0, 0, 80)
                outline_color = (255, 0, 0, 255)
                width = 5
            else:
                fill_color = (0, 0, 255, 20)
                outline_color = (0, 0, 255, 100)
                width = 2
            
            draw.rectangle(bbox, fill=fill_color, outline=outline_color, width=width)
            
            # Draw ID Text
            text_pos = (bbox[0], max(0, bbox[1] - 35))
            text_display = str(rid)
            
            # Text background
            left, top, right, bottom = draw.textbbox(text_pos, text_display, font=font)
            draw.rectangle((left-5, top-5, right+5, bottom+5), fill=(255, 255, 255, 200))
            draw.text(text_pos, text_display, fill=(0,0,0,255), font=font)

        return Image.alpha_composite(img, overlay)
    except Exception as e:
        st.error(f"Image Error: {e}")
        return None

def create_zip_export(pairs):
    """Create a ZIP file of all current Markdown files."""
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        for p in pairs:
            if os.path.exists(p['markdown_path']):
                # Arcname: e.g., 43xxx/43xxx.md
                folder_name = p['name']
                zf.write(p['markdown_path'], arcname=f"{folder_name}/{folder_name}.md")
            if os.path.exists(p['layout_path']):
                 folder_name = p['name']
                 zf.write(p['layout_path'], arcname=f"{folder_name}/layout.json")
    return buffer.getvalue()

# --- Main Logic ---

def main():
    st.sidebar.title("🔧 设置 & 导航")
    
    # 1. Configuration
    default_img_dir = "images"
    default_out_dir = "output"
    
    # Auto-detect subdirectory in output if exists (e.g. output/full_batch.../)
    if os.path.exists(default_out_dir):
        subs = [os.path.join(default_out_dir, d) for d in os.listdir(default_out_dir) if os.path.isdir(os.path.join(default_out_dir, d))]
        if subs:
            # Pick the most recent one ideally, or just the first that isn't empty
            subs.sort()
            if subs:
                default_out_dir = subs[-1]

    img_dir = st.sidebar.text_input("图片目录", value=default_img_dir)
    out_dir = st.sidebar.text_input("数据目录 (Output)", value=default_out_dir)
    
    if st.sidebar.button("🔄 刷新文件列表"):
        st.cache_data.clear()

    # 2. Load File List
    pairs = load_file_pairs(img_dir, out_dir)
    
    if not pairs:
        st.warning(f"未找到匹配的数据文件。\n请确认路径：\n- 图片目录: `{img_dir}`\n- 数据目录: `{out_dir}`")
        return

    # 3. Sidebar Filtering/Selection
    search_query = st.sidebar.text_input("🔍 搜索文件名 (Filter)", "")
    
    filtered_pairs = [p for p in pairs if search_query.lower() in p["name"].lower()] if search_query else pairs
    
    if not filtered_pairs:
        st.sidebar.warning("无匹配文件")
        selected_pair = None
    else:
        # Paginator / Selector
        # Use a selectbox for file navigation
        filenames = [p["display_name"] for p in filtered_pairs]
        selected_idx = st.sidebar.selectbox("选择文件", range(len(filenames)), format_func=lambda x: filenames[x])
        selected_pair = filtered_pairs[selected_idx]

    # 4. Global Actions (Export)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📤 导出")
    if st.sidebar.button("下载所有结果 (ZIP)"):
        with st.spinner("打包中..."):
            zip_data = create_zip_export(pairs)
        st.sidebar.download_button(
            label="⬇️ 点击下载 ZIP",
            data=zip_data,
            file_name="ocr_results_export.zip",
            mime="application/zip"
        )
        
    # --- Main Content Area ---
    if selected_pair:
        render_editor(selected_pair)
    else:
        st.info("👈 请在左侧选择一个文件开始校对")

def render_editor(pair):
    st.header(f"{pair['display_name']}")
    
    col_img, col_data = st.columns([1.2, 1])
    
    # Load Data
    regions = load_data(pair['layout_path'])
    
    if not regions:
        st.error("无法加载区域数据")
        return

    # Create DF for Editor
    df = pd.DataFrame(regions)
    
    # Ensure columns exist
    for col in ['id', 'text', 'region_type', 'bbox']:
        if col not in df.columns:
            df[col] = None

    # Reorder columns for display
    # We display ID at the start
    df_editor = df[['id', 'region_type', 'text', 'bbox']] 

    with col_data:
        st.subheader("📝 文本校对")
        
        # Save Button & Highlight Selector
        c1, c2 = st.columns([1, 1])
        with c1:
            save_clicked = st.button("💾 保存修改", type="primary", key="save_btn")
            
        with c2:
            # Highlight selector inside the toolbar
             highlight_id = st.selectbox("高亮显示 ID", [None] + list(df['id']), format_func=lambda x: f"ID: {x}" if x is not None else "显示全部", key="hl_select")

        # Data Editor
        # key needs to be unique per file
        editor_key = f"editor_{pair['name']}"
        
        edited_df = st.data_editor(
            df_editor,
            key=editor_key,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                "region_type": st.column_config.SelectboxColumn("类型", options=["text", "title", "header", "footer", "image", "table"], width="small"),
                "text": st.column_config.TextColumn("识别文本", width="large"),
                "bbox": st.column_config.TextColumn("坐标", disabled=True)
            },
            hide_index=True,
            use_container_width=True,
            height=700,
            num_rows="dynamic"
        )
        
        if save_clicked:
            # Reconstruct list from DF
            new_regions = []
            
            # Need to be careful about preserving other fields if they exist in original JSON but aren't in DF.
            # load_data only returns 'regions'. 
            # In save_data, we load 'full_data' again, so we just replace the 'regions' list.
            # But wait, if we drop fields from individual region objects (like 'confidence'), we lose them.
            # Let's map back.
            
            # Create a dict map of original regions by ID for easy lookup of extra fields
            original_map = {str(r.get('id')): r for r in regions}
            
            for index, row in edited_df.iterrows():
                rid = row['id']
                # If it's a new row added by user, it might not have an ID or valid bbox?
                # st.data_editor adds rows with None/default values.
                # If ID is missing, we should auto-generate or skip? 
                # For now assume mostly edits. New rows might be tricky without logic to add bbox.
                
                # Basic Reconstruction
                r = {
                    "id": rid,
                    "region_type": row['region_type'],
                    "text": row['text'],
                    "bbox": row['bbox']
                }
                
                # Restore extra fields (confidence, etc.) if ID matches
                if str(rid) in original_map:
                    orig = original_map[str(rid)]
                    # Merge orig into r, but let r overwrite keys we edited
                    # Actually safer: take orig and update with edited fields
                    merged = orig.copy()
                    merged.update(r)
                    new_regions.append(merged)
                else:
                    # New region? Or ID changed?
                    # If user adds a row, ID is likely None/Empty. 
                    # This simple editor doesn't support drawing new boxes, so adding rows is weird.
                    # We'll just append what we have.
                    new_regions.append(r)
                
            if save_data(pair['layout_path'], pair['markdown_path'], new_regions):
                st.toast("✅ 保存成功!", icon="🎉")
                st.rerun() # Refresh to update any state if needed

    with col_img:
        st.subheader("🖼️ 图片预览")
        
        # Draw on image
        annotated_img = draw_annotations(pair['image_path'], regions, selected_id=highlight_id)
        if annotated_img:
            st.image(annotated_img, use_container_width=True)

if __name__ == "__main__":
    main()
