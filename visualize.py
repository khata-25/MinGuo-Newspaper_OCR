import streamlit as st
import os
import glob
from PIL import Image
import json
import base64
from io import BytesIO
import streamlit.components.v1 as components

# --- Config & CSS ---
st.set_page_config(layout="wide", page_title="长沙大公报识别校对", initial_sidebar_state="expanded")

# CSS: Cleaner UI, Compact Header, Hidden Streamlit Elements
st.markdown("""
    <style>
        /* Compact Header */
        .block-container { padding-top: 0.5rem; padding-bottom: 0rem; }
        /* header { visibility: hidden; } REMOVED: Caused sidebar toggle to disappear */
        
        /* Typography */
        h3 { font-size: 1.2rem !important; margin: 0 !important; padding: 0 !important;}
        .stMarkdown p { font-size: 0.9rem; }
        
        /* Compact Tabs */
        .stTabs [data-baseweb="tab-list"] { gap: 4px; margin-bottom: 10px; }
        .stTabs [data-baseweb="tab"] { height: 35px; padding: 4px 12px; font-size: 0.9rem; }
        
        /* Sidebar tweaks */
        section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
        
        /* Hide full screen button on images to prevent UI clutter */
        button[title="View fullscreen"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- Helper Functions ---
def get_subdirs(path):
    if not os.path.exists(path): return []
    return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]

def load_files(image_dir, output_dir):
    if not os.path.isdir(image_dir) or not os.path.isdir(output_dir): return []
    layout_files = glob.glob(os.path.join(output_dir, "**", "layout.json"), recursive=True)
    supported_img_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.pdf']
    pairs = []
    
    # Pre-scan markdowns to avoid repeated OS calls
    # Map dir -> md_path
    
    for layout_path in layout_files:
        subdir = os.path.dirname(layout_path)
        dirname = os.path.basename(subdir)
        
        # Locate Markdown
        md_path = None
        candidates = [
            os.path.join(output_dir, f"{dirname}.md"),
            os.path.join(subdir, f"{dirname}.md")
        ]
        for c in candidates:
            if os.path.exists(c):
                md_path = c
                break
        
        # Locate Image
        img_path = None
        for ext in supported_img_exts:
            potential_path = os.path.join(image_dir, dirname + ext)
            if os.path.exists(potential_path):
                img_path = potential_path
                break
        
        if img_path:
             pairs.append({
                "name": dirname,
                "image": img_path,
                "layout": layout_path,
                "markdown": md_path,
                "sort_key": dirname
            })
    pairs.sort(key=lambda x: x["sort_key"])
    return pairs

def pil_to_base64(img, quality=80):
    buffered = BytesIO()
    if img.mode == 'RGBA': img = img.convert('RGB')
    img.save(buffered, format="JPEG", quality=quality)
    return base64.b64encode(buffered.getvalue()).decode()

def search_files(query, file_pairs):
    """Global search in markdown content and layout text."""
    results = []
    if not query: return []
    q = query.lower()
    
    for idx, pair in enumerate(file_pairs):
        # 1. Search Markdown (Preferred)
        if pair["markdown"]:
            try:
                with open(pair["markdown"], 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                if q in content:
                    # Extract context
                    match_idx = content.find(q)
                    start = max(0, match_idx - 10)
                    end = min(len(content), match_idx + 20)
                    snippet = content[start:end].replace('\n', ' ')
                    results.append({
                        "index": idx,
                        "name": pair["name"],
                        "match": f"...{snippet}...",
                        "source": "MD"
                    })
                    continue # Found in MD, skip layout to avoid dupes per file
            except: pass
            
        # 2. Search Layout JSON
        if pair["layout"]:
            try:
                with open(pair["layout"], 'r', encoding='utf-8') as f:
                    layout = json.load(f)
                for r in layout.get('regions', []):
                    if q in r.get('text', '').lower():
                         results.append({
                            "index": idx,
                            "name": pair["name"],
                            "match": f"[{r.get('id')}] {r.get('text')[:15]}...",
                            "source": "OCR"
                        })
                         break
            except: pass
    return results

def generate_interactive_viewer(image_path, layout_path, zoom_level=100, show_text_list=True, split_ratio=70):
    """
    Generates HTML component with:
    1. Top horizontal scrollbar.
    2. JS-based local search/filter.
    3. Vertical layout safe rendering.
    4. Adjustable Split Ratio
    """
    try:
        pil_image = Image.open(image_path)
        w, h = pil_image.size
        img_b64 = pil_to_base64(pil_image)
        
        with open(layout_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            regions = data.get('regions', [])
            
        # Minimal JSON for frontend
        js_regions = []
        for r in regions:
            js_regions.append({
                "id": str(r.get('id', r.get('order', ''))),
                "text": r.get('text', '') or "(空)",
                "type": r.get('region_type', 'text'),
                # Geometry %
                "x": (r['bbox'][0] / w) * 100,
                "y": (r['bbox'][1] / h) * 100,
                "w": ((r['bbox'][2] - r['bbox'][0]) / w) * 100,
                "h": ((r['bbox'][3] - r['bbox'][1]) / h) * 100
            })
        js_regions_json = json.dumps(js_regions)
        
    except Exception as e:
        return f"<div style='color:red'>Data Load Error: {e}</div>"

    img_width_style = f"{zoom_level}%"
    text_col_flex = 100 - split_ratio if show_text_list else 0
    img_col_flex = split_ratio

    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <style>
            :root {{
                --bg-color: #f0f2f6;
                --border-color: #ddd;
                --highlight-color: #ff4b4b;
                --hover-color: #262730;
            }}
            body {{
                margin: 0; padding: 0;
                font-family: sans-serif;
                background-color: var(--bg-color);
                height: 800px; /* Viewport Height */
                display: flex;
                overflow: hidden;
            }}
            
            /* --- Layout Columns --- */
            .main-container {{
                display: flex;
                flex: 1;
                height: 100%;
                width: 100%;
            }}
            
            .image-column {{
                flex: {img_col_flex};
                display: flex;
                flex-direction: column;
                min-width: 0; /* Flexbox safety */
                border-right: 1px solid var(--border-color);
                background: #e5e5e5;
                position: relative;
            }}
            
            .text-column {{
                flex: {text_col_flex};
                display: {'flex' if show_text_list else 'none'};
                flex-direction: column;
                background: white;
                border-left: 1px solid #ccc;
                flex-shrink: 0;
                min-width: 0;
            }}
            
            /* --- Top Scrollbar Sync Logic --- */
            /* A dummy div at top to provide the scrollbar */
            #top-scroll-track {{
                width: 100%;
                height: 18px;
                overflow-x: auto;
                overflow-y: hidden;
                background: #f1f1f1;
                flex-shrink: 0;
                border-bottom: 1px solid #ccc;
            }}
            #top-scroll-dummy {{
                height: 1px;
                width: {zoom_level}%; /* Must match image width */
            }}
            
            /* The real scrolling container for image */
            #image-scroll-view {{
                flex: 1;
                overflow: auto; /* Allow both, but we hide X scrollbar via CSS if we can, or just let it sync */
                position: relative;
                padding: 20px;
                /* Hide native scrollbar if we only want top? 
                   Browsers make this hard. We'll keep default behavior + top sync 
                */
            }}
            
            /* Hide bottom scrollbar to force top usage? Risk of bad UX. 
               Let's just keep both or let top control bottom. 
            */
            
            /* Image Wrapper */
            #image-wrapper {{
                position: relative;
                display: inline-block; /* Tight fit */
                width: {img_width_style};
                min-width: 100px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                background: white;
            }}
            
            #main-image {{
                width: 100%; display: block;
            }}
            
            /* --- Overlays --- */
            .box {{
                position: absolute;
                border: 1px solid rgba(0,0,0,0.05); /* Almost invisible hint */
                cursor: pointer;
                transition: 0.1s;
                z-index: 10;
            }}
            .box:hover {{
                border: 2px solid #0068c9;
                background: rgba(0, 104, 201, 0.1);
                z-index: 20;
            }}
            .box.active {{
                border: 2px solid #ff2b2b;
                z-index: 30;
            }}
            .box.filtered-match {{
                background-color: rgba(255, 215, 0, 0.3);
                border: 1px solid orange;
            }}
            
            /* Tooltip */
            #tooltip {{
                position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                background: rgba(0,0,0,0.8); color: white;
                padding: 6px 12px; border-radius: 4px; font-size: 14px;
                display: none; z-index: 999; pointer-events: none;
            }}
            
            /* --- Text List UI --- */
            .search-header {{
                padding: 8px;
                background: #f8f9fa;
                border-bottom: 1px solid #eee;
            }}
            #local-search-input {{
                width: 95%;
                padding: 6px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
            }}
            #text-list {{
                flex: 1;
                overflow-y: auto;
            }}
            .text-item {{
                padding: 8px 10px;
                border-bottom: 1px solid #f0f0f0;
                font-size: 13px;
                cursor: pointer;
                color: #333;
            }}
            .text-item:hover {{ background: #f0f5ff; }}
            .text-item.active {{ background: #e6f0ff; border-left: 3px solid #0068c9; }}
            .text-item.hidden {{ display: none; }}
            .text-id {{ font-size: 10px; color: #999; margin-bottom: 2px; display: block; }}
            
        </style>
    </head>
    <body>

    <div class="main-container">
        <!-- Image Area -->
        <div class="image-column">
            <!-- Sync Scrollbar (Top) -->
            <div id="top-scroll-track">
                <div id="top-scroll-dummy"></div>
            </div>
            
            <!-- Main Scroll View -->
            <div id="image-scroll-view" onscroll="syncScroll()">
                <div id="image-wrapper">
                    <img id="main-image" src="data:image/jpeg;base64,{img_b64}">
                    <div id="boxes-layer"></div>
                </div>
            </div>
            <div id="tooltip"></div>
            
            <label style="position: absolute; top: 30px; left: 30px; background: rgba(255,255,255,0.8); padding: 5px; z-index: 900; font-size: 12px; border-radius:3px;">
                <input type="checkbox" onchange="document.body.classList.toggle('show-all-boxes', this.checked)"> 显示所有边框
            </label>
        </div>
        
        <!-- Text Area -->
        <div class="text-column">
            <div class="search-header">
                <input type="text" id="local-search-input" placeholder="在当前页查找 (Local Search)..." oninput="filterList()">
            </div>
            <div id="text-list"></div>
        </div>
    </div>

    <script>
        const regions = {js_regions_json};
        const showTextList = { 'true' if show_text_list else 'false' };
        
        let activeId = null;
        
        // --- Init ---
        (function init() {{
            const boxLayer = document.getElementById('boxes-layer');
            const listEl = document.getElementById('text-list');
            const topTrack = document.getElementById('top-scroll-track');
            const view = document.getElementById('image-scroll-view');
            
            // Sync Top Scrollbar
            topTrack.addEventListener('scroll', () => {{
                view.scrollLeft = topTrack.scrollLeft;
            }});
            view.addEventListener('scroll', () => {{
                topTrack.scrollLeft = view.scrollLeft;
            }});
            
            // Render
            regions.forEach(r => {{
                // Box
                const box = document.createElement('div');
                box.className = 'box';
                box.id = 'b-' + r.id;
                box.style.left = r.x + '%';
                box.style.top = r.y + '%';
                box.style.width = r.w + '%';
                box.style.height = r.h + '%';
                box.title = r.text; // Native tooltip
                
                box.onclick = (e) => {{ e.stopPropagation(); activate(r.id); }};
                boxLayer.appendChild(box);
                
                // List Item
                if (showTextList) {{
                    const item = document.createElement('div');
                    item.className = 'text-item';
                    item.id = 't-' + r.id;
                    item.innerHTML = `<span class="text-id">#${{r.id}}</span>${{r.text}}`;
                    item.onclick = () => activate(r.id);
                    listEl.appendChild(item);
                }}
            }});
            
             // Style for show all
            const style = document.createElement('style');
            style.innerHTML = `
                .show-all-boxes .box {{ border: 1px solid rgba(255,0,0,0.3); }}
            `;
            document.head.appendChild(style);
        }})();

        // --- Interaction ---
        function activate(id) {{
            if (activeId === id) return;
            
            // Unset old
            if (activeId) {{
                const oldB = document.getElementById('b-' + activeId);
                const oldT = document.getElementById('t-' + activeId);
                if (oldB) oldB.classList.remove('active');
                if (oldT) oldT.classList.remove('active');
            }}
            
            activeId = id;
            const newB = document.getElementById('b-' + id);
            const newT = document.getElementById('t-' + id);
            
            if (newB) {{
                newB.classList.add('active');
                if (!isShowTextList()) {{
                    showTooltip(regions.find(x => x.id === id).text);
                }}
            }}
            
            if (newT && isShowTextList()) {{
                newT.classList.add('active');
                newT.scrollIntoView({{behavior: "smooth", block: "center"}});
            }}
        }}
        
        function isShowTextList() {{ return { 'true' if show_text_list else 'false' }; }}
        
        function showTooltip(text) {{
            const tt = document.getElementById('tooltip');
            tt.innerText = text;
            tt.style.display = 'block';
            setTimeout(() => tt.style.display = 'none', 3000);
        }}
        
        // --- Filter ---
        function filterList() {{
            const q = document.getElementById('local-search-input').value.toLowerCase();
            regions.forEach(r => {{
                const item = document.getElementById('t-' + r.id);
                const box = document.getElementById('b-' + r.id);
                
                const match = r.text.toLowerCase().includes(q);
                
                // List visibility
                if (item) {{
                    if (match || q === '') item.classList.remove('hidden');
                    else item.classList.add('hidden');
                }}
                
                // Box highlighting for search
                if (box) {{
                    if (q !== '' && match) box.classList.add('filtered-match');
                    else box.classList.remove('filtered-match');
                }}
            }});
        }}
    </script>
    </body>
    </html>
    """
    return html_template

# --- Initialization ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMAGES = os.path.join(BASE_DIR, "images")
DEFAULT_OUTPUT = os.path.join(BASE_DIR, "output")

if "file_pairs" not in st.session_state:
    st.session_state.file_pairs = []
    st.session_state.current_index = 0

# --- Sidebar ---
with st.sidebar:
    st.title("📂 长沙大公报")
    
    # Batch Select
    out_dir = st.text_input("Output Dir", DEFAULT_OUTPUT)
    batches = get_subdirs(out_dir) if os.path.exists(out_dir) else []
    sel_batch = st.selectbox("Batch", batches) if batches else None
    
    if st.button("↻ 刷新 / 加载文件"):
        img_root = DEFAULT_IMAGES
        work_out = DEFAULT_OUTPUT
        if sel_batch:
            work_out = os.path.join(DEFAULT_OUTPUT, sel_batch)
            guess_img = sel_batch.split('_')[-1] if '_' in sel_batch else sel_batch
            img_root = os.path.join(DEFAULT_IMAGES, guess_img)
            
        st.session_state.file_pairs = load_files(img_root, work_out)
        st.session_state.current_index = 0

    st.markdown("---")
    
    # Global Search
    st.subheader("🔍 全局搜索")
    g_search = st.text_input("关键词", placeholder="搜索所有文档...")
    if g_search:
        results = search_files(g_search, st.session_state.file_pairs)
        st.caption(f"找到 {len(results)} 处")
        for res in results[:20]: # Limit display
            if st.button(f"{res['name']}\n{res['match']}", key=f"s_{res['index']}_{res['match'][:5]}"):
                st.session_state.current_index = res['index']
                st.rerun()
        if len(results) > 20: st.caption("...更多结果省略")
        st.markdown("---")

    # Navigation
    pairs = st.session_state.file_pairs
    if pairs:
        cur = st.session_state.current_index
        c1, c2 = st.columns(2)
        if c1.button("⬅️ 上一页") and cur > 0:
            st.session_state.current_index -= 1
            st.rerun()
        if c2.button("下一页 ➡️") and cur < len(pairs) - 1:
            st.session_state.current_index += 1
            st.rerun()
            
        # Jump List
        names = [p['name'] for p in pairs]
        new_name = st.selectbox("跳转到文件", names, index=cur)
        if new_name != names[cur]:
            st.session_state.current_index = names.index(new_name)
            st.rerun()

    st.markdown("---")
    st.caption("界面设置")
    # Split Ratio Slider
    split_ratio = st.slider("分割比例 (图/文)", 10, 90, 50, 5, help="调整图片区域和文本区域的宽度比例")

# --- Main Content ---
if not st.session_state.file_pairs:
    st.info("请在左侧加载文件文件")
    st.stop()

data = st.session_state.file_pairs[st.session_state.current_index]

# Compact Title
st.subheader(f"📄 {data['name']}")

# Tabs
tab_view, tab_edit = st.tabs(["👁️ 浏览校对", "✏️ 文本编辑"])

with tab_view:
    # Custom Layout: Tools (Left) | Viewer (Right)
    c_tools, c_view = st.columns([1, 20])
    
    with c_tools:
        # Vertical-ish Tools
        st.markdown("**缩放**")
        zoom = st.slider("Zoom", 20, 400, 100, step=10, label_visibility="collapsed", key="zoom_view")
    
    with c_view:
        if data["layout"]:
            html = generate_interactive_viewer(data["image"], data["layout"], zoom, show_text_list=True, split_ratio=split_ratio)
            components.html(html, height=800, scrolling=False)
        else:
            st.error("No Layout JSON")

with tab_edit:
    # Layout: Ref Image (Left) | Editor (Right)
    # Use split ratio for columns
    c_ref, c_edit = st.columns([split_ratio, 100-split_ratio])
    
    with c_ref:
        # Zoom above image
        c_z_label, c_z_slider = st.columns([2, 8])
        with c_z_label:
            st.markdown("##### 🔍 缩放")
        with c_z_slider:
            zoom_e = st.slider("Zoom", 20, 400, 100, step=10, label_visibility="collapsed", key="zoom_edit")
            
        st.caption("参考视图 (Reference)")
        if data["layout"]:
            html_ref = generate_interactive_viewer(data["image"], data["layout"], zoom_e, show_text_list=False)
            components.html(html_ref, height=800, scrolling=False)
            
    with c_edit:
        # Header + Find/Replace (Right Aligned)
        c_title, c_f, c_r, c_b = st.columns([2, 1.5, 1.5, 0.8])
        with c_title:
             st.caption("Markdown 编辑 (Editor)")
        with c_f:
             find_txt = st.text_input("Find", placeholder="查找内容", label_visibility="collapsed", key="ft")
        with c_r:
             repl_txt = st.text_input("Replace", placeholder="替换为", label_visibility="collapsed", key="rt")
        with c_b:
             do_replace = st.button("替换", key="btn_rep")

        if data["markdown"] and os.path.exists(data["markdown"]):
            with open(data["markdown"], "r", encoding="utf-8") as f:
                content = f.read()
                
            if do_replace and find_txt:
                count = content.count(find_txt)
                if count > 0:
                    content = content.replace(find_txt, repl_txt)
                    st.toast(f"已替换 {count} 处匹配")
                else:
                    st.toast("未找到匹配项")
                
            new_content = st.text_area("Content", content, height=750, label_visibility="collapsed")
            
            if st.button("💾 保存修改 (Save)"):
                with open(data["markdown"], "w", encoding="utf-8") as f:
                    f.write(new_content)
                st.success("File saved!")
        else:
            st.info("No Markdown file found")
