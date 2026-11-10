#!/usr/bin/env python3
"""建置 index.html：從範本擷取用到的字，子集化字體後以 base64 內嵌。

用法（在專案根目錄執行）：
    pip install fonttools brotli
    python3 tools/build.py [字體檔路徑]

預設字體檔路徑：fonts/LXGWWenKaiTC-Regular.ttf（原始完整字體，未隨附於壓縮檔）。
若找不到原始字體，會改用 fonts/WenKai-subset.woff2（僅含目前用到的字）；
這種情況下若範本新增了新的中文字，新字會以備用字體顯示，並列出缺字。
"""
import base64, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "src", "xinjing.template.html")
OUT = os.path.join(ROOT, "index.html")
FULL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "fonts", "LXGWWenKaiTC-Regular.ttf")
SUBSET = os.path.join(ROOT, "fonts", "WenKai-subset.woff2")
EXTRA = "0123456789民國年月日敬書"  # 匯出圖片落款會用到、但不一定出現在 HTML 原文的字

html = open(TEMPLATE, encoding="utf-8").read()
if "__FONT_B64__" not in html:
    sys.exit("範本缺少 __FONT_B64__ 預留位置")

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
open(OUT, "w", encoding="utf-8").write(html.replace("__FONT_B64__", b64))
print(f"完成：{OUT}（{os.path.getsize(OUT)//1024} KB）")
