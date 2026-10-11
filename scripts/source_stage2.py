"""Coordinate transcription from PDF vectors; run with system Python + Pillow.

Vector page bounds: (246.60,216.14)-(586.74,499.58) pt.
Separate X/Y calibration to the printed 12000 x 10000 mm footprint.
Printed lengths take precedence over ~2-mm PDF vector quantisation.
Unlabelled jambs rounded to 10 mm and retain a ±50-mm scenario envelope.
"""
import json
from pathlib import Path
from stage1 import sha256

ROOT = Path(__file__).resolve().parents[1]


def specification():
    walls = [('south',0,0,12000,400), ('north',0,9600,12000,10000),
             ('west',0,400,400,9600), ('east',11600,400,12000,9600),
             ('spine',6200,400,6600,9600), ('cross',400,5700,11600,6100),
             ('west_partition',3500,400,3700,5700),
             ('west_mid',400,4000,3500,4200),
             ('south_cells',3700,2300,6200,2500),
             ('south_divider',4900,400,5000,2300),
             ('small_west',4800,4000,5000,5700),
             ('small_south',4800,4000,6200,4200),
             ('north_divider',9100,6100,9300,9600),
             ('north_mid',6600,7300,9100,7400),
             ('north_east',9300,7200,11600,7400)]
    # axis is the long axis of the opening, across the corresponding wall.
    openings = [
        ('window_n1','north','x',1300,2700,900,2100,False,1),
        ('window_n2','north','x',3900,5300,900,2100,False,1),
        ('door_north','north','x',6900,7800,0,2100,True,1),
        ('door_south','south','x',3860,4760,0,2100,True,-1),
        ('window_w','west','y',1900,3100,900,2100,False,1),
        ('garage_gate','west','y',6350,9350,0,2100,False,-1),
        ('window_e','east','y',2150,3650,900,2100,False,1),
        ('door_terrace','east','y',625,1525,0,2100,True,1),
        ('door_garage','cross','x',3800,4700,0,2100,True,-1),
        ('door_kitchen_north','cross','x',7400,8200,0,2100,True,-1),
        ('door_kitchen_west','spine','y',2700,3600,0,2100,True,-1),
        ('door_bedroom','west_partition','y',3000,3800,0,2100,True,-1),
        ('door_mid_left','west_mid','x',2400,3100,0,2100,True,-1),
        ('door_small','small_south','x',5400,6100,0,2100,True,-1),
        ('door_lower_w','south_cells','x',3910,4710,0,2100,True,1),
        ('door_lower_e','south_cells','x',5200,5900,0,2100,True,1),
        ('door_upper_m','north_mid','x',8100,8900,0,2100,True,1),
        ('door_upper_e','north_east','x',9400,10200,0,2100,True,-1),
        ('door_upper_link','north_divider','y',6250,7050,0,2100,True,1)]
    room_data = [
        ('A','Гараж',3,[400,6100,6200,9600]),
        ('B','Кухня-гостиная',7,[6600,400,11600,5700]),
        ('C',None,None,[400,400,3500,4000]),
        ('D',None,None,[400,4200,3500,5700]),
        ('E',None,None,[5000,4200,6200,5700]),
        ('F',None,None,[3700,400,4900,2300]),
        ('G',None,None,[5000,400,6200,2300]),
        ('H',None,None,[6600,7400,9100,9600]),
        ('I',None,None,[9300,7400,11600,9600]),
        ('J',None,None,None),
        ('K',None,None,[6600,6100,9100,7300]),
        ('L',None,None,[9300,6100,11600,7200])]
    rooms=[]
    for key,name,rid,b in room_data:
        poly = ([[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]]] if b else
                [[3700,2500],[6200,2500],[6200,4000],[4800,4000],[4800,5700],[3700,5700]])
        area=abs(sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(poly,poly[1:]+poly[:1])))/2e6
        rooms.append(dict(id=key,name=name,explication_id=rid,polygon_mm=poly,area_m2=area,
                          naming_status='user_confirmed' if key in ('A','B') else 'unresolved'))
    ws=[dict(id=n,rect_mm=[a,b,c,d],z_mm=[0,2900],source_page=2) for n,a,b,c,d in walls]
    ops=[]
    for key,wall,axis,a,b,bot,top,door,sgn in openings:
        printed=key.startswith('window') or key in ('garage_gate','door_terrace')
        ops.append(dict(id=key,wall=wall,axis=axis,interval_mm=[a,b],z_mm=[bot,top],
                        kind='door' if door else 'gate' if key=='garage_gate' else 'window',
                        width_status='dimensioned' if printed else 'reconstructed',
                        position_status='reconstructed_from_pdf_vectors',
                        width_range_mm=[b-a,b-a] if printed else [b-a-50,b-a+50],
                        position_range_mm=[a-50,a+50],hinge='low',swing_sign=sgn,
                        swing_deg=30, swing_status='schematic; side from plan, angle illustrative',
                        source_page=2,height_status='reconstructed_from_facade_alignment' if key=='garage_gate' else 'dimensioned'))
    poses={'door_north':('high',-1),'door_south':('high',1),'door_terrace':('low',-1),
           'door_kitchen_west':('high',1),'door_bedroom':('high',1),'door_mid_left':('high',1),
           'door_lower_w':('high',1),'door_upper_m':('high',-1),'door_upper_e':('high',1)}
    for opening in ops:
        if opening['id'] in poses:
            opening['hinge'],opening['swing_sign']=poses[opening['id']]
        if opening['kind']=='door':
            opening['swing_status']='hinge and opening side visually transcribed from PDF page 2; 30-degree display angle illustrative'
    return dict(schema_version=1,linear_unit='mm',stage=2,
                authorization='User: реализуй план, following approved stage 2 plan',
                stage1_spec_sha256=sha256(ROOT/'data/house_spec.json'),
                sources=[dict(path=p.name,sha256=sha256(p)) for p in [ROOT/'PRD.md',ROOT/'TASKS.md',*ROOT.glob('*.pdf')]],
                coordinates=dict(origin='southwest outside corner',x='right on PDF',y='up on PDF',z='up'),
                extraction=dict(method='PDF vector paths via pdftocairo; independent X/Y calibration',
                                page_bounds_pt=[246.60,216.14,586.74,499.58],
                                calibration_mm=[12000,10000],unsigned_snap_mm=10),
                walls=ws,openings=ops,rooms=rooms,
                roof=dict(ridge_y_mm=5900,ridge_z_mm=5320,slope_south_deg=20,slope_north_deg=28,
                          x_mm=[-500,12500],y_mm=[-500,10500],thickness_mm=120,
                          thickness_status='reconstructed visual envelope from PDF section, not structural design',
                          inner_ridge_node_z_mm=4770),
                assumptions=[
                    'Плита пола 200 мм вниз от Z=0; конструктивный состав не задан.',
                    'Потолочное перекрытие: низ +2700, верх +2900 по разрезам; разделено со стенами без наложения.',
                    'Оболочка исходной кровли 120 мм вертикально по масштабу разреза; фермы показаны отдельно. 350–450 мм из этапа 1 относятся к будущей проверке альтернатив.',
                    'Сечение показанных элементов стропильной схемы 100 × 150 мм, условно; шаг конструкций на PDF не задан, показаны две схемы по разрезам.',
                    'Дверная коробка 50 мм, глубина 100 мм, полотно 40 мм, монтажные зазоры 5 мм; предварительно.',
                    'Условные оконные рамы 60 мм, глубина 80 мм; без спецификации производителя.',
                    'Ворота: верх +2100 восстановлен по совмещению с верхом окна фасада, не отдельный подписанный размер.',
                    'Площадки крылец и террасы −20 мм; для террасы отметка принята по фасаду. Земля −600 мм.',
                    'Четыре подъёма наружных ступеней по 145 мм до −20; глубина проступи 300 мм. Количество и размеры не подписаны.',
                    'Навесы: наружные габариты по плану и фасадам, панели 80 мм; подписи +2200/+2400/+2600 относятся к разным примыканиям.',
                    'Неподписанные ширины дверей повторно сняты с векторов PDF; сценарий ±50 мм сохранён. Это не точность строительного обмера.',
                    'В малых помещениях есть расхождения площадей с экспликацией; названия D–L требуют подтверждения.',
                    'Терраса вылет 3000, длина 6200; северный край Y=6150 по цепочке 3850, южный край Y=−50. Расхождение 50 мм с углом дома не сглажено.',
                ])


def diagram(spec):
    from PIL import Image, ImageDraw, ImageFont
    from geometry_stage2 import boundary_mesh
    out=ROOT/'renders/stage2'
    out.mkdir(parents=True,exist_ok=True)
    im=Image.new('RGB',(1500,1400),'#f7f5f0'); d=ImageDraw.Draw(im)
    font='/System/Library/Fonts/Supplemental/Arial.ttf'
    f=ImageFont.truetype(font,25); big=ImageFont.truetype(font,38); small=ImageFont.truetype(font,20)
    scale=.082
    def p(x,y): return (90+x*scale,1080-y*scale)
    d.text((80,35),'Назначения помещений — схема для уточнения',font=big,fill='#202833')
    d.text((80,90),'Буквы — метки этой схемы. Площади рассчитаны по размерным линиям.',font=small,fill='#555d66')
    for w in spec['walls']:
        a,b,c,e=w['rect_mm']; d.rectangle([p(a,e),p(c,b)],fill='#35414b')
    wallmap={w['id']:w for w in spec['walls']}
    for o in spec['openings']:
        a,b,c,e=wallmap[o['wall']]['rect_mm'];lo,hi=o['interval_mm']
        if o['axis']=='x':a,c=lo,hi
        else:b,e=lo,hi
        d.rectangle([p(a,e),p(c,b)],fill='#f7f5f0')
        if o['kind']=='window':
            pts=[p(a,(b+e)/2),p(c,(b+e)/2)] if o['axis']=='x' else [p((a+c)/2,b),p((a+c)/2,e)]
            d.line(pts,fill='#53849b',width=4)
    for r in spec['rooms']:
        poly=r['polygon_mm'];x=sum(p[0] for p in poly)/len(poly);y=sum(p[1] for p in poly)/len(poly)
        if r['id']=='J':x,y=4240,3850
        label=r['id'];xx,yy=p(x,y)
        d.text((xx-12,yy-25),label,font=big,fill='#162b3b')
        d.text((xx-35,yy+18),f"{r['area_m2']:.2f} м²",font=small,fill='#555d66')
    d.text((1120,240),'A — гараж\nB — кухня-зал\n     будущая антресоль\nC — __________\nD — __________\nE — __________\nF — __________\nG — __________\nH — __________\nI — __________\nJ — __________\nK — __________\nL — __________',font=small,fill='#263541',spacing=20)
    d.text((80,1150),'Просьба подписать буквы C–L. A и B уже подтверждены; нужно найти в том числе котельную.',font=small,fill='#555d66')
    d.text((80,1190),'Не все площади совпадают с экспликацией. Возможно, таблица относится к другой редакции плана.',font=small,fill='#555d66')
    d.text((80,1230),'Размеры стен и проёмов сохраняются по чертежу; названия не меняют их геометрию.',font=small,fill='#555d66')
    im.save(out/'room_mapping_question.png')


if __name__=='__main__':
    spec=specification()
    target=ROOT/'data/house_stage2_geometry.json'
    if target.exists():
        raise SystemExit('Preserve existing transcription/user room mapping; do not overwrite')
    target.write_text(json.dumps(spec,ensure_ascii=False,indent=2)+'\n')
    diagram(spec)
