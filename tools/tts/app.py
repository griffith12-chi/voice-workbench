"""文字转语音（整合包版）—— 输入文字，用所选模型的声音朗读。"""
import asyncio
import os
import queue
import subprocess
import sys
import threading
import time

ARGS = sys.argv[1:]
sys.argv = sys.argv[:1]

BASE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(os.path.dirname(BASE))
RVC = os.path.join(PKG, "RVC")
MODELS_DIR = os.path.join(PKG, "模型")
OUT_DIR = os.path.join(BASE, "输出")
CONFIG = os.path.join(BASE, "config.json")

VOICES = {
    "云希（男声·自然）": "zh-CN-YunxiNeural",
    "晓晓（女声）": "zh-CN-XiaoxiaoNeural",
    "云健（男声·沉稳）": "zh-CN-YunjianNeural",
}

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(OUT_DIR, exist_ok=True)

_VC = {"path": None, "inst": None}


def scan_models():
    found = {}
    for d in (MODELS_DIR, os.path.join(RVC, "assets", "weights")):
        if not os.path.isdir(d):
            continue
        for name in sorted(os.listdir(d)):
            if name.lower().endswith(".pth"):
                found[os.path.splitext(name)[0]] = os.path.join(d, name)
    return found


def find_index(pth):
    import re
    stem = os.path.splitext(os.path.basename(pth))[0]
    cands = []
    for c in (stem, re.sub(r"_e\d+_s\d+$", "", stem), stem.split("_e")[0]):
        if c and c not in cands:
            cands.append(c)

    def match(d):
        if not os.path.isdir(d):
            return ""
        for name in os.listdir(d):
            if name.endswith(".index"):
                for c in cands:
                    if c in name:
                        return os.path.join(d, name)
        return ""

    return match(os.path.dirname(pth)) or match(os.path.join(RVC, "logs"))


def ascii_safe(path):
    if not path or path.isascii():
        return path
    import shutil
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "vc_tts_index")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "model.index")
    if not os.path.isfile(dst) or os.path.getsize(dst) != os.path.getsize(path):
        shutil.copyfile(path, dst)
    return dst


def synth_base(text, voice, stem, progress):
    mp3 = os.path.join(OUT_DIR, "_tmp_%s.mp3" % stem)
    try:
        import edge_tts

        async def run():
            await edge_tts.Communicate(text, voice).save(mp3)

        asyncio.run(run())
        if os.path.isfile(mp3) and os.path.getsize(mp3) > 1000:
            return mp3
    except Exception:
        pass

    progress("联网语音失败，改用系统语音...")
    wav = os.path.join(OUT_DIR, "_tmp_%s.wav" % stem)
    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SelectVoice('Microsoft Huihui Desktop'); "
        "$s.SetOutputToWaveFile('%s'); $s.Speak([Console]::In.ReadToEnd()); $s.Dispose()"
    ) % wav
    subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                   input=text.encode("utf-8"), check=True)
    return wav


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

    progress("加载模型...")
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


def gui():
    import tkinter as tk
    from tkinter import font as tkfont, messagebox, ttk
    try:
        import winsound
    except ImportError:
        winsound = None

    root = tk.Tk()
    root.title("文字转语音")
    root.geometry("760x640")
    root.minsize(680, 560)
    root.configure(bg="#f5f6f8")

    ui = tkfont.Font(family="Microsoft YaHei UI", size=10)
    bold = tkfont.Font(family="Microsoft YaHei UI", size=11, weight="bold")

    tk.Label(root, text="输入文字，用模型的声音读出来", font=bold,
             bg="#f5f6f8", fg="#111827").pack(pady=(14, 8))

    top = tk.Frame(root, bg="#f5f6f8")
    top.pack(fill="x", padx=16)
    tk.Label(top, text="模型", font=ui, bg="#f5f6f8").pack(side="left")
    models = scan_models()
    model_var = tk.StringVar()
    ttk.Combobox(top, textvariable=model_var, values=sorted(models), state="readonly",
                 width=30, font=ui).pack(side="left", padx=(6, 14))
    if models:
        model_var.set(sorted(models)[0])

    tk.Label(top, text="基础音色", font=ui, bg="#f5f6f8").pack(side="left")
    voice_var = tk.StringVar(value=list(VOICES)[0])
    ttk.Combobox(top, textvariable=voice_var, values=list(VOICES), state="readonly",
                 width=18, font=ui).pack(side="left", padx=6)

    text = tk.Text(root, font=ui, wrap="word", height=9, relief="flat", bg="white",
                   fg="#111827", insertbackground="#111827", padx=10, pady=8)
    text.pack(fill="both", expand=True, padx=16, pady=10)
    text.insert("1.0", "你好，这是一段测试语音。")

    par = tk.Frame(root, bg="#f5f6f8")
    par.pack(fill="x", padx=16)
    tk.Label(par, text="变调", font=ui, bg="#f5f6f8").pack(side="left")
    pitch_var = tk.IntVar(value=-6)
    pl = tk.Label(par, text="-6", font=ui, bg="#f5f6f8", width=4)
    pl.pack(side="left", padx=4)
    ttk.Scale(par, from_=-14, to=6, variable=pitch_var, orient="horizontal", length=180,
              command=lambda v: pl.config(text="%+d" % int(float(v)))).pack(side="left")

    row = tk.Frame(root, bg="#f5f6f8")
    row.pack(fill="x", padx=16, pady=10)
    run_btn = tk.Button(row, text="生成语音", font=bold, bg="#2563eb", fg="white",
                        activebackground="#1d4ed8", activeforeground="white", relief="flat",
                        padx=22, pady=7, cursor="hand2")
    run_btn.pack(side="left")
    play_btn = tk.Button(row, text="播放", font=ui, bg="white", relief="flat",
                         padx=16, pady=7, state="disabled", cursor="hand2")
    play_btn.pack(side="left", padx=8)
    tk.Button(row, text="打开输出目录", font=ui, bg="white", relief="flat", padx=14, pady=7,
              command=lambda: os.startfile(OUT_DIR)).pack(side="left")

    status = tk.Label(root, text="就绪", font=ui, bg="#f5f6f8", fg="#6b7280", anchor="w")
    status.pack(fill="x", padx=16)

    q = queue.Queue()
    state = {"last": None, "busy": False}

    def poll():
        try:
            while True:
                kind, payload = q.get_nowait()
                if kind == "log":
                    status.config(text=payload)
                elif kind == "done":
                    path, dur = payload
                    state["last"] = path
                    state["busy"] = False
                    run_btn.config(state="normal", text="生成语音")
                    play_btn.config(state="normal")
                    status.config(text="完成：%.1f 秒 → %s" % (dur, os.path.basename(path)))
                elif kind == "error":
                    state["busy"] = False
                    run_btn.config(state="normal", text="生成语音")
                    messagebox.showerror("失败", payload)
        except queue.Empty:
            pass
        root.after(120, poll)

    def worker(txt, voice, pitch, pth):
        try:
            stem = time.strftime("%Y%m%d_%H%M%S")
            q.put(("log", "合成基础语音..."))
            src = synth_base(txt, voice, stem, lambda m: q.put(("log", m)))
            vc = get_vc(pth, lambda m: q.put(("log", m)))
            q.put(("log", "转换音色..."))

            import numpy as np
            import soundfile as sf

            index = ascii_safe(find_index(pth))
            info, result = vc.vc_single(0, src, pitch, None, "rmvpe", index, index,
                                        0.5, 3, 0, 0.25, 0.33)
            if result is None:
                raise RuntimeError(str(info))
            sr, audio = result
            a = np.asarray(audio)
            a = (a.astype(np.float32) / 32768.0) if a.dtype == np.int16 else a.astype(np.float32)
            a = a.reshape(-1)
            peak = float(np.abs(a).max()) if a.size else 0.0
            if peak > 0:
                a = a / peak * 0.89
            tag = "".join(c for c in txt[:10] if c not in '\\/:*?"<>|\n').strip() or "语音"
            dst = os.path.join(OUT_DIR, "%s_%s.wav" % (stem, tag))
            sf.write(dst, a, sr, subtype="PCM_16")
            try:
                os.remove(src)
            except OSError:
                pass
            q.put(("done", (dst, len(a) / float(sr))))
        except Exception as exc:
            q.put(("error", str(exc)))

    def on_run():
        if state["busy"]:
            return
        txt = text.get("1.0", "end").strip()
        if not txt:
            messagebox.showinfo("提示", "先输入文字")
            return
        name = model_var.get()
        if not name or name not in models:
            messagebox.showinfo("提示", "请把模型放进 模型 文件夹后重开本程序")
            return
        state["busy"] = True
        run_btn.config(state="disabled", text="生成中...")
        play_btn.config(state="disabled")
        threading.Thread(target=worker, args=(txt, VOICES[voice_var.get()],
                                              int(pitch_var.get()), models[name]),
                         daemon=True).start()

    def on_play():
        if state["last"] and os.path.isfile(state["last"]) and winsound:
            winsound.PlaySound(state["last"], winsound.SND_FILENAME | winsound.SND_ASYNC)

    run_btn.config(command=on_run)
    play_btn.config(command=on_play)
    root.after(120, poll)
    root.mainloop()


if __name__ == "__main__":
    try:
        gui()
    except Exception:
        import traceback
        with open(os.path.join(BASE, "错误.log"), "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise
