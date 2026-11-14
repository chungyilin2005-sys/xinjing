#!/usr/bin/env python3
"""用 edge-tts（Edge 瀏覽器「大聲朗讀」的微軟語音）把經文、白話、註解逐項合成成音檔，存到 audio/，
供 build.py 內嵌成「預錄朗讀」。不需要金鑰。

用法（在專案根目錄執行）：
    pip install edge-tts           # 註解轉成 24 kbps mp3 需要 ffmpeg
    python tools/tts_edge.py       # 只重做文字或設定有變的項目
    其他選項：
        --force                    全部重做
        --only j:3                 只重做指定項目（可重複指定；j:段、p:段、n:段:句）

聲音：
    經文 zh-TW-HsiaoYuNeural 曉雨，mp3 48 kbps（edge-tts 原檔）
    白話 zh-TW-HsiaoChenNeural 曉臻，mp3 24 kbps（使用者 2026-11-14 決定預錄白話、選曉臻）
    註解 zh-TW-HsiaoChenNeural 曉臻，mp3 24 kbps
語速一律 -10%（網頁以 0.8 為原速）。
manifest 每項記下聲音；換聲音時只重做該類。

注意：edge-tts 使用的是 Edge 的非公開介面，不是微軟正式授權的服務，可能隨時改變或失效。
若出現 403，先升級 edge-tts；不要用偽造標頭等方式繞過。

念的文字（含讀音校正 SAY、SAY_NOTE）由 tools/textdata.py 產生，與網頁一致；
manifest.json 記下每項的文字，build.py 會核對。產生後執行 python tools/build.py。
"""
import argparse, asyncio, json, os, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import textdata  # noqa: E402

OUTDIR = os.path.join(ROOT, "audio")
MANIFEST = os.path.join(OUTDIR, "manifest.json")
VOICES = {"j": "zh-TW-HsiaoYuNeural", "p": "zh-TW-HsiaoChenNeural", "n": "zh-TW-HsiaoChenNeural"}
RATE, PITCH = "-10%", "+0Hz"
FFMPEG_24K = ["-ac", "1", "-ar", "22050", "-b:a", "24k"]


async def synth(text, path, voice):
    import edge_tts
    err = "音檔是空的"
    for attempt in range(8):  # 服務偶爾回「No audio was received」，多試幾次
        try:
            await edge_tts.Communicate(text, voice, rate=RATE, pitch=PITCH).save(path)
            if os.path.getsize(path) > 0:
                return True
        except Exception as e:
            err = e
        await asyncio.sleep(3 * (attempt + 1))
    print(f"產生失敗，先跳過：{os.path.basename(path)}（{err}）", flush=True)
    return False


def fname(iid):
    return iid.replace(":", "_") + ".mp3"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", action="append")
    a = ap.parse_args()
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        sys.exit("請先安裝：pip install edge-tts")
    if not shutil.which("ffmpeg"):
        sys.exit("需要 ffmpeg（註解轉成 24 kbps）")

    old = {}
    if os.path.exists(MANIFEST):
        m = json.load(open(MANIFEST, encoding="utf-8"))
        if m.get("rate") == RATE:
            # 項目沒有記聲音時（舊版 manifest），以 manifest 的 voices 判斷；聲音相同才沿用
            mv = m.get("voices", {})
            old = {it["id"]: it for it in m.get("items", [])
                   if it.get("voice", mv.get(it["id"][0])) == VOICES.get(it["id"][0])}
    os.makedirs(OUTDIR, exist_ok=True)
    todo, ok = [], []  # ok：檔案存在且文字相符，可寫進 manifest
    for iid, kind, text in textdata.items(textdata.load()):
        if kind not in VOICES:
            continue
        f = fname(iid)
        path = os.path.join(OUTDIR, f)
        it = {"id": iid, "file": f, "text": text, "voice": VOICES[kind]}
        same = iid in old and old[iid].get("text") == text and os.path.exists(path)
        redo = (iid in a.only) if a.only else (a.force or not same)
        todo.append((it, kind, redo))
        if same and not redo:
            ok.append(iid)

    def save():
        # 每做完一項就寫一次 manifest，中途失敗時下次可以接著做
        items = [it for it, _, _ in todo if it["id"] in ok]
        manifest = {"voices": VOICES, "rate": RATE, "pitch": PITCH, "source": "edge-tts", "items": items}
        with open(MANIFEST, "w", encoding="utf-8") as fp:
            json.dump(manifest, fp, ensure_ascii=False, indent=1)
        return items

    made = 0
    for it, kind, redo in todo:
        if not redo:
            continue
        path = os.path.join(OUTDIR, it["file"])
        if kind == "j":
            if not await synth(it["text"], path, VOICES[kind]):
                continue
        else:
            with tempfile.TemporaryDirectory() as td:
                tmp = os.path.join(td, "a.mp3")
                if not await synth(it["text"], tmp, VOICES[kind]):
                    continue
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp] + FFMPEG_24K + [path], check=True)
        made += 1
        if it["id"] not in ok:
            ok.append(it["id"])
        save()
        print(f"{it['id']:8s} {os.path.getsize(path)//1024:3d} KB  {it['text']}", flush=True)
    items = save()
    # 清掉不再使用的舊音檔（只限本工具產生的 mp3：舊版的「數字開頭」與 j_／p_／n_）
    keep = {it["file"] for it, _, _ in todo}
    for f in os.listdir(OUTDIR):
        if f.endswith(".mp3") and f not in keep and (f[:2].isdigit() or f[:2] in ("j_", "p_", "n_")):
            os.remove(os.path.join(OUTDIR, f))
    if len(items) < len(todo):
        sys.exit(f"還有 {len(todo) - len(items)} 項沒有錄音（服務不穩），請再執行一次，只會補做缺的")
    total = sum(os.path.getsize(os.path.join(OUTDIR, it["file"])) for it in items)
    print(f"完成：重做 {made} 項，共 {len(items)} 項，{total//1024} KB → {OUTDIR}。接著執行 python tools/build.py")


if __name__ == "__main__":
    asyncio.run(main())
