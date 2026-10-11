"""Draw the dimensioned transcription with Pillow; never edit model/source data."""
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from geometry_stage2 import door_pose

ROOT = Path(__file__).resolve().parents[1]
spec = json.loads((ROOT/'data/house_stage2_geometry.json').read_text())
validation = json.loads((ROOT/'data/stage2_validation.json').read_text())
im = Image.new('RGB', (2400, 2000), '#faf9f6')
d = ImageDraw.Draw(im)
font = '/System/Library/Fonts/Supplemental/Arial.ttf'
f = ImageFont.truetype(font, 25)
small = ImageFont.truetype(font, 22)
big = ImageFont.truetype(font, 40)
scale = .105

def pt(x, y):
    return (180+x*scale, 1530-y*scale)

def rect(bounds, fill, outline=None):
    x,y,a,b = bounds
    d.rectangle([pt(x,b),pt(a,y)], fill=fill, outline=outline, width=2)

def label(x,y,text,font=f):
    d.text(pt(x,y),text,font=font,fill='#263541',anchor='mm')

def dimension(a,b,text,offset=(0,0)):
    p,q=pt(*a),pt(*b)
    d.line([p,q],fill='#66717b',width=2)
    for x,y in (p,q):
        d.line([(x-7,y+7),(x+7,y-7)],fill='#66717b',width=2)
    d.text(((p[0]+q[0])/2+offset[0],(p[1]+q[1])/2-20+offset[1]),text,font=small,fill='#263541',anchor='mm')

d.text((90,50),'Исходный дом · размерный план',font=big,fill='#1a2d3c')
d.text((90,110),'Размеры в мм. ≈ — восстановленный размер; точность построения не равна точности обмера.',font=f,fill='#59646c')
rect([3200,-1900,5400,0],'#e3e1db','#899198')
rect([6250,10000,8450,11900],'#e3e1db','#899198')
rect([12000,-50,15000,6150],'#e3e1db','#899198')
label(13700,4000,'Терраса')
for w in spec['walls']:
    rect(w['rect_mm'],'#38444d')
wallmap={w['id']:w for w in spec['walls']}
for o in spec['openings']:
    x,y,a,b=wallmap[o['wall']]['rect_mm'];lo,hi=o['interval_mm']
    if o['axis']=='x':x,a=lo,hi
    else:y,b=lo,hi
    rect([x,y,a,b],'#faf9f6')
    if o['kind']=='window':
        d.line([pt(x,(y+b)/2),pt(a,(y+b)/2)] if o['axis']=='x' else [pt((x+a)/2,y),pt((x+a)/2,b)],fill='#528292',width=5)
    if o['kind']=='door':
        center=(y+b)/2 if o['axis']=='x' else (x+a)/2
        start,angle=door_pose(o['axis'],lo+55,hi-55,center,o['hinge'],o['swing_sign'],o['swing_deg'])
        angle=math.radians(angle)
        end=(start[0]+(hi-lo-110)*math.cos(angle),start[1]+(hi-lo-110)*math.sin(angle))
        d.line([pt(*start),pt(*end)],fill='#967b58',width=4)
for r in spec['rooms']:
    poly=r['polygon_mm'];x=sum(p[0] for p in poly)/len(poly);y=sum(p[1] for p in poly)/len(poly)
    if r['id']=='J':x,y=4220,3900
    label(x,y+160,r['id'],big)
    label(x,y-160,f"{r['area_m2']:.2f} м²",small)
for a,b,t in [((0,12500),(12000,12500),'12 000'),((-850,0),(-850,10000),'10 000'),
               ((6600,1700),(11600,1700),'5 000'),((400,8500),(6200,8500),'5 800'),
               ((12000,6900),(15000,6900),'3 000')]:
    dimension(a,b,t)
label(10100,4800,'B · кухня-зал')
label(10000,4300,'5 000 × 5 300')
label(3300,7400,'A · гараж 5 800 × 3 500')
for y,text in enumerate(['ПОДТВЕРЖДЕНО','A — гараж','B — кухня-зал; будущая антресоль','','ТРЕБУЕТ УТОЧНЕНИЯ','C–L — назначение помещений','Ширины и привязки дверей ≈ ±50','Петли и стороны открывания по PDF','','КОНТРОЛЬНЫЕ РАЗМЕРЫ','Стены: 400 / 200 / 100','Потолок: +2 700','Конёк: +5 320','Кухня: 26,50 м² по геометрии','В экспликации: 26,49 м²','','Исходный вариант: антресоли нет.']):
    d.text((1850,290+y*47),text,font=small,fill='#263541')
d.text((90,1810),'План — координатная расшифровка PDF. Все комнаты и проёмы проверены по поверхностям сохранённой 3D-модели.',font=small,fill='#59646c')
d.text((90,1850),'Крыльца и терраса здесь показаны контурами; ступени и навесы смотрите на фасадах. Площади C–L предварительные.',font=small,fill='#59646c')
d.text((90,1890),'Петли и стороны открывания сверены с PDF. Угол 30° иллюстративный; полный ход проверяется при расстановке мебели.',font=small,fill='#59646c')
im.save(ROOT/'renders/stage2/plan_dimensions.png')
print('Saved renders/stage2/plan_dimensions.png')
