# -*- coding: utf-8 -*-
import urllib.request, json, base64
B='http://127.0.0.1:3081'
def ex(cmd, t=300):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')

# 在设备上直接改 c3shot.c：① 用 renderD128 建 GBM ② 每步 fflush ③ 打印进度
patch = r'''
python3 - <<'EOF'
import io, re
p='/tmp/c3shot.c'; s=io.open(p).read()
# ① GBM 用 render 节点
s=s.replace('  struct gbm_device *gbm = gbm_create_device(drm);',
'''  int rfd = open("/dev/dri/renderD128", O_RDWR);
  fprintf(stderr, "renderD128 fd=%d\\n", rfd); fflush(stderr);
  struct gbm_device *gbm = gbm_create_device(rfd > 0 ? rfd : drm);''')
# ② 每个关键步骤后 fflush（崩溃就能看出死在哪儿）
s=s.replace('  if (getPlat && gbm) dpy = getPlat(EGL_PLATFORM_GBM_KHR, (void*)gbm, NULL);',
'''  fprintf(stderr, "call getPlat=%p gbm=%p\\n", (void*)getPlat, (void*)gbm); fflush(stderr);
  if (getPlat && gbm) dpy = getPlat(EGL_PLATFORM_GBM_KHR, (void*)gbm, NULL);
  fprintf(stderr, "dpy=%p\\n", (void*)dpy); fflush(stderr);''')
s=s.replace('  if (!eglInitialize(dpy,&maj,&min)){',
'''  fprintf(stderr, "eglInitialize...\\n"); fflush(stderr);
  if (!eglInitialize(dpy,&maj,&min)){''')
s=s.replace('  eglBindAPI(EGL_OPENGL_ES_API);',
'''  fprintf(stderr, "eglInitialize ok %d.%d\\n", maj, min); fflush(stderr);
  eglBindAPI(EGL_OPENGL_ES_API);''')
s=s.replace('  EGLSurface surf = eglCreatePbufferSurface(dpy,cfg,pbAttr);',
'''  fprintf(stderr, "chooseConfig ok n=%d\\n", n); fflush(stderr);
  EGLSurface surf = eglCreatePbufferSurface(dpy,cfg,pbAttr);
  fprintf(stderr, "pbuffer surf=%p\\n", (void*)surf); fflush(stderr);''')
s=s.replace('  if (!eglMakeCurrent(dpy,surf,surf,ctx)){',
'''  fprintf(stderr, "ctx=%p makeCurrent...\\n", (void*)ctx); fflush(stderr);
  if (!eglMakeCurrent(dpy,surf,surf,ctx)){''')
io.open(p,'w').write(s)
print('已打补丁 ✓')
EOF
'''
print(ex(patch)[:400])
print('=== 重编 ===')
print(ex('cd /tmp && gcc -O2 -I/usr/include/drm -I/usr/include/libdrm -o c3shot c3shot.c -ldrm -lgbm -lEGL -lGLESv2 2>&1 | head -10; ls -la /tmp/c3shot 2>/dev/null|head -1')[:600])
print('=== 运行（看死在哪一步 ✓）===')
print(ex('sudo XDG_RUNTIME_DIR=/run/user/0 /tmp/c3shot /tmp/c3shot.ppm 2>&1 | head -20')[:1500])
print('=== 结果 ===')
print(ex('ls -la /tmp/c3shot.ppm 2>/dev/null || echo "没有产出"')[:200])
b64png = ex('base64 -w0 /tmp/c3shot.png 2>/dev/null').strip()
if not b64png:
    ex('/usr/local/venv/bin/python3 -c "from PIL import Image; im=Image.open(\'/tmp/c3shot.ppm\'); im.save(\'/tmp/c3shot.png\')" 2>/dev/null')
    b64png = ex('base64 -w0 /tmp/c3shot.png 2>/dev/null').strip()
print('  PNG base64:', len(b64png))
open('/storage/emulated/0/openpilot/c3shell/_attic/c3screen.b64','w').write(b64png)

