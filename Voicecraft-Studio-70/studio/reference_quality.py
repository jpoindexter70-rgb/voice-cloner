"""Signal-only reference suggestions; never a speaker-similarity or speech detector."""
import numpy as np
from .prosody import edge_trim

def evaluate(values,sr):
    values=np.asarray(values,dtype=np.float32)
    if values.ndim>1:values=values.mean(axis=1)
    frame=max(1,int(sr*.03));levels=np.array([np.sqrt(np.mean(values[i:i+frame]**2)) for i in range(0,len(values),frame)])
    if not len(levels):raise ValueError('No audio was supplied.')
    low=float(np.percentile(levels,10));high=float(np.percentile(levels,90))
    contrast=20*np.log10(max(high,.000001)/max(low,.000001))
    quiet=float(np.mean(levels<max(.003,high*.08)))
    clipped=float(np.mean(np.abs(values)>=.99))
    warnings=[]
    if clipped>.001:warnings.append('Clipping cannot be restored; choose an unclipped take.')
    if quiet>.45:warnings.append('Large quiet portions; select a clean speaking section.')
    if contrast<10:warnings.append('Low level contrast may indicate steady background noise or continuous sound. Listen before using.')
    return {'quiet_fraction':round(quiet,3),'estimated_level_contrast_db':round(float(contrast),1),'clipped_fraction':round(clipped,5),'warnings':warnings,'method':'Signal checks only: no speech detection, speaker matching or guaranteed noise/SNR measurement.'}

def suggestions(values,sr,seconds=12):
    if values.ndim>1:values=values.mean(axis=1)
    duration=len(values)/sr;seconds=min(seconds,duration)
    starts=list(np.arange(0,max(.01,duration-seconds+.01),max(2,seconds/3)))
    if duration>seconds:starts.append(duration-seconds)
    ranked=[]
    for start in starts:
        clip=values[int(start*sr):int((start+seconds)*sr)];quality=evaluate(clip,sr)
        score=quality['quiet_fraction']+quality['clipped_fraction']*30+max(0,10-quality['estimated_level_contrast_db'])/30
        ranked.append({'start':round(float(start),2),'end':round(float(start+seconds),2),'signal_penalty':round(score,3),'quality':quality})
    best=[]
    for item in sorted(ranked,key=lambda q:q['signal_penalty']):
        if all(abs(item['start']-q['start'])>seconds*.5 for q in best):best.append(item)
        if len(best)==3:break
    return best

def clean(values,sr):
    if values.ndim>1:values=values.mean(axis=1)
    values=edge_trim(values,sr)
    rms=float(np.sqrt(np.mean(values**2)));peak=float(np.max(np.abs(values),initial=0))
    if rms>0:
        gain=min(10**(12/20),.1/rms,.95/max(peak,.000001))
        values=values*gain
    return values
