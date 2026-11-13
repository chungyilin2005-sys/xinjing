#!/usr/bin/env python3
"""下載維基文庫《般若波羅蜜多心經註解》（明 宗泐、如玘）的原始碼，解析成 data/notes.json。

用法（在專案根目錄執行）：
    python tools/fetch_notes.py            # 下載固定版本（OLDID），解析並輸出
    python tools/fetch_notes.py --offline  # 不連網，直接用 data/raw/ 裡已下載的原始碼

來源固定為 OLDID 這一版，確保每次結果相同。原始碼原封不動存在 data/raw/，不修改。
這一頁的原始碼本來就是繁體字，不需要簡繁轉換。

處理步驟：
1. 以 index.php?oldid=…&action=raw 下載原始碼（不抓網頁 HTML），並以 API 核對頁名、版本號、大小與 SHA-1。
2. 「御製心經序」→ preface；經題、譯者、註者署名 → credit；「按施護譯本…」→ 經題的註解（第 0 段）。
3. 其後每段是「經文　註解」（以全形空格分隔）。「故說般若波羅蜜多呪。即說呪曰。」沒有註解；
   咒語一行之後的段落是咒語的註解。
4. 每段經文去掉標點後，必須剛好對上網頁經文（src/xinjing.template.html 的 BODY）連續幾個子句，
   記下子句範圍 [起, 迄]（0 = 經題）。註解本用字「呪」「薩摩訶」與網頁的「咒」「薩婆訶」視為相同，
   差異記在 SOURCES.md。對不上就停止。

錄入錯字與斷句修正不在這裡改。經使用者確認的修正放在 data/corrections.json，由 build.py 套用。
"""
import argparse, datetime, hashlib, json, os, re, sys, urllib.parse, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RAWDIR = os.path.join(DATA, "raw")
TEMPLATE = os.path.join(ROOT, "src", "xinjing.template.html")
TITLE = "般若波羅蜜多心經註解"
OLDID = 2601426
API = "https://zh.wikisource.org/w/api.php"
RAW_URL = f"https://zh.wikisource.org/w/index.php?oldid={OLDID}&action=raw"
PAGE_URL = "https://zh.wikisource.org/zh-hant/" + urllib.parse.quote(TITLE)
UA = "xinjing-notes-fetch/1.0 (personal study project)"
RAWFILE = os.path.join(RAWDIR, f"wikisource-{OLDID}.wiki")
HAN = re.compile(r"[㐀-鿿豈-﫿]")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def download():
    q = urllib.parse.urlencode({"action": "query", "prop": "revisions", "revids": OLDID,
                                "rvprop": "ids|timestamp|size|sha1", "format": "json", "formatversion": 2})
    info = json.loads(get(API + "?" + q))
    page = info["query"]["pages"][0]
    rev = page["revisions"][0]
    if page["title"] != TITLE or rev["revid"] != OLDID:
        sys.exit(f"版本資訊不符：{page['title']} / {rev['revid']}")
    raw = get(RAW_URL)
    if len(raw) != rev["size"]:
        sys.exit(f"下載大小 {len(raw)} 與版本大小 {rev['size']} 不符")
    if hashlib.sha1(raw).hexdigest() != rev["sha1"]:
        sys.exit("下載內容的 SHA-1 與維基文庫紀錄不符")
    os.makedirs(RAWDIR, exist_ok=True)
    open(RAWFILE, "wb").write(raw)
    meta = {"title": TITLE, "page_url": PAGE_URL, "raw_url": RAW_URL, "oldid": OLDID,
            "rev_timestamp": rev["timestamp"], "size": rev["size"], "sha1": rev["sha1"],
            "fetched": datetime.date.today().isoformat()}
    json.dump(meta, open(os.path.join(RAWDIR, "source.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"已下載 oldid={OLDID}（{rev['timestamp']}，{len(raw)} 位元組，SHA-1 相符）")


def clauses_of_template():
    html = open(TEMPLATE, encoding="utf-8").read()
    title = re.search(r'var TITLE="([^"]+)"', html).group(1)
    body = re.search(r'var BODY="([^"]+)"', html).group(1)
    return [title] + re.findall(r"[^，。：；]+[，。：；]?", body)


def norm(s):
    s = "".join(HAN.findall(s))
    return s.replace("呪", "咒").replace("菩提薩摩訶", "菩提薩婆訶")


def parse(src):
    src = re.sub(r"\{\{header.*?\n\}\}\n", "", src, flags=re.S)
    src = src.replace("{{PD-old}}", "")
    paras = [p.strip() for p in re.split(r"\n\s*\n", src) if p.strip()]
    it = iter(paras)
    if next(it) != "御製心經序":
        sys.exit("第一段不是「御製心經序」")
    preface = [next(it)]
    if next(it) != TITLE:
        sys.exit("序之後不是經題")
    translator = next(it)
    credit = next(it)
    if "玄奘" not in translator or "宗泐" not in credit or "如玘" not in credit:
        sys.exit("譯者或註者署名不符")
    intro = next(it)
    if not intro.startswith("按施護譯本"):
        sys.exit("經題註解不是「按施護譯本」開頭")
    segs = [{"jing": "般若波羅蜜多心經", "note": intro}]
    rest = list(it)
    if rest[-1] != TITLE:
        sys.exit("最後一段不是經題（卷末題）")
    rest = rest[:-1]
    k = 0
    while k < len(rest):
        p = rest[k]
        if p.startswith("揭諦"):
            segs.append({"jing": p, "note": rest[k + 1]})
            k += 2
            continue
        if "　" in p:
            j, n = p.split("　", 1)
            segs.append({"jing": j, "note": n.strip()})
        else:
            segs.append({"jing": p, "note": ""})
        k += 1
    # 署名：維基文庫以括號標示小字（臣）與人名，畫面上不顯示括號
    credit_txt = credit.replace("(", "").replace(")", "")
    credit_txt = credit_txt.replace("宗泐演福", "宗泐　演福").replace("如玘奉詔", "如玘　奉詔")
    return preface, translator, credit_txt, segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    a = ap.parse_args()
    if not a.offline or not os.path.exists(RAWFILE):
        download()
    src = open(RAWFILE, encoding="utf-8").read()
    preface, translator, credit, segs = parse(src)

    # ---- 對照網頁經文，求每段的子句範圍 ----
    cl = clauses_of_template()
    i = 0
    for n, s in enumerate(segs):
        want = norm(s["jing"])
        acc, j = "", i
        while j < len(cl) and len(acc) < len(want):
            acc += norm(cl[j])
            j += 1
        if acc != want:
            sys.exit(f"第 {n} 段經文對不上網頁經文：{s['jing']} ≠ {''.join(cl[i:j])}")
        s["range"] = [i, j - 1]
        i = j
    if i != len(cl):
        sys.exit(f"註解只涵蓋到第 {i} 個子句，網頁經文共 {len(cl)} 個子句")
    if len(segs) != 19:
        sys.exit(f"段數 {len(segs)} 不是 19（經題＋18 段）")

    out = {"source": "維基文庫〈般若波羅蜜多心經註解〉oldid %d" % OLDID,
           "author": "明　宗泐、如玘　奉詔同註",
           "translator": translator, "credit": credit,
           "preface_title": "御製心經序", "preface": preface,
           "segs": [{"range": s["range"], "jing": s["jing"], "note": s["note"]} for s in segs]}
    json.dump(out, open(os.path.join(DATA, "notes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    nchars = sum(len(HAN.findall(s["note"])) for s in segs)
    print(f"完成：data/notes.json（序 {len(HAN.findall(preface[0]))} 字，"
          f"{len(segs)} 段，註解 {nchars} 字）")
    for n, s in enumerate(segs):
        print(f"{n:2d} {s['range']}  {s['jing']}  ({len(HAN.findall(s['note']))} 字)")


if __name__ == "__main__":
    main()
