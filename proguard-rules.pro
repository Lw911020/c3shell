# c3shell 混淆规则（build_apk.py 调 R8 时用）
# 2026-09-24：先只"改名"，不删代码（-dontshrink），避免反射/框架回调被误删
-dontwarn **
-dontshrink
-dontoptimize
-dontpreverify
-keepattributes *Annotation*, Signature, InnerClasses, EnclosingMethod, SourceFile, LineNumberTable

# AndroidManifest 里按名字引用的组件：名字绝不能改
-keep class com.padagent.c3shell.MainActivity { *; }
-keep class com.padagent.c3shell.SpeechService { *; }
-keep class com.padagent.c3shell.FloatWin { *; }
-keep class com.padagent.c3shell.FloatA11y { *; }
-keep class * extends android.app.Activity
-keep class * extends android.app.Service
-keep class * extends android.accessibilityservice.AccessibilityService
-keep class * extends android.app.Application
-keep class * extends android.content.BroadcastReceiver
-keep class * extends android.content.ContentProvider

# JSch：套件里的密码学/密钥交换实现是按类名反射加载的，整包保留
-keep class com.jcraft.jsch.** { *; }
-dontwarn com.jcraft.**
