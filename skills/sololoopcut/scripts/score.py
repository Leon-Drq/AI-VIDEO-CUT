"""Generate the original SoloLoop / Face to Face instrumental, 96 BPM."""
from pathlib import Path
import argparse,json,wave
import numpy as np
from scipy import signal

def generate(duration,out):
    if duration<=0:raise ValueError('duration must be positive')
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    sr=48000;n=round((duration+3)*sr);score=np.zeros((n,2));rng=np.random.default_rng(20261117)
    beat=60/96;bar=beat*4
    def add(z,start,amp=.1,pan=0):
        a=round(start*sr)
        if a>=n:return
        if z.ndim==1:z=np.column_stack([z*np.sqrt((1-pan)/2),z*np.sqrt((1+pan)/2)])
        k=min(len(z),n-a)
        if k>0:score[a:a+k]+=z[:k]*amp
    def freq(note):return 440*2**((note-69)/12)
    def key(note,length=1.8,soft=.65):
        t=np.arange(round(length*sr))/sr;f=freq(note);z=np.zeros(len(t))
        for h,a in [(1,1),(2,.30),(3,.12),(4,.045),(6,.012)]:z+=a*np.sin(2*np.pi*f*h*(1+.00011*h*h)*t)*np.exp(-t/(1.25/h**.67))
        z*=np.minimum(t/.008,1)*np.minimum((length-t)/.13,1)
        return np.tanh(z*soft)
    def pad(notes,length):
        t=np.arange(round(length*sr))/sr;z=np.zeros((len(t),2));env=np.minimum(t/.35,1)*np.minimum((length-t)/.6,1)
        for note in notes:
            f=freq(note)
            for ch,dt in enumerate([-.0018,.0018]):z[:,ch]+=(np.sin(2*np.pi*f*(1+dt)*t)+.12*np.sin(2*np.pi*2*f*t))*env/len(notes)
        return z
    def bass(note,length):
        t=np.arange(round(length*sr))/sr;f=freq(note);env=(1-np.exp(-t/.009))*np.exp(-t/1.2)*np.minimum((length-t)/.12,1)
        return (np.sin(2*np.pi*f*t)+.16*np.sin(2*np.pi*f*2*t))*env
    def kick():
        t=np.arange(round(.32*sr))/sr;phase=2*np.pi*(46*t+75*.018*(1-np.exp(-t/.018)))
        return np.sin(phase)*np.exp(-t/.065)*(1-np.exp(-t/.0006))
    def hat():
        t=np.arange(round(.06*sr))/sr;z=signal.sosfilt(signal.butter(2,7000,fs=sr,btype='highpass',output='sos'),rng.normal(size=len(t)))
        return z*np.exp(-t/.012)*(1-np.exp(-t/.001))
    def snare():
        t=np.arange(round(.18*sr))/sr;z=signal.sosfilt(signal.butter(2,[1100,6500],fs=sr,btype='bandpass',output='sos'),rng.normal(size=len(t)))
        return .8*z*np.exp(-t/.035)+.20*np.sin(2*np.pi*180*t)*np.exp(-t/.025)
    chords=[[62,66,69,73],[61,64,68,71],[59,62,66,69],[55,59,62,66]];roots=[38,42,35,43];bars=int(np.ceil(duration/bar))
    for k in range(bars):
        start=k*bar;idx=k%4;notes=chords[idx]
        if k==bars-1:notes=chords[0];idx=0
        add(pad(notes,bar+.65),start,.020)
        for j,offset in enumerate([0,.75,1.5,2.75]):
            if k==0 and j>1:continue
            for h,nt in enumerate(notes):add(key(nt,1.7),start+offset*beat+h*.018,.048*(.9 if j%2 else 1),pan=(-.34 if h%2==0 else .34))
        add(bass(roots[idx],beat*1.6),start,.055)
        if k>1:
            add(bass(roots[idx]+7,beat*.75),start+2.5*beat,.025);add(kick(),start,.075);add(kick(),start+2*beat,.052)
            for b in [1,3]:add(snare(),start+b*beat,.025)
            for j in range(8):add(hat(),start+j*beat/2,.009*(.7 if j%2 else 1),pan=(-.25 if j%2 else .25))
        if k in [3,7,11,15]:
            for j,nt in enumerate([notes[2]+12,notes[1]+12,notes[0]+12]):add(key(nt,1.4,.4),start+(1+j*.5)*beat,.019,pan=.22)
    for delay,amount in [(.047,.13),(.089,.075),(.143,.045)]:
        k=round(delay*sr);score[k:]+=score[:-k,::-1]*amount
    score=score[:round(duration*sr)];t=np.arange(len(score))/sr
    score*=np.minimum(np.minimum(t/.4,1),np.minimum((duration-t)/1.1,1))[:,None]
    score*=.72/max(float(np.max(np.abs(score))),.72)
    pcm=np.rint(np.clip(score,-1,1-2**-23)*8388608).astype('<i4')
    packed=pcm.reshape(-1).view(np.uint8).reshape(-1,4)[:,:3].tobytes()
    with wave.open(str(out),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(3);wav.setframerate(sr);wav.writeframes(packed)
    out.with_suffix('.json').write_text(json.dumps({'title':'SoloLoop / Face to Face','creation':'original procedural instrumental','bpm':96,'duration':duration,'seed':20261117,'reference_soundtrack':'unidentified; this is not the reference recording'},ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--duration',type=float,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();generate(a.duration,a.out)
