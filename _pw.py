# -*- coding: utf-8 -*-
import urllib.request, json, base64
B='http://127.0.0.1:3081'
def ex(cmd, t=300):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
# 在设备上直接改：按 pitch/4 作为导入宽度，读取后再裁回 1080
print(ex(r'''python3 - <<'PYEOF'
import io
p='/tmp/c3shot.c'; s=io.open(p).read()
s=s.replace('''  unsigned char *px = malloc((size_t)w*h*4);
  glPixelStorei(GL_PACK_ALIGNMENT,1);
  glReadPixels(0,0,(GLsizei)w,(GLsizei)h,GL_RGBA,GL_UNSIGNED_BYTE,px);''',
'''  uint32_t wFull = pitch / 4;                 // 真实行宽（含 padding）✓
  fprintf(stderr,"import width=%u (fb width=%u pitch=%u)\n", wFull, w, pitch); fflush(stderr);
  unsigned char *px = malloc((size_t)wFull*h*4);
  glPixelStorei(GL_PACK_ALIGNMENT,1);
  glReadPixels(0,0,(GLsizei)wFull,(GLsizei)h,GL_RGBA,GL_UNSIGNED_BYTE,px);''')
s=s.replace('''  for (unsigned y=0;y<h;y++){ const unsigned char *row=px+(size_t)y*w*4;
    for (unsigned x=0;x<w;x++){ fputc(row[x*4+0],f); fputc(row[x*4+1],f); fputc(row[x*4+2],f); } }''',
'''  for (unsigned y=0;y<h;y++){ const unsigned char *row=px+(size_t)y*wFull*4;
    for (unsigned x=0;x<w;x++){ fputc(row[x*4+0],f); fputc(row[x*4+1],f); fputc(row[x*4+2],f); } }''')
# EGLImage 导入宽度也要用真实行宽
s=s.replace('a[k++]=EGL_WIDTH; a[k++]=(EGLint)w; a[k++]=EGL_HEIGHT; a[k++]=(EGLint)h;',
            'a[k++]=EGL_WIDTH; a[k++]=(EGLint)(pitch/4); a[k++]=EGL_HEIGHT; a[k++]=(EGLint)h;')
# pbuffer 也要够大
s=s.replace('EGLint pbAttr[] = { EGL_WIDTH,(EGLint)w, EGL_HEIGHT,(EGLint)h, EGL_NONE };',
            'EGLint pbAttr[] = { EGL_WIDTH,(EGLint)(pitch/4), EGL_HEIGHT,(EGLint)h, EGL_NONE };')
io.open(p,'w').write(s)
print('已改：按 pitch/4 导入 ✓')
PYEOF''')[:400])
print('编译:', ex('cd /tmp && gcc -O2 -I/usr/include/drm -I/usr/include/libdrm -o c3shot c3shot.c -ldrm -lgbm -lEGL -lGLESv2 2>&1|head -6; ls /tmp/c3shot >/dev/null 2>&1 && echo OK || echo FAIL')[:400])
r = ex('sudo XDG_RUNTIME_DIR=/run/user/0 /tmp/c3shot /tmp/c3shot.ppm 2>&1 | tail -8')
print(r[:900])
ex('/usr/local/venv/bin/python3 -c "from PIL import Image; im=Image.open(chr(47)+chr(116)+chr(109)+chr(112)+chr(47)+chr(99)+chr(51)+chr(115)+chr(104)+chr(111)+chr(116)+chr(46)+chr(112)+chr(112)+chr(109)); im.thumbnail((480,960)); im.convert(chr(82)+chr(71)+chr(66)).save(chr(47)+chr(116)+chr(109)+chr(112)+chr(47)+chr(99)+chr(51)+chr(115)+chr(109)+chr(97)+chr(108)+chr(108)+chr(46)+chr(106)+chr(112)+chr(103), quality=70)" 2>&1|head -2')
b64 = ex('base64 -w0 /tmp/c3small.jpg').strip()
print('  小图 base64:', len(b64))
open('/storage/emulated/0/openpilot/c3shell/_attic/c3small.b64','w').write(b64)

