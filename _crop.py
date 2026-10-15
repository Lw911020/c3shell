import struct, zlib, sys
def crop_raw(src, dst, x0,y0,x1,y1, scale=2):
    d=open(src,'rb').read()
    w,h,f=struct.unpack('<III', d[:12]); px=d[12:]
    cw,ch=x1-x0,y1-y0
    out=bytearray()
    for y in range(y0,y1):
        row=bytearray()
        base=(y*w+x0)*4
        for x in range(cw):
            i=base+x*4
            row += bytes((px[i],px[i+1],px[i+2]))*scale
        for _ in range(scale):
            out += b'\x00' + bytes(row)
    def chunk(t,data):
        c=t+data
        return struct.pack('>I',len(data))+c+struct.pack('>I',zlib.crc32(c)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',cw*scale,ch*scale,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(out),6))+chunk(b'IEND',b'')
    open(dst,'wb').write(png)
    return cw*scale, ch*scale
a=sys.argv[1]
print(crop_raw(a, a.replace('.raw','_crop.png'), int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), 2))
