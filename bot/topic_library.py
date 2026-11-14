"""Validated editorial topic bank; readiness is not factual or publication approval."""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from briefs import Brief
from content_layers import FEATURES, validate_selection

BANK = Path(__file__).resolve().parents[1] / 'knowledge/topics/bot_topics.json'

@dataclass(frozen=True)
class Topic:
    id: str
    title: str
    pillar_id: str
    pillar_label: str
    series: str
    feature_id: str
    strategy_id: str
    structure_id: str
    format: str
    angle: str
    outline: tuple[str, ...]
    audience: str
    research_note: str
    hold: bool
    published: bool
    source_status: str
    note: str
    format_note: str

    def __post_init__(self):
        for key in self.__dataclass_fields__:
            value=getattr(self,key)
            if key in ('hold','published'):
                if type(value) is not bool: raise ValueError('invalid topic flag')
            elif key=='outline':
                if not isinstance(value,tuple) or not 1<=len(value)<=8 or any(
                    not isinstance(v,str) or not v.strip() or len(v)>500 for v in value):
                    raise ValueError('invalid topic outline')
            elif not isinstance(value,str) or len(value)>1200:
                raise ValueError('invalid topic field')
        if not re.fullmatch(r'CONT-[0-9]{1,6}',self.id) or not re.fullmatch(r'P[1-6]',self.pillar_id):
            raise ValueError('invalid topic identity')
        if not self.title.strip() or len(self.title)>300 or not self.pillar_label.strip():
            raise ValueError('invalid topic title')
        validate_selection(self.format,self.feature_id,self.strategy_id,self.structure_id)
        if self.format not in FEATURES[self.feature_id][1]:
            raise ValueError('topic format is not a menu format')

    @property
    def ready(self):
        return not self.hold and not self.published

    def chosen_format(self,current=None):
        return current if current in FEATURES[self.feature_id][1] else self.format

    def brief(self,fmt=None):
        from layer_navigation import selected_brief
        material=('خطة تحريرية للموضوع، مو حقائق متحقق منها ولا سكربت جاهز.\n'
                  'زاوية الطرح: '+self.angle+'\nمحطات تساعد بالترتيب:\n'
                  +'\n'.join(f'{i}. {v}' for i,v in enumerate(self.outline,1))
                  +'\nالتحقق عند الحاجة: '+self.research_note+
                  '\nالمحطات إرشادية؛ لا تفرض عدد نصائح أو تلخيص أو سؤال ختامي. '
                  'لا تخترع أرقام أو مصادر أو تجربة شخصية.')
        brief=selected_brief({'feature_id':self.feature_id,'strategy_id':self.strategy_id,
                              'structure_id':self.structure_id},
                             Brief(audience=self.audience,takeaway=self.angle,source_material=material,
                                   duration_seconds=30 if self.feature_id=='story' else 60 if self.feature_id=='reel' else 30))
        brief.validate_format(fmt or self.format)
        return brief


def load_topics(path=None):
    path=Path(path) if path is not None else BANK
    if path.stat().st_size>1_500_000: raise ValueError('topic bank too large')
    def unique(pairs):
        data={}
        for k,v in pairs:
            if k in data: raise ValueError('duplicate bank key')
            data[k]=v
        return data
    data=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique)
    if not isinstance(data,dict) or set(data)!={'version','topics'} or type(data['version']) is not int or data['version']!=1:
        raise ValueError('invalid topic bank version')
    if not isinstance(data['topics'],list) or not 1<=len(data['topics'])<=1000:
        raise ValueError('invalid topic bank count')
    result={}
    for row in data['topics']:
        if not isinstance(row,dict) or set(row)!=set(Topic.__dataclass_fields__):
            raise ValueError('invalid topic row')
        row=dict(row)
        if not isinstance(row['outline'],list): raise ValueError('invalid topic outline')
        row['outline']=tuple(row['outline'])
        item=Topic(**row)
        if item.id in result: raise ValueError('duplicate topic ID')
        result[item.id]=item
    return result
