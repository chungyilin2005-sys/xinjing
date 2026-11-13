"""經文、註解、白話的共用處理，供 build.py 與 tts_edge.py 使用，確保網頁與錄音用的是同一份文字。

- 經文、讀音校正表（SAY、SAY_NOTE）直接從 src/xinjing.template.html 讀出。
- 註解、序來自 data/notes.json（tools/fetch_notes.py 產生，不手改），
  再套用 data/corrections.json（使用者確認過的修正；每條必須在指定位置剛好出現一次）。
- 白話來自 data/plain.json（{"段序": "白話"}）。
"""
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
TEMPLATE = os.path.join(ROOT, "src", "xinjing.template.html")
HAN = re.compile(r"[㐀-鿿豈-﫿]")
CHUNK = 40  # 註解每一「句」（標亮與錄音的單位）最多約 40 字


def template_bits():
    html = open(TEMPLATE, encoding="utf-8").read()
    title = re.search(r'var TITLE="([^"]+)"', html).group(1)
    body = re.search(r'var BODY="([^"]+)"', html).group(1)
    def rules(name):
        src = re.search(r"var " + name + r"=\[(.*?)\];", html, re.S).group(1)
        return re.findall(r'\[/(.+?)/g,"(.*?)"\]', src)
    clauses = [title] + re.findall(r"[^，。：；]+[，。：；]?", body)
    return {"title": title, "body": body, "clauses": clauses, "say": rules("SAY"), "say_note": rules("SAY_NOTE")}


def _sub(text, rules):
    for pat, rep in rules:
        text = re.sub(pat, rep, text)
    return text


def spoken_jing(text, tb):
    return _sub(text, tb["say"])


def spoken_note(text, tb):
    """註解：先套 SAY、SAY_NOTE；「者。」念成「者，」，句讀較順。須與範本的 spokenNote() 一致。"""
    return _sub(_sub(text, tb["say"]), tb["say_note"]).replace("者。", "者，")


def spoken_plain(text, tb):
    """白話：全形括號念成停頓。須與範本的 spokenPlain() 一致。"""
    t = _sub(_sub(text, tb["say"]), tb["say_note"])
    t = t.replace("（", "，").replace("）", "，")
    t = re.sub(r"，+", "，", t)
    t = re.sub(r"，([。？！；：」、])", r"\1", t)
    return re.sub(r"，$", "。", t)


def chunks(note):
    """以「。」切成小句，再把相鄰小句併成不超過 CHUNK 字的一段（單一小句超過時自成一段）。"""
    if not note:
        return []
    pieces = re.findall(r"[^。]+。?", note)
    out, cur = [], ""
    for p in pieces:
        if cur and len(HAN.findall(cur + p)) > CHUNK:
            out.append(cur)
            cur = p
        else:
            cur += p
    if cur:
        out.append(cur)
    assert "".join(out) == note
    return out


def apply_corrections(notes):
    path = os.path.join(DATA, "corrections.json")
    if not os.path.exists(path):
        return 0
    cs = json.load(open(path, encoding="utf-8"))["corrections"]
    for c in cs:
        w = c["where"]
        if w == "preface":
            s = notes["preface"][0]
        elif w.startswith("seg:"):
            s = notes["segs"][int(w[4:])]["note"]
        else:
            sys.exit(f"corrections.json：無法辨認的位置 {w}")
        n = s.count(c["from"])
        if n != 1:
            sys.exit(f"corrections.json：「{c['from']}」在 {w} 出現 {n} 次（必須剛好 1 次）")
        s = s.replace(c["from"], c["to"])
        if w == "preface":
            notes["preface"][0] = s
        else:
            notes["segs"][int(w[4:])]["note"] = s
    return len(cs)


def load():
    tb = template_bits()
    notes = json.load(open(os.path.join(DATA, "notes.json"), encoding="utf-8"))
    ncorr = apply_corrections(notes)
    plain_path = os.path.join(DATA, "plain.json")
    plain = json.load(open(plain_path, encoding="utf-8")) if os.path.exists(plain_path) else {}
    segs = []
    for k, s in enumerate(notes["segs"]):
        segs.append({"r": s["range"], "n": chunks(s["note"]), "p": plain.get(str(k), "")})
    return {"tb": tb, "segs": segs, "preface": notes["preface"], "preface_title": notes["preface_title"],
            "credit": notes["credit"], "ncorr": ncorr}


def items(d):
    """錄音與朗讀的單位：j:段（經文）、p:段（白話）、n:段:句（註解）。回傳 [(id, 種類, 念的文字)]。"""
    tb, out = d["tb"], []
    for k, s in enumerate(d["segs"]):
        a, b = s["r"]
        out.append((f"j:{k}", "j", spoken_jing("".join(tb["clauses"][a:b + 1]), tb)))
    for k, s in enumerate(d["segs"]):
        if s["p"]:
            out.append((f"p:{k}", "p", spoken_plain(s["p"], tb)))
    for k, s in enumerate(d["segs"]):
        for c, t in enumerate(s["n"]):
            out.append((f"n:{k}:{c}", "n", spoken_note(t, tb)))
    return out
