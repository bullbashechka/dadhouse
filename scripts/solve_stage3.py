"""Reproducible finite concept search; no claim of exhaustive architectural optimisation."""
import hashlib
import itertools
import json
from pathlib import Path
from geometry_stage3 import *

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'data/stage3'


def dump(name, value):
    (OUT/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    protected = [ROOT/'PRD.md', ROOT/'TASKS.md', ROOT/'models/house_stage2_review.blend',
                 ROOT/'data/house_spec.json', ROOT/'data/house_stage2_geometry.json',
                 *ROOT.glob('*.pdf'), *ROOT.glob('*.png'), *ROOT.glob('WhatsApp*.txt')]
    if not (OUT/'protected.json').exists():
        dump('protected.json', {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})
    layouts=[]
    for position, stair, furniture, shape in itertools.product(('north','west'),('ordinary','compact'),('loungers','double_bed'),('u','l')):
        layout=make_layout(position,stair,furniture,shape)
        layout['id']=f'{position}_{stair}_{furniture}_{shape}'
        layout['ground']=ground_check(layout)
        layout['ok']=not layout['layout_issues'] and layout['ground']['ok']
        layouts.append(layout)
    results=[]
    for family in ('mansard','gable','high_kitchen'):
        domain=[-500,-500,12500,10500] if family!='high_kitchen' else [6200,-500,12500,6600]
        axes=(1,) if family!='high_kitchen' else (0,1)
        for layout in layouts:
            support=dict(rect=[0,0,12000,10000] if family!='high_kitchen' else [6200,0,12000,6100],z=1050,role='roof_support_envelope')
            requirements=layout['requirements']+[support]
            symmetric=fit_profile(family,domain,requirements,True,axes)
            asymmetric=fit_profile(family,domain,requirements,False,axes)
            # Retain symmetric when its extra height is less than 200 mm; both recorded.
            selected=asymmetric if asymmetric and (not symmetric or symmetric['ridge_z']-asymmetric['ridge_z']>=200) else symmetric
            if selected:
                clearances=[rectangle_clearance(selected['profile'], selected['axis'], q['rect'], q['z'],450) for q in layout['requirements']]
                status='conditional' if layout['ok'] and min(clearances)>=2050 else 'rejected'
            else:
                clearances=[];status='rejected'
            results.append(dict(id=f'{family}_{layout["id"]}',family=family,layout_id=layout['id'],
                                status=status,roof=selected,symmetric=symmetric,asymmetric=asymmetric,
                                minimum_clearance_mm=min(clearances) if clearances else None,
                                issues=layout['layout_issues']+([] if layout['ground']['ok'] else ['Не проходят нижние проходы или мебель в этой расстановке.'])))
    main_variants=[]
    for family in ('mansard','gable','high_kitchen'):
        acceptable=[r for r in results if r['family']==family and r['status']=='conditional']
        if not acceptable:
            raise RuntimeError(f'No main concept found for {family}; inspect layouts, do not fake acceptance')
        choice=min(acceptable,key=lambda r:(r['roof']['ridge_z'],r['layout_id']))
        choice=dict(choice);choice['layout']=next(l for l in layouts if l['id']==choice['layout_id'])
        p=choice['roof']
        lower=[(x,z-(300 if 0<i<len(p['profile'])-1 else 0)) for i,(x,z) in enumerate(p['profile'])]
        reduced_clearance=min(rectangle_clearance(lower,p['axis'],q['rect'],q['z'],450) for q in choice['layout']['requirements'])
        choice['lower_300mm']=dict(profile=lower,minimum_clearance_mm=reduced_clearance,
            status='rejected' if reduced_clearance<2050 else 'conditional',
            reason='Внутренние вершины опущены на 300 мм при сохранении карнизов; проверить высоты и изменённые уклоны.')
        main_variants.append(choice)
    dump('concepts.json',dict(layouts=layouts,candidates=results,main=main_variants,
        assumptions=dict(platform_floor_mm=3100,platform_thickness_mm=[300,400],roof_normal_thickness_mm=[350,450],
                         mauerlat_side_mm=[150,200],upper_route_width_mm=1000,lower_test_route_width_mm=900,
                         stair_clear_width_mm=900,stair_tread_slab_mm=100,eave_outer_mm=3550,
                         clearance_design_target_mm=2060,clearance_acceptance_mm=2050,
                         scope='finite U/L layouts; straight ordinary stair needs >=6000 mm including both 1000-mm landings',
                         structure='Support and wall-top proposals require owner review and structural calculation; not certified.',
                         six_seats='Table extension checked for direct stair overlap; complete six-seat circulation remains conditional.')))
    print(json.dumps([dict(family=r['family'],layout=r['layout_id'],ridge=r['roof']['ridge_z'],clearance=r['minimum_clearance_mm']) for r in main_variants],ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
