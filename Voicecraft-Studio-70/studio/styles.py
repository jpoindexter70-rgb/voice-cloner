"""Auditable delivery presets; Turbo has no native named acting-style API."""
STYLES = {
    'normal': {'name':'Normal / My Voice','speed':1.,'pitch':0.,'volume':1.,'pause':.2,'temperature':.8,'expression':.5},
    'storytelling': {'name':'Storytelling','speed':.96,'pitch':0.,'volume':1.,'pause':.35,'temperature':.8,'expression':.7},
    'bedtime': {'name':'Bedtime Reading','speed':.88,'pitch':-.3,'volume':.85,'pause':.5,'temperature':.65,'expression':.3},
    'energetic': {'name':'Energetic Character','speed':1.08,'pitch':.4,'volume':1.05,'pause':.15,'temperature':.95,'expression':1.},
    'calm': {'name':'Calm Narration','speed':.94,'pitch':0.,'volume':.95,'pause':.35,'temperature':.65,'expression':.35},
    'horror': {'name':'Horror / Suspense','speed':.88,'pitch':-.8,'volume':.95,'pause':.65,'temperature':.7,'expression':.65},
    'presenter': {'name':'YouTube Presenter','speed':1.02,'pitch':0.,'volume':1.,'pause':.2,'temperature':.8,'expression':.65},
    'food': {'name':'Food Narration','speed':.98,'pitch':.1,'volume':1.,'pause':.25,'temperature':.8,'expression':.65},
    'demo': {'name':'Toy / Product Demo','speed':1.05,'pitch':.3,'volume':1.,'pause':.18,'temperature':.9,'expression':.85},
    'review': {'name':'Product Review','speed':1.,'pitch':0.,'volume':1.,'pause':.25,'temperature':.7,'expression':.45},
}

def effective(settings):
    result=dict(settings);preset=STYLES.get(settings.get('style','normal'),STYLES['normal'])
    result['speed']=max(.5,min(2,settings['speed']*preset['speed']))
    result['pitch']=max(-6,min(6,settings['pitch']+preset['pitch']))
    result['volume']=max(0,min(2,settings.get('volume',1)*preset['volume']))
    if settings.get('style','normal')!='normal':
        for name in ('pause','temperature','expression'):result[name]=preset[name]
    return result
