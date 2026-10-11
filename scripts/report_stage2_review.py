"""Russian review sheets and an evidence-bound text report. Requires Pillow."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from review_geometry import polygon_at, sweep

ROOT=Path(__file__).resolve().parents[1]
INK='#243744'
MUTED='#596a72'
AMBER='#a35d08'
RED='#ad352b'
GREEN='#277459'
PAPER='#faf9f5'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'


def font(size):
    return ImageFont.truetype(FONT,size)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(spec,review,destination,doors=False):
    im=Image.new('RGB',(2400,2100),PAPER)
    d=ImageDraw.Draw(im)
    scale=.112
    def pt(x,y):
        return 170+x*scale,1660-y*scale
    def polygon(points,fill,outline=None,width=2):
        points=[pt(*p) for p in points]
        d.polygon(points,fill=fill)
        if outline:
            d.line(points+[points[0]],fill=outline,width=width)
    def rect(b,fill):
        x,y,a,c=b
        polygon([(x,y),(a,y),(a,c),(x,c)],fill)
    def text(x,y,t,size=21,color=INK,anchor='mm'):
        d.text(pt(x,y),t,font=font(size),fill=color,anchor=anchor)
    def dimension(a,b,t):
        p,q=pt(*a),pt(*b)
        d.line([p,q],fill=MUTED,width=2)
        for x,y in (p,q):
            d.line([(x-6,y+6),(x+6,y-6)],fill=MUTED,width=2)
        d.text(((p[0]+q[0])/2,(p[1]+q[1])/2-22),t,font=font(25),fill=INK,anchor='mm')
    title='Двери · полный ход и свободный просвет' if doors else 'Базовый дом · проверенные размеры'
    d.text((75,50),title,font=font(44),fill=INK)
    d.text((75,112),'Размеры в мм · оранжевый и ≈ — предварительно · ±50 — согласованный диапазон',font=font(25),fill=MUTED)
    for b in [[3200,-1900,5400,0],[6250,10000,8450,11900],[12000,-50,15000,6150],[-3000,6350,0,9350]]:
        # Ramp is shown by a note on this sheet; its full footprint is on façades.
        if b[0]<0:
            continue
        rect(b,'#e7e4db')
    wallmap={w['id']:w for w in spec['walls']}
    for w in spec['walls']:
        rect(w['rect_mm'],'#34454e')
    for o in spec['openings']:
        x,y,a,b=wallmap[o['wall']]['rect_mm']
        lo,hi=o['interval_mm']
        if o['axis']=='x':
            x,a=lo,hi
        else:
            y,b=lo,hi
        rect([x,y,a,b],PAPER)
        if o['kind']=='window':
            line=[pt(x,(y+b)/2),pt(a,(y+b)/2)] if o['axis']=='x' else [pt((x+a)/2,y),pt((x+a)/2,b)]
            d.line(line,fill='#4e8595',width=6)
    if doors:
        for r in review['doors']:
            for piece in sweep(r['model']):
                polygon(piece['polygon'],'#dcebdc')
            polygon(polygon_at(r['model'],90),'#546f52')
    else:
        for r in review['doors']:
            polygon(polygon_at(r['model'],30),'#a68c62')
    for room in spec['rooms']:
        poly=room['polygon_mm']
        x=sum(p[0] for p in poly)/len(poly)
        y=sum(p[1] for p in poly)/len(poly)
        if room['id']=='J':
            x,y=4250,3550
        if doors:
            x=min(p[0] for p in poly)+220
            y=max(p[1] for p in poly)-230
            text(x,y,room['id'],27,MUTED)
        else:
            text(x,y+290,room['id'],32)
            if len(poly)==4:
                width=max(p[0] for p in poly)-min(p[0] for p in poly)
                depth=max(p[1] for p in poly)-min(p[1] for p in poly)
                text(x,y,f'{width} × {depth}',20)
            text(x,y-260,f"{room['area_m2']:.2f} м²",20,MUTED)
    dimension((0,12850),(12000,12850),'12 000')
    dimension((-850,0),(-850,10000),'10 000')
    dimension((12000,6800),(15000,6800),'3 000')
    text(13700,4600,'Терраса',25)
    text(13700,4200,'3000 × 6200',21)
    labels={
        'door_north':(7400,10800),'door_south':(4400,-1000),'door_terrace':(13500,950),
        'door_garage':(4300,6800),'door_kitchen_north':(8100,4850),'door_kitchen_west':(7900,2950),
        'door_bedroom':(2400,3150),'door_mid_left':(1850,4700),'door_small':(5600,4800),
        'door_lower_w':(3850,1400),'door_lower_e':(5850,1400),'door_upper_m':(7800,8050),
        'door_upper_e':(10500,8050),'door_upper_link':(7900,6600)}
    omap={o['id']:o for o in spec['openings']}
    for r in review['doors']:
        o=omap[r['id']]
        w=wallmap[o['wall']]['rect_mm']
        mid=sum(o['interval_mm'])/2
        target=(mid,(w[1]+w[3])/2) if o['axis']=='x' else ((w[0]+w[2])/2,mid)
        x,y=labels[r['id']]
        if doors:
            px,py=pt(x,y)
            d.line([pt(*target),(px,py)],fill=AMBER,width=1)
            d.rounded_rectangle((px-99,py-42,px+99,py+44),radius=6,fill=PAPER,outline='#d8c8af')
            size=18
            t=(f"{r['label']} · ≈{r['opening_width_mm']} ±50" if o['width_status']!='dimensioned' else
               f"{r['label']} · {r['opening_width_mm']}")
            d.text((px,py-21),t,font=font(size),fill=AMBER if o['width_status']!='dimensioned' else INK,anchor='mm')
            d.text((px,py+2),f"{o['axis']}≈{r['position_mm']} ±50",font=font(size),fill=AMBER,anchor='mm')
            d.text((px,py+25),f"Просвет ≈{round(r['clear_width_at_90_mm'])}",font=font(size),fill=AMBER,anchor='mm')
        else:
            text(*target,r['label'],18,AMBER)
    if not doors:
        # Window widths are printed; positions are reconstructed.
        annotations=[('window_n1',2000,10600),('window_n2',4500,10600),
                     ('window_w',-650,2850),('window_e',13700,3200),('garage_gate',1900,7800)]
        for key,x,y in annotations:
            o=omap[key]
            text(x,y,str(o['interval_mm'][1]-o['interval_mm'][0]),23)
            text(x,y-280,f"{o['axis']}≈{o['interval_mm'][0]} ±50",17,AMBER)
    sidebar_x=1910
    conflicts=review['nominal_conflicts']+review['uncertain_doors']+review['pair_conflicts']
    status='Столкновения не найдены' if not conflicts else 'Ограничения: см. отчёт'
    entries=(['ПРОВЕРКА ДВЕРЕЙ','14 дверей · 0–90°','91 пара · разные углы',status,'','СВЕТЛО-ЗЕЛЁНЫЙ','Полная зона движения','','ПРОСВЕТ ПРИ 90°','Номинально: 550–750 мм','С диапазонами: 500–800 мм','','УСЛОВНЫЕ РАЗМЕРЫ','Коробка: 50 мм','Монтажный зазор: 5 мм','Полотно: 40 мм','Зазор у притвора: 3 мм','','x / y: нижняя привязка','от левого нижнего угла.','Петли и стороны — по PDF.','','Ручки и мебель не заданы.'] if doors else
                 ['ПРОВЕРЕНО ПО ГЕОМЕТРИИ','Контур: 12 000 × 10 000','A · гараж: 5800 × 3500','B · кухня: 5000 × 5300','Стены: 400 / 200 / 100','','Крыша: конёк +5,320 м','Скаты: 20° / 28°','Потолок: +2,700 м','','ДВЕРИ Д01–Д14','Подробные ширины,','привязки и движение —','на листе «Двери».','','ПРЕДВАРИТЕЛЬНО','Ступени: 145 × 300','Пандус: ≈3000 × 3000','Подъём пандуса: 600','','C–L остаются буквами.','Их геометрия проверена.','Назначения отложены.'])
    for i,t in enumerate(entries):
        d.text((sidebar_x,280+i*49),t,font=font(22),fill=INK if t.isupper() else MUTED)
    d.line([(75,1920),(2325,1920)],fill='#d6d5cd',width=2)
    notes=(['Открывание проверено на геометрии сохранённой ревизии, включая диапазоны ширин и привязок.',
            'Просвет учитывает коробку и полотно. Отсутствие столкновения не означает удобства прохода с мебелью или вещами.',
            'Д08, Д09 и Д11: номинальный просвет ≈550 мм; на нижней границе размеров ≈500 мм.'] if doors else
           ['Линейные размеры имеют приоритет. Кухня: 26,50 м² по геометрии; в экспликации 26,49 м².',
            'Крыльца и терраса показаны контурами; ступени, навесы и пандус смотрите на фасадах.',
            'Исходный дом с потолком. Антресоль и альтернативные крыши в эту ревизию не входят.'])
    for i,t in enumerate(notes):
        d.text((75,1950+i*43),t,font=font(22),fill=AMBER if doors and i==2 else MUTED)
    im.save(destination)


def sheets(render_dir):
    titles={'01_original_exterior':'Исходный дом · общий вид','02_original_room_with_ceiling':'Кухня-гостиная · исходный потолок +2,700 м',
            '03_diagnostic_cutaway':'Диагностический вид · крыша и потолок скрыты',
            'facade_south':'Южный фасад','facade_north':'Северный фасад',
            'facade_east':'Восточный фасад · терраса','facade_west':'Западный фасад · гараж',
            'section_kitchen':'Разрез через кухню-гостиную','section_garage':'Разрез через гараж'}
    for key,title in titles.items():
        raw=Image.open(render_dir/'raw'/(key+'.png')).convert('RGB')
        canvas=Image.new('RGB',(2400,raw.height+310),PAPER)
        canvas.paste(raw,(0,110))
        d=ImageDraw.Draw(canvas)
        d.text((65,30),title,font=font(39),fill=INK)
        d.text((65,raw.height+135),'Оранжевый и ≈ — предварительная реконструкция; подписанные отметки сохранены по PDF.',font=font(23),fill=MUTED)
        notes=[]
        if key.startswith('section_'):
            def p(y,z):
                return 1200+(y-5)*2400/14,110+raw.height/2-(z-2.1)*2400/14
            roof_point=p(1.7,5.32-(5.9-1.7)*math.tan(math.radians(20))-.06)
            anchor=(330,310)
            d.line([anchor,roof_point],fill=AMBER,width=3)
            d.rounded_rectangle((70,228,710,306),radius=8,fill=PAPER,outline='#dcccb5')
            d.text((95,240),'≈120 мм · оболочка исходной крыши',font=font(25),fill=AMBER)
            d.text((95,274),'Толщина по вертикали, предварительно',font=font(22),fill=AMBER)
            floor=p(6,-.1)
            d.line([(floor[0]-120,floor[1]+135),floor],fill=AMBER,width=3)
            d.text((floor[0]-120,floor[1]+155),'≈200 мм · плита пола',font=font(24),fill=AMBER,anchor='mm')
            notes=['Фермы ≈100 × 150 мм: условная схема по разрезам; шаг и несущая способность не определены.',
                   'Толщина 350–450 мм из подготовки относится к будущим альтернативам, а не к этой оболочке.']
        elif key=='facade_west':
            gate=(1200-(7.85-5)*2400/17,110+raw.height/2-(2.1-2.4)*2400/17)
            d.line([(300,350),gate],fill=AMBER,width=3)
            d.text((75,305),'Верх ворот ≈+2,100 м',font=font(27),fill=AMBER)
            notes=['Высота ворот восстановлена по совмещению на фасаде; отдельный размер отсутствует.',
                   'Пандус: длина ≈3000 мм, ширина 3000 мм, подъём 600 мм; длина и конструкция предварительные.']
        elif key=='facade_east':
            point=(1200+(3.4-5)*2400/17,110+raw.height/2-(3.6-2.4)*2400/17)
            d.line([(370,260),point],fill=AMBER,width=3)
            d.text((65,215),'Верхнее окно: ширина ≈4200 мм',font=font(26),fill=AMBER)
            notes=['Верхнее окно: низ +3,130 м, верх +3,980 м; горизонтальная форма и привязки предварительные.',
                   'Навес ≈80 мм; ступени 4 × 145 мм, проступь ≈300 мм; ограждения упрощены.']
        elif key.startswith('facade_'):
            notes=['Ступени: 4 подъёма по ≈145 мм, проступь ≈300 мм; навесы ≈80 мм — предварительно.',
                   'Площадка −0,020 м; земля −0,600 м. Пандус гаража реконструирован с длиной ≈3000 мм.']
        elif key=='03_diagnostic_cutaway':
            notes=['Этот вид раскрывает планировку. В исходном доме потолок и крыша сохранены.',
                   'C–L: только буквенные обозначения; назначения отложены, геометрия проверена.']
        elif key=='02_original_room_with_ceiling':
            notes=['Кухня-гостиная: 5000 × 5300 мм. Исходный потолок +2,700 м, без антресоли.',
                   'Коробки ≈50 мм, полотна ≈40 мм, рамы ≈60 мм. На общем виде двери приоткрыты на 30°.']
        else:
            notes=['Сдержанная детализация: профили рам, ограждения, ступени и пандус имеют предварительное исполнение.',
                   'Конёк +5,320 м; исходная планировка сохранена. Полный ход дверей показан на отдельной схеме.']
        for i,t in enumerate(notes):
            d.text((65,raw.height+185+i*43),t,font=font(23),fill=AMBER if '≈' in t else MUTED)
        canvas.save(render_dir/(key+'.png'))


def report(scene,out,render_dir):
    validation=json.loads((out/'stage2_validation.json').read_text())
    doors=json.loads((out/'door_review.json').read_text())
    manifest=json.loads((out/'manifest.json').read_text())
    if not validation['ok'] or not doors['door_review_complete']:
        raise RuntimeError('Geometry or door review is incomplete')
    if any(r['scene_sha256']!=sha(scene) for r in (doors,manifest,validation)):
        raise RuntimeError('Reports refer to different scenes')
    render_manifest=json.loads((render_dir/'raw/render_manifest.json').read_text())
    if render_manifest['scene_sha256']!=sha(scene) or any(sha(render_dir/'raw'/name)!=h for name,h in render_manifest['images'].items()):
        raise RuntimeError('Render images do not match the saved revision')
    spec=json.loads((ROOT/'data/house_stage2_geometry.json').read_text())
    plan(spec,doors,render_dir/'plan_dimensions.png')
    plan(spec,doors,render_dir/'door_sweeps.png',True)
    sheets(render_dir)
    negatives=json.loads((out/'stage2_negative_tests.json').read_text())
    checked=len(validation['checks'])+len(validation['review_checks'])
    lines=['ЭТАП 2 — РЕВИЗИЯ ДЛЯ ПРИЁМКИ ГЕОМЕТРИИ',
        '', 'Модель: '+str(scene), 'Изображения: '+str(render_dir),
        '', 'РЕЗУЛЬТАТ',
        f'{checked} геометрических проверок пройдено. Проверены реальные поверхности сохранённой сцены.',
        '14 дверей проверены на всём ходе 0–90°, 91 пара — при независимых углах.',
        ('Столкновений не обнаружено при номинальных размерах и в согласованных диапазонах ширин/привязок.'
         if not (doors['nominal_conflicts'] or doors['uncertain_doors'] or doors['pair_conflicts']) else
         'Обнаружены ограничения: '+json.dumps({k:doors[k] for k in ('nominal_conflicts','uncertain_doors','pair_conflicts')},ensure_ascii=False)),
        'Приёмка геометрии выполняется отдельно. Назначения C–L отложены; полный этап не объявлен завершённым.',
        '', 'ИЗМЕНЕНИЯ',
        'Уточнена условная ось петель и добавлен зазор полотна у притвора 3 мм; проёмы не переносились.',
        'Верхнее окно выключается с исходной крышей; навесы принадлежат базовому дому.',
        'Восстановлен пандус гаража по фасаду: длина ≈3000 мм, ширина 3000 мм, подъём 600 мм.',
        'Размеры-допущения обозначены на планах и разрезах. Исходная модель, PRD, TASKS и источники сохранены.',
        '', 'ПРОХОДЫ ПРИ 90° — мм',
        'Дверь | Проём | Между коробками | Свободный просвет | Диапазон просвета']
    for row in doors['doors']:
        low,high=row['clear_width_range_at_90_mm']
        lines.append(f"{row['label']} | {row['opening_width_mm']} | {row['frame_clear_mm']:.0f} | {row['clear_width_at_90_mm']:.0f} | {low}–{high}")
    lines+=['', 'ГРАНИЦЫ ПРОВЕРКИ',
        'Принятые коробки 50 мм, монтажные зазоры 5 мм, полотна 40 мм, притвор 3 мм предварительны.',
        'Д08, Д09 и Д11 дают около 550 мм свободного просвета; в диапазоне размеров — 500–600 мм.',
        'Ручки, мебель, лестница и маршруты с крупными предметами проверяются на следующих этапах.',
        'Движение ворот не оценивалось: механизм не задан. Их проём и восстановленная высота проверены.',
        'Крыша 120 мм по вертикали, сечения схемы ферм и пандус предварительные; расчёт несущих конструкций не выполнялся.',
        'Проверка движения использует поверхности реальных мешей, отсечённые по высоте полотна, и проверку вложения в объём.',
        'Круговые дуги огибаются касательными с ошибкой <=0,25 мм. Уточнение угла столкновения <=0,5 мм по концу полотна.',
        'Диапазоны ширины и привязки проверены консервативными непрерывными оболочками; граничные и номинальные сценарии сохранены.',
        'Прочие стыки и пересечения проверены геометрически и визуально; это не инженерная проверка всех конструктивных узлов.',
        '', 'ВОСПРОИЗВЕДЕНИЕ',
        'Требуются Blender 5.2.1, Python 3.12 и Pillow. Дополнительные пакеты геометрии не требуются.',
        'Все команды выполняются из корня проекта. Фоновый Blender в этой среде требует запуска вне sandbox из-за сбоя Metal.',
        "python3 -m unittest discover -s tests -p 'test_*.py' -v",
        'Для нового экземпляра выбрать незанятые пути сцены и каталогов. prepare сохраняет исходную модель.']
    common=' --scene models/house_stage2_review.blend --output-dir data/stage2_review --render-dir renders/stage2_review'
    prefix='"/Applications/Blender.app/Contents/MacOS/Blender" --background --factory-startup --offline-mode --python-exit-code 1 --python scripts/blender_stage2_review.py -- '
    for action in ('prepare','finish_geometry','verify','test','preview'):
        lines.append(prefix+action+common)
    lines+=['python3 scripts/review_doors.py --scene models/house_stage2_review.blend --output-dir data/stage2_review',
        'python3 scripts/report_stage2_review.py'+common,
        '', 'Свидетельства: manifest.json, stage2_validation.json, geometry_snapshot.json, door_review.json, stage2_negative_tests.json.',
        'Визуальная приёмка отражается отдельно в visual_qa.json; автоматические проверки её не заменяют.']
    (out/'review_report.txt').write_text('\n'.join(lines)+'\n')
    index=dict(scene_path=str(scene),scene_sha256=sha(scene),geometry_verified=validation['ok'],
        door_review_complete=doors['door_review_complete'],naming_deferred=True,stage_complete=False,
        checks=checked,negative_scenarios_passed=negatives['ok'],
        images={p.name:sha(p) for p in render_dir.glob('*.png')})
    qa_path=out/'visual_qa.json'
    qa=json.loads(qa_path.read_text()) if qa_path.exists() else {}
    index['visual_verified']=bool(qa.get('ok') and qa.get('scene_sha256')==index['scene_sha256']
        and qa.get('images')==index['images'])
    unit_path=out/'unit_tests.json'
    index['unit_tests']=json.loads(unit_path.read_text()) if unit_path.exists() else {'ok':False}
    index['protected_sources_unchanged']=all(sha(ROOT/name)==digest
        for name,digest in manifest['protected_sha256'].items())
    index['geometry_ready_for_review']=all((index['geometry_verified'],index['door_review_complete'],
        index['visual_verified'],index['unit_tests']['ok'],index['negative_scenarios_passed'],
        index['protected_sources_unchanged']))
    with (out/'review_report.txt').open('a') as handle:
        handle.write('\nИТОГОВАЯ ПРОВЕРКА\n')
        handle.write(f"Автоматические тесты: {index['unit_tests'].get('tests_run',0)}, успешно: {index['unit_tests']['ok']}.\n")
        handle.write(f"Ручная визуальная проверка текущих изображений: {index['visual_verified']}.\n")
        handle.write(f"Геометрия готова к рассмотрению: {index['geometry_ready_for_review']}.\n")
    (out/'delivery.json').write_text(json.dumps(index,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--render-dir',type=Path,required=True)
    args=parser.parse_args()
    report(args.scene.resolve(),args.output_dir.resolve(),args.render_dir.resolve())
