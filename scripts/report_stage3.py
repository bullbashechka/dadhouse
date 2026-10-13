"""Create source-backed concept sheets and a Russian report. Python 3 + Pillow."""
import csv
import hashlib
import html
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from geometry_stage3 import (inner_profile, roof_inner, corners, ground_furniture,
                             rectangle_clearance)

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/stage3';OUT=ROOT/'renders/stage3'
C=json.loads((DATA/'concepts.json').read_text())
TITLES={'Original':'Исходная крыша','mansard':'Ломаная мансардная','gable':'Двускатная','high_kitchen':'Высокая над гостиной'}
BG='#f7f6f2';INK='#253c46';MUTED='#62737b';ORANGE='#bc7338';GREEN='#38927b';RED='#b44f41'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf'
BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'


def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)


def text(d,xy,value,size=24,color=INK,bold=False):d.text(xy,str(value),font=font(size,bold),fill=color)


def wrap(d,xy,value,width,size=24,color=INK):
    x,y=xy;line=''
    for word in value.split():
        test=(line+' '+word).strip()
        if d.textlength(test,font=font(size))>width and line:
            text(d,(x,y),line,size,color);y+=size+8;line=word
        else:line=test
    if line:text(d,(x,y),line,size,color)
    return y+size+8


def overview():
    im=Image.new('RGB',(2400,1970),BG);d=ImageDraw.Draw(im)
    text(d,(70,45),'Этап 3 · формы крыши',48,bold=True)
    text(d,(70,110),'Одинаковый ракурс и масштаб. Альтернативы — предварительные, с условиями.',28,MUTED)
    for i,family in enumerate(TITLES):
        x=40+(i%2)*1200;y=180+(i//2)*850
        d.rounded_rectangle((x,y,x+1160,y+825),radius=20,fill='white')
        text(d,(x+25,y+20),TITLES[family],34,bold=True)
        src=Image.open(OUT/f'{family}_exterior.png').convert('RGB');src.thumbnail((1100,670))
        im.paste(src,(x+(1160-src.width)//2,y+70))
        if family=='Original':
            caption='Конёк +5,320 м · сохранённый исходный дом'
        else:
            c=next(c for c in C['main'] if c['family']==family)
            caption=f'Конёк +{c["roof"]["ridge_z"]/1000:.3f} м · проход ≥{c["minimum_clearance_mm"]/1000:.3f} м'
        text(d,(x+25,y+755),caption,27)
    text(d,(70,1900),'Коричневые верхние участки стен — предложения для отдельного согласования.',27,ORANGE)
    im.save(OUT/'00_roof_comparison.png')


def section_panel(d,box,c,garage=False):
    x0,y0,x1,y1=box
    scale=.084;origin=(x0+95,y1-90)
    def p(y,z):return (origin[0]+(y+500)*scale,origin[1]-z*scale)
    text(d,(x0+30,y0+15),'Гараж · разрез X = 3,30 м' if garage else 'Гостиная · разрез X = 10,20 м',27,bold=True)
    roof=c['roof']
    if garage and c['family']=='high_kitchen':
        prof=[(-500,4000),(10500,3550)]
    elif c['family']=='high_kitchen':
        prof=roof['profile']
        lp=[(6600,4000-7100*450/11000),(10500,3550)]
        poly=lp+list(reversed(inner_profile(lp,450)));d.polygon([p(*q) for q in poly],fill='#4c5864')
    else:prof=roof['profile']
    polygon=prof+list(reversed(inner_profile(prof,450)))
    d.polygon([p(*q) for q in polygon],fill='#4c5864')
    d.line([p(-500,0),p(10500,0)],fill=INK,width=3)
    if garage:
        for y in (5700,9600):
            d.rectangle((*p(y,2200),*p(y+400,0)),fill='#c8c7c0')
            top=2900 if y==5700 else min(roof_inner(prof,y,450),roof_inner(prof,y+400,450))
            d.rectangle((*p(y,top),*p(y+400,2400)),fill='#cfb79b')
            d.rectangle((*p(y,2400),*p(y+400,2200)),fill='#92704b')
        text(d,(x0+160,y1-220),'Основная стена: 2,20 м',24)
        text(d,(x0+160,y1-180),'Выше — мауэрлат и предлагаемая надстройка',21,ORANGE)
    else:
        layout=c['layout'];r=layout['platform']
        d.rectangle((*p(r[1],3100),*p(r[3],2700)),fill='#ad8c66')
        for s in layout['stair']['steps']:
            r=s['rect']
            if r[0]<=10200<=r[2]:
                d.rectangle((*p(r[1],s['z']),*p(r[3],s['z']-100)),fill='#ba9d7e')
        for y in (0,5700):
            d.rectangle((*p(y,2800),*p(y+400,0)),fill='#c8c7c0')
            d.rectangle((*p(y,3000),*p(y+400,2800)),fill='#92704b')
            d.polygon([p(y,3000),p(y+400,3000),p(y+400,roof_inner(prof,y+400,450)),p(y,roof_inner(prof,y,450))],fill='#cfb79b')
        # The upper clearance area is the actual section of the prescribed route.
        rr=[r for r in layout['routes'] if r[0]<=10200<=r[2]]
        for r in rr:
            d.rectangle((*p(r[1],5150),*p(r[3],3100)),outline=GREEN,width=3)
        py=4150;pz=3100
        cx,cy=p(py,pz+1740);rad=12
        d.ellipse((cx-rad,cy-rad,cx+rad,cy+rad),fill=INK)
        d.line([p(py,pz+1570),p(py,pz+750)],fill=INK,width=7)
        d.line([p(py-190,pz+80),p(py,pz+750),p(py+190,pz+80)],fill=INK,width=6)
        d.line([p(py-250,pz+950),p(py,pz+1420),p(py+250,pz+950)],fill=INK,width=5)
        text(d,(x0+110,y1-220),'Пол +3,10 · низ +2,70 м',23)
        text(d,(x0+110,y1-182),'Силуэт 1,90 м · зелёный контур 2,05 м',22,GREEN)
        label=f'Мин. по всему маршруту: {c["minimum_clearance_mm"]/1000:.3f} м'
        text(d,(x0+110,y1-144),label,23,GREEN)
    for z in (0,2200,2800,3100,5320):
        xx,yy=p(-500,z)
        d.line((xx-8,yy,xx,yy),fill=MUTED,width=2)
        text(d,(xx-78,yy-14),f'{z/1000:.2f}',18,MUTED)
    text(d,(x0+110,y1-55),'Крыша 450 мм нормально к скату; конструкции предварительные.',19,MUTED)


def sections():
    im=Image.new('RGB',(2400,2540),BG);d=ImageDraw.Draw(im)
    text(d,(60,35),'Размерные разрезы · одинаковый масштаб',42,bold=True)
    text(d,(60,100),'Высоты измеряются до нижней поверхности конструкций. Надстройки не согласованы.',25,MUTED)
    for i,c in enumerate(C['main']):
        y=160+i*780
        text(d,(60,y),f'{TITLES[c["family"]]} · конёк +{c["roof"]["ridge_z"]/1000:.3f} м',30,bold=True)
        section_panel(d,(40,y+45,1190,y+760),c)
        section_panel(d,(1210,y+45,2360,y+760),c,True)
    im.save(OUT/'01_sections.png')


def plan_panel(d,origin,layout,upper=True,scale=.17):
    x0,y0=origin
    def p(x,y):return (x0+(x-6600)*scale,y0+(5700-y)*scale)
    def rect(r,fill,outline=None,width=2):
        d.rectangle((*p(r[0],r[3]),*p(r[2],r[1])),fill=fill,outline=outline,width=width)
    rect([6600,400,11600,5700],'white',INK,5)
    if not upper:
        for a,b in [((6600,2700),(6600,3600)),((7400,5700),(8200,5700)),((11600,625),(11600,1525))]:
            d.line([p(*a),p(*b)],fill=BG,width=10)
        d.line([p(11600,2150),p(11600,3650)],fill='#5a98ad',width=7)
    if upper:
        rect(layout['platform'],'#e7d7bb')
        if layout['opening']:rect(layout['opening'],BG,RED,3)
        for r in layout['routes']:rect(r,'#c9e5db')
        for b in layout['beds']:rect(b['rect'],'#688c8c',INK)
        if layout['opening']:rect(layout['opening'],None,RED,5)
    else:
        for f in ground_furniture():rect(f['rect'],'#abc0bc',INK)
        for path in layout['ground'].get('paths',{}).values():
            if len(path)>1:d.line([p(*q) for q in path],fill=GREEN,width=4)
    for s in layout['stair']['steps']:rect(s['rect'],None,'#897255',2)
    if upper:
        r=layout['stair']['exit'];rect(r,None,GREEN,3)
        baseline=y0+5300*scale-220
        text(d,(x0+20,baseline),'Два спальных места',23)
        text(d,(x0+20,baseline+40),'Маршрут 1,00 м',22,GREEN)
        text(d,(x0+20,baseline+80),f'Площадка {layout["platform_area_m2"]:.2f} м²',23)
    else:
        for point,label in [((11000,4100),'Кухня'),((6850,1500),'Диван'),((8400,4750),'Стол')]:
            text(d,p(*point),label,20)
    text(d,(x0+315,y0+5300*scale+25),'5000 мм',23,MUTED)
    text(d,(x0-5,y0-42),'5300 мм по вертикали плана',23,MUTED)


def plans():
    im=Image.new('RGB',(2200,1320),BG);d=ImageDraw.Draw(im)
    text(d,(60,35),'Предварительная компоновка для трёх крыш',40,bold=True)
    text(d,(60,100),'Компактная П-образная лестница · 16 подъёмов по 193,75 мм · проступь 180 мм · ширина 900 мм',24,MUTED)
    layout=C['main'][0]['layout']
    text(d,(120,170),'Первый этаж',30,bold=True);text(d,(1220,170),'Антресоль +3,10 м',30,bold=True)
    plan_panel(d,(120,260),layout,False)
    plan_panel(d,(1220,260),layout,True)
    text(d,(60,1230),'Внизу проверена полоса 0,90 м; исходные узкие дверные проёмы сохранены.',24,MUTED)
    text(d,(60,1270),'Шесть мест за столом требуют отдельной проверки использования; на основном плане показаны четыре.',23,ORANGE)
    im.save(OUT/'02_layout.png')


def edge_cases():
    im=Image.new('RGB',(2400,1730),BG);d=ImageDraw.Draw(im)
    text(d,(60,35),'Компромиссы, которые влияют на выбор',43,bold=True)
    text(d,(60,100),'Проверенные примеры ограничений; это не доказательство невозможности всех других компоновок.',25,MUTED)
    for i,(stair,furniture,title) in enumerate([
        ('ordinary','loungers','Обычная лестница'),('compact','double_bed','Двуспальная кровать')]):
        x=100+i*1200;layout=next(l for l in C['layouts'] if l['id']==f'north_{stair}_{furniture}_u')
        text(d,(x,180),title,32,bold=True)
        plan_panel(d,(x,285),layout,i!=0,scale=.17)
        issue='; '.join(layout['layout_issues']) or 'Нижний маршрут к кухне/террасе не проходит при текущей расстановке.'
        wrap(d,(x,1270),issue,1020,25,RED)
    y=1430
    for c in C['main']:
        text(d,(100,y),TITLES[c['family']],26,bold=True)
        reduced=c['lower_300mm']['minimum_clearance_mm']
        text(d,(650,y),f'При снижении внутренних вершин на 300 мм: проход {reduced/1000:.3f} м',25,RED if reduced<2050 else ORANGE)
        y+=62
    text(d,(100,1640),'Для мансардной крыши более низкий вариант требует пересмотра принятого уклона верхних скатов ≥15°.',22,ORANGE)
    im.save(OUT/'03_edge_cases.png')


def profiles():
    im=Image.new('RGB',(2400,1910),BG);d=ImageDraw.Draw(im)
    text(d,(60,35),'Симметрия и снижение высоты',43,bold=True)
    text(d,(60,100),'Серый — симметричный профиль; синий — основной; оранжевый — внутренние вершины ниже на 300 мм.',24,MUTED)
    for i,c in enumerate(C['main']):
        top=175+i*545
        text(d,(70,top),TITLES[c['family']],31,bold=True)
        ox,oy=120,top+420;scale=.07
        def p(y,z):return(ox+(y+500)*scale,oy-z*scale)
        # Show the roof in its own profile coordinate, not a perspective projection.
        zero=min(z for _,z in c['roof']['profile'])-500
        def p(y,z):return(ox+(y+500)*scale,oy-(z-zero)*scale)
        if c['symmetric'] and c['symmetric']['axis']==c['roof']['axis']:
            d.line([p(*q) for q in c['symmetric']['profile']],fill='#b2b4b5',width=7)
        d.line([p(*q) for q in c['roof']['profile']],fill='#365d73',width=6)
        d.line([p(*q) for q in c['lower_300mm']['profile']],fill=ORANGE,width=4)
        x=1120
        text(d,(x,top+85),f'Основной конёк: +{c["roof"]["ridge_z"]/1000:.3f} м',28,bold=True)
        if c['symmetric']:
            text(d,(x,top+140),f'Симметричный: +{c["symmetric"]["ridge_z"]/1000:.3f} м',27,MUTED)
        reduced=c['lower_300mm']['minimum_clearance_mm']
        text(d,(x,top+195),f'Ниже на 300 мм: проход {reduced/1000:.3f} м',27,RED if reduced<2050 else ORANGE)
        msg='Высота прохода меньше 2,05 м.' if reduced<2050 else 'Проход сохраняется; меняются принятые уклоны. Это отдельное условное предложение.'
        wrap(d,(x,top+250),msg,1100,26,RED if reduced<2050 else ORANGE)
        text(d,(x,top+365),'Основные уклоны: '+', '.join(f'{abs(s):.1f}°' for s in c['roof']['slopes_deg']),25)
    text(d,(60,1840),'Минимумы относятся к заданной компоновке и рассмотренным профилям. Карнизы при снижении сохраняются.',23,MUTED)
    im.save(OUT/'04_profiles.png')


def platform_sizes():
    im=Image.new('RGB',(2400,1800),BG);d=ImageDraw.Draw(im)
    text(d,(60,35),'Два размера антресоли',43,bold=True)
    text(d,(60,100),'Одинаковые лестница, спальные места и метровый маршрут. Компактный вариант имеет сложнее форму края.',26,MUTED)
    layout=C['main'][0]['layout'];a,b,c,e=layout['platform'];front=min(bed['rect'][1] for bed in layout['beds'])
    removed=2*(front-b)*1000/1e6
    for i,label in enumerate((f'Прямоугольная · {layout["platform_area_m2"]:.2f} м²',f'С вырезанными углами · {layout["platform_area_m2"]-removed:.2f} м²')):
        x=120+i*1200;text(d,(x,180),label,31,bold=True)
        shown=dict(layout)
        if i:shown['platform_area_m2']-=removed
        plan_panel(d,(x,280),shown,True,.15)
        if i:
            def p(xx,yy):return(x+(xx-6600)*.15,280+(5700-yy)*.15)
            for r in ([a,b,a+1000,front],[c-1000,b,c,front]):
                d.rectangle((*p(r[0],r[3]),*p(r[2],r[1])),fill='white',outline=ORANGE,width=3)
        src=Image.open(OUT/('gable_compact_interior.png' if i else 'gable_interior.png')).convert('RGB')
        src.thumbnail((1060,500));im.paste(src,(x,1180))
    text(d,(60,1710),f'Снизу открывается дополнительно {removed:.2f} м². В Blender: слои 04–06. Расчёт опирания новой формы не выполнен.',26,ORANGE)
    im.save(OUT/'05_platform_sizes.png')


def report():
    validation=json.loads((DATA/'validation.json').read_text())
    rows=[]
    for r in C['candidates']:
        l=next(l for l in C['layouts'] if l['id']==r['layout_id'])
        rows.append(dict(id=r['id'],status=r['status'],ridge_mm=r['roof']['ridge_z'] if r['roof'] else '',
                         minimum_height_mm=r['minimum_clearance_mm'],platform_m2=l['platform_area_m2'],
                         stair_angle=l['stair']['slope_deg'],issues='; '.join(r['issues'])))
    with (DATA/'candidate_matrix.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['ЭТАП 3 — ТРИ АЛЬТЕРНАТИВЫ КРЫШИ','',
           'Сцена: models/house_stage3.blend',
           'Переключение: View Layer → 00_Original, 01_Mansard, 02_Gable, 03_High_Kitchen.',
           'Слои 04–06: те же крыши с площадкой 12,82 м² вместо 14,70 м²; оба спальных места и метровый маршрут сохраняются.',
           'Варианты независимы; исходная сцена, PRD.md, TASKS.md и источники сохранены.',
           '', 'РЕЗУЛЬТАТ И ГРАНИЦЫ',
           'Три геометрические концепции. Все имеют условный статус из-за предлагаемых надстроек и неподтверждённых конструкций.',
           'Основной показ: площадка вдоль верхней стены на плане, компактная П-образная лестница и две лежанки.',
           'Помещения C–L не переименованы. Перенос двери не выполнен и не использован для заявления о пригодности.',
           '48 сочетаний: три крыши × две стороны площадки × два типа лестниц × две обстановки × две формы поворота.',
           'Прямой обычный марш при рассмотренных ступенях с двумя метровыми площадками требует минимум 6000 мм; длины комнаты недостаточно.',
           'Отказы относятся к проверенным расстановкам, а не ко всем возможным решениям.',
           '', 'ОСНОВНЫЕ ВАРИАНТЫ']
    for c in C['main']:
        r=c['roof'];s=c['symmetric'];a=c['asymmetric']
        lines += [f'{TITLES[c["family"]]}: конёк +{r["ridge_z"]/1000:.3f} м; минимальный проход {c["minimum_clearance_mm"]/1000:.3f} м.',
                  '  Уклоны: '+', '.join(f'{abs(x):.2f}°' for x in r['slopes_deg']),
                  f'  Симметричный конёк: {s["ridge_z"] if s else "не найден"} мм; асимметричный: {a["ridge_z"] if a else "не найден"} мм.',
                  f'  Снижение внутренних вершин на 300 мм: минимум {c["lower_300mm"]["minimum_clearance_mm"]:.1f} мм.']
    lines += ['', 'ДОПУЩЕНИЯ И НЕОБХОДИМЫЕ РЕШЕНИЯ',
              '1. Стены: основная часть гаража 2200 мм, кухни-гостиной 2800 мм; сверху мауэрлат 200 мм. Остальные — 2900 мм.',
              '   Над ними построены коричневые замыкающие панели/надстройки до крыши. Это отдельное предложение, а не сохранение прежней полной высоты фасада.',
              '   Общие крыши требуют повышения верхнего объёма гаража. Без согласования надстроек их нельзя считать окончательно подходящими.',
              '2. Верх ворот по исходной реконструкции 2100 мм: до верха основной стены остаётся только 100 мм.',
              '   Перемычка/опорный узел не рассчитаны; локальное повышение должно быть согласовано, если расчёт его потребует.',
              '3. Пол антресоли +3100 мм. Толщина 400 мм; чистый низ +2700 мм. Балка переднего края включена в общий габарит.',
              '   Пролёт около 5 м требует расчёта. Новые колонны в гостиной не добавлялись.',
              '4. Крыша 450 мм нормально к скату. Минимум 2050 мм учитывает эту толщину, а не условную тонкую поверхность.',
              '   Площадка 300–400, крыша 350–450, мауэрлат 150–200 мм — предварительные диапазоны.',
              '   При уменьшении мауэрлата наружная крыша остаётся на месте; меняется высота замыкающей надстройки.',
              '5. Верхние скаты мансардной крыши в поиске ограничены снизу 15° как рабочее допущение, не норматив.',
              '   Поэтому вариант на 300 мм ниже может сохранять проход, но требует пересмотра уклона и покрытия.',
              '6. Основная лестница: ширина 900 мм, 16 подъёмов по 193,75 мм, проступь 180 мм, угол около 47°.',
              '   Выход на площадку 1000 мм; верхний маршрут 1000 мм. Лестница остаётся крутой.',
              '7. Внизу проверена связность коридора 900 мм с учётом ступеней и мебели; ширины исходных дверей не увеличены.',
              '   У дверей проверка 900-мм коридора начинается внутри комнаты после раскрытого полотна; просвет самих проёмов остаётся исходным.',
              '   Стол на четыре человека; раскладывание до шести проверено только на прямое пересечение с лестницей.',
              '   Полное использование шести посадочных мест остаётся условием дальнейшей компоновки.',
              '8. Обычные лестницы и кровать показаны с найденными ограничениями. Ближайший проверенный выход — компактная лестница и лежанки.',
              '   Это изменение предпочтений, а не утверждение, что обычная лестница или кровать невозможны в принципе.',
              '9. Остекление фронтона предварительное. Видимый торец антресоли частично пересекает нижнюю часть остекления.',
              '   Здесь принят вариант разделённого остекления; сохранение единого высокого окна потребует другой площадки.',
              '10. Высокая крыша соединена с односкатными низкими частями, уклон низкой части 2,34° — предварительная геометрия, материал не выбран.',
              '    Вертикальные примыкания показаны; вода низкой крыши направлена к заднему краю, высоких скатов — к соответствующим карнизам.',
              '    Показанные водостоки условные; подбор покрытия, снеговые/ветровые нагрузки и водосбор не рассчитаны.',
              '', 'ПРОВЕРКИ',
              f'Проверки сохранённой сцены: {len(validation["checks"])}; успешно: {validation["ok"]}.',
              'Геометрическая регрессия исходного варианта выполнена отдельно от исторических хешей PRD/TASKS.',
              'Их старые хеши в этапе 2 предшествуют закрытию этапа; неизменность на этапе 3 проверяется по снимку начала работы.',
              'Проверены реальные поверхности крыши, площадки, стен и проёмов, полный ход трёх дверей у гостиной в диапазонах исходных размеров.',
              'Проверены реальные поверхности вдоль нижних маршрутов, включая косоуры; исправлен найденный выход опоры в первоначальный маршрут.',
              'Над матрасом проверен габарит 600 мм для лежания и 1100 мм для сидения в выделенной зоне; эти антропометрические значения предварительные.',
              'Восемь сочетаний толщин на крышу проверены расчётно; сохранённая геометрия соответствует 450/400/200 мм.',
              'Новые меши замкнуты и имеют положительный объём. Геометрия компактных площадок проверена после повторного открытия.',
              'Искусственное опускание крыши на 100 мм обнаруживается проверкой высоты.',
              'Это архитектурная концепция. Несущая способность, нормы лестниц/ограждений и теплотехника не подтверждены.',
              '', 'ВОСПРОИЗВЕДЕНИЕ',
              'Требуются Python 3, Pillow, Blender 5.2.1. Команды из корня проекта:',
              'python3 -B -m unittest discover -s tests -p "test_*.py" -v',
              'python3 -B scripts/solve_stage3.py',
              '"/Applications/Blender.app/Contents/MacOS/Blender" --background --factory-startup --offline-mode --python-exit-code 1 --python scripts/blender_stage3.py -- build',
              'Та же команда с verify проверяет сохранённую сцену; с preview создаёт технические виды.',
              'python3 -B scripts/report_stage3.py',
              'Фоновый Blender в этой среде запускать вне sandbox: внутри наблюдался системный сбой.',
              'При несовпадении хеша существующей сцены сборка отказывается её перезаписывать.',
              'Визуальная приёмка хранится отдельно в visual_qa.json. Полный комплект этапа 4 и окончательный выбор этапа 5 не объявляются выполненными.']
    (DATA/'report.txt').write_text('\n'.join(lines)+'\n')
    images=['00_roof_comparison.png','01_sections.png','02_layout.png','03_edge_cases.png','04_profiles.png','05_platform_sizes.png']
    cards=''.join(f'<figure><a href="../../renders/stage3/{p}"><img src="../../renders/stage3/{p}"></a></figure>' for p in images)
    body=f'''<!doctype html><html lang="ru"><meta charset="utf-8"><title>Этап 3 — крыши</title>
<style>body{{background:#f7f6f2;color:#253c46;font:18px system-ui;max-width:1250px;margin:40px auto;padding:0 20px}}img{{width:100%}}figure{{margin:28px 0}}pre{{white-space:pre-wrap;line-height:1.6;font:16px system-ui}}a{{color:#287566}}</style>
<h1>Три альтернативы крыши</h1><p>Предварительные концепции с явно указанными условиями. <a href="../../models/house_stage3.blend">Сцена Blender</a> · <a href="candidate_matrix.csv">Все проверенные сочетания</a></p>
{cards}<h2>Параметры, ограничения и проверки</h2><pre>{html.escape(chr(10).join(lines))}</pre></html>'''
    (DATA/'index.html').write_text(body)


if __name__=='__main__':
    overview();sections();plans();edge_cases();profiles();platform_sizes();report()
