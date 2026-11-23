"""Transcribe prepared source audio using a local faster-whisper model."""
from pathlib import Path
import argparse,json,os

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path)
    p.add_argument('--model',default=os.environ.get('SOLOLOOP_WHISPER_MODEL'));p.add_argument('--language',default='zh')
    p.add_argument('--device',default='auto');p.add_argument('--compute-type',default='auto');a=p.parse_args()
    if not a.model:p.error('provide --model or SOLOLOOP_WHISPER_MODEL; models are not bundled')
    from faster_whisper import WhisperModel
    m=WhisperModel(a.model,device=a.device,compute_type=a.compute_type,local_files_only=True);result=[]
    sources=json.loads((a.project/'source-inventory.json').read_text(encoding='utf-8'))
    for s in sources:
        folder=a.project/'sources'/s['id'];segments=[]
        if s['has_audio']:
            it,_=m.transcribe(str(folder/'audio.wav'),language=a.language,word_timestamps=True,vad_filter=True,beam_size=5)
            for x in it:
                seg={'start':round(x.start,3),'end':round(x.end,3),'text':x.text,'words':[{'start':round(w.start,3),'end':round(w.end,3),'word':w.word,'probability':round(w.probability,3)} for w in x.words or []]}
                segments.append(seg);print(s['id'],seg['start'],seg['end'],seg['text'],flush=True)
        (folder/'transcript.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding='utf-8')
        result.append({'source_id':s['id'],'segments':segments,'status':'ASR draft; verify facts and original audio' if s['has_audio'] else 'no audio'})
    (a.project/'transcripts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()
