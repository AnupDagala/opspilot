"""Render recorded execution results into a clearly labelled evidence replay.

This is not generated UI footage or a claimed browser recording.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,subprocess,textwrap

ROOT=Path(__file__).resolve().parent.parent
evidence=ROOT/'evidence';frames=ROOT/'artifacts/video-frames';frames.mkdir(parents=True,exist_ok=True)
steps=json.loads((evidence/'execution-transcript.json').read_text())
report=json.loads((evidence/('hosted-api-verification.json' if (evidence/'hosted-api-verification.json').exists() else 'local-api-verification.json')).read_text())
fontdir=Path('/usr/share/fonts/truetype/dejavu')
def font(size,bold=False,mono=False):return ImageFont.truetype(str(fontdir/('DejaVuSansMono.ttf' if mono else 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')),size)
def wrapped(draw,text,pos,size,width,color,bold=False):
    y=pos[1]
    for line in textwrap.wrap(text,width):draw.text((pos[0],y),line,font=font(size,bold),fill=color);y+=size+10
    return y
images=[]
for index,step in enumerate([None]+steps+[None]):
    im=Image.new('RGB',(1280,720),'#f0f3eb');d=ImageDraw.Draw(im)
    d.rectangle((0,0,1280,87),fill='#172925');d.text((45,25),'dealerops / lab',font=font(29,True),fill='#d9edaf');d.text((865,34),'EXECUTION EVIDENCE REPLAY',font=font(14,True),fill='#cbd9cb')
    if index==0:
        d.text((58,136),'An order is only done',font=font(47,True),fill='#172925');d.text((58,200),'when the evidence agrees.',font=font(47,True),fill='#172925')
        wrapped(d,'A focused dealer-order automation project by Anup Dagala.',(62,295),25,64,'#526a5b')
        wrapped(d,'Watch actual captured Request-handler outcomes: clarification, reviewer approval, stale revisions, duplicate delivery and recovery.',(62,382),23,86,'#526a5b')
        d.rounded_rectangle((60,533,1220,617),12,fill='#d9edaf');wrapped(d,'Recording format: execution-result replay, not a browser screen recording.',(83,552),20,90,'#172925',True)
    elif index==len(steps)+1:
        d.text((58,139),'16 checks. One committed effect.',font=font(39,True),fill='#172925')
        wrapped(d,'The interrupted order recovered from its persisted receipt. Inventory stayed at 99 cartons after repeated execution.',(62,225),26,78,'#526a5b')
        wrapped(d,'44 behavioural tests and 60 deterministic extraction cases also passed. These counts do not establish live-model performance.',(62,355),24,80,'#526a5b')
        d.text((63,520),'github.com/AnupDagala/opspilot',font=font(27,True),fill='#1e5545');d.text((63,566),'examples/dealerops',font=font(22,mono=True),fill='#63736c')
    else:
        d.text((54,122),f'CHECK {index:02} / {len(steps):02}',font=font(15,True),fill='#1e5545');wrapped(d,step['step'],(53,169),34,31,'#172925',True)
        d.rounded_rectangle((54,363,300,416),8,fill='#d9edaf');d.text((77,374),step['result'],font=font(23,True),fill='#1e5545')
        d.text((55,452),'Captured application result',font=font(17,True),fill='#526a5b')
        d.text((55,486),report['captured_at'][:19]+' UTC',font=font(14,mono=True),fill='#63736c')
        d.rounded_rectangle((580,119,1220,609),12,fill='#172925');d.text((607,144),'OBSERVED EVIDENCE',font=font(15,True),fill='#91aa9b')
        y=191
        for line in json.dumps(step['evidence'],indent=2).splitlines():
            for part in textwrap.wrap(line,48,replace_whitespace=False,drop_whitespace=False) or ['']:
                d.text((609,y),part,font=font(17,mono=True),fill='#d9edaf');y+=29
        d.rectangle((0,645,1280*(index/len(steps)),653),fill='#1e5545')
    mode='Hosted HTTP API' if report.get('hosted_api_verified') else 'Worker handlers · file-backed R2 contract emulator'
    d.text((39,674),mode+' · deterministic extraction · synthetic ERP',font=font(13),fill='#526a5b')
    file=frames/f'{index:02}.png';im.save(file);images.append(file)
concat=frames/'concat.txt';concat.write_text(''.join(f"file '{p}'\nduration {5 if 0<i<len(images)-1 else 6}\n" for i,p in enumerate(images))+f"file '{images[-1]}'\n")
subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-f','concat','-safe','0','-i',str(concat),'-vf','fps=24,format=yuv420p','-c:v','libx264','-crf','30','-preset','slow','-movflags','+faststart',str(evidence/'execution-walkthrough.mp4')],check=True)
Image.open(images[1]).save(evidence/'execution-preview.png')
print('Saved execution-walkthrough.mp4 (92-second evidence replay).')
