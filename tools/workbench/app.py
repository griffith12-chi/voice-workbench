"""变声工作台（整合包版）—— 拖入音频/视频，选择模型，一键变声。"""
import json
import os
import queue
import sys
import threading

ARGS = sys.argv[1:]
sys.argv = sys.argv[:1]

BASE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(BASE))
RVC = os.path.join(PKG, "RVC")
MODELS_DIR = os.path.join(PKG, "模型")
OUT_DIR = os.path.join(BASE, "outputs")
CONFIG = os.path.join(BASE, "config.json")

AUDIO_EXT = {".wav", ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".opus",
             ".wma", ".mp4", ".mkv", ".mov", ".webm", ".avi"}

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

_cfg = {"last_model": "", "pitch": 0, "index_rate": 0.5, "extra_models": []}
try:
    if os.path.isfile(CONFIG):
        with open(CONFIG, "r", encoding="utf-8") as f:
            _cfg.update(json.load(f) or {})
except Exception:
    pass


def save_cfg():
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(_cfg, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def scan_models():
    found = {}
    for d in (MODELS_DIR, os.path.join(RVC, "assets", "weights")):
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".pth"):
                found[os.path.splitext(name)[0]] = os.path.join(d, name)
    for p in _cfg.get("extra_models", []):
        if os.path.isfile(p) and p.lower().endswith(".pth"):
            found[os.path.splitext(os.path.basename(p))[0]] = p
    return found


def find_index(pth):
    import re
    stem = os.path.splitext(os.path.basename(pth))[0]
    cands = []
    for c in (stem, re.sub(r"_e\d+_s\d+$", "", stem), stem.split("_e")[0]):
        if c and c not in cands:
            cands.append(c)

    def match(dir_path):
        if not os.path.isdir(dir_path):
            return ""
        for name in os.listdir(dir_path):
            if not name.endswith(".index"):
                continue
            for c in cands:
                if c in name:
                    return os.path.join(dir_path, name)
        return ""

    hit = match(os.path.dirname(pth))
    if hit:
        return hit
    for c in cands:
        hit = match(os.path.join(RVC, "logs", c))
        if hit:
            return hit
    return match(os.path.join(RVC, "logs"))


def ascii_safe(path):
    if path.isascii():
        return path
    import shutil
    import tempfile
    safe_dir = os.path.join(tempfile.gettempdir(), "vc_workbench_index")
    os.makedirs(safe_dir, exist_ok=True)
    dst = os.path.join(safe_dir, "model.index")
    if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(path):
        shutil.copyfile(path, dst)
    return dst


_VC = {"path": None, "inst": None}


def get_vc(pth, progress):
    if _VC["inst"] is not None and _VC["path"] == pth:
        return _VC["inst"]

    os.chdir(RVC)
    if RVC not in sys.path:
        sys.path.insert(0, RVC)
    os.environ["PATH"] = RVC + os.pathsep + os.environ.get("PATH", "")
    os.environ["weight_root"] = os.path.dirname(pth)
    os.environ["index_root"] = os.path.join(RVC, "logs")
    os.environ["rmvpe_root"] = os.path.join(RVC, "assets", "rmvpe")
    os.environ["hubert_root"] = os.path.join(RVC, "assets", "hubert")

    from configs.config import Config
    from infer.modules.vc.modules import VC

    progress("加载模型 %s ..." % os.path.basename(pth))
    config = Config()
    config.device = "cuda:0"
    config.is_half = True
    vc = VC(config)
    try:
        vc.get_vc(os.path.basename(pth), 0.33, 0.33)
    except Exception:
        vc.get_vc(os.path.basename(pth), 0.33)
    _VC["path"] = pth
    _VC["inst"] = vc
    return vc


def convert_one(vc, src, pth, pitch, index_rate, progress):
    import numpy as np
    import soundfile as sf

    index = find_index(pth)
    index = ascii_safe(index) if index else ""

    progress("转换 %s ..." % os.path.basename(src))
    info, result = vc.vc_single(0, src, pitch, None, "rmvpe", index, index,
                                index_rate, 3, 0, 0.25, 0.33)
    if result is None:
        raise RuntimeError(str(info))

    sr, audio = result
    a = np.asarray(audio)
    a = (a.astype(np.float32) / 32768.0) if a.dtype == np.int16 else a.astype(np.float32)
    a = a.reshape(-1)
    peak = float(np.abs(a).max()) if a.size else 0.0
    if peak > 0:
        a = a / peak * 0.89

    tag = os.path.splitext(os.path.basename(src))[0]
    model_tag = os.path.splitext(os.path.basename(pth))[0]
    dst = os.path.join(OUT_DIR, "%s_%s_p%+d.wav" % (tag, model_tag, pitch))
    sf.write(dst, a, sr, subtype="PCM_16")
    return dst, len(a) / float(sr)


def gui():
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
        root = TkinterDnD.Tk()
        dnd = True
    except Exception:
        import tkinter as tk
        root = tk.Tk()
        dnd = False

    import tkinter as tk
    from tkinter import filedialog, font as tkfont, messagebox, ttk

    root.title("变声工作台")
    root.geometry("900x700")
    root.minsize(820, 620)
    root.configure(bg="#f5f6f8")

    ui = tkfont.Font(family="Microsoft YaHei UI", size=10)
    bold = tkfont.Font(family="Microsoft YaHei UI", size=11, weight="bold")

    tk.Label(root, text="拖入录音或视频 → 选择模型 → 一键变声",
             font=bold, bg="#f5f6f8", fg="#111827").pack(pady=(14, 8))

    row = tk.Frame(root, bg="#f5f6f8")
    row.pack(fill="x", padx=16)
    tk.Label(row, text="模型", font=ui, bg="#f5f6f8").pack(side="left")
    models = scan_models()
    model_var = tk.StringVar()
    combo = ttk.Combobox(row, textvariable=model_var, values=sorted(models), state="readonly",
                         width=38, font=ui)
    combo.pack(side="left", padx=(6, 8))
    if models:
        default = os.path.splitext(os.path.basename(_cfg.get("last_model", "")))[0]
        model_var.set(default if default in models else sorted(models)[0])

    def pick_model():
        p = filedialog.askopenfilename(title="选择 RVC 模型", filetypes=[("RVC 模型", "*.pth")])
        if not p:
            return
        stem = os.path.splitext(os.path.basename(p))[0]
        models[stem] = p
        extra = _cfg.setdefault("extra_models", [])
        if p not in extra:
            extra.append(p)
        save_cfg()
        combo["values"] = sorted(models)
        model_var.set(stem)

    tk.Button(row, text="浏览...", font=ui, relief="flat", bg="white", padx=10, pady=3,
              command=pick_model).pack(side="left")
    tk.Button(row, text="刷新", font=ui, relief="flat", bg="white", padx=10, pady=3,
              command=lambda: (models.update(scan_models()), combo.configure(values=sorted(models)))
              ).pack(side="left", padx=6)

    drop = tk.Label(root, text="把文件拖到这里（支持 mp3 / wav / m4a / mp4 / mkv）\n或点下方“添加文件”",
                    font=ui, bg="#ffffff", fg="#6b7280", relief="flat", height=4)
    drop.pack(fill="x", padx=16, pady=(12, 8))

    listbox = tk.Listbox(root, font=ui, height=7, relief="flat", bg="white",
                         selectmode="extended", activestyle="none")
    listbox.pack(fill="both", expand=True, padx=16)

    files = []

    def add_files(paths):
        for p in paths:
            p = p.strip().strip("{}").strip()
            if not os.path.isfile(p):
                continue
            if os.path.splitext(p)[1].lower() not in AUDIO_EXT:
                continue
            if p in files:
                continue
            files.append(p)
            listbox.insert("end", "  " + os.path.basename(p))

    if dnd:
        def on_drop(event):
            add_files(root.tk.splitlist(event.data))
            log("已添加 %d 个文件" % len(files))
        drop.drop_target_register(DND_FILES)
        drop.dnd_bind("<<Drop>>", on_drop)
        listbox.drop_target_register(DND_FILES)
        listbox.dnd_bind("<<Drop>>", on_drop)
    else:
        drop.config(text="当前环境不支持拖拽，请点“添加文件”")

    btns = tk.Frame(root, bg="#f5f6f8")
    btns.pack(fill="x", padx=16, pady=8)

    def pick_files():
        ps = filedialog.askopenfilenames(title="选择音频/视频")
        add_files(list(ps))

    tk.Button(btns, text="添加文件", font=ui, relief="flat", bg="white", padx=14, pady=5,
              command=pick_files).pack(side="left")
    tk.Button(btns, text="清空列表", font=ui, relief="flat", bg="white", padx=14, pady=5,
              command=lambda: (files.clear(), listbox.delete(0, "end"))).pack(side="left", padx=8)

    par = tk.Frame(root, bg="#f5f6f8")
    par.pack(fill="x", padx=16, pady=(0, 6))
    tk.Label(par, text="变调", font=ui, bg="#f5f6f8").pack(side="left")
    pitch_var = tk.IntVar(value=int(_cfg.get("pitch", 0)))
    pitch_lbl = tk.Label(par, text="%+d" % pitch_var.get(), font=ui, bg="#f5f6f8", width=4)
    pitch_lbl.pack(side="left", padx=4)
    ttk.Scale(par, from_=-14, to=6, variable=pitch_var, orient="horizontal", length=150,
              command=lambda v: pitch_lbl.config(text="%+d" % int(float(v)))).pack(side="left")
    tk.Label(par, text="   索引率", font=ui, bg="#f5f6f8").pack(side="left")
    ir_var = tk.DoubleVar(value=float(_cfg.get("index_rate", 0.5)))
    ir_lbl = tk.Label(par, text="%.2f" % ir_var.get(), font=ui, bg="#f5f6f8", width=5)
    ir_lbl.pack(side="left", padx=4)
    ttk.Scale(par, from_=0, to=1, variable=ir_var, orient="horizontal", length=130,
              command=lambda v: ir_lbl.config(text="%.2f" % float(v))).pack(side="left")

    run_row = tk.Frame(root, bg="#f5f6f8")
    run_row.pack(fill="x", padx=16, pady=6)
    run_btn = tk.Button(run_row, text="开始转换", font=bold, bg="#2563eb", fg="white",
                        activebackground="#1d4ed8", activeforeground="white", relief="flat",
                        padx=22, pady=7, cursor="hand2")
    run_btn.pack(side="left")
    tk.Button(run_row, text="打开输出目录", font=ui, relief="flat", bg="white", padx=14, pady=6,
              command=lambda: os.startfile(OUT_DIR)).pack(side="left", padx=8)

    status = tk.Label(root, text="就绪", font=ui, bg="#f5f6f8", fg="#6b7280", anchor="w")
    status.pack(fill="x", padx=16)

    logbox = tk.Text(root, height=7, font=("Consolas", 9), relief="flat", bg="#eef0f3",
                     fg="#374151", state="disabled", padx=8, pady=6)
    logbox.pack(fill="x", padx=16, pady=(6, 12))

    def log(msg):
        logbox.config(state="normal")
        logbox.insert("end", msg + "\n")
        logbox.see("end")
        logbox.config(state="disabled")
        status.config(text=msg)

    q = queue.Queue()
    busy = {"v": False}

    def poll():
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "log":
                    log(payload)
                elif kind == "done":
                    busy["v"] = False
                    run_btn.config(state="normal", text="开始转换")
                    log(payload)
                elif kind == "error":
                    busy["v"] = False
                    run_btn.config(state="normal", text="开始转换")
                    log("错误：" + payload)
                    messagebox.showerror("转换失败", payload)
        except queue.Empty:
            pass
        root.after(120, poll)

    def worker(sel_model, pitch, idx_rate):
        try:
            vc = get_vc(sel_model, lambda m: q.put(("log", m)))
            ok = 0
            for i, src in enumerate(list(files), 1):
                q.put(("log", "[%d/%d] %s" % (i, len(files), os.path.basename(src))))
                dst, dur = convert_one(vc, src, sel_model, pitch, idx_rate,
                                       lambda m: q.put(("log", "  " + m)))
                ok += 1
                q.put(("log", "  完成 %.1fs -> %s" % (dur, os.path.basename(dst))))
            q.put(("done", "全部完成：%d 个文件 → %s" % (ok, OUT_DIR)))
        except Exception as exc:
            import traceback
            q.put(("error", str(exc) + "\n\n" + traceback.format_exc(limit=3)))

    def on_run():
        if busy["v"]:
            return
        if not files:
            messagebox.showinfo("提示", "先拖入或添加文件")
            return
        name = model_var.get()
        if not name or name not in models:
            messagebox.showinfo("提示", "请选择模型（.pth）")
            return
        sel = models[name]
        _cfg["last_model"] = sel
        _cfg["pitch"] = int(pitch_var.get())
        _cfg["index_rate"] = round(float(ir_var.get()), 2)
        save_cfg()
        busy["v"] = True
        run_btn.config(state="disabled", text="转换中...")
        threading.Thread(target=worker, args=(sel, int(pitch_var.get()), float(ir_var.get())),
                         daemon=True).start()

    run_btn.config(command=on_run)
    root.after(120, poll)
    log("模型目录：%s" % MODELS_DIR)
    if not models:
        log("没有找到模型，请把 .pth 放进 模型 文件夹，或点“浏览...”选择。")
    root.mainloop()


if __name__ == "__main__":
    try:
        gui()
    except Exception:
        import traceback
        with open(os.path.join(BASE, "错误.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
