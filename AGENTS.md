# AGENTS.md

給接手這個專案的 AI 代理（Claude Code、Codex、Cursor 等）的工作說明。功能細節以 `SPEC.md` 為準，本檔說明怎麼改、改完要做什麼。

## 專案概要

《般若波羅蜜多心經》讀誦與描寫網頁，附明代宗泐、如玘註解、御製心經序與逐段白話。單一 HTML 檔，主要在 Android 手機的 Chrome 上使用，並發布為 claude.ai Artifact。

## 檔案結構

```
xinjing/
├── index.html                  建置產物，可直接開啟或發布（勿手改）
├── src/xinjing.template.html   原始碼：HTML + CSS + JS，預留位置 __FONT_B64__、/*__DATA__*/null、/*__AUDIO__*/null
├── tools/build.py              建置腳本：內嵌註解等資料、子集化字體、內嵌字體與預錄音檔 → 寫出 index.html
├── tools/fetch_notes.py        下載維基文庫固定版本的註解，解析成 data/notes.json
├── tools/textdata.py           build.py 與 tts_edge.py 共用：套用修正、切小句、產生朗讀文字
├── tools/tts_edge.py           用 edge-tts 逐項產生預錄朗讀音檔（經文、註解；白話不預錄）→ audio/
├── data/notes.json             註解與序（fetch_notes.py 產生，勿手改）
├── data/raw/                   維基文庫原始碼與版本資訊
├── data/corrections.json       使用者確認過的註解修正
├── data/corrections.proposed.json  候選修正（待確認）
├── data/plain.json             逐段白話（Claude 依註解意譯）
├── icons/icon-512.png         主畫面圖示（建置時產生）
├── audio/                      預錄音檔與 manifest.json（產生後才有）
├── fonts/WenKai-subset.woff2   目前使用的子集字體（建置時產生）
├── SPEC.md                     規格書
├── SOURCES.md                  註解來源、版本與校勘
├── TODO.md                     待使用者決定、待實機確認的事項
└── AGENTS.md                   本檔
```

原始完整字體 `fonts/LXGWWenKaiTC-Regular.ttf`（約 13 MB）已放在 GitHub 儲存庫裡；舊的壓縮檔版本沒有附上它。授權見 `fonts/FONT-LICENSE.md`。

## 修改流程

1. **只改 `src/xinjing.template.html`**，不要直接改 `index.html`。
2. 執行建置：
   ```bash
   pip install fonttools brotli pillow
   python3 tools/build.py                     # 使用 fonts/LXGWWenKaiTC-Regular.ttf
   python3 tools/build.py /path/to/字體.ttf    # 或指定路徑
   ```
3. 依 `SPEC.md` 第 7 節驗收清單檢查。
4. 若有新增或刪改功能，同步更新 `SPEC.md`。

### 為什麼新增中文字一定要重建字體

內嵌字體只包含範本裡出現過的字元（目前約 400 字）。在介面上新增任何中文字（按鈕文字、提示訊息等），若沒有用完整字體重新建置，新字會顯示成手機的備用字體，字形不一致。

`build.py` 找不到完整字體時，會改用現有子集並**列出缺字**。看到缺字警告就代表必須取得完整字體重建，不可忽略。

匯出圖片落款用到、但不一定出現在 HTML 原文的字，放在 `build.py` 的 `EXTRA` 常數。註解、序、白話會先內嵌再子集化，不必另外列。

### 註解、白話的規則

- `data/notes.json` 由 `tools/fetch_notes.py` 產生，**不手改**。錄入錯字或句讀修正寫成 `data/corrections.json` 的一條，**必須先經使用者同意**；候選放 `data/corrections.proposed.json`。
- 白話（`data/plain.json`）是 Claude 依註解意譯，可依使用者意見修改；頁面固定標示未經專家審訂。
- 改了註解、`SAY` 或 `SAY_NOTE`，都要重新執行 `tools/tts_edge.py`（只重做有變的項目），否則 `build.py` 會停止。白話不預錄（使用者決定），預錄模式下用手機語音念，改白話不必重錄。

## 必須遵守的規則

### 不可違反

- **單一檔案、零外部資源**：不可引用 CDN、外部圖片、外部字體或任何網路請求。Artifact 的內容安全政策會直接擋掉，而且是無聲失敗。
- **不可修改顯示用的經文**來修正讀音。讀音問題只改 `SAY` 校正表；只影響註解、白話的改 `SAY_NOTE`（見 `SPEC.md` 3.3）。`tools/textdata.py` 會從範本讀出這兩張表，規則要維持 `[/原文/g,"替代"]` 的寫法。
- **經文版本固定為玄奘譯本**。若使用者要求改字（例如「薩婆訶」改「娑婆訶」），描寫序列總數與既有描寫紀錄的字序對應都可能受影響，須先向使用者說明。
- **儲存格式向後相容**：`xj.*` 這幾個 localStorage 鍵與筆畫格式裡有使用者的描寫紀錄。變更結構時必須寫遷移程式，不可讓舊資料失效。
- **夜間配色兩處同步**：深色變數同時存在 `@media (prefers-color-scheme: dark)` 區塊與 `:root[data-theme="dark"]` 區塊，改一處就要改另一處。

### 慣例

- 介面文字一律繁體中文、台灣用語（資料夾、軟體、網路、設定）。引號用「」。
- JS 維持目前的 ES5 風格（`var`、`function`），不引入框架或建置工具鏈。
- 所有 `localStorage`、`indexedDB`、`claude.use()` 呼叫都包在 try/catch 或 `.catch()`，失敗時功能照常、只是不記住。
- canvas 顏色一律透過 `css("--變數")` 讀取 CSS 變數，不寫死色碼（匯出圖片除外，固定日間配色）。
- 在 canvas 上畫字之前先 `document.fonts.load()`。
- 新增按鈕的觸控區至少 44 × 44 px。

## 朗讀相關注意事項

Android Chrome 的 `speechSynthesis` 有幾個已知問題，現行設計就是為了避開它們，修改時不要回退：

- 長文字一次送出會在約 15 秒後中斷 → 所以逐句送出。
- `pause()` / `resume()` 不可靠 → 所以暫停是 `cancel()` 後記住句序。
- `cancel()` 之後舊的 `onend` 仍可能觸發 → 所以用遞增的 `token` 判斷回呼是否過期。
- 語音清單是非同步載入 → 所以監聽 `voiceschanged` 重新挑選。

預錄朗讀的音檔由 `tools/tts_edge.py`（edge-tts，不需金鑰，需要 ffmpeg）產生。改了經文、註解、`SAY` 或 `SAY_NOTE` 就要重新產生錄音再建置。朗讀文字的轉換在範本（`spoken`、`spokenNote`、`spokenPlain`）與 `tools/textdata.py` 各有一份，兩邊要一致。edge-tts 是非公開介面，若出現 403 先升級套件版本；不要用偽造標頭等方式繞過封鎖。

以上只針對「手機語音」引擎。「Claude 語音」引擎（`tts` 能力）可以整句送出、用平台的 `pause()`／`resume()`；它回報 `not_granted` 時不可自動改用手機語音朗讀（會違反使用者關掉朗讀的選擇）。

Claude Android App 內嵌的網頁畫面通常沒有 `speechSynthesis`，也拿不到 `tts` 能力。這是平台限制，不是程式錯誤；處理方式是提示使用者改用 Chrome。

## 測試

用 Playwright 在手機尺寸做基本檢查：

```python
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": 360, "height": 740},
                              device_scale_factor=2, has_touch=True)
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto("file:///絕對路徑/index.html")
        await pg.wait_for_timeout(600)
        await pg.screenshot(path="read.png")
        await pg.click("[data-view=trace]")
        await pg.wait_for_timeout(400)
        box = await pg.locator("#ink").bounding_box()
        await pg.mouse.move(box["x"] + 60, box["y"] + 80)
        await pg.mouse.down()
        for i in range(20):
            await pg.mouse.move(box["x"] + 60 + i * 8, box["y"] + 80 + i * 2)
        await pg.mouse.up()
        await pg.screenshot(path="trace.png")
        await pg.click("#themeBtn")
        await pg.screenshot(path="dark.png")
        print("errors:", errs)
        await b.close()

asyncio.run(main())
```

Playwright 無法驗證語音朗讀的實際聲音、Android 檔案選擇器與 `downloads` 能力，這些需要使用者在實機上確認。回報時請明確列出哪些項目只在模擬環境測過。

## 發布

- 發布到 claude.ai Artifact 時宣告能力 `{"downloads": true, "tts": {}}`，favicon 用 🪷。
- 更新既有頁面時帶上原本的 Artifact 網址，不要另建新頁，否則使用者的書籤會失效；描寫紀錄存在瀏覽器且依網址區分，換網址等於紀錄消失。
- 小幅修改可用 Artifact 的 edit 動作直接改已發布頁面，但之後要把同樣的修改套回 `src/xinjing.template.html`，避免範本與線上版本分歧。

## 授權

霞鶩文楷（LXGW WenKai TC）採 SIL Open Font License 1.1，允許嵌入網頁與再散布子集，但字體本身不可單獨販售。對外散布專案時，建議一併附上該字體的 OFL 授權全文。
