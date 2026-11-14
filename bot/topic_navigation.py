"""Read-only browsing and explicit confirmation before topic generation."""
from telegram import InlineKeyboardButton as Button, InlineKeyboardMarkup as Markup
from content_layers import CATALOG, FEATURES, FLOWS

PAGE_SIZE=7


def home(topics):
    labels={item.pillar_id:item.pillar_label for item in topics.values()}
    rows=[[Button(f'{labels[key]} ({sum(t.pillar_id==key for t in topics.values())})',
                  callback_data=f'bank:page:{key}:0')] for key in sorted(labels)]
    rows.append([Button('↩️ نوع المحتوى',callback_data='ly:root')])
    ready=sum(item.ready for item in topics.values())
    return (f'📚 مواضيع المحتوى: {len(topics)} فكرة\n{ready} فكرة محددة وغير مستخدمة. '
            'الباقي مستخدم أو يحتاج تفاصيل.\nاختار المحور:',Markup(rows))


def page(topics,pillar,number):
    items=[t for t in topics.values() if t.pillar_id==pillar]
    items.sort(key=lambda t:(t.hold,t.published))
    pages=(len(items)+PAGE_SIZE-1)//PAGE_SIZE
    if not items or not 0<=number<pages: raise ValueError('invalid topic page')
    rows=[];lines=[f'📚 {items[0].pillar_label} — {number+1}/{pages}']
    for item in items[number*PAGE_SIZE:(number+1)*PAGE_SIZE]:
        flag='⚠️ ' if item.hold else '↻ ' if item.published else ''
        lines.append(f'\n{item.id}\n{flag}{item.title}')
        rows.append([Button(flag+item.id,callback_data='bank:select:'+item.id)])
    nav=[]
    if number:nav.append(Button('السابق',callback_data=f'bank:page:{pillar}:{number-1}'))
    if number+1<pages:nav.append(Button('التالي',callback_data=f'bank:page:{pillar}:{number+1}'))
    if nav:rows.append(nav)
    rows.append([Button('↩️ المحاور',callback_data='bank:home')])
    return '\n'.join(lines),Markup(rows)


def preview(item,fmt,formats,token):
    text=(f'📌 {item.id}\n{item.title}\n\n'
          +formats[fmt][0]+'\n'+FEATURES[item.feature_id][0]+' → '+CATALOG[item.strategy_id].label+
          '\nالبنية: '+FLOWS[item.structure_id]+'\n\nالزاوية: '+item.angle)
    if item.published:text+='\n\n↻ هذا الموضوع مستخدم حسب ملفك. الاختيار هنا لإعادة صياغته.'
    text+='\n\nنبدي نكتب ونفحص؟'
    button='أعد صياغة الموضوع المستخدم' if item.published else 'ابدأ كتابة السكربت'
    return text,Markup([[Button(button,callback_data=f'bank:run:{item.id}:{token}')],
                        [Button('↩️ المواضيع',callback_data='bank:home')]])
