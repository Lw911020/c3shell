import io
# -*- coding: utf-8 -*-
"""通用 APK 构建器（复用已装好的 Termux aarch64 构建工具链）。

用法: python3 build_apk.py <src目录> <输出apk路径> [--label 名称]

src目录需包含:
  AndroidManifest.xml
  java/**/*.java        (只编译这一棵，test/ 等目录会被忽略)

流程: javac -> d8 -> aapt2 link -> 注入 classes.dex -> apksigner(v1+v2+v3)
注意: LD_LIBRARY_PATH 只作用于单条 JDK/aapt2 命令, 绝不 export,
      否则会劫持宿主 shell 自身的动态库解析。
"""
import os, re, shutil, subprocess, sys, zipfile

HOME = os.path.expanduser("~")
TC = os.path.join(HOME, ".apktc/root/data/data/com.termux/files/usr")
BUILDROOT = os.path.join(HOME, ".apktc/build")
LIBS = os.path.dirname(os.path.abspath(__file__)) + "/libs"
EXTRA_JAR = os.path.join(LIBS, "jsch.jar")
ASSETS = os.path.join(SRC, "assets") if "SRC" in dir() else None
ANDROID_JAR = os.path.join(LIBS, "android.jar")
FRAMEWORK_RES = "/system/framework/framework-res.apk"
KS = os.path.join(BUILDROOT, "padagent.p12")
KSPASS = "android"
RULES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "proguard-rules.pro")

JAVA = os.path.join(TC, "bin/java")
JAVAC = os.path.join(TC, "bin/javac")
KEYTOOL = os.path.join(TC, "bin/keytool")
AAPT2 = os.path.join(TC, "bin/aapt2")
D8_JAR = os.path.join(TC, "share/java/d8.jar")
APKSIGNER_JAR = os.path.join(TC, "share/java/apksigner.jar")
# R8（混淆/压缩）就在 d8.jar 里；Termux 那个 r8 壳子只是 java -cp d8.jar com.android.tools.r8.R8
USE_R8 = True

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(2)
SRC = os.path.abspath(sys.argv[1])
OUT = os.path.abspath(sys.argv[2])
NAME = os.path.basename(OUT)[:-4]
BUILD = os.path.join(BUILDROOT, "app-" + NAME)

LIBENV = {"LD_LIBRARY_PATH": os.path.join(TC, "lib"),
          "TMPDIR": os.path.join(HOME, "tmp")}
os.makedirs(LIBENV["TMPDIR"], exist_ok=True)


def run(cmd, label):
    env = dict(os.environ)
    env.update(LIBENV)
    print("\n$ %s" % " ".join(cmd), flush=True)
    if subprocess.call(cmd, env=env) != 0:
        print("!! 失败: %s" % label, flush=True)
        sys.exit(1)


def out_of(cmd):
    env = dict(os.environ)
    env.update(LIBENV)
    return subprocess.run(cmd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True).stdout


if os.path.isdir(BUILD):
    shutil.rmtree(BUILD)
os.makedirs(os.path.join(BUILD, "classes"))
os.makedirs(os.path.join(BUILD, "dex"))

# ── 2026-09-24 加固 ①：先备好签名密钥，再拿证书指纹去派生"资产密钥" ──
#    这样别人二次打包/重新签名后，资产解不开（拿了壳也用不了）✓
if not os.path.exists(KS):
    run([KEYTOOL, "-genkeypair", "-keystore", KS, "-storetype", "PKCS12",
         "-alias", "padagent", "-keyalg", "RSA", "-keysize", "2048",
         "-validity", "10000", "-storepass", KSPASS, "-keypass", KSPASS,
         "-dname", "CN=Pad Agent, OU=Local, O=PadAgent, C=CN"], "keytool(首次建密钥)")

_cert_der = os.path.join(BUILDROOT, "cert.der")
run([KEYTOOL, "-exportcert", "-keystore", KS, "-storetype", "PKCS12",
     "-storepass", KSPASS, "-alias", "padagent", "-file", _cert_der], "keytool(导出证书)")
CERT = open(_cert_der, "rb").read()
CERT_TAIL = CERT[-9:]                       # 运行时用 PackageManager 拿同一份 DER → 取尾部 9 字节 ✓
print("签名证书 %d 字节，指纹尾 9 字节: %s" % (len(CERT), CERT_TAIL.hex()))

# BuildInfo.java：把证书指纹与构建号写进代码（运行时校验签名用）
_mf0 = io.open(os.path.join(SRC, "AndroidManifest.xml"), encoding="utf-8").read()
_ver0 = re.search(r'android:versionName="([^"]+)"', _mf0)
_ver0 = _ver0.group(1) if _ver0 else "0"
_bi = os.path.join(SRC, "java/com/padagent/c3shell/BuildInfo.java")
io.open(_bi, "w", encoding="utf-8").write(
    "package com.padagent.c3shell;\n"
    "/** 构建时生成（build_apk.py）—— 签名指纹与构建号；请勿手改 */\n"
    "public final class BuildInfo {\n"
    "    public static final String CERT_TAIL = \"%s\";\n"
    "    public static final String BUILD_ID = \"%s-%d\";\n"
    "    private BuildInfo() {}\n"
    "}\n" % (CERT_TAIL.hex(), _ver0, int(__import__("time").time())))
print("已生成 BuildInfo.java（CERT_TAIL=%s）" % CERT_TAIL.hex())

# ── 2026-09-24 体验版（用户要求）：构建时把体验期起止写进代码 ──
#    用法： C3_TRIAL=1 bash build.sh 3.00.60 trial
#    默认体验期：2026-09-25 08:00 → 2026-09-28 08:00（**3 天 = 72 小时**，北京时间 UTC+8）✓
#    可用 C3_TRIAL_START / C3_TRIAL_END 覆盖（形如 "2026-09-25 08:00:00"）
import calendar as _cal


def _epoch_ms(s):
    s = str(s).strip()
    d = s.split()[0]
    t = s.split()[1] if len(s.split()) > 1 else "00:00:00"
    y, mo, dd = [int(x) for x in d.split("-")]
    hh, mi, ss = [int(x) for x in t.split(":")]
    return (_cal.timegm((y, mo, dd, hh, mi, ss, 0, 0, 0)) - 8 * 3600) * 1000


TRIAL_ON = os.environ.get("C3_TRIAL", "") == "1"
T_START = os.environ.get("C3_TRIAL_START", "2026-09-25 08:00:00")
T_END = os.environ.get("C3_TRIAL_END", "2026-09-28 08:00:00")
_ti = os.path.join(SRC, "java/com/padagent/c3shell/TrialInfo.java")
io.open(_ti, "w", encoding="utf-8").write(
    "package com.padagent.c3shell;\n"
    "/** 构建时生成（build_apk.py）—— 体验版开关与体验期；请勿手改 */\n"
    "public final class TrialInfo {\n"
    "    public static final boolean ON = %s;\n"
    "    public static final long START = %dL;\n"
    "    public static final long END = %dL;\n"
    "    public static final String LABEL = \"%s\";\n"
    "    private TrialInfo() {}\n"
    "}\n" % ("true" if TRIAL_ON else "false", _epoch_ms(T_START), _epoch_ms(T_END),
              "体验版" if TRIAL_ON else ""))
print("体验版: %s   体验期 %s → %s" % (("开（%d 天倒计时）" % max(1, int((_epoch_ms(T_END) - _epoch_ms(T_START)) / 86400000))) if TRIAL_ON else "关（正式版）", T_START, T_END))

java_files = []
for dp, dn, fn in os.walk(os.path.join(SRC, "java")):
    for f in fn:
        if f.endswith(".java"):
            java_files.append(os.path.join(dp, f))
java_files.sort()
print("Java 源文件 %d 个:" % len(java_files))
for f in java_files:
    print("   " + os.path.relpath(f, SRC))

cp = ANDROID_JAR + (os.pathsep + EXTRA_JAR if os.path.exists(EXTRA_JAR) else "")
run([JAVAC, "-encoding", "UTF-8", "-source", "11", "-target", "11",
     "-Xlint:-options", "-classpath", cp,
     "-d", os.path.join(BUILD, "classes")] + java_files, "javac")

class_files = []
for dp, dn, fn in os.walk(os.path.join(BUILD, "classes")):
    for f in fn:
        if f.endswith(".class"):
            class_files.append(os.path.join(dp, f))
class_files.sort()
print("\nclass 文件 %d 个" % len(class_files))

d8_in = list(class_files)
if os.path.exists(EXTRA_JAR):
    d8_in.append(EXTRA_JAR)
# ── 2026-09-24 加固 ②：d8 → **R8 混淆**（类名/方法名/字段名全部重命名，反编译出来读不动）──
#    规则文件 proguard-rules.pro：只保 manifest 组件 + JSch（反射加载密码学实现）
DEXOUT = os.path.join(BUILD, "dex")
r8_ok = False
if USE_R8 and os.path.exists(RULES):
    env = dict(os.environ); env.update(LIBENV)
    LIBJAVA = os.path.join(BUILDROOT, "libjava.jar")   # java.* 库类（android.jar 里没有 java.*）
    libs = ["--lib", ANDROID_JAR]
    if os.path.exists(LIBJAVA):
        libs += ["--lib", LIBJAVA]
    # R8 默认不写映射表 → 临时加一条 -printmapping（解混淆线上堆栈要用）✓
    RULES2 = os.path.join(BUILD, "rules-print.pro")
    try:
        io.open(RULES2, "w", encoding="utf-8").write(
            io.open(RULES, encoding="utf-8").read() + "\n-printmapping " +
            os.path.join(DEXOUT, "mapping.txt") + "\n")
        _usepg = RULES2
    except Exception:
        _usepg = RULES
    cmd = [JAVA, "-cp", D8_JAR, "com.android.tools.r8.R8", "--release",
           "--min-api", "19"] + libs + [
           "--pg-conf", _usepg, "--output", DEXOUT] + d8_in
    print("\n$ R8 (混淆) ...", flush=True)
    if subprocess.call(cmd, env=env) == 0 and os.path.exists(os.path.join(DEXOUT, "classes.dex")):
        r8_ok = True
        print("  R8 混淆完成 ✓（mapping 见 %s/mapping.txt）" % DEXOUT)
    else:
        print("  R8 失败 → 回退 d8（不混淆）")
if not r8_ok:
    run([JAVA, "-cp", D8_JAR, "com.android.tools.r8.D8",
         "--min-api", "19", "--lib", ANDROID_JAR,
         "--output", DEXOUT] + d8_in, "d8(回退)")

dex = os.path.join(BUILD, "dex/classes.dex")
print("classes.dex = %d 字节" % os.path.getsize(dex))

base = os.path.join(BUILD, "base.apk")
link = [AAPT2, "link", "-o", base, "-I", FRAMEWORK_RES,
        "--manifest", os.path.join(SRC, "AndroidManifest.xml"),
        "--min-sdk-version", "19", "--target-sdk-version", "34",
        "--auto-add-overlay"]
if os.path.isdir(os.path.join(SRC, "assets")):
    # ── 资产加密（2026-09-21）：敏感文件加密成 <名>.enc 后再打进 APK ──
    import shutil, hashlib
    # 2026-09-24 加固 ③：密钥 = 固定基串 + **签名证书尾部 9 字节**
    #   运行时用 PackageManager 取自己签名 → 同一份 DER → 同一把钥匙 ✓
    #   别人重新签名 = 钥匙不对 = 资产全解不开（连页面都加载不出来）✓
    KEY = bytes([0x43,0x33,0x53,0x68, 0x65,0x6c,0x6c,0x32,0x30, 0x32,0x36,0x2d,0x50,0x41,0x44]) + CERT_TAIL
    def _ks(n):
        S=list(range(256)); j=0
        for i in range(256):
            j=(j+S[i]+KEY[i%len(KEY)])&255; S[i],S[j]=S[j],S[i]
        out=bytearray(); i2=j=0
        for _ in range(n):
            i2=(i2+1)&255; j=(j+S[i2])&255; S[i2],S[j]=S[j],S[i2]
            out.append(S[(S[i2]+S[j])&255])
        return bytes(out)
    def _enc(data):
        k=_ks(len(data)); body=bytes(a^b for a,b in zip(data,k))
        s=sum(data)&0xFFFFFFFF
        return b"C3S1"+len(data).to_bytes(4,"big")+body+s.to_bytes(4,"big")
    stage=os.path.join(SRC,".assets_stage")
    if os.path.isdir(stage): shutil.rmtree(stage)
    shutil.copytree(os.path.join(SRC,"assets"), stage)
    # 2026-09-24：把 .json（参数词库）和 .c（设备端钩子源码）也纳入加密 —— 这些都是"攒出来的know-how" ✓
    ENC_EXT=(".html",".js",".css",".py",".jpg",".md",".json",".c")
    # 2026-09-23 缓存治理：把文本资产里的 __VER__ 换成版本号 ✓
    #   （否则 WebView 缓存旧 page.html / theme.css → 主题切换后重载拿到的还是旧样式 ✗）
    try:
        _mf = io.open(os.path.join(SRC, "AndroidManifest.xml"), encoding="utf-8").read()
        _m = re.search(r'android:versionName="([^"]+)"', _mf)
        _VER = _m.group(1) if _m else "0"
    except Exception:
        _VER = "0"
    print("  版本号(防缓存):", _VER)
    # 2026-09-24：清掉不该进包的杂物（__pycache__ / *.pyc / *.bak* / *.tmp）
    _junk = 0
    for root, dirs, files in list(os.walk(stage)):
        if "__pycache__" in root:
            shutil.rmtree(root, ignore_errors=True); _junk += 1; continue
        for f in files:
            if f.endswith((".pyc", ".tmp")) or ".bak" in f:
                os.remove(os.path.join(root, f)); _junk += 1
    if _junk:
        print("  清理杂物 %d 个" % _junk)
    for root, dirs, files in os.walk(stage):
        for f in files:
            if not f.endswith((".html", ".js", ".css")):
                continue
            fp = os.path.join(root, f)
            try:
                t = io.open(fp, encoding="utf-8").read()
                if "__VER__" in t:
                    io.open(fp, "w", encoding="utf-8").write(t.replace("__VER__", str(_VER)))
            except Exception:
                pass
    cnt=0
    for root,dirs,files in os.walk(stage):
        for f in files:
            fp=os.path.join(root,f)
            rel=os.path.relpath(fp,stage).replace("\\","/")
            if f.endswith(".enc"): continue
            if rel.startswith("keys/"):
                continue            # 密钥不加密（2026-09-21 用户要求）
            if f.endswith(ENC_EXT):
                data=open(fp,"rb").read()
                open(fp+".enc","wb").write(_enc(data))
                os.remove(fp); cnt+=1
    print("  资产加密: %d 个文件 → .enc" % cnt)
    link += ["-A", stage]
res_dir = os.path.join(SRC, "res")
if os.path.isdir(res_dir):
    comp = os.path.join(BUILD, "resources.zip")
    run([AAPT2, "compile", "--dir", res_dir, "-o", comp, "--no-crunch"],
        "aapt2 compile")
    link.append(comp)
run(link, "aapt2 link")

tmp = os.path.join(BUILD, "withdex.apk")
with zipfile.ZipFile(base) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for n in zin.namelist():
        zout.writestr(zin.getinfo(n), zin.read(n))
    zout.write(dex, "classes.dex")
os.replace(tmp, base)
print("\nAPK 内容: %s" % ", ".join(sorted(zipfile.ZipFile(base).namelist())))

if os.path.exists(OUT):
    os.remove(OUT)
run([JAVA, "-jar", APKSIGNER_JAR, "sign",
     "--ks", KS, "--ks-type", "PKCS12",
     "--ks-pass", "pass:" + KSPASS, "--key-pass", "pass:" + KSPASS,
     "--min-sdk-version", "19",
     "--v1-signing-enabled", "true", "--v2-signing-enabled", "true",
     "--out", OUT, base], "apksigner sign")

# ── 把 R8 的映射表留在产物旁边（解混淆线上堆栈用；没有混淆就没这个文件）✓
_mapping = os.path.join(DEXOUT, "mapping.txt")
if os.path.exists(_mapping):
    try:
        shutil.copyfile(_mapping, OUT + ".mapping.txt")
        print("R8 映射表: %s.mapping.txt" % OUT)
    except Exception as _e:
        print("映射表复制失败:", _e)

print("\n=== apksigner verify ===")
for line in out_of([JAVA, "-jar", APKSIGNER_JAR, "verify", "--verbose", OUT]).splitlines():
    if "Verifies" in line or "scheme" in line:
        print("  " + line)

print("\n=== aapt2 dump badging ===")
for line in out_of([AAPT2, "dump", "badging", OUT]).splitlines()[:6]:
    print("  " + line)

print("\n产物: %s (%d 字节)" % (OUT, os.path.getsize(OUT)))
