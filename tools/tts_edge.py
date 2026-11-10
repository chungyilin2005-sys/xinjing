#!/usr/bin/env python3
"""用 edge-tts（Edge 瀏覽器「大聲朗讀」的微軟語音）把經文逐句合成成音檔，存到 audio/，
供 build.py 內嵌成「預錄朗讀」。不需要金鑰。

用法（在專案根目錄執行）：
    pip install edge-tts
    python tools/tts_edge.py
    其他選項：
        --voice zh-TW-HsiaoYuNeural   聲音（預設曉雨；另有 zh-TW-HsiaoChenNeural 曉臻、zh-TW-YunJheNeural 雲哲）
        --rate -10%                   語速（預設 -10%）
        --pitch +0Hz                  音高
        --only 3                      只重做第 3 句（從 0 起算，可重複指定）

注意：edge-tts 使用的是 Edge 的非公開介面，不是微軟正式授權的服務，可能隨時改變或失效。

經文、句子切法與讀音校正表（SAY）都直接從 src/xinjing.template.html 讀出，與網頁一致。
產生後執行 python tools/build.py 重建 index.html。
"""
import argparse, asyncio, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "src", "xinjing.template.html")
OUTDIR = os.path.join(ROOT, "audio")


def read_template():
    html = open(TEMPLATE, encoding="utf-8").read()
    title = re.search(r'var TITLE="([^"]+)"', html).group(1)
    body = re.search(r'var BODY="([^"]+)"', html).group(1)
    say_src = re.search(r"var SAY=\[(.*?)\];", html).group(1)
    say = re.findall(r'\[/(.+?)/g,"(.+?)"\]', say_src)
    return title, body, say


def sentences(title, body):
    """與網頁相同：子句以「，。：；」為界；句子到「。」或「：」為止；經題自成一句。"""
    clauses = [title] + re.findall(r"[^，。：；]+[，。：；]?", body)
    out, i = [(0, 0)], 1
    while i < len(clauses):
        j = i
        while j < len(clauses) - 1 and not re.search(r"[。：]$", clauses[j]):
            j += 1
        out.append((i, j))
        i = j + 1
    return clauses, out


def spoken(text, say):
    for pat, rep in say:
        text = re.sub(pat, rep, text)
    return text


async def synth(text, path, voice, rate, pitch):
    import edge_tts
    err = "音檔是空的"
    for attempt in range(4):
        try:
            await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path)
            if os.path.getsize(path) > 0:
                return
        except Exception as e:
            err = e
        await asyncio.sleep(2 * (attempt + 1))
    sys.exit(f"產生失敗：{path}（{err}）")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="zh-TW-HsiaoYuNeural")
    ap.add_argument("--rate", default="-10%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--only", type=int, action="append")
    a = ap.parse_args()
    try:
        import edge_tts  # noqa: F401
    except ImportError:
        sys.exit("請先安裝：pip install edge-tts")

    title, body, say = read_template()
    clauses, sents = sentences(title, body)
    os.makedirs(OUTDIR, exist_ok=True)
    items = []
    for n, (i, j) in enumerate(sents):
        fname = f"{n:02d}_{i}-{j}.mp3"
        items.append({"id": f"{i}-{j}", "file": fname})
        if a.only and n not in a.only:
            continue
        text = spoken("".join(clauses[i:j + 1]), say)
        path = os.path.join(OUTDIR, fname)
        await synth(text, path, a.voice, a.rate, a.pitch)
        print(f"{n:2d} {fname}  {os.path.getsize(path)//1024} KB  {text}")
    manifest = {"voice": a.voice, "rate": a.rate, "pitch": a.pitch, "source": "edge-tts", "items": items}
    with open(os.path.join(OUTDIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"完成：{len(items)} 句 → {OUTDIR}。接著執行 python tools/build.py")


if __name__ == "__main__":
    asyncio.run(main())
