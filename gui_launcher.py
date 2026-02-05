import tkinter as tk
from tkinter import filedialog, scrolledtext, messagebox
import subprocess
import threading
import sys
import os
import queue

class OCRGuiApp:
    def __init__(self, root):
        self.root = root
        self.root.title("民国报纸 OCR 识别工具箱 (Windows版)")
        self.root.geometry("900x700")
        
        # 样式设置
        self.font_style = ("Microsoft YaHei", 10)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(2, weight=1)

        # 1. 配置区域
        config_frame = tk.LabelFrame(root, text=" 路径配置 ", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        config_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        config_frame.columnconfigure(1, weight=1)

        # 输入目录
        tk.Label(config_frame, text="输入目录 (Images):", font=self.font_style).grid(row=0, column=0, sticky="w")
        self.input_entry = tk.Entry(config_frame, font=self.font_style)
        self.input_entry.insert(0, "images/42")  # 默认值
        self.input_entry.grid(row=0, column=1, sticky="ew", padx=5)
        tk.Button(config_frame, text="浏览...", command=self.browse_input).grid(row=0, column=2)

        # 输出目录
        tk.Label(config_frame, text="输出目录 (Output):", font=self.font_style).grid(row=1, column=0, sticky="w", pady=5)
        self.output_entry = tk.Entry(config_frame, font=self.font_style)
        self.output_entry.insert(0, "output/full_batch_run_42")  # 默认值
        self.output_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        tk.Button(config_frame, text="浏览...", command=self.browse_output).grid(row=1, column=2)

        # 2. 功能按钮区域
        action_frame = tk.LabelFrame(root, text=" 操作面板 ", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        action_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=5)

        btn_font = ("Microsoft YaHei", 11)
        
        # 按钮
        self.btn_run = tk.Button(action_frame, text="🚀 开始批量识别 (异步)", font=btn_font, bg="#e1f5fe", command=self.run_ocr_async)
        self.btn_run.pack(side="left", padx=10, expand=True, fill="x")

        self.btn_fix = tk.Button(action_frame, text="🔧 修复失败任务 (异步)", font=btn_font, bg="#fff3e0", command=self.run_fix_async)
        self.btn_fix.pack(side="left", padx=10, expand=True, fill="x")

        self.btn_vis = tk.Button(action_frame, text="📊 打开可视化界面", font=btn_font, bg="#e8f5e9", command=self.run_visualize)
        self.btn_vis.pack(side="left", padx=10, expand=True, fill="x")

        # 3. 日志区域
        log_frame = tk.LabelFrame(root, text=" 运行日志 ", font=("Microsoft YaHei", 10, "bold"), padx=10, pady=10)
        log_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, font=("Consolas", 9), state='disabled', height=20)
        self.log_text.pack(expand=True, fill="both")

        # 4. 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.grid(row=3, column=0, sticky="ew")

        # 队列用于线程间通信
        self.log_queue = queue.Queue()
        self.process = None
        
        # 定时检查队列更新日志
        self.root.after(100, self.update_log_from_queue)

    def browse_input(self):
        d = filedialog.askdirectory()
        if d:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, d)

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, d)

    def log(self, message):
        self.log_queue.put(message + "\n")

    def update_log_from_queue(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.configure(state='normal')
            self.log_text.insert(tk.END, msg)
            self.log_text.see(tk.END)
            self.log_text.configure(state='disabled')
        self.root.after(100, self.update_log_from_queue)

    def run_process(self, command, cwd=None):
        if self.process and self.process.poll() is None:
            messagebox.showwarning("警告", "当前已有任务在运行中，请等待结束或重启程序。")
            return

        def target():
            self.btn_run.config(state='disabled')
            self.btn_fix.config(state='disabled')
            
            self.log(f"---- 开始执行: {' '.join(command)} ----")
            self.status_var.set("运行中...")
            
            try:
                # 隐藏控制台窗口 (Windows)
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                
                self.process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    cwd=cwd,
                    startupinfo=startupinfo
                )

                for line in self.process.stdout:
                    self.log(line.strip())
                
                self.process.wait()
                rc = self.process.returncode
                if rc == 0:
                    self.log(f"---- 执行完成 (成功) ----")
                    self.status_var.set("执行完成")
                else:
                    self.log(f"---- 执行结束 (退出码: {rc}) ----")
                    self.status_var.set("执行出错")
                    
            except Exception as e:
                self.log(f"启动失败: {str(e)}")
                self.status_var.set("启动失败")
            finally:
                self.btn_run.config(state='normal')
                self.btn_fix.config(state='normal')
                self.process = None

        threading.Thread(target=target, daemon=True).start()

    def run_ocr_async(self):
        inp = self.input_entry.get()
        out = self.output_entry.get()
        if not inp or not out:
            messagebox.showerror("错误", "请先配置输入和输出目录")
            return
        
        cmd = ["python", "main_async.py", "-i", inp, "-o", out]
        self.run_process(cmd)

    def run_fix_async(self):
        inp = self.input_entry.get()
        out = self.output_entry.get()
        if not inp or not out:
            messagebox.showerror("错误", "请先配置输入和输出目录")
            return
            
        cmd = ["python", "fix_failed_images.py", "-i", inp, "-o", out]
        self.run_process(cmd)

    def run_visualize(self):
        self.log("---- 启动可视化界面 (Streamlit) ----")
        self.log("正在打开浏览器...")
        
        def target():
            try:
                # Streamlit 作为一个后台服务运行，不捕获输出到日志框以免阻塞
                cmd = ["streamlit", "run", "visualize.py"]
                subprocess.Popen(cmd, shell=True) 
            except Exception as e:
                self.log(f"启动失败: {e}")
        
        threading.Thread(target=target, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = OCRGuiApp(root)
    root.mainloop()
