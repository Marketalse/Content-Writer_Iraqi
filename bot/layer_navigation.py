"""Three content-layer menus. Destination platform remains a separate routing choice."""
from dataclasses import replace
from telegram import InlineKeyboardButton as Button, InlineKeyboardMarkup as Markup
from briefs import Brief
from content_layers import FEATURES, STRATEGIES, FLOWS, get_strategy, validate_selection
from story_styles import is_story

KEYS = ('feature_id','strategy_id')


def root_keyboard():
    return Markup([[Button(label,callback_data='ly:f:'+key)] for key,(label,_) in FEATURES.items()]
                  + [[Button('➕ فورمات إضافية / الاختيارات السابقة',callback_data='ly:legacy')]])


def platform_keyboard(feature, formats):
    return Markup([[Button(formats[fmt][0],callback_data=f'ly:p:{feature}:{fmt}')]
                   for fmt in FEATURES[feature][1]] + [[Button('↩️ نوع المحتوى',callback_data='ly:root')]])


def strategy_keyboard(feature, fmt):
    return Markup([[Button(get_strategy(feature,key).label,callback_data=f'ly:s:{fmt}:{key}')]
                   for key in STRATEGIES[feature]] + [[Button('↩️ المنصة',callback_data='ly:b:platform')]])


def structure_keyboard(feature, fmt, strategy):
    flow=get_strategy(feature,strategy).flow
    return Markup([[Button('✅ استخدم هذه البنية',callback_data=f'ly:n:{fmt}:{strategy}:{flow}')],
                   [Button('↩️ استراتيجية المحتوى',callback_data='ly:b:strategy')]])


def selected_brief(data, brief=None):
    brief=brief or Brief()
    feature,strategy=data['feature_id'],data['strategy_id']
    intent=('entertain' if strategy=='comedy' else 'everyday' if strategy=='experiment' else
            'ask_audience' if strategy=='engage' else 'educational') if feature=='story' else 'auto'
    purpose='entertain' if strategy=='comedy' else 'conversation' if strategy in ('engage','quiz','poll','clinic','guest') else 'educate'
    return replace(brief,feature_id=feature,strategy_id=strategy,structure_id=data.get('structure_id',''),
                   story_mode='moment',story_intent=intent,purpose=purpose,
                   production=brief.production if feature=='reel' else False)


async def show_current(message, data, formats, *, edit=False):
    send=message.edit_message_text if edit else message.reply_text
    feature,fmt=data['feature_id'],data.get('format')
    stage=data.get('menu_stage')
    if stage=='layer_platform':
        await send('نوع المحتوى: '+FEATURES[feature][0]+'\nاختار المنصة / صيغة النشر:',reply_markup=platform_keyboard(feature,formats))
    elif stage=='layer_strategy':
        await send('الطبقة 2/3 — استراتيجية المحتوى\n'+formats[fmt][0],reply_markup=strategy_keyboard(feature,fmt))
    elif stage=='layer_structure':
        flow=get_strategy(feature,data['strategy_id']).flow
        await send('الطبقة 3/3 — بنية السكربت\n'+FLOWS[flow].replace(' → ', '\n↓\n')+
                   '\n\nتسلسل إرشادي يتكيّف ويا الفكرة والمدة.',reply_markup=structure_keyboard(feature,fmt,data['strategy_id']))
    else:
        await send('تم الاختيار ✅\n'+FEATURES[feature][0]+' → '+get_strategy(feature,data['strategy_id']).label+
                   '\nالبنية: '+FLOWS[data['structure_id']]+'\nهسه دزلي الموضوع كتابةً.',
                   reply_markup=Markup([[Button('↩️ بنية السكربت',callback_data='ly:b:structure')]]))


async def handle(query, data, formats, clear_selection, legacy_keyboard):
    parts=query.data.split(':')
    if parts==['ly','root']:
        clear_selection(data)
        await query.edit_message_text('الطبقة 1/3 — اختار نوع المحتوى:',reply_markup=root_keyboard())
        return
    if parts==['ly','legacy']:
        clear_selection(data)
        await query.edit_message_text('فورمات إضافية / الاختيارات السابقة:',reply_markup=legacy_keyboard())
        return
    if len(parts)==3 and parts[1]=='f' and parts[2] in FEATURES:
        clear_selection(data)
        data.update(feature_id=parts[2],menu_stage='layer_platform')
    elif (len(parts)==4 and parts[1]=='p' and data.get('menu_stage')=='layer_platform'
          and data.get('feature_id')==parts[2] and parts[3] in FEATURES[parts[2]][1]):
        data.update(format=parts[3],menu_stage='layer_strategy')
    elif (len(parts)==4 and parts[1]=='s' and data.get('menu_stage')=='layer_strategy'
          and data.get('format')==parts[2]):
        try:
            get_strategy(data['feature_id'],parts[3])
        except (KeyError,ValueError):
            return
        data.update(strategy_id=parts[3],angle=parts[3],menu_stage='layer_structure')
        data['content_brief']=selected_brief(data)
    elif (len(parts)==5 and parts[1]=='n' and data.get('menu_stage')=='layer_structure'
          and data.get('format')==parts[2] and data.get('strategy_id')==parts[3]):
        try:
            validate_selection(parts[2],data['feature_id'],parts[3],parts[4])
        except (KeyError,ValueError):
            return
        data.update(structure_id=parts[4],menu_stage='topic')
        data['content_brief']=selected_brief(data,data.get('content_brief'))
    elif len(parts)==3 and parts[1]=='b' and data.get('feature_id'):
        previous=data.get('menu_stage')
        if parts[2]=='platform' and previous=='layer_strategy':
            for key in ('format','strategy_id','structure_id','angle','content_brief','pending_clarification'):
                data.pop(key,None)
            data['menu_stage']='layer_platform'
        elif parts[2]=='strategy' and previous=='layer_structure':
            for key in ('strategy_id','structure_id','angle','content_brief','pending_clarification'):
                data.pop(key,None)
            data['menu_stage']='layer_strategy'
        elif parts[2]=='structure' and previous=='topic':
            data.pop('structure_id',None)
            data.pop('pending_clarification',None)
            data['content_brief']=selected_brief(data,data.get('content_brief'))
            data['menu_stage']='layer_structure'
        else:
            return
    else:
        return
    await show_current(query,data,formats,edit=True)
