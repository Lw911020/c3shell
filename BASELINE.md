# c3shell 原始版（基线）= v2.48

> 2026-09-22 用户指定：**c3shell-2.48.apk 就是「原始版」**，以后所有改动（主题等）都从它起。
> 本文说明基线怎么定的、原件在哪、怎么重建与校验。

## 一、原始版是哪一版（有据可查）

| 项 | 值 |
|---|---|
| 版本 | **2.48**（versionCode 248） |
| 原件 APK | `releases/c3shell-2.48-原始版.apk`（md5 `9c88868fe29df0bb115e20164fd9c757`，1361820 字节） |
| 副本 | `/sdcard/Download/c3shell-2.48-原始版.apk`（同 md5） |
| 原始资产明文 | `_attic/assets-2.48/`（21 个文件，从原件 APK 解密所得） |

## 二、工作源码现在是什么

2026-09-22 19:3x 起，`c3shell/` 工作树已还原成 **2.48 基线**：

- `assets/` = **2.48 原始资产**（21 个文件：`page.html` + `diag.html` **两页独立**、`theme.css`、`theme.js`、`remote/*.py`、`keys/*`、`vendor/*`、`voice/*`）
  · 4.x 那套 `assets/app/*.js`（menu/nav/base/displaymode…）与 4.x 的 page.html/theme.css **已移出工作树**（明文副本在 `_attic/assets-4.35/`）
- `AndroidManifest.xml` = `versionName="2.48" / versionCode="248"`
- `CHANGELOG.md` = 2.48 那版（与 `assets/CHANGELOG.md` 一致；4.35 那份在 `_attic/CHANGELOG-4.35.md`）

**唯一保留的新代码（必须）**：`java/` 仍是 4.x 的源码 —— APK 里的 dex 无法还原成 Java 源码，只能保留。
它对 2.48 资产是**超集**：2.48 页面用到的 `/api/**` 接口在 4.x Api.java 里**全部存在**（已逐个核对：ssh/exec、params/all|apply、pkg、prefs、term/tail、voice/*、ai/*、log 等）。
唯一需要补的一处是 `Web.java` 的 `/diag` 路由 —— 4.x 是「单文档」(`/diag → page.html`)，2.48 是**两页独立**，已改成：

    // 原始版（2.48）两页独立：/diag 直接给 diag.html（包内没有 diag.html 时才回退合并文档）
    if (wantDiag) name = (readAsset("diag.html") != null) ? "diag.html" : "page.html";

## 三、怎么重建 / 校验

    cd /storage/emulated/0/openpilot/c3shell
    python3 build_apk.py . c3shell.apk            # 构建（版本号取自 AndroidManifest.xml）
    python3 tools/extract_assets.py <apk> <目录>   # 解出 APK 内资产（C3S1 + RC4，见 Sec.java）

已做校验（2026-09-22）：基线包 `_attic/c3shell-2.48-baseline.apk` 内 **21 个资产与原件 APK 逐个 md5 一致** ✓，且 APK 内 `assets/` 条目清单与原件完全一致 ✓。

## 四、实机验证（平板 127.0.0.1:36515）

| 项 | 结果 |
|---|---|
| 安装 | `adb install -r _attic/c3shell-2.48-baseline.apk` ✓（APP 数据保留：主机 c3 / 192.168.0.66 / 神牛 都在） |
| `/` | HTTP 200 · 118223 B · 标题 `控制台 · DSH` ✓ |
| `/diag` | HTTP 200 · 70822 B · 标题 `诊断台 · DSH C3 控制台` ✓（= diag.html 被正确送出） |
| `/api/store` | `{"version":"2.48"}` ✓ |
| 截图 | `_attic/verify-tablet-baseline.png`（左栏 2.48 布局、版本 v2.48 ✓） |

想换回**逐字节原件**：`adb -s 127.0.0.1:36515 install -r releases/c3shell-2.48-原始版.apk`

## 五、备份都在 `_attic/`（不进 releases/，build.sh 不会动它）

| 文件 | 内容 |
|---|---|
| `src-4.35-20260922-193312.tar.zst` | 改动前的**整棵 4.35 源码树**（含 docs/test/java/assets；不含 releases/） |
| `assets-4.35/` | 4.35 的 `assets/` 明文副本（方便 diff） |
| `assets-2.48/` | 2.48 原始资产明文（= 现在工作树的 assets/） |
| `CHANGELOG-4.35.md` | 4.35 那版 CHANGELOG |
| `c3shell-2.48-baseline.apk` | 本次构建的基线包（资产与原件一致） |
| `verify-baseline/` | 基线包解出的资产（用于 md5 比对） |

回滚整棵树：`zstd -d -c _attic/src-4.35-*.tar.zst | tar -x -C /tmp/restore`（或在 `c3shell/` 里直接解）


## 六、⚠️ test/ 下的门禁是 4.x 时代的，对 2.48 基线不适用

- `test/syntax.py`：直接报错（它要读 `assets/app/`，2.48 没有这个目录 —— 2.48 是 page.html + diag.html 两页自持）
- `test/techdebt.py`：报 5/22（D1–D22 判据全是 4.x 的模块/菜单结构）
- `test/e2e.py` / `sweep.py` / `codemap.py` 同理
- 结论：**现在别把这两条当红灯**；要给基线做门禁，得按 2.48 的两页结构重写（等主题改完再说）
