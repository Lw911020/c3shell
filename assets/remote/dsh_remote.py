#!/usr/bin/env python3
# 独立版 APP 的远端小工具：ls / read / write（自带，不依赖连接器）
import os, sys, json, base64

def out(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False))
    sys.stdout.flush()

cmd = sys.argv[1] if len(sys.argv) > 1 else ''

if cmd == 'ls':
    p = sys.argv[2] if len(sys.argv) > 2 else '/data/openpilot'
    try:
        ap = os.path.realpath(p)
        if not os.path.isdir(ap):
            ap = os.path.dirname(ap) or '/'
        ents = []
        for n in sorted(os.listdir(ap)):
            f = os.path.join(ap, n)
            try:
                st = os.lstat(f)
                ents.append({'name': n, 'dir': os.path.isdir(f), 'size': st.st_size,
                             'mtime': int(st.st_mtime), 'link': os.path.islink(f)})
            except Exception:
                pass
        out({'ok': True, 'path': ap, 'requested': p, 'entries': ents})
    except Exception as e:
        out({'ok': False, 'error': {'message': str(e)}, 'path': p, 'requested': p, 'entries': []})

elif cmd == 'read':
    p = sys.argv[2]
    try:
        with open(p, 'rb') as fh:
            b = fh.read(4 * 1024 * 1024)
        out({'ok': True, 'path': p, 'size': len(b), 'b64': base64.b64encode(b).decode()})
    except Exception as e:
        out({'ok': False, 'error': {'message': str(e)}})

elif cmd == 'write':
    p = sys.argv[2]
    data = base64.b64decode((sys.stdin.read() or '').strip() or '')
    try:
        d = os.path.dirname(p)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with open(p, 'wb') as fh:
            fh.write(data)
        out({'ok': True, 'path': p, 'size': len(data)})
    except Exception as e:
        out({'ok': False, 'error': {'message': str(e)}})

elif cmd == 'lsdirs':
    p = sys.argv[2] if len(sys.argv) > 2 else '/'
    try:
        out({'ok': True, 'dirs': sorted([d for d in os.listdir(p) if os.path.isdir(os.path.join(p, d))])})
    except Exception as e:
        out({'ok': False, 'error': {'message': str(e)}})

elif cmd == 'routes':
    # 形状要与诊断页对齐：{ok, root, routes:[{root, segments:[{dir,bytes,mtime,hasRlog}]}], totalBytes}
    root = sys.argv[2] if len(sys.argv) > 2 else '/data/media/0/realdata'
    segs = []
    total = 0
    try:
        for n in sorted(os.listdir(root), reverse=True):
            p2 = os.path.join(root, n)
            if not os.path.isdir(p2):
                continue
            if n in ('boot', 'realdata') or n.startswith('.'):
                continue
            sz = 0
            mt = 0
            for dp, dn, fn in os.walk(p2):
                for f in fn:
                    try:
                        st = os.stat(os.path.join(dp, f))
                        sz += st.st_size
                        mt = max(mt, int(st.st_mtime))
                    except Exception:
                        pass
            has_rlog = os.path.exists(os.path.join(p2, 'rlog.zst')) or os.path.exists(os.path.join(p2, 'rlog.bz2'))
            segs.append({'dir': n, 'bytes': sz, 'mtime': mt, 'hasRlog': has_rlog})
            total += sz
        out({'ok': True, 'root': root, 'routes': [{'root': root, 'segments': segs}], 'totalBytes': total})
    except Exception as e:
        out({'ok': False, 'root': root, 'routes': [], 'totalBytes': 0, 'error': {'message': str(e)}})

else:
    out({'ok': False, 'error': {'message': 'unknown command: ' + cmd}})
