import struct, sys, os
def read_bsa(path):
    f=open(path,'rb')
    magic,ver,off,flags,fc,filec,tfn,tfl,fflags=struct.unpack('<4sIIIIIIII',f.read(36))
    assert magic==b'BSA\0'
    compressed=bool(flags&4); embed=bool(flags&0x100)
    folders=[]
    for i in range(fc):
        if ver==105: h,c,_,o=struct.unpack('<QIIQ',f.read(24))
        else: h,c,o=struct.unpack('<QII',f.read(16))
        folders.append(c)
    entries=[]
    for c in folders:
        n=f.read(1)[0]; name=f.read(n)[:-1].decode('cp1252')
        for j in range(c):
            h,size,o=struct.unpack('<QII',f.read(16))
            entries.append([name,size,o])
    names=f.read(tfl).split(b'\0')
    for e,n in zip(entries,names): e.insert(1,n.decode('cp1252'))
    return f,ver,compressed,embed,entries
def extract(path,pred,out):
    import lz4.frame, zlib
    f,ver,comp,embed,entries=read_bsa(path)
    res=[]
    for folder,name,size,o in entries:
        full=folder+chr(92)+name
        if not pred(full): continue
        c=comp ^ bool(size&0x40000000); size&=0x3fffffff
        f.seek(o); data=f.read(size)
        if embed:
            l=data[0]; data=data[1+l:]
        if c:
            orig=struct.unpack('<I',data[:4])[0]; data=data[4:]
            data=lz4.frame.decompress(data) if ver==105 else zlib.decompress(data)
        p=os.path.join(out,*full.split(chr(92))); os.makedirs(os.path.dirname(p),exist_ok=True)
        open(p,'wb').write(data); res.append(full)
    return res
if __name__=='__main__':
    f,ver,comp,embed,entries=read_bsa(sys.argv[1])
    for folder,name,size,o in entries:
        full=folder+chr(92)+name
        if len(sys.argv)<3 or any(k in full.lower() for k in sys.argv[2:]): print(full,size&0x3fffffff)
