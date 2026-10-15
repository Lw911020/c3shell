# -*- coding: utf-8 -*-
import urllib.request, json
B='http://127.0.0.1:3081'
def ex(cmd, t=300):
    r=urllib.request.Request(B+'/api/ssh/exec?token=embedded', data=json.dumps({'command':cmd}).encode(),
                             headers={'content-type':'application/json'}, method='POST')
    j=json.loads(urllib.request.urlopen(r, timeout=t).read().decode())
    return ((j.get('result') or {}).get('stdout') or '') + ((j.get('result') or {}).get('stderr') or '')
# 直接把 image 创建那段换成"多组合自动试"（用 python 改文件 ✓ 单引号安全 ✓）
patch = r'''
python3 - <<'PYEOF'
import io
p='/tmp/c3shot.c'; s=io.open(p).read()
old_start = s.find('  EGLint imgAttr[] = {')
old_end   = s.find('  GLuint tex=0,fbo=0;')
new = '''  const char *exts = eglQueryString(dpy, EGL_EXTENSIONS);
  fprintf(stderr, "dma_buf_import_ext=%s\\n", (exts && strstr(exts, "EGL_EXT_image_dma_buf_import")) ? "YES" : "NO"); fflush(stderr);
  if (exts) fprintf(stderr, "exts=%s\\n", exts); fflush(stderr);
  PFNEGLCREATEIMAGEKHRPROC createImg = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
  PFNGLEGLIMAGETARGETTEXTURE2DOESPROC targetTex = (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");
  if (!createImg || !targetTex){ fprintf(stderr,"no image procs\\n"); return 10; }
  uint32_t fmts[4] = { format, DRM_FORMAT_ABGR8888, DRM_FORMAT_ARGB8888, DRM_FORMAT_XBGR8888 };
  const char *fnames[4] = { "orig", "ABGR8888", "ARGB8888", "XBGR8888" };
  int modes[3] = { 0, 1, 2 };   // 0=无 modifier 属性 1=modifier 0 2=MOD_INVALID
  EGLImageKHR img = EGL_NO_IMAGE_KHR;
  for (int mi=0; mi<3 && img==EGL_NO_IMAGE_KHR; mi++){
    for (int fi=0; fi<4 && img==EGL_NO_IMAGE_KHR; fi++){
      EGLint a[20]; int k=0;
      a[k++]=EGL_WIDTH; a[k++]=(EGLint)w; a[k++]=EGL_HEIGHT; a[k++]=(EGLint)h;
      a[k++]=EGL_LINUX_DRM_FOURCC_EXT; a[k++]=(EGLint)fmts[fi];
      a[k++]=EGL_DMA_BUF_PLANE0_FD_EXT; a[k++]=dmabuf;
      a[k++]=EGL_DMA_BUF_PLANE0_OFFSET_EXT; a[k++]=0;
      a[k++]=EGL_DMA_BUF_PLANE0_PITCH_EXT; a[k++]=(EGLint)pitch;
      if (modes[mi]==1){ a[k++]=EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT; a[k++]=0; a[k++]=EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT; a[k++]=0; }
      if (modes[mi]==2){ long long INV=((1LL<<56)-1); a[k++]=EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT; a[k++]=(EGLint)(INV & 0xffffffff); a[k++]=EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT; a[k++]=(EGLint)(INV >> 32); }
      a[k++]=EGL_NONE;
      img = createImg(dpy,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,NULL,a);
      fprintf(stderr, "try fmt=%s modifier_mode=%d -> %s (err 0x%x)\\n", fnames[fi], modes[mi],
              img==EGL_NO_IMAGE_KHR?"fail":"OK", eglGetError()); fflush(stderr);
      if (img!=EGL_NO_IMAGE_KHR){ format = fmts[fi]; break; }
    }
  }
  if (img==EGL_NO_IMAGE_KHR){ fprintf(stderr,"all import tries failed\\n"); return 11; }

'''
s = s[:old_start] + new + s[old_end:]
# 删掉后面重复的 proc 获取（原代码在 imgAttr 之后还有一段）
s = s.replace('''  PFNEGLCREATEIMAGEKHRPROC createImg = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
  PFNGLEGLIMAGETARGETTEXTURE2DOESPROC targetTex = (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");
  STEPP("createImg", createImg); STEPP("targetTex", targetTex);
  if (!createImg || !targetTex){ fprintf(stderr,"no image procs\\n"); return 10; }
  STEP("eglCreateImageKHR...");
  EGLImageKHR img = createImg(dpy,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,NULL,imgAttr);
  STEPP("img", img);
  if (img==EGL_NO_IMAGE_KHR){ fprintf(stderr,"create image failed 0x%x\\n", eglGetError()); return 11; }
''', '')
io.open(p,'w').write(s)
print('patched', len(s))
