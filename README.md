# 心經

《般若波羅蜜多心經》（玄奘譯本）讀誦與描寫網頁。單一 HTML 檔，主要在 Android 手機的 Chrome 上使用。

- **讀誦**：直排或橫排，逐句標亮朗讀。可選預錄、Claude 語音或手機語音，並調整語速與音高。
- **註解與白話**：明代宗泐、如玘《般若波羅蜜多心經註解》與御製心經序；逐段白話（Claude 依註解意譯，僅供參考）。可放在篇末或逐段對照，也可接著經文朗讀，聲音與經文不同。
- **描寫**：用手指一字一字描寫，共 268 字，紀錄存在瀏覽器裡；可看整篇，並存成朱絲欄圖片。
- **外觀**：日間（宣紙與墨）、夜間（磁青紙配泥金字）。

直接用瀏覽器開啟 `index.html` 就能使用。

## 開發

只改 `src/xinjing.template.html`，再建置：

```bash
pip install fonttools brotli pillow
python3 tools/build.py
```

規格見 [SPEC.md](SPEC.md)，修改流程與規則見 [AGENTS.md](AGENTS.md)。

## 授權

經文、註解、御製心經序為公有領域（來源見 [SOURCES.md](SOURCES.md)）。字體為霞鶩文楷 TC，採 SIL Open Font License 1.1，見 [fonts/FONT-LICENSE.md](fonts/FONT-LICENSE.md)。
