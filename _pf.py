# -*- coding: utf-8 -*-
import io, sys
D='/storage/emulated/0/openpilot/c3shell/'
p = D+'java/com/padagent/c3shell/Api.java'
s = io.open(p, encoding='utf-8').read()
def rep(s, old, new, tag):
    if old not in s: sys.exit('锚点没找到: '+tag)
    return s.replace(old, new, 1)

# ① 接口本体（放在 /api/ssh/params/all 之前）
s = rep(s, """        if (path.equals("/api/ssh/params/all")) {""",
"""        if (path.equals("/api/ssh/profiles")) {
            // 2026-09-22：参数档案（A–H/Z）。APP 原来没实现 ✗ → 页面「保存」只写本地缓存、"存到机器"必失败
            // 存储：SharedPreferences 每档一个 key（不用 JSON 库 ✓）；同时 best-effort 镜像到 C3 设备 ✓
            android.content.SharedPreferences sp = ctx.getSharedPreferences("c3shell", Context.MODE_PRIVATE);
            String[] SLOTS = { "A", "B", "C", "D", "E", "F", "G", "H", "Z" };
            if (!"POST".equalsIgnoreCase(method)) {
                StringBuilder sb = new StringBuilder();
                for (String sl : SLOTS) {
                    String rec = sp.getString("prof:" + sl, null);
                    if (rec == null || rec.length() == 0) continue;
                    if (sb.length() > 0) sb.append(",");
                    sb.append("\\"").append(sl).append("\\":").append(rec);
                }
                return "{\\"ok\\":true,\\"file\\":\\"APP 内置存档（随 APP，卸载会丢）\\",\\"remoteDir\\":\\"/data/openpilot/dsh-profiles\\","
                     + "\\"profiles\\":{" + sb.toString() + "}}";
            }
            String slot = nz(jstr(body, "slot"), "");
            if (slot.length() == 0) return "{\\"ok\\":false,\\"error\\":{\\"message\\":\\"slot required\\"}}";
            if ("delete".equalsIgnoreCase(nz(jstr(body, "action"), "save"))) {
                sp.edit().remove("prof:" + slot).commit();
                mirrorProfiles(slot, "{\\"deleted\\":true}");
                return "{\\"ok\\":true,\\"slot\\":\\"" + q(slot) + "\\"}";
            }
            String values = jobj(body, "values"); if (values == null) values = "{}";
            String note = nz(jstr(body, "note"), "");
            int count = jint(body, "count", 0);
            String t = new java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss").format(new java.util.Date());
            String rec = "{\\"t\\":\\"" + q(t) + "\\",\\"note\\":\\"" + q(note) + "\\",\\"count\\":" + count + ",\\"p\\":" + values + "}";
            sp.edit().putString("prof:" + slot, rec).commit();
            mirrorProfiles(slot, rec);
            return "{\\"ok\\":true,\\"slot\\":\\"" + q(slot) + "\\",\\"count\\":" + count + ",\\"note\\":\\"" + q(note) + "\\"}";
        }
        if (path.equals("/api/ssh/params/all")) {""", 'profiles 接口')

# ② 两个助手
s = rep(s, """    private static String nz(String v, String def) { return (v == null || v.length() == 0) ? def : v; }""",
"""    private static String nz(String v, String def) { return (v == null || v.length() == 0) ? def : v; }

    /** 取 body 里对象字段的原始 JSON（如 values:{...}）——不引 JSON 库，靠括号配平 ✓ */
    private static String jobj(String body, String key) {
        try {
            int i = body.indexOf("\\"" + key + "\\"");
            if (i < 0) return null;
            int c = body.indexOf(':', i);
            int b = body.indexOf('{', c);
            if (b < 0) return null;
            int d = 0;
            for (int j = b; j < body.length(); j++) {
                char ch = body.charAt(j);
                if (ch == '{') d++;
                else if (ch == '}') { d--; if (d == 0) return body.substring(b, j + 1); }
            }
        } catch (Throwable ignore) { }
        return null;
    }

    /** 把档案顺手镜像一份到 C3 设备（best-effort：失败不影响主流程，也不阻塞响应） */
    private void mirrorProfiles(final String slot, final String json) {
        new Thread(new Runnable() { public void run() {
            try {
                Store.Host d = store.defaultHost();
                String b64 = android.util.Base64.encodeToString(json.getBytes("UTF-8"), android.util.Base64.NO_WRAP);
                String cmd = "mkdir -p /data/openpilot/dsh-profiles && echo " + b64
                           + " | base64 -d > /data/openpilot/dsh-profiles/" + slot + ".json";
                ssh.execJson(cmd, d == null ? null : d.host, d == null ? 22 : d.port,
                             d == null ? null : d.user, d == null ? null : d.key);
            } catch (Throwable ignore) { }
        }}).start();
    }""", '助手函数')
io.open(p,'w',encoding='utf-8').write(s)
print('Api.java OK /api/ssh/profiles + jobj + mirrorProfiles')

# ③ 页面：保存不再"没反应"
p = D+'assets/diag.html'
s = io.open(p, encoding='utf-8').read()
s = rep(s, """function profSave(){
  var sel=Object.keys(PSEL).filter(function(x){return PSEL[x]});
  if(sel.length!==1){ log('请先只选中一个档案位（当前 '+sel.length+' 个）'); return; }
  var s=sel[0], note=((document.getElementById('profNote')||{}).value||'').trim();
  profSaveSlot(s, note);
}""",
"""function profSave(){
  var sel=Object.keys(PSEL).filter(function(x){return PSEL[x]});
  if(sel.length!==1){
    // 2026-09-22 用户反馈「参数备份没效果」：原来这里只写一行日志 ✗ 屏幕上毫无反应
    if(sel.length>1){ toast('请只选中一个档案位（当前选了 '+sel.length+' 个）','warn'); log('请先只选中一个档案位（当前 '+sel.length+' 个）'); return; }
    var free=null; for(var i=0;i<PSLOTS.length;i++){ if(!pLoad(PSLOTS[i])){ free=PSLOTS[i]; break; } }
    if(!free){ toast('A–H/Z 都满了：请先点选一个要覆盖的档位','warn'); log('档案位都满了，请先点选要覆盖的档位'); return; }
    PSEL[free]=true; profRender();
    toast('未选档位 → 已自动用空档 '+free,'ok'); log('未选档位 → 自动用空档 '+free);
    sel=[free];
  }
  var s=sel[0], note=((document.getElementById('profNote')||{}).value||'').trim();
  profSaveSlot(s, note);
}""", 'profSave')
s = rep(s, """    log('已存档案 '+slot+'（'+n+' 项）'+(note?('，备注：'+note):''));
    api('/profiles',{method:'POST',json:{hostId:sel(),action:'save',slot:slot,note:note||'',values:o}})
      .then(function(){ log('档案 '+slot+' 已存到机器（并镜像到 C3 设备）'); })
      .catch(function(e){ log('存到机器失败（本地已存）：'+e.message; });""",
"""    log('已存档案 '+slot+'（'+n+' 项）'+(note?('，备注：'+note):''));
    toast('✓ 已备份到档案 '+slot+'（'+n+' 项）'+(note?('，备注：'+note):''),'ok');
    api('/profiles',{method:'POST',json:{hostId:sel(),action:'save',slot:slot,note:note||'',values:o,count:n}})
      .then(function(r){ if(r&&r.ok){ log('档案 '+slot+' 已存到机器（并镜像到 C3 设备）'); }
        else { log('存到机器失败（本地已存）'); toast('本地已存，但同步到机器失败','warn'); } })
      .catch(function(e){ log('存到机器失败（本地已存）：'+e.message); toast('本地已存，但同步机器失败：'+e.message,'warn'); });""", 'profSaveSlot 提示')
io.open(p,'w',encoding='utf-8').write(s)
print('diag.html OK 未选档位自动挑空档 + 明确提示')

