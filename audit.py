import re,json,glob,html,sys
from collections import Counter
pages={}
for f in sorted(glob.glob('dist/**/*.html',recursive=True)):
    t=open(f).read(); pages[f]=t
titles=Counter();descs=Counter()
for f,t in pages.items():
    ti=html.unescape(re.search(r'<title>(.*?)</title>',t,re.S).group(1))
    de=html.unescape(re.search(r'<meta name="description" content="(.*?)">',t).group(1))
    can=re.findall(r'<link rel="canonical" href="(.*?)"',t)
    rob=re.findall(r'<meta name="robots" content="(.*?)"',t)
    h=re.findall(r'<h([1-6])[ >]',t)
    h1=h.count('1')
    # heading order skips
    skips=[(a,b) for a,b in zip(h,h[1:]) if int(b)>int(a)+1]
    ld=[]
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>',t,re.S):
        try: ld.append(json.loads(m)['@type'])
        except Exception as e: ld.append('BAD '+str(e))
    inl=set(re.findall(r'href="(/[^"#]*)"',t))
    inl={u for u in inl if not u.startswith('/assets') and u!='/favicon.svg'}
    print(f, len(ti),len(de),can,rob,'h1=',h1,'skips',skips[:3],ld)
    print('   T:',ti);print('   D:',de)
    titles[ti]+=1;descs[de]+=1
    print('   links:',sorted(inl))
print([k for k,v in titles.items() if v>1],[k for k,v in descs.items() if v>1])
