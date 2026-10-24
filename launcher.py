"""变声整合包 启动器。"""
import os
import subprocess
import sys
import threading
import time
import webbrowser

BASE = os.path.dirname(os.path.abspath(__file__))
RVC = os.path.join(BASE, "RVC")
PY = os.path.join(RVC, "runtime", "python.exe")
PYW = os.path.join(RVC, "runtime", "pythonw.exe")
MODELS = os.path.join(BASE, "模型")


def resolve_tool(*candidates):
    for parts in candidates:
        full = os.path.join(BASE, *parts)
        if os.path.isfile(full):
            return full
    return os.path.join(BASE, *candidates[0])


# 发布包用中文目录，源码仓库用 tools/ 目录，两种都支持
WORKBENCH = resolve_tool(("工具", "变声工作台", "app.py"), ("tools", "workbench", "app.py"))
TTS = resolve_tool(("工具", "文字转语音", "app.py"), ("tools", "tts", "app.py"))
GUIDE = os.path.join(BASE, "说明.txt")

CREATE_NEW_CONSOLE = 0x00000010


def gui():
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import messagebox

    root = tk.Tk()
    root.title("变声整合包")
    root.geometry("580x660")
    root.resizable(False, False)
    root.configure(bg="#f5f6f8")

    ui = tkfont.Font(family="Microsoft YaHei UI", size=10)
    bold = tkfont.Font(family="Microsoft YaHei UI", size=12, weight="bold")

    tk.Label(root, text="变声整合包", font=tkfont.Font(family="Microsoft YaHei UI", size=16, weight="bold"),
             bg="#f5f6f8", fg="#111827").pack(pady=(22, 4))
    tk.Label(root, text="四个功能，按需选择", font=ui, bg="#f5f6f8", fg="#6b7280").pack()

    status = tk.Label(root, text="", font=ui, bg="#f5f6f8", fg="#2563eb")
    status.pack(pady=(6, 10))

    frame = tk.Frame(root, bg="#f5f6f8")
    frame.pack(padx=26, fill="x")

    def make_btn(title, desc, command, color="#2563eb"):
        box = tk.Frame(frame, bg="white")
        box.pack(fill="x", pady=6)
        btn = tk.Button(box, text=title, font=bold, bg=color, fg="white",
                        activebackground=color, activeforeground="white",
                        relief="flat", anchor="w", padx=16, pady=8, cursor="hand2",
                        command=command)
        btn.pack(fill="x")
        tk.Label(box, text=desc, font=ui, bg="white", fg="#6b7280",
                 anchor="w", padx=16, pady=6).pack(fill="x")
        return btn

    def launch(path, cwd=None, pythonw=True, new_console=False):
        if not os.path.isfile(path):
            messagebox.showerror("找不到文件", path)
            return
        exe = PYW if pythonw else PY
        flags = CREATE_NEW_CONSOLE if new_console else 0
        subprocess.Popen([exe, path], cwd=cwd or os.path.dirname(path),
                         creationflags=flags)

    def open_workbench():
        status.config(text="正在打开 拖文件变声 ...")
        launch(WORKBENCH)

    def open_tts():
        status.config(text="正在打开 文字转语音 ...")
        launch(TTS)

    def open_realtime():
        status.config(text="正在打开 实时变声 ...")
        p = os.path.join(RVC, "gui_v1.py")
        launch(p, cwd=RVC)

    def open_train():
        if not os.path.isfile(PY):
            messagebox.showerror("错误", "运行环境不完整：%s" % PY)
            return
        status.config(text="正在启动训练界面，浏览器约 20 秒后自动打开 ...")
        subprocess.Popen([PY, "infer-web.py", "--port", "7897"], cwd=RVC,
                         creationflags=CREATE_NEW_CONSOLE)

        def open_later():
            time.sleep(18)
            webbrowser.open("http://127.0.0.1:7897")

        threading.Thread(target=open_later, daemon=True).start()

    def open_models():
        os.makedirs(MODELS, exist_ok=True)
        os.startfile(MODELS)

    def open_guide():
        if os.path.isfile(GUIDE):
            os.startfile(GUIDE)
        else:
            messagebox.showinfo("说明", "找不到 说明.txt")

    make_btn("1. 拖文件变声", "拖入音频或视频，选择模型，一键转换", open_workbench)
    make_btn("2. 文字转语音", "输入文字，用模型的声音朗读", open_tts)
    make_btn("3. 实时变声", "接麦克风，边说话边变声（需声卡/虚拟声卡）", open_realtime, "#7c3aed")
    make_btn("4. 训练模型", "打开 RVC 训练界面，用自己的录音训练新模型", open_train, "#059669")

    bottom = tk.Frame(root, bg="#f5f6f8")
    bottom.pack(fill="x", padx=26, pady=(14, 8))
    tk.Button(bottom, text="打开模型文件夹", font=ui, bg="white", relief="flat",
              padx=14, pady=6, command=open_models).pack(side="left")
    tk.Button(bottom, text="使用说明", font=ui, bg="white", relief="flat",
              padx=14, pady=6, command=open_guide).pack(side="left", padx=8)

    if not os.path.isdir(MODELS) or not any(f.endswith(".pth") for f in os.listdir(MODELS)):
        tk.Label(root, text="提示：模型文件夹为空。请把 .pth 放进去，功能 1 和 2 才能用。",
                 font=ui, bg="#f5f6f8", fg="#b45309").pack(pady=(4, 12))
    else:
        tk.Label(root, text="模型已就绪", font=ui, bg="#f5f6f8", fg="#059669").pack(pady=(4, 12))

    root.mainloop()


if __name__ == "__main__":
    try:
        gui()
    except Exception:
        import traceback
        with open(os.path.join(BASE, "错误.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
