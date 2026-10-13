"""Local, source-bound review sheets and HTML. No external services or assets."""
import argparse,csv,hashlib,html,json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from geometry_stage3 import inner_profile,roof_inner
ROOT=Path(__file__).resolve().parents[1]
P=argparse.ArgumentParser();P.add_argument('--revision',default='stage3_v2',choices=['stage3_v2']);P.add_argument('--schemes-only',action='store_true');A=P.parse_args()
DATA=ROOT/'data'/A.revision;OUT=ROOT/'renders'/A.revision
C=json.loads((DATA/'concepts.json').read_text());NAMES={'Original':'Исходный дом','mansard':'Ломаная мансардная','gable':'Двускатная','high_kitchen':'Высокая над гостиной'}
BG='#f7f6f2';INK='#263e49';MUTED='#617681';AMBER='#b76320';GREEN='#318971'
FONT='/System/Library/Fonts/Supplemental/Arial.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def text(d,xy,s,size=25,fill=INK,bold=False):d.text(xy,str(s),font=font(size,bold),fill=fill)
def wrap(d,xy,s,width,size=24,fill=INK):
    x,y=xy;line=''
    for word in s.split():
        trial=(line+' '+word).strip()
        if d.textlength(trial,font=font(size))>width and line:text(d,(x,y),line,size,fill);y+=size+8;line=word
        else:line=trial
    if line:text(d,(x,y),line,size,fill)
    return y+size+8

def canvas(w,h,title,subtitle):
    im=Image.new('RGB',(w,h),BG);d=ImageDraw.Draw(im);text(d,(45,28),title,38,bold=True);wrap(d,(45,80),subtitle,w-90,22,MUTED);return im,d

def plan(d,xy,l,mode='daily',upper=False,scale=.11):
    ox,oy=xy
    def pt(x,y):return (ox+x*scale,oy+(5300-y)*scale)
    def rect(r,fill,outline=None,width=2):
        a,b,c,e=r;d.rectangle([pt(a,e),pt(c,b)],fill=fill,outline=outline,width=width)
    def label(r,t):text(d,(pt(r[0],r[3])[0]+7,pt(r[0],r[3])[1]+8),t,18)
    rect([0,0,5000,5300],'white',INK,3)
    # Three unchanged doors and original terrace window.
    for a,b in [((0,2300),(0,3200)),((800,5300),(1600,5300)),((5000,225),(5000,1125))]:d.line([pt(*a),pt(*b)],fill='white',width=7)
    d.line([pt(5000,1750),pt(5000,3250)],fill='#6aafb9',width=5)
    if upper:
        rect(l['platform'],'#e8d6b6')
        for r in l['holes']:rect(r,'white','#bd8a54')
        for r in l['routes']:rect(r,'#c7e2d7')
        for b in l['beds']:rect(b['rect'],'#729395',INK);label(b['rect'],'Отдых')
    else:
        for f in l['ground'][mode]['objects']:
            r=f['rect'];rect(r,'#b4c5c1',INK)
            if f['name'] in ('Kitchen','Fridge','Sofa','Table','TV'):label(r,{'Kitchen':'Кухня','Fridge':'Хол.','Sofa':'Диван','Table':'Стол','TV':'ТВ'}[f['name']])
        for key,path in l['ground'][mode]['circulation']['paths'].items():
            if not key.endswith(':terrace'):continue
            color=GREEN if key.startswith('D06') else '#426e9b';d.line([pt(x,y) for x,y in path],fill=color,width=4)
    for s in l['stair']['steps']:rect(s['rect'],None,'#a78156',2)
    text(d,(ox,oy+5300*scale+14),'5000 × 5300 мм',20,MUTED)
    if not upper:
        text(d,(ox-38,pt(0,2900)[1]),'Д06',17,GREEN);text(d,(pt(950,5300)[0],oy-28),'Д05',17,'#426e9b')
        text(d,(ox+5000*scale+12,oy+250),'Терраса',18,MUTED)

def layouts():
    l=C['main'][0]['layout'];im,d=canvas(2050,1050,'Гостиная: обычный день и гости','Лестница у боковой стены. Цветные линии — центры свободной полосы 0,90 м к террасе от двух входов.')
    for i,(mode,title) in enumerate([('daily','Четыре места ежедневно'),('guests','Шесть мест для гостей')]):
        text(d,(80+i*690,145),title,29,bold=True);plan(d,(80+i*690,205),l,mode,scale=.105)
    text(d,(1460,145),'Что меняется для гостей',28,bold=True)
    wrap(d,(1460,205),'Стол удлиняется с 1200 до 1800 мм и смещается на 400 мм вправо и 450 мм к нижней стене плана. Диван смещается на 300 мм к этой же стене.',500,25)
    wrap(d,(1460,410),'Два складных стула хранятся под лестницей. На плане показаны занятые места со стульями, а не только столешница.',500,25)
    wrap(d,(1460,590),'Проверены проход 900 мм и боковой подход 450 мм к каждому стулу. Это предварительные габариты использования, не оценка удобства для всех пользователей.',500,23,AMBER)
    wrap(d,(80,825),'Двери в расчётном сценарии открыты на 90°. Их положение и размеры сохранены. Исходные дверные просветы уже 900 мм; проверка широкой полосы начинается внутри комнаты после двери.',1880,25,AMBER)
    wrap(d,(80,925),'Кухня: ряд 1200 мм; холодильник 700 × 700 × 1700 мм под верхним маршем. Размеры техники предварительные; конкретная модель и открывание её двери ещё не выбраны.',1880,23,MUTED)
    im.save(OUT/'01_ground_layouts.png')
    im,d=canvas(1550,1050,'Открытая чилл-зона для двоих','Главная открытая часть гостиной остаётся перед восточной стеной с окнами и террасой.')
    plan(d,(80,175),l,upper=True,scale=.13)
    text(d,(830,175),f"Площадка {l['platform_area_m2']:.2f} м²",34,bold=True)
    yy=245
    for s in ['Пол +3,10 м; низ перекрытия +2,70 м.','Две лежанки 900 × 2000 мм. Двуспальная кровать не определяет размер площадки.',f"П-образная лестница: {l['stair']['risers']} подъёмов по {l['stair']['rise']:.2f} мм; проступь {l['stair']['tread']} мм; наклон {l['stair']['slope_deg']:.1f}°.",'Ширина лестницы 900 мм; разворотная площадка длиной 900 мм. Маршрут наверху — 1000 мм.','Средина гостиной без дополнительных колонн. Опирание площадки требует конструктивного расчёта.']:
        yy=wrap(d,(830,yy),s,630,25)+20
    wrap(d,(80,935),'Оба входа находятся под антресолью. С порога видны окна и выход; высокая крыша раскрывается при продвижении к открытой части комнаты.',1370,25,AMBER)
    im.save(OUT/'02_mezzanine.png')

def roof_section(d,origin,c,garage=False):
    ox,oy=origin;scale=.053;roof=c['roof'];axis=roof['axis']
    def pt(u,z):return (ox+(u+500)*scale,oy-z*scale)
    if c['family']=='high_kitchen' and garage:profile=[[-500,4000],[10500,3550]];axis=1
    else:profile=roof['profile']
    inner=inner_profile(profile,450);d.polygon([pt(*p) for p in profile+list(reversed(inner))],fill='#485660')
    a,b=(6100,9600) if garage and axis==1 else (400,6200) if garage else (400,5700) if axis==1 else (6600,11600)
    h=2200 if garage else 2800
    for u in (a,b):
        d.rectangle([pt(u-100,h),pt(u+100,0)],fill='#c5c5ba');d.rectangle([pt(u-100,h+200),pt(u+100,h)],fill='#9d7952')
        upper=roof_inner(profile,u,450)
        if upper>h+200:d.rectangle([pt(u-100,upper),pt(u+100,h+200)],fill='#c8a67c')
    d.line([pt(a,0),pt(b,0)],fill=INK,width=3)
    if not garage:
        # Actual intersection of the platform and stair holes with this section.
        l=c['layout'];r=l['platform'];fixed=2400 if axis==1 else 3100
        start,end=(r[1]+400,r[3]+400) if axis==1 else (r[0]+6600,r[2]+6600)
        intervals=[(start,end)]
        for hole in l['holes']:
            cross0,cross1=(hole[0],hole[2]) if axis==1 else (hole[1],hole[3])
            if cross0<fixed<cross1:
                lo,hi=(hole[1]+400,hole[3]+400) if axis==1 else (hole[0]+6600,hole[2]+6600)
                intervals=[q for s,e in intervals for q in ((s,min(e,lo)),(max(s,hi),e)) if q[1]>q[0]]
        for s,e in intervals:d.rectangle([pt(s,3100),pt(e,2700)],fill='#b59065')
        u=3800 if axis==1 else 8100;x,y=pt(u,3100);top=pt(u,5000)[1]
        d.ellipse([x-7,top,x+7,top+14],outline=INK,width=2);d.line([(x,top+14),(x,y-35),(x-13,y)],fill=INK,width=3);d.line([(x,y-35),(x+13,y)],fill=INK,width=3)
        d.rectangle([pt(u-350,5150),pt(u+350,3100)],outline=GREEN,width=2)
    for z,label in [(0,'0,00'),(2200 if garage else 2800,'2,20' if garage else '2,80'),(5320,'Исх. 5,32')]:
        py=pt(0,z)[1];text(d,(ox-75,py-10),label,15,MUTED)
    label=('Гараж' if garage else 'Гостиная')+' · '+(('X = 3,30 м' if garage else 'X = 9,00 м') if axis==1 else ('Y = 7,85 м' if garage else 'Y = 3,50 м'))
    text(d,(ox,oy+20),label,22,bold=True)

def sections():
    im,d=canvas(1660,1630,'Разрезы: высота крыши и надстройки','Единый масштаб; силуэт 1,90 м, зелёный контур 2,05 м. Коричневым — предлагаемые продолжения стен.')
    for i,c in enumerate(C['main']):
        y=135+i*480;text(d,(85,y),NAMES[c['family']]+f" · конёк +{c['roof']['ridge_z']/1000:.2f} м",28,bold=True)
        roof_section(d,(100,y+390),c);roof_section(d,(900,y+390),c,True)
        text(d,(85,y+435),f"Минимальная высота маршрута: {c['roof']['minimum_clearance_mm']/1000:.3f} м. Крыша 450 мм; площадка 400 мм.",22,GREEN)
    wrap(d,(85,1570),'Высота основных стен 2,20 / 2,80 м не равна полной высоте фасада с надстройкой. Все три решения требуют её согласования.',1480,21,AMBER)
    im.save(OUT/'03_sections.png')

def overview():
    im,d=canvas(1800,1490,'Три крыши · первая редакция для выбора направления','Одинаковые ракурс, масштаб и отделка. Компоновка предварительная; изменения стен не согласованы.')
    entries=[('Original',None)]+[(c['family'],c) for c in C['main']]
    for i,(f,c) in enumerate(entries):
        x=45+(i%2)*880;y=135+(i//2)*635;text(d,(x+15,y),NAMES[f],29,bold=True)
        src=Image.open(OUT/(f+'_Terrace.png')).convert('RGB');src.thumbnail((850,520));im.paste(src,(x,y+45))
        if c:s=f"Конёк +{c['roof']['ridge_z']/1000:.2f} м · проход ≥{c['roof']['minimum_clearance_mm']/1000:.3f} м"
        else:s='Исходная крыша +5,32 м · геометрия сохранена'
        text(d,(x+15,y+575),s,23)
    wrap(d,(60,1420),'Лестница сбоку. Оба входа под антресолью. Низкий гараж и панорамные проёмы первого этажа ещё не являются принятыми решениями.',1680,23,AMBER)
    im.save(OUT/'00_roof_comparison.png')

def entry_sheet():
    im,d=canvas(1800,2120,'Что видно при входе и в открытой части гостиной','Пример двускатной крыши. Камера: 1,65 м над полом каждого уровня; объектив 28 мм. Геометрия и окна показаны без скрытия препятствий.')
    for i,(v,label) in enumerate([('D06','Вход Д06 слева'),('D05','Вход Д05 сверху плана'),('D06_After','После продвижения к открытой части'),('Upper','Вид с антресоли'),('Interior_Reverse','Обратный вид из гостиной'),('Lounge','Место отдыха на антресоли')]):
        x=45+(i%2)*880;y=135+(i//2)*640;text(d,(x+10,y),label,27,bold=True)
        src=Image.open(OUT/('gable_'+v+'.png')).convert('RGB');src.thumbnail((850,565));im.paste(src,(x,y+48))
    wrap(d,(60,2070),'Навес террасы сохранён и виден за стеклом. У входов потолок +2,70 м; панорамные проёмы до пола здесь ещё не предложены.',1680,21,AMBER)
    im.save(OUT/'04_entry_experience.png')

def report():
    validation=json.loads((DATA/'validation.json').read_text());build=json.loads((DATA/'build.json').read_text());summary=json.loads((DATA/'search_summary.json').read_text())
    lines=['Этап 3 / v2 — предварительные цельные концепции','',
           'Сделано: три крыши, исходный дом, боковая лестница, открытая антресоль и оба обеденных сценария. Оба внутренних входа равнозначны.',
           'Все три концепции условные: надстройки стен не согласованы. Входы находятся под площадкой; высокое пространство раскрывается в дальней части комнаты. Полностью высокий вход с порога пока не достигнут.',
           'В первом показе проёмы первого этажа и навес террасы сохранены. Это исходная сторона будущего сравнения с панорамными проёмами и частично крытой террасой.', '',
           'ПАРАМЕТРЫ']
    for c in C['main']:
        roof=c['roof'];lines.append(f"{NAMES[c['family']]}: конёк +{roof['ridge_z']/1000:.2f} м; проход {roof['minimum_clearance_mm']/1000:.3f} м; уклоны "+', '.join(f'{abs(v):.1f}°' for v in roof['slopes_deg']))
        sym=c['symmetric'];lines.append('  Симметричный профиль: '+(f"+{sym['ridge_z']/1000:.2f} м" if sym else 'не найден в рассмотренной сетке'))
        lines.append(f"  Снижение внутренних вершин на 300 мм: проход {c['lower_300mm']['minimum_mm']/1000:.3f} м; это расчётное сравнение, а не принятый вариант.")
        ext=[]
        for item in validation['details'][c['family']]['upper_wall_proposals']:
            idx=int(item['name'].rsplit('_',1)[-1]);part=C['walls'][idx]
            if part['height']==2200 and part['wall'] in ('west','north'):ext.append(item['extension_mm'])
        if ext:lines.append(f"  Над гаражом: дополнительная высота над мауэрлатом до {max(ext)/1000:.2f} м. Строго низкий гараж в этой геометрии не соблюдён.")
    l=C['main'][0]['layout'];lines += ['',f"Антресоль {l['platform_area_m2']:.2f} м²; пол +3,10, низ +2,70 м. Две лежанки 900 × 2000 мм.",
        f"Лестница: ширина 900 мм, {l['stair']['risers']} подъёмов по {l['stair']['rise']:.2f} мм, проступь {l['stair']['tread']} мм, угол {l['stair']['slope_deg']:.1f}°. Это крутая предварительная лестница, не выбранная пользователем окончательно.",
        'В гостевом режиме стол 1800 × 800 мм сдвигается вправо на 400 мм и вниз плана на 450 мм; диван — вниз на 300 мм. Два дополнительных складных стула хранятся под лестницей.',
        'Проверены полоса 900 мм внутри комнаты и боковой подход 450 мм к каждому занятому стулу. Широкая полоса начинается после раскрытых дверей; исходные узкие дверные просветы не расширены.',
        'Стол в обоих состояниях не перекрывает доступ к кухне, дивану, лестнице и террасе. Уборка и извлечение складных стульев не симулировались как движение человека.',
        'Кухонный ряд 1200 мм; компактный холодильник 700 × 700 × 1700 мм под верхним маршем. Проверен подход от обоих входов и запас над корпусом не менее 100 мм. Для конкретной модели ещё проверить вентиляцию и открывание двери. Холодильник 1900 мм в прежнем размещении перекрывал вид на террасу; он не принят.',
        '', 'ПРОВЕРКИ И ГРАНИЦЫ ПОИСКА',
        f"Проверено {summary['layouts']} пространственных сочетаний; {summary['spatially_passing']} прошли предварительные ограничения. Для крыш рассчитаны шесть первых компоновок после сортировки по площади и лестнице.",
        'Рассмотрены два положения площадки, обычные/компактные прямые, Г- и П-образные лестницы, три ширины боковой площадки и три положения ежедневного стола. Это конечный поиск, не доказательство глобального минимума.',
        'Крыши: оба направления конька, симметрия/асимметрия, шесть отметок карниза; для мансардной нижние скаты 45/55/65°, верхние не менее 15° как допущение. Материал кровли и допустимость уклонов для него не выбраны.',
        f"Проверок сохранённой сцены: {len(validation['checks'])}; результат: {validation['ok']}. Перепроверены исходная геометрия, проёмы, реальные поверхности проходов, переключение слоёв, крыша и толщина конструкций.",
        'Диапазоны: крыша 350–450 мм, площадка 300–400 мм, мауэрлат 150–200 мм. Снижение мауэрлата при фиксированной крыше компенсируется замыкающей надстройкой и не считается снижением фасада.',
        'Верхний маршрут 1000 мм, чистая высота 2050 мм. Лежание: 600 мм над матрасом; сидение: 1100 мм в обозначенной части лежанки. Эти антропометрические конверты предварительные.',
        'Для обеих дверей проверены лучи видимости на окно и выход с высоты 1,65 м. Это не проверка полного вида на крышу: низ площадки на порогах виден и отражён в изображениях.',
        'Опоры не добавлены в середину гостиной. Несущая способность, нормы лестниц/ограждений, теплоизоляция, снеговые нагрузки и подбор водостока не подтверждены; это архитектурная концепция.',
        '', 'ПОСЛЕ ВЫБОРА НАПРАВЛЕНИЯ',
        'Низкий / повышенный гараж; комфортная / пониженная крыша и симметрия; обычная / компактная лестница; размер площадки и впечатление на пороге; панорамные проёмы / исходные; покрытие террасы; лежанки / обычная посадка; стекло / стойки.',
        'Ни одно согласие на сравнение не считается принятием изменения стен, окон или навеса. TASKS.md и PRD.md сохранены.',
        '', 'ВОСПРОИЗВЕДЕНИЕ',
        'Python 3 + Pillow, Blender '+build['blender_version']+'. Запускать из корня перенесённого проекта:',
        'python3 -B -m unittest discover -s tests -p "test_*.py" -v',
        'python3 -B scripts/solve_stage3_v2.py --revision stage3_v2',
        '/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --offline-mode --threads 6 --python-exit-code 1 --python scripts/blender_stage3_v2.py -- build --revision stage3_v2',
        'Та же команда с verify проверяет сцену; с preview создаёт изображения. preview --pilot — дешёвые пробные виды.',
        'python3 -B scripts/report_stage3_v2.py --revision stage3_v2',
        'Файл повторно открыт и проверен фоновым Blender. Нативный интерфейс Blender в этой выдаче не проверялся.',
        'Слои 00–03: исходный дом и три крыши; 04–06: гостевой режим на шестерых. Геометрия редактируется без запуска внешних скриптов. Сборка откажется перезаписывать файл с нераспознанными ручными изменениями.'
    ]
    (DATA/'report.txt').write_text('\n'.join(lines)+'\n')
    with (DATA/'candidate_matrix.csv').open('w') as stream:
        writer=csv.writer(stream);writer.writerow(['id','position','stair_type','platform_m2','spatially_passes','issues'])
        for c in C['layouts']:writer.writerow([c['id'],c['position'],c['stair_type'],c['platform_area_m2'],c['geometric_ok'],'; '.join(c['issues'])])
    cards=[]
    for c in C['main']:
        f=c['family'];r=c['roof'];imgs=''.join(f'<figure><img loading="lazy" src="../../renders/{A.revision}/{f}_{v}.png" alt="{caption}"><figcaption>{caption}</figcaption></figure>' for v,caption in [('Garage','Со стороны гаража'),('Facade_East','Фасад со стороны террасы'),('Facade_West','Фасад со стороны гаража'),('D06','Порог Д06'),('D05','Порог Д05'),('D06_After','Открытая часть после входа Д06'),('D05_After','Открытая часть после входа Д05'),('Upper','Вид с антресоли'),('Interior_Reverse','Обратный вид из гостиной'),('Lounge','Место отдыха на антресоли')])
        cards.append(f'<article><h2>{NAMES[f]}</h2><img src="../../renders/{A.revision}/{f}_Terrace.png" alt="{NAMES[f]} со стороны террасы"><p>Конёк +{r["ridge_z"]/1000:.2f} м · проход ≥{r["minimum_clearance_mm"]/1000:.3f} м</p><p class="condition">Надстройки стен требуют согласования. Входы под антресолью.</p><details><summary>Рассмотреть фасады и интерьер</summary>{imgs}</details></article>')
    doc='''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Дом · три крыши · v2</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f7f6f2;color:#263e49;font:17px/1.55 system-ui,sans-serif}main{max-width:1500px;margin:auto;padding:32px}h1{font-size:clamp(28px,4vw,48px);line-height:1.15}h2{font-size:25px}a{color:#225f73}img{display:block;width:100%;height:auto}article{padding:22px;background:white;border-radius:12px} .cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}.condition{color:#945016}.intro{max-width:1050px}.links{display:flex;gap:22px;flex-wrap:wrap;margin:25px 0}summary{cursor:pointer;padding:12px 0;font-weight:650}figure{margin:20px 0}figcaption{color:#617681}section{margin:35px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:16px/1.6 system-ui,sans-serif;background:white;padding:25px;border-radius:12px}@media(max-width:950px){.cards{grid-template-columns:1fr}main{padding:18px}}</style><main>
    <h1>Три крыши и открытая чилл-зона</h1><p class="intro">Первый показ цельных концепций. Лестница сбоку, проход к террасе свободен от обоих входов. Стол на четверых ежедневно и на шестерых с перестановкой.</p>
    <p class="intro condition">Это предварительные предложения. Высота с порога пока ограничена антресолью; высокий объём раскрывается дальше. Все три крыши требуют надстроек над стенами. Панорамные проёмы первого этажа и изменение навеса ещё не приняты.</p>
    '''+f'<nav class="links"><a href="../../models/house_{A.revision}.blend">Модель Blender</a><a href="../../renders/{A.revision}/00_roof_comparison.png">Общее сравнение</a><a href="report.txt">Параметры и ограничения</a><a href="candidate_matrix.csv">Рассмотренные компоновки</a></nav><div class="cards">'+''.join(cards)+'</div>'
    for file,title in [('04_entry_experience.png','Вид при входе'),('01_ground_layouts.png','Четыре и шесть мест'),('02_mezzanine.png','Антресоль'),('03_sections.png','Разрезы'),('00_roof_comparison.png','Сравнение с исходным домом')]:doc+=f'<section><details><summary>{title}</summary><img loading="lazy" src="../../renders/{A.revision}/{file}" alt="{title}"></details></section>'
    doc+='<section><h2>Следующий выбор</h2><p>Выбрать одно или два направления для подробных парных сравнений. Согласование направления не означает принятия надстроек или изменения проёмов.</p></section><details><summary>Полный отчёт и проверки</summary><pre>'+html.escape('\n'.join(lines))+'</pre></details></main></html>'
    (DATA/'index.html').write_text(doc)

layouts();sections()
if not A.schemes_only:overview();entry_sheet();report()
print('Review outputs:',OUT)
