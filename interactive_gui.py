"""
交互式民国报纸 OCR 识别软件
Interactive MinGuo Newspaper OCR Application

功能特性：
1. 单文件上传识别
2. 实时图像预览（含区域标注）
3. 实时识别结果显示
4. 进度跟踪
"""
import tkinter as tk
from tkinter import filedialog, ttk, scrolledtext, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageFont
import json
import cv2
import numpy as np
from pathlib import Path
import threading
import tempfile
import shutil
import logging
import sys

# 导入处理器
from processor import MinguoOCRProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InteractiveOCRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("民国报纸 OCR 交互式识别软件 v1.0")
        self.root.geometry("1400x900")
        
        # 配置
        self.config = self.load_config()
        self.processor = None
        self.current_image_path = None
        self.current_result = None
        self.temp_dir = None
        self.processing = False
        
        # 样式
        self.font_normal = ("Microsoft YaHei UI", 10)
        self.font_title = ("Microsoft YaHei UI", 11, "bold")
        self.font_large = ("Microsoft YaHei UI", 12, "bold")
        
        # 创建UI
        self.setup_ui()
        
    def load_config(self):
        """加载配置文件"""
        config_path = Path("config.json")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            messagebox.showerror("错误", "配置文件 config.json 不存在！")
            sys.exit(1)
    
    def setup_ui(self):
        """设置UI界面"""
        # 主容器
        main_container = tk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 顶部工具栏
        self.create_toolbar(main_container)
        
        # 中间分隔区域（图片 + 结果）
        content_frame = tk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 左侧：图片预览区
        self.create_image_panel(content_frame)
        
        # 右侧：识别结果区
        self.create_result_panel(content_frame)
        
        # 底部：日志区
        self.create_log_panel(main_container)
        
        # 状态栏
        self.create_status_bar()
        
    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar = tk.Frame(parent, relief=tk.RAISED, bd=2)
        toolbar.pack(fill=tk.X)
        
        # 标题
        title_label = tk.Label(
            toolbar, 
            text="🗞️ 民国报纸 OCR 识别系统",
            font=self.font_large,
            fg="#2196F3"
        )
        title_label.pack(side=tk.LEFT, padx=10, pady=5)
        
        # 按钮区
        btn_frame = tk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT, padx=10, pady=5)
        
        self.btn_upload = tk.Button(
            btn_frame,
            text="📁 选择图片",
            command=self.upload_image,
            font=self.font_normal,
            bg="#4CAF50",
            fg="white",
            padx=20,
            pady=5,
            cursor="hand2"
        )
        self.btn_upload.pack(side=tk.LEFT, padx=5)
        
        self.btn_recognize = tk.Button(
            btn_frame,
            text="🚀 开始识别",
            command=self.start_recognition,
            font=self.font_normal,
            bg="#2196F3",
            fg="white",
            padx=20,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.btn_recognize.pack(side=tk.LEFT, padx=5)
        
        self.btn_save = tk.Button(
            btn_frame,
            text="💾 保存结果",
            command=self.save_result,
            font=self.font_normal,
            bg="#FF9800",
            fg="white",
            padx=20,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.btn_save.pack(side=tk.LEFT, padx=5)
        
        self.btn_clear = tk.Button(
            btn_frame,
            text="🗑️ 清空",
            command=self.clear_all,
            font=self.font_normal,
            bg="#F44336",
            fg="white",
            padx=20,
            pady=5,
            cursor="hand2"
        )
        self.btn_clear.pack(side=tk.LEFT, padx=5)
        
    def create_image_panel(self, parent):
        """创建图片预览面板"""
        image_frame = tk.LabelFrame(
            parent,
            text=" 📷 图片预览 ",
            font=self.font_title,
            padx=10,
            pady=10
        )
        image_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 图片显示区域（带滚动）
        canvas_frame = tk.Frame(image_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.image_canvas = tk.Canvas(canvas_frame, bg="#f0f0f0", highlightthickness=0)
        
        v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.image_canvas.yview)
        h_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self.image_canvas.xview)
        
        self.image_canvas.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.image_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 默认提示
        self.image_canvas.create_text(
            350, 300,
            text="点击 '选择图片' 上传要识别的图片",
            font=("Microsoft YaHei UI", 14),
            fill="#999",
            tags="placeholder"
        )
        
    def create_result_panel(self, parent):
        """创建识别结果面板"""
        result_frame = tk.LabelFrame(
            parent,
            text=" 📝 识别结果 ",
            font=self.font_title,
            padx=10,
            pady=10
        )
        result_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            result_frame,
            variable=self.progress_var,
            maximum=100,
            mode='determinate'
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        self.progress_label = tk.Label(
            result_frame,
            text="等待开始...",
            font=self.font_normal,
            fg="#666"
        )
        self.progress_label.pack(pady=(0, 10))
        
        # 结果文本区域
        self.result_text = scrolledtext.ScrolledText(
            result_frame,
            font=("Microsoft YaHei UI", 10),
            wrap=tk.WORD,
            height=20
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.insert("1.0", "识别结果将在此显示...")
        self.result_text.config(state=tk.DISABLED)
        
    def create_log_panel(self, parent):
        """创建日志面板"""
        log_frame = tk.LabelFrame(
            parent,
            text=" 📋 运行日志 ",
            font=self.font_title,
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            font=("Consolas", 9),
            height=6,
            bg="#1e1e1e",
            fg="#d4d4d4"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
    def create_status_bar(self):
        """创建状态栏"""
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        
        status_bar = tk.Label(
            self.root,
            textvariable=self.status_var,
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=self.font_normal
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def log(self, message, level="INFO"):
        """添加日志"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = self.get_timestamp()
        self.log_text.insert(tk.END, f"[{timestamp}] {level}: {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        logger.info(message)
        
    def get_timestamp(self):
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")
        
    def upload_image(self):
        """上传图片"""
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=[
                ("图片文件", "*.png *.jpg *.jpeg *.bmp"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            self.current_image_path = file_path
            self.log(f"已选择图片: {Path(file_path).name}")
            self.status_var.set(f"已加载: {Path(file_path).name}")
            
            # 显示图片
            self.display_image(file_path)
            
            # 启用识别按钮
            self.btn_recognize.config(state=tk.NORMAL)
            
    def display_image(self, image_path, regions=None):
        """显示图片（可选：带区域标注）"""
        try:
            # 读取图片
            if regions:
                # 如果有区域信息，用 OpenCV 绘制
                image = cv2.imdecode(
                    np.fromfile(image_path, dtype=np.uint8),
                    cv2.IMREAD_COLOR
                )
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                
                # 绘制区域框
                for idx, region in enumerate(regions):
                    bbox = region['bbox']
                    x1, y1, x2, y2 = bbox
                    color = (255, 0, 0)  # 红色
                    cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
                    
                    # 添加区域编号
                    cv2.putText(
                        image,
                        f"#{idx+1}",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        color,
                        2
                    )
                
                # 转换为 PIL Image
                pil_image = Image.fromarray(image)
            else:
                # 直接用 PIL 打开
                pil_image = Image.open(image_path)
            
            # 调整大小以适应显示区域
            display_width = 700
            display_height = 600
            
            pil_image.thumbnail((display_width, display_height), Image.Resampling.LANCZOS)
            
            # 转换为 Tkinter 格式
            self.tk_image = ImageTk.PhotoImage(pil_image)
            
            # 清除画布
            self.image_canvas.delete("all")
            
            # 显示图片
            self.image_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
            self.image_canvas.config(scrollregion=self.image_canvas.bbox("all"))
            
        except Exception as e:
            self.log(f"显示图片失败: {e}", "ERROR")
            messagebox.showerror("错误", f"无法显示图片: {e}")
            
    def start_recognition(self):
        """开始识别"""
        if not self.current_image_path:
            messagebox.showwarning("警告", "请先选择图片！")
            return
            
        if self.processing:
            messagebox.showwarning("警告", "正在识别中，请稍候...")
            return
        
        # 在后台线程中运行识别
        thread = threading.Thread(target=self.run_recognition, daemon=True)
        thread.start()
        
    def run_recognition(self):
        """执行识别（后台线程）"""
        self.processing = True
        
        # 禁用按钮
        self.root.after(0, lambda: self.btn_recognize.config(state=tk.DISABLED))
        self.root.after(0, lambda: self.btn_upload.config(state=tk.DISABLED))
        
        try:
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="minguo_ocr_")
            temp_input = Path(self.temp_dir) / "input"
            temp_output = Path(self.temp_dir) / "output"
            temp_input.mkdir(exist_ok=True)
            temp_output.mkdir(exist_ok=True)
            
            # 复制图片到临时目录
            image_name = Path(self.current_image_path).name
            temp_image = temp_input / image_name
            shutil.copy2(self.current_image_path, temp_image)
            
            self.root.after(0, lambda: self.log("开始识别..."))
            self.root.after(0, lambda: self.status_var.set("识别中..."))
            self.root.after(0, lambda: self.progress_label.config(text="Stage 1: 版面分割..."))
            self.root.after(0, lambda: self.progress_var.set(10))
            
            # 初始化处理器
            self.processor = MinguoOCRProcessor(self.config)
            
            # Stage 1: 版面分割
            self.root.after(0, lambda: self.log("Stage 1: 版面分割..."))
            layout_meta = self.processor.stage1.process_image(
                str(temp_image),
                str(temp_output)
            )
            
            self.root.after(0, lambda: self.progress_var.set(40))
            self.root.after(0, lambda: self.log(f"检测到 {layout_meta['total_regions']} 个区域"))
            
            # 显示带区域标注的图片
            self.root.after(0, lambda: self.display_image(
                self.current_image_path,
                layout_meta['regions']
            ))
            
            # Stage 2: 区域识别
            self.root.after(0, lambda: self.progress_label.config(text="Stage 2: 区域识别..."))
            self.root.after(0, lambda: self.log("Stage 2: 区域识别..."))
            
            image_stem = Path(image_name).stem
            image_output_dir = temp_output / image_stem
            output_md_path = temp_output / f"{image_stem}.md"
            
            # 定义进度回调
            def progress_callback(current, total):
                progress = 40 + int((current / total) * 50)
                self.root.after(0, lambda: self.progress_var.set(progress))
                self.root.after(0, lambda: self.progress_label.config(
                    text=f"识别中: {current}/{total} 区域"
                ))
            
            result = self.processor.stage2.process_image(
                str(image_output_dir),
                str(output_md_path),
                progress_callback=progress_callback
            )
            
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_label.config(text="识别完成！"))
            
            # 显示结果
            self.current_result = result
            self.root.after(0, lambda: self.display_result(result))
            
            self.root.after(0, lambda: self.log("识别完成！"))
            self.root.after(0, lambda: self.status_var.set("识别完成"))
            
            # 启用保存按钮
            self.root.after(0, lambda: self.btn_save.config(state=tk.NORMAL))
            
        except Exception as e:
            error_msg = f"识别失败: {str(e)}"
            self.root.after(0, lambda: self.log(error_msg, "ERROR"))
            self.root.after(0, lambda: self.status_var.set("识别失败"))
            self.root.after(0, lambda: messagebox.showerror("错误", error_msg))
            import traceback
            logger.error(traceback.format_exc())
        finally:
            self.processing = False
            self.root.after(0, lambda: self.btn_recognize.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.btn_upload.config(state=tk.NORMAL))
            
    def display_result(self, result_text):
        """显示识别结果"""
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", result_text)
        self.result_text.config(state=tk.DISABLED)
        
    def save_result(self):
        """保存识别结果"""
        if not self.current_result:
            messagebox.showwarning("警告", "没有可保存的结果！")
            return
            
        file_path = filedialog.asksaveasfilename(
            title="保存识别结果",
            defaultextension=".md",
            filetypes=[
                ("Markdown 文件", "*.md"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_result)
                self.log(f"结果已保存: {Path(file_path).name}")
                messagebox.showinfo("成功", f"结果已保存到:\n{file_path}")
            except Exception as e:
                self.log(f"保存失败: {e}", "ERROR")
                messagebox.showerror("错误", f"保存失败: {e}")
                
    def clear_all(self):
        """清空所有内容"""
        # 清空图片
        self.image_canvas.delete("all")
        self.image_canvas.create_text(
            350, 300,
            text="点击 '选择图片' 上传要识别的图片",
            font=("Microsoft YaHei UI", 14),
            fill="#999",
            tags="placeholder"
        )
        
        # 清空结果
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", "识别结果将在此显示...")
        self.result_text.config(state=tk.DISABLED)
        
        # 重置变量
        self.current_image_path = None
        self.current_result = None
        self.progress_var.set(0)
        self.progress_label.config(text="等待开始...")
        
        # 禁用按钮
        self.btn_recognize.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        
        # 清理临时目录
        if self.temp_dir and Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir)
            except:
                pass
        
        self.log("已清空")
        self.status_var.set("就绪")


def main():
    """主函数"""
    root = tk.Tk()
    app = InteractiveOCRApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
