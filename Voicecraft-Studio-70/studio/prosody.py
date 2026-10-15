"""Conservative English narration preparation. No SSML or invented model controls."""
import re
import numpy as np

SMALL='zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS='zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
ABBREVIATIONS={'Dr.':'doctor','Mr.':'mister','Mrs.':'missus','Ms.':'miz','e.g.':'for example','i.e.':'that is','U.S.':'U S','U.K.':'U K','AI':'A I','CPU':'C P U','GPU':'G P U','GHz':'gigahertz','MHz':'megahertz','GB':'gigabytes','MB':'megabytes','Hz':'hertz','kg':'kilograms','cm':'centimeters'}

def integer(value):
    n=int(value)
    if n<20:return SMALL[n]
    if n<100:return TENS[n//10]+(' '+SMALL[n%10] if n%10 else '')
    if n<1000:return SMALL[n//100]+' hundred'+(' '+integer(n%100) if n%100 else '')
    for scale,name in [(10**12,'trillion'),(10**9,'billion'),(10**6,'million'),(1000,'thousand')]:
        if n>=scale:return integer(n//scale)+' '+name+(' '+integer(n%scale) if n%scale else '')

def number(value):
    value=value.replace(',','')
    if '.' in value:
        whole,decimal=value.split('.',1)
        return integer(whole)+' point '+' '.join(SMALL[int(c)] for c in decimal)
    if len(value)>1 and value.startswith('0'):return ' '.join(SMALL[int(c)] for c in value)
    return integer(value)

def currency(match):
    value=match[1].replace(',','')
    if '.' in value and len(value.split('.')[1])>2:return number(value)+' dollars'
    whole,_,decimal=value.partition('.')
    dollars=int(whole);cents=int(decimal.ljust(2,'0')) if decimal else 0
    parts=[]
    if dollars or not cents:parts.append(integer(dollars)+(' dollar' if dollars==1 else ' dollars'))
    if cents:parts.append(integer(cents)+(' cent' if cents==1 else ' cents'))
    return ' and '.join(parts)

def normalize(text,corrections=None):
    text=text.replace('\r\n','\n').replace('\r','\n').replace('\u00a0',' ')
    corrections=corrections or {}
    # Literal, case-insensitive, whole-word corrections; never interpret user input as regex.
    for source in sorted(corrections,key=len,reverse=True):
        if not source.strip():continue
        text=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',lambda m:corrections[source],text,flags=re.I)
    text=re.sub(r'(\d)(GHz|MHz|GB|MB|kg|cm|Hz)\b',r'\1 \2',text)
    for source,target in ABBREVIATIONS.items():
        text=re.sub(r'(?<!\w)'+re.escape(source)+r'(?!\w)',lambda m:target,text)
    # Avoid silently reading URLs, times, dates, ordinals or version numbers as plain quantities.
    protected={}
    def protect(match):
        key='PROTECTEDTOKEN'+integer(len(protected)).replace(' ','')+'END'
        protected[key]=match.group();return key
    text=re.sub(r'https?://\S+|\b\d+(?:[:/\-]\d+)+\b|\b\d+(?:\.\d+){2,}\b|\b\d+(?:st|nd|rd|th)\b',protect,text)
    text=re.sub(r'\$(\d[\d,]*(?:\.\d+)?)',currency,text)
    text=re.sub(r'(?<!\w)-(?=\d)','minus ',text)
    text=re.sub(r'(?<![\w.])\d[\d,]*(?:\.\d+)?(?!\w|\.\d)',lambda m:number(m[0]),text)
    text=re.sub(r'(?<=\w)\s*%',' percent',text)
    for token,value in protected.items():text=text.replace(token,value)
    return '\n'.join(re.sub(r'[ \t]+',' ',line).strip() for line in text.split('\n')).strip()

def sentences(text):
    """Retain punctuation and section boundaries. No splitting within decimal numbers or initials."""
    result=[]
    for paragraph in re.split(r'\n\s*\n',text.strip()):
        paragraph=re.sub(r'\s+',' ',paragraph).strip()
        if not paragraph:continue
        start=0;units=[]
        for match in re.finditer(r'''[.!?]+["”’')\]]*''',paragraph):
            end=match.end();tail=paragraph[end:]
            if tail and not tail[0].isspace():continue
            before=paragraph[:match.start()+1]
            if re.search(r'\b(?:Dr|Mr|Mrs|Ms|Prof|St|vs|etc)\.$|\b[A-Z]\.$',before,re.I):continue
            value=paragraph[start:end].strip()
            if value:units.append(value)
            start=end
        if paragraph[start:].strip():units.append(paragraph[start:].strip())
        for index,value in enumerate(units):result.append({'text':value,'section_end':index==len(units)-1})
    return result

def plan(text,corrections=None,limit=420):
    prepared=normalize(text,corrections);units=[]
    if len(prepared)>60000:raise ValueError('Pronunciation expansion is too long. Shorten the script or corrections.')
    for sentence_index,sentence in enumerate(sentences(prepared)):
        remaining=sentence['text'];chunks=[]
        while len(remaining)>limit:
            # Prefer real clauses; only fall back to a word boundary for an overlong clause.
            candidates=[m.end() for m in re.finditer(r'[,;:—–](?:\s+)',remaining[:limit+1]) if m.end()>=80]
            cut=candidates[-1] if candidates else remaining.rfind(' ',0,limit+1)
            if cut<=0:raise ValueError('A script token exceeds 420 characters. Replace long URLs or identifiers with their spoken form.')
            chunks.append(remaining[:cut].strip());remaining=remaining[cut:].strip()
        if remaining:chunks.append(remaining)
        for i,chunk in enumerate(chunks):
            units.append({'text':chunk,'sentence':sentence_index,'section_end':sentence['section_end'] and i==len(chunks)-1,'sentence_end':i==len(chunks)-1})
    if not units:raise ValueError('Enter a narration script.')
    return {'prepared_text':prepared,'segments':units,'note':'Review numbers, dates, names and pronunciation corrections before generating. Listening is required to check actual spoken words.'}

def edge_trim(values,sr):
    """Only shorten excessive digital/very quiet padding, preserving breaths and word onsets."""
    values=np.asarray(values,dtype=np.float32)
    block=max(1,int(sr*.01));energy=np.array([np.sqrt(np.mean(values[i:i+block]**2)) for i in range(0,len(values),block)])
    active=np.flatnonzero(energy>max(.001,float(energy.max(initial=0))*.015))
    if not len(active):return values
    start=max(0,int(active[0]*block-sr*.08));end=min(len(values),int((active[-1]+1)*block+sr*.12))
    return values[start:end]

def join(clips,sr,segments,pause=.2):
    # Punctuation has already conditioned the model. Add only the missing small boundary gap.
    values=[];offset=0;timings=[]
    for i,clip in enumerate(clips):
        clip=edge_trim(clip,sr)
        if i:
            previous=segments[i-1]
            desired=max(0,(.32 if previous['section_end'] else .16 if previous['sentence_end'] else .045)+pause-.2)
            def quiet_edge(a,reverse=False):
                a=a[::-1] if reverse else a
                indices=np.flatnonzero(np.abs(a)>.004)
                return (int(indices[0]) if len(indices) else len(a))/sr
            existing=quiet_edge(values[-1],True)+quiet_edge(clip)
            gap=max(0,desired-existing)
            if gap:padding=np.zeros(int(sr*gap),dtype=np.float32);values.append(padding);offset+=len(padding)
        # A sub-millisecond taper removes cut-edge clicks; it is not pitch/volume acting.
        clip=clip.copy();fade=min(int(sr*.001),len(clip)//2)
        if fade:clip[:fade]*=np.linspace(0,1,fade);clip[-fade:]*=np.linspace(1,0,fade)
        timings.append({'index':i,'start_sample':offset,'end_sample':offset+len(clip),**segments[i]});values.append(clip);offset+=len(clip)
    return np.concatenate(values),timings
