// touchd.c — C3 触摸注入常驻守护（2026-09-23）
// 目的：替代「每次点击新起 python touch.py」（约 250-350ms ✗）→ 常驻 + TCP 直投（约 10ms ✓）
// 协议：GET /tap?x=<panelX>&y=<panelY>   或   GET /swipe?x1=&y1=&x2=&y2=&ms=
// 输入事件：MT protocol B（weston 1.9 的 libinput 只认 MT-B ✓）
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/time.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define EV_SYN 0
#define EV_KEY 1
#define EV_ABS 3
#define SYN_REPORT 0
#define ABS_MT_SLOT 0x2f
#define ABS_MT_POSITION_X 0x35
#define ABS_MT_POSITION_Y 0x36
#define ABS_MT_PRESSURE 0x3a
#define ABS_MT_TRACKING_ID 0x39
#define BTN_TOUCH 0x14a

struct input_event { struct timeval time; unsigned short type; unsigned short code; int value; };

static int evfd = -1;
static int PW = 1080, PH = 2160;   /* 触摸面板：竖屏 1080x2160 ✓ */

static void emit(int t, int c, int v){
  struct input_event e; memset(&e, 0, sizeof e);
  e.type = t; e.code = c; e.value = v;
  if (write(evfd, &e, sizeof e) != (ssize_t)sizeof e) { }
}
static void syn(void){ emit(EV_SYN, SYN_REPORT, 0); }
static int clampi(int v, int lo, int hi){ return v < lo ? lo : (v > hi ? hi : v); }

static void down(int x, int y){
  x = clampi(x, 0, PW - 1); y = clampi(y, 0, PH - 1);
  emit(EV_ABS, ABS_MT_SLOT, 0);
  emit(EV_ABS, ABS_MT_TRACKING_ID, 1001);
  emit(EV_ABS, ABS_MT_POSITION_X, x);
  emit(EV_ABS, ABS_MT_POSITION_Y, y);
  emit(EV_ABS, ABS_MT_PRESSURE, 60);
  emit(EV_KEY, BTN_TOUCH, 1);
  syn();
}
static void up(void){
  emit(EV_ABS, ABS_MT_TRACKING_ID, -1);
  emit(EV_KEY, BTN_TOUCH, 0);
  syn();
}
static void do_tap(int x, int y){ down(x, y); usleep(40000); up(); }
static void do_swipe(int x1, int y1, int x2, int y2, int ms){
  int n = 10, i;
  if (ms < 80) ms = 80;
  down(x1, y1);
  for (i = 1; i <= n; i++){
    emit(EV_ABS, ABS_MT_POSITION_X, clampi(x1 + (x2 - x1) * i / n, 0, PW - 1));
    emit(EV_ABS, ABS_MT_POSITION_Y, clampi(y1 + (y2 - y1) * i / n, 0, PH - 1));
    syn();
    usleep((useconds_t)(ms * 1000 / n));
  }
  up();
}
static int qv(const char *q, const char *k, int dflt){
  char pat[32]; const char *p; int v;
  snprintf(pat, sizeof pat, "%s=", k);
  p = strstr(q, pat);
  if (!p) return dflt;
  v = atoi(p + strlen(pat));
  return v;
}
int main(int argc, char **argv){
  int port = (argc > 1) ? atoi(argv[1]) : 8091;
  int srv, one = 1;
  struct sockaddr_in a;
  evfd = open("/dev/input/event2", O_WRONLY);
  if (evfd < 0){ fprintf(stderr, "open event2 failed\n"); return 1; }
  srv = socket(AF_INET, SOCK_STREAM, 0);
  setsockopt(srv, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
  memset(&a, 0, sizeof a);
  a.sin_family = AF_INET; a.sin_addr.s_addr = htonl(INADDR_ANY); a.sin_port = htons(port);
  if (bind(srv, (struct sockaddr*)&a, sizeof a) < 0){ fprintf(stderr, "bind %d failed\n", port); return 1; }
  listen(srv, 8);
  printf("touchd on %d  (tap/swipe)\n", port); fflush(stdout);
  for (;;){
    int c = accept(srv, NULL, NULL);
    char buf[1024]; int n;
    if (c < 0) continue;
    n = read(c, buf, sizeof buf - 1);
    if (n > 0){
      char *q, path[512];
      buf[n] = 0;
      q = strchr(buf, ' ');        /* "GET /tap?... HTTP/1.1" */
      if (q){ q++; n = 0; while (q[n] && q[n] != ' ' && n < 500){ path[n] = q[n]; n++; } path[n] = 0;
        if (!strncmp(path, "/tap", 4)){
          do_tap(qv(path, "x", 0), qv(path, "y", 0));
        } else if (!strncmp(path, "/swipe", 6)){
          do_swipe(qv(path, "x1", 0), qv(path, "y1", 0), qv(path, "x2", 0), qv(path, "y2", 0), qv(path, "ms", 260));
        }
      }
    }
    { const char *ok = "HTTP/1.1 200 OK\r\nAccess-Control-Allow-Origin: *\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok";
      if (write(c, ok, strlen(ok)) != (ssize_t)strlen(ok)) { } }
    close(c);
  }
  return 0;
}

