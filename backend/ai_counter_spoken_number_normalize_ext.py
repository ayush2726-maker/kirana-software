from __future__ import annotations

import re

import backend.ai_counter_ext as counter
import backend.ai_counter_route_order_ext as desk

VERSION = "192"
_prev_norm = counter._norm
_prev_page = desk._desk_page_with_quantity_fix

NUM_WORDS = {
    "zero":0,"shunya":0,"शून्य":0,
    "one":1,"ek":1,"एक":1,"two":2,"do":2,"दो":2,"three":3,"teen":3,"तीन":3,
    "four":4,"char":4,"chaar":4,"चार":4,"five":5,"panch":5,"paanch":5,"पांच":5,"पाँच":5,
    "six":6,"chhe":6,"che":6,"छह":6,"seven":7,"saat":7,"सात":7,"eight":8,"aath":8,"आठ":8,
    "nine":9,"nau":9,"नौ":9,"ten":10,"das":10,"दस":10,
    "eleven":11,"gyarah":11,"ग्यारह":11,"twelve":12,"barah":12,"बारह":12,
    "thirteen":13,"terah":13,"तेरह":13,"fourteen":14,"chaudah":14,"चौदह":14,
    "fifteen":15,"pandrah":15,"पंद्रह":15,"sixteen":16,"solah":16,"सोलह":16,
    "seventeen":17,"satrah":17,"सत्रह":17,"eighteen":18,"atharah":18,"अठारह":18,
    "nineteen":19,"unnis":19,"उन्नीस":19,"twenty":20,"bees":20,"बीस":20,
    "twentyfive":25,"pachis":25,"पच्चीस":25,"thirty":30,"tees":30,"तीस":30,
    "forty":40,"chalis":40,"चालीस":40,"fifty":50,"pachas":50,"पचास":50,
    "sixty":60,"saath":60,"साठ":60,"seventy":70,"sattar":70,"सत्तर":70,
    "eighty":80,"assi":80,"अस्सी":80,"ninety":90,"nabbe":90,"नब्बे":90,
    "hundred":100,"sau":100,"सौ":100,"thousand":1000,"hazaar":1000,"hazar":1000,"हजार":1000,
}

PHRASES = {
    "डेढ़ सौ":"150", "डेढ सौ":"150", "dedh sau":"150", "derh sau":"150",
    "ढाई सौ":"250", "dhai sau":"250",
    "सवा सौ":"125", "sawa sau":"125",
    "दो सौ":"200", "do sau":"200", "तीन सौ":"300", "teen sau":"300",
    "चार सौ":"400", "char sau":"400", "पांच सौ":"500", "पाँच सौ":"500", "paanch sau":"500",
    "एक हजार":"1000", "ek hazaar":"1000", "ek hazar":"1000",
}

def spoken_numbers_to_digits(value: str) -> str:
    text = str(value or "")
    low = text.lower()
    for src, dst in PHRASES.items():
        low = re.sub(rf"(?<!\w){re.escape(src)}(?!\w)", dst, low, flags=re.I)
    for word, num in sorted(NUM_WORDS.items(), key=lambda kv: len(kv[0]), reverse=True):
        low = re.sub(rf"(?<!\w){re.escape(word)}(?!\w)", str(num), low, flags=re.I)
    return re.sub(r"\s+", " ", low).strip()

def _norm(value):
    return _prev_norm(spoken_numbers_to_digits(str(value or "")))

counter._norm = _norm

JS = r'''
function spokenDigits192(s){
  var t=String(s||'');
  var p=[
    [/डे[ढ़ढ]\s*सौ|dedh\s*sau|derh\s*sau/gi,'150'],[/ढाई\s*सौ|dhai\s*sau/gi,'250'],[/सवा\s*सौ|sawa\s*sau/gi,'125'],
    [/दो\s*सौ|do\s*sau/gi,'200'],[/तीन\s*सौ|teen\s*sau/gi,'300'],[/चार\s*सौ|chaar?\s*sau/gi,'400'],[/पांच\s*सौ|पाँच\s*सौ|paanch\s*sau/gi,'500'],
    [/एक\s*हजार|ek\s*haza?r/gi,'1000']
  ];p.forEach(function(x){t=t.replace(x[0],x[1]);});
  var m={
   'शून्य':'0','zero':'0','एक':'1','ek':'1','one':'1','दो':'2','do':'2','two':'2','तीन':'3','teen':'3','three':'3','चार':'4','char':'4','chaar':'4','four':'4',
   'पांच':'5','पाँच':'5','panch':'5','paanch':'5','five':'5','छह':'6','chhe':'6','che':'6','six':'6','सात':'7','saat':'7','seven':'7','आठ':'8','aath':'8','eight':'8','नौ':'9','nau':'9','nine':'9','दस':'10','das':'10','ten':'10',
   'ग्यारह':'11','gyarah':'11','eleven':'11','बारह':'12','barah':'12','twelve':'12','तेरह':'13','terah':'13','thirteen':'13','चौदह':'14','chaudah':'14','fourteen':'14','पंद्रह':'15','pandrah':'15','fifteen':'15','सोलह':'16','solah':'16','sixteen':'16','सत्रह':'17','satrah':'17','seventeen':'17','अठारह':'18','atharah':'18','eighteen':'18','उन्नीस':'19','unnis':'19','nineteen':'19','बीस':'20','bees':'20','twenty':'20',
   'पच्चीस':'25','pachis':'25','तीस':'30','tees':'30','thirty':'30','चालीस':'40','chalis':'40','forty':'40','पचास':'50','pachas':'50','fifty':'50','साठ':'60','saath':'60','sixty':'60','सत्तर':'70','sattar':'70','seventy':'70','अस्सी':'80','assi':'80','eighty':'80','नब्बे':'90','nabbe':'90','ninety':'90','सौ':'100','sau':'100','hundred':'100','हजार':'1000','hazaar':'1000','hazar':'1000','thousand':'1000'
  };
  Object.keys(m).sort(function(a,b){return b.length-a.length;}).forEach(function(k){var e=k.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');t=t.replace(new RegExp('(^|\\s)'+e+'(?=\\s|$)','gi'),function(_,pre){return pre+m[k];});});
  return t.replace(/\s+/g,' ').trim();
}
var _processSpeech192=processSpeech;
processSpeech=async function(raw){var n=spokenDigits192(raw);$('heard').textContent='You: '+n;return await _processSpeech192(n);};
'''

def _page() -> str:
    page = _prev_page()
    marker = "$('scanBarcode').onclick=openScanner;"
    if "spokenDigits192" not in page and marker in page:
        page = page.replace(marker, JS + "\n" + marker, 1)
    return page

desk._desk_page_with_quantity_fix = _page
