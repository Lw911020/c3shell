// c3shot.c v2 — DRM plane → dma-buf → EGL import → glReadPixels → PPM
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <GLES2/gl2.h>
#include <GLES2/gl2ext.h>

int main(int argc, char **argv){
  const char *dev = "/dev/dri/card0";
  const char *out = argc > 1 ? argv[1] : "/tmp/c3shot.ppm";
  int drm = open(dev, O_RDWR);
  if (drm < 0){ perror("open drm"); return 1; }
  drmSetClientCap(drm, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1);

  uint32_t fb_id=0, w=0, h=0, format=0, handle=0, pitch=0;
  drmModePlaneRes *pres = drmModeGetPlaneResources(drm);
  if (!pres){ fprintf(stderr,"no plane res\n"); return 2; }
  for (uint32_t i=0; i<pres->count_planes && !fb_id; i++){
    drmModePlane *pl = drmModeGetPlane(drm, pres->planes[i]);
    if (!pl) continue;
    if (pl->fb_id && pl->crtc_id){
      drmModeFB2 *fb2 = drmModeGetFB2(drm, pl->fb_id);
      if (fb2 && fb2->width){
        w=fb2->width; h=fb2->height; format=fb2->pixel_format;
        handle=fb2->handles[0]; pitch=fb2->pitches[0]; fb_id=pl->fb_id;
        fprintf(stderr,"FB2: %ux%u fourcc=0x%08x modifier=0x%llx pitch=%u\n",
                w,h,format,(unsigned long long)fb2->modifier,pitch);
      }
      if (fb2) drmModeFreeFB2(fb2);
      if (!fb_id){
        drmModeFB *fb = drmModeGetFB(drm, pl->fb_id);
        if (fb && fb->width){
          w=fb->width; h=fb->height; handle=fb->handle; pitch=fb->pitch; fb_id=pl->fb_id;
          format = DRM_FORMAT_XRGB8888;
          fprintf(stderr,"FB(legacy): %ux%u pitch=%u -> assume XRGB8888\n", w,h,pitch);
        }
        if (fb) drmModeFreeFB(fb);
      }
    }
    drmModeFreePlane(pl);
  }
  if (!fb_id){ fprintf(stderr,"no active plane\n"); return 3; }

  int dmabuf=-1;
  if (drmPrimeHandleToFD(drm, handle, DRM_CLOEXEC, &dmabuf)!=0 || dmabuf<0){ perror("prime"); return 4; }

  EGLDisplay dpy = eglGetDisplay(EGL_DEFAULT_DISPLAY);
  if (dpy==EGL_NO_DISPLAY){ fprintf(stderr,"no egl display\n"); return 5; }
  EGLint maj,min;
  if (!eglInitialize(dpy,&maj,&min)){ fprintf(stderr,"eglInitialize failed\n"); return 6; }
  eglBindAPI(EGL_OPENGL_ES_API);
  EGLint cfgAttr[] = { EGL_SURFACE_TYPE, EGL_PBUFFER_BIT, EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
                       EGL_RED_SIZE,8, EGL_GREEN_SIZE,8, EGL_BLUE_SIZE,8, EGL_ALPHA_SIZE,8, EGL_NONE };
  EGLConfig cfg; EGLint n=0;
  if (!eglChooseConfig(dpy,cfgAttr,&cfg,1,&n) || n<1){ fprintf(stderr,"no egl config\n"); return 7; }
  EGLint pbAttr[] = { EGL_WIDTH,(EGLint)w, EGL_HEIGHT,(EGLint)h, EGL_NONE };
  EGLSurface surf = eglCreatePbufferSurface(dpy,cfg,pbAttr);
  EGLint ctxAttr[] = { EGL_CONTEXT_CLIENT_VERSION,2, EGL_NONE };
  EGLContext ctx = eglCreateContext(dpy,cfg,EGL_NO_CONTEXT,ctxAttr);
  if (!eglMakeCurrent(dpy,surf,surf,ctx)){ fprintf(stderr,"makeCurrent failed 0x%x\n", eglGetError()); return 8; }

  EGLint imgAttr[] = {
    EGL_WIDTH,(EGLint)w, EGL_HEIGHT,(EGLint)h, EGL_LINUX_DRM_FOURCC_EXT,(EGLint)format,
    EGL_DMA_BUF_PLANE0_FD_EXT,dmabuf, EGL_DMA_BUF_PLANE0_OFFSET_EXT,0,
    EGL_DMA_BUF_PLANE0_PITCH_EXT,(EGLint)pitch, EGL_NONE };
  PFNEGLCREATEIMAGEKHRPROC createImg = (PFNEGLCREATEIMAGEKHRPROC)eglGetProcAddress("eglCreateImageKHR");
  PFNGLEGLIMAGETARGETTEXTURE2DOESPROC targetTex = (PFNGLEGLIMAGETARGETTEXTURE2DOESPROC)eglGetProcAddress("glEGLImageTargetTexture2DOES");
  if (!createImg || !targetTex){ fprintf(stderr,"no image procs\n"); return 9; }
  EGLImageKHR img = createImg(dpy,EGL_NO_CONTEXT,EGL_LINUX_DMA_BUF_EXT,NULL,imgAttr);
  if (img==EGL_NO_IMAGE_KHR){ fprintf(stderr,"create image failed 0x%x\n", eglGetError()); return 10; }

  GLuint tex=0,fbo=0;
  glGenTextures(1,&tex); glBindTexture(GL_TEXTURE_2D,tex);
  glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST);
  glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST);
  targetTex(GL_TEXTURE_2D,img);
  glGenFramebuffers(1,&fbo); glBindFramebuffer(GL_FRAMEBUFFER,fbo);
  glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,tex,0);
  GLenum st = glCheckFramebufferStatus(GL_FRAMEBUFFER);
  if (st!=GL_FRAMEBUFFER_COMPLETE){ fprintf(stderr,"fbo incomplete 0x%x\n",st); return 11; }

  unsigned char *px = malloc((size_t)w*h*4);
  glPixelStorei(GL_PACK_ALIGNMENT,1);
  glReadPixels(0,0,(GLsizei)w,(GLsizei)h,GL_RGBA,GL_UNSIGNED_BYTE,px);
  GLenum e = glGetError();
  if (e!=GL_NO_ERROR){ fprintf(stderr,"glReadPixels err 0x%x\n",e); return 13; }

  FILE *f=fopen(out,"wb");
  if (!f){ perror("fopen"); return 14; }
  fprintf(f,"P6\n%d %d\n255\n",w,h);
  for (unsigned y=0;y<h;y++){
    const unsigned char *row = px + (size_t)y*w*4;
    for (unsigned x=0;x<w;x++){ fputc(row[x*4+0],f); fputc(row[x*4+1],f); fputc(row[x*4+2],f); }
  }
  fclose(f);
  fprintf(stderr,"saved %s (%ux%u)\n",out,w,h);
  return 0;
}
