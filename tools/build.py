#!/usr/bin/env python3
"""建置 index.html：從範本擷取用到的字，子集化字體後以 base64 內嵌。

用法（在專案根目錄執行）：
    pip install fonttools brotli pillow
    python3 tools/build.py [字體檔路徑] [--no-audio]

也會內嵌 data/ 的註解、序與白話（經 tools/textdata.py 套用 data/corrections.json），
以及 audio/ 的預錄朗讀（tools/tts_edge.py 產生）。錄音的文字與目前的經文、註解、白話、
讀音校正表不一致時會停止，請重新執行 tts_edge.py；--no-audio 則略過預錄。

預設字體檔路徑：fonts/LXGWWenKaiTC-Regular.ttf（原始完整字體，未隨附於壓縮檔）。
若找不到原始字體，會改用 fonts/WenKai-subset.woff2（僅含目前用到的字）；
這種情況下若範本新增了新的中文字，新字會以備用字體顯示，並列出缺字。
"""
import base64, json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import textdata  # noqa: E402

TEMPLATE = os.path.join(ROOT, "src", "xinjing.template.html")
OUT = os.path.join(ROOT, "index.html")
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
NO_AUDIO = "--no-audio" in sys.argv
FULL = ARGS[0] if ARGS else os.path.join(ROOT, "fonts", "LXGWWenKaiTC-Regular.ttf")
SUBSET = os.path.join(ROOT, "fonts", "WenKai-subset.woff2")
EXTRA = "0123456789民國年月日敬書"  # 匯出圖片落款會用到、但不一定出現在 HTML 原文的字

html = open(TEMPLATE, encoding="utf-8").read()
if "__FONT_B64__" not in html:
    sys.exit("範本缺少 __FONT_B64__ 預留位置")

# 註解、序、白話：先內嵌，字體子集才會包含這些字
D = textdata.load()
if "/*__DATA__*/null" not in html:
    sys.exit("範本缺少 /*__DATA__*/null 預留位置")
data = {"segs": D["segs"], "preface": D["preface"], "preface_title": D["preface_title"], "credit": D["credit"]}
html = html.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
print(f"已內嵌註解 {sum(len(s['n']) for s in D['segs'])} 句、白話 {sum(1 for s in D['segs'] if s['p'])} 段、"
      f"序 {len(D['preface'])} 段（套用修正 {D['ncorr']} 條）")

chars = set(c for c in html if ord(c) > 127) | set(EXTRA) | set(chr(c) for c in range(32, 127))

if os.path.exists(FULL):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("".join(sorted(chars)))
        txt = f.name
    subprocess.run(["pyftsubset", FULL, f"--text-file={txt}", "--flavor=woff2",
                    f"--output-file={SUBSET}", "--layout-features=*"], check=True)
    os.unlink(txt)
    print(f"已從完整字體子集化 {len(chars)} 個字元 → {SUBSET}")
else:
    print(f"找不到 {FULL}，改用現有子集字體 {SUBSET}")
    try:
        from fontTools.ttLib import TTFont
        cmap = TTFont(SUBSET).getBestCmap()
        missing = sorted(c for c in chars if ord(c) not in cmap and not c.isspace())
        if missing:
            print("警告：子集字體缺少這些字，會以備用字體顯示：", "".join(missing))
    except Exception as e:
        print("（無法檢查缺字：", e, "）")

b64 = base64.b64encode(open(SUBSET, "rb").read()).decode()
html = html.replace("__FONT_B64__", b64)

# 主畫面圖示：磁青底、泥金「心」字，512 px，全幅底色（可當 maskable 圖示），字在中央安全範圍內
ICON = os.path.join(ROOT, "icons", "icon-512.png")
def make_icon():
    from PIL import Image, ImageDraw, ImageFont
    S = 512
    img = Image.new("RGB", (S, S), "#16203A")
    d = ImageDraw.Draw(img)
    src = FULL if os.path.exists(FULL) else SUBSET
    font = ImageFont.truetype(src, int(S * 0.64))
    l, t, r, b = d.textbbox((0, 0), "心", font=font)
    d.text(((S - (r - l)) / 2 - l, (S - (b - t)) / 2 - t), "心", font=font, fill="#D3B169")
    os.makedirs(os.path.dirname(ICON), exist_ok=True)
    img.save(ICON, optimize=True)
try:
    make_icon()
    print(f"已產生圖示 {ICON}（{os.path.getsize(ICON)//1024} KB）")
except Exception as e:
    if not os.path.exists(ICON):
        sys.exit(f"無法產生圖示（需要 pip install pillow）：{e}")
    print("（無法重新產生圖示，沿用現有檔案：", e, "）")
if "__ICON_B64__" not in html:
    sys.exit("範本缺少 __ICON_B64__ 預留位置")
html = html.replace("__ICON_B64__", base64.b64encode(open(ICON, "rb").read()).decode())

# 預錄朗讀：audio/manifest.json 存在時，把各項音檔以 base64 內嵌（由 tools/tts_edge.py 產生）
AUDIO = os.path.join(ROOT, "audio")
MANIFEST = os.path.join(AUDIO, "manifest.json")
if "/*__AUDIO__*/null" not in html:
    sys.exit("範本缺少 /*__AUDIO__*/null 預留位置")
if NO_AUDIO:
    print("--no-audio：略過預錄朗讀")
elif os.path.exists(MANIFEST):
    man = json.load(open(MANIFEST, encoding="utf-8"))
    # 網頁把音檔逐幀接成一條連續音訊：每幀固定 FRAME 位元組、24 ms，不可有標頭（見 tts_edge.py 的 FORMAT）
    FRAME = 120
    if man.get("format") != "mp3 24000Hz mono 40k cbr noreservoir noxing":
        sys.exit("錄音格式是舊版，請執行 python tools/tts_edge.py 重新產生；或加 --no-audio 略過預錄")
    def frames_ok(b):
        return len(b) % FRAME == 0 and all(b[i] == 0xFF and b[i + 1] & 0xE0 == 0xE0 for i in range(0, len(b), FRAME))
    have = {it["id"]: it for it in man.get("items", [])}
    mimes = {".mp3": "audio/mpeg", ".webm": "audio/webm", ".ogg": "audio/ogg", ".wav": "audio/wav"}
    items, bad = [], []
    for iid, kind, text in textdata.items(D):
        if kind not in man["voices"]:  # manifest 沒有這類的聲音：不預錄，網頁改用手機語音
            continue
        it = have.get(iid)
        p = it and os.path.join(AUDIO, it["file"])
        if not it or it.get("text") != text or it.get("voice") != man["voices"][kind] or not os.path.exists(p):
            bad.append(iid)
            continue
        b = open(p, "rb").read()
        if not frames_ok(b):
            sys.exit(f"{it['file']} 不是固定 {FRAME} 位元組的 MP3 幀，請執行 python tools/tts_edge.py --force")
        items.append({"id": iid, "type": mimes.get(os.path.splitext(p)[1], "audio/mpeg"),
                      "b64": base64.b64encode(b).decode()})
    if bad:
        sys.exit(f"錄音缺少或與目前文字不一致（{len(bad)} 項，例如 {', '.join(bad[:5])}），"
                 "請執行 python tools/tts_edge.py；或加 --no-audio 略過預錄")
    sb = open(os.path.join(AUDIO, man["silence"]), "rb").read()
    if not frames_ok(sb) or len(sb) < FRAME * 30:
        sys.exit("silence.mp3 格式不對，請執行 python tools/tts_edge.py")
    rec = {"voice": man["voices"]["j"], "voices": man["voices"], "frame": FRAME, "fdur": 0.024,
           "sil": base64.b64encode(sb[FRAME * 20:FRAME * 21]).decode(), "items": items}
    html = html.replace("/*__AUDIO__*/null", json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
    size = sum(len(i["b64"]) for i in items)
    print(f"已內嵌預錄朗讀 {len(items)} 項（base64 {size//1024} KB）")
else:
    print("沒有 audio/manifest.json，略過預錄朗讀")

open(OUT, "w", encoding="utf-8").write(html)
print(f"完成：{OUT}（{os.path.getsize(OUT)//1024} KB）")
