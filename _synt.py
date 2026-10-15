import io, subprocess
s=io.open('/storage/emulated/0/openpilot/c3shell/assets/diag.html',encoding='utf-8').read()
def grab(name):
    i=s.index('function '+name+'(')
    d=0; j=i
    while j<len(s):
        if s[j]=='{': d+=1
        elif s[j]=='}':
            d-=1
            if d==0: break
        j+=1
    return s[i:j+1]
js=''
for fn in ('_csvMenu','toast','exportAll','importAllText'):
    js += 'var a_%s = %s;
' % (fn, grab(fn))
js += 'console.log("4 个函数语法 OK");
'
io.open('/storage/emulated/0/openpilot/c3shell/_attic/_m2.js','w',encoding='utf-8').write(js)
r=subprocess.run(['node','/storage/emulated/0/openpilot/c3shell/_attic/_m2.js'],capture_output=True,text=True)
print(' ', r.stdout.strip() or r.stderr[:300])
print('  括号差 {}=', s.count('{')-s.count('}'))
