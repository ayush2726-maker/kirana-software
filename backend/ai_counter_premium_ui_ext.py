from __future__ import annotations

import backend.ai_counter_route_order_ext as desk

VERSION = "200"
_prev_page = desk._desk_page_with_quantity_fix

STYLE = r'''
<style id="ai-desk-premium-200">
:root{--p1:#2563eb;--p2:#6d4cff;--cyan:#16b8e8;--ink:#12213a;--muted:#64748b;--line:#e4e9f2;--card:#fff;--bg:#f5f7fb}
html,body{background:linear-gradient(180deg,#f8fbff 0,#f4f6fb 42%,#eef4fb 100%)!important;color:var(--ink)!important}
body:before{content:"";position:fixed;inset:0;pointer-events:none;background:radial-gradient(circle at 92% 3%,rgba(109,76,255,.12),transparent 24rem),radial-gradient(circle at 5% 35%,rgba(22,184,232,.08),transparent 22rem)}
.shell{max-width:980px!important;padding:14px 14px 36px!important;position:relative}
.top{position:sticky;top:0;z-index:20;margin:0 -2px 16px!important;padding:10px 4px 12px;background:rgba(248,251,255,.88);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px)}
.brand{min-width:0}.brand b{font-size:22px!important;letter-spacing:-.4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.brand span{font-size:13px!important;color:#718096!important}.status{background:#ecfdf3;border:1px solid #bbf7d0;color:#14813f!important;border-radius:999px;padding:7px 12px;font-size:13px;white-space:nowrap}
.panel{border:1px solid rgba(213,221,235,.9)!important;border-radius:28px!important;box-shadow:0 18px 55px rgba(37,60,105,.09)!important;background:rgba(255,255,255,.96)!important}
.start-wrap{min-height:72vh!important;padding:26px!important;background:linear-gradient(180deg,#fff 0,#fbfdff 100%)!important}
.start-wrap>div{width:min(560px,100%)}
.start-wrap .avatar{width:106px!important;height:106px!important;border-radius:32px!important;font-size:56px!important;background:linear-gradient(145deg,#eef2ff,#e4f5ff)!important;box-shadow:inset 0 0 0 1px #dfe7f4,0 14px 34px rgba(67,94,160,.12)}
.start-wrap h1{font-size:42px;margin:22px 0 8px;letter-spacing:-1.2px}.start-wrap p{font-size:18px;color:var(--muted);max-width:420px;margin:0 auto 28px}
.start{min-height:82px!important;width:min(460px,100%)!important;border-radius:24px!important;background:linear-gradient(135deg,var(--p1),var(--p2))!important;box-shadow:0 16px 34px rgba(69,76,220,.28)!important;font-size:24px!important;letter-spacing:.2px;transition:.18s transform}.start:active{transform:scale(.985)}
.layout{grid-template-columns:minmax(0,1.35fr) minmax(300px,.72fr)!important;gap:18px!important}.assistant{gap:16px!important}
.hero{position:relative;overflow:hidden;grid-template-columns:auto 1fr!important;border-radius:26px!important;padding:20px!important;background:linear-gradient(135deg,#1476f2 0,#5a56ed 54%,#17b7df 100%)!important;box-shadow:0 16px 36px rgba(48,92,222,.22)}
.hero:after{content:"";position:absolute;width:180px;height:180px;border-radius:50%;right:-55px;top:-75px;background:rgba(255,255,255,.14)}
.hero .avatar{width:82px!important;height:82px!important;border-radius:26px!important;background:rgba(255,255,255,.92)!important;box-shadow:0 8px 22px rgba(25,45,120,.16);font-size:44px!important}.hero small{font-size:12px!important;letter-spacing:1.1px}.hero h2{font-size:26px!important;letter-spacing:-.5px!important}
.prompt{font-size:31px!important;letter-spacing:-.8px!important;line-height:1.15!important;margin:2px 0 0!important}.heard{min-height:58px!important;border:1px solid #dce4f0!important;background:#f8fafc!important;border-radius:17px!important;padding:16px!important;font-size:17px!important;color:#65758b!important}
.choices{gap:10px!important}.choice,.choice-action{border:1px solid #dce4f0!important;border-radius:17px!important;padding:15px 16px!important;background:#fff!important;box-shadow:0 4px 14px rgba(15,40,80,.04)}.choice-action{background:linear-gradient(180deg,#f8fbff,#f3f7ff)!important;color:#1d4ed8}.choice-action.red{color:#b42318!important;background:#fff7f6!important}
.error{border-radius:16px!important;padding:14px 16px!important}
.main-actions{gap:11px!important}.speak{min-height:78px!important;border-radius:22px!important;background:linear-gradient(135deg,var(--p1),var(--p2))!important;box-shadow:0 13px 30px rgba(69,76,220,.25)!important;font-size:23px!important}.speak.listening{background:linear-gradient(135deg,#e5484d,#b42318)!important}.secondary{min-height:60px!important;border-radius:18px!important;background:#fff!important;border:1px solid #dde4ef!important;font-size:16px}.secondary.danger{background:#fff9f8!important}
.quick-tools{gap:11px!important}.tool{min-height:66px!important;border-radius:18px!important;background:linear-gradient(180deg,#fff,#f8fbff)!important;border:1px solid #dce6f3!important;color:#243b5a!important}
.manual{gap:9px!important}.manual input{min-height:56px;border-radius:17px!important;background:#fbfcfe!important;border:1px solid #dce4ef!important;padding:0 16px!important}.manual button{border-radius:17px!important;background:#152b46!important;padding:0 21px!important}
.pay-grid{gap:9px!important}.pay{border-radius:17px!important;background:#fff!important;border:1px solid #dce4ef!important}.pay.active{background:linear-gradient(135deg,var(--p1),var(--p2))!important;border-color:transparent!important}
.layout>aside.panel{align-self:start;position:sticky;top:84px}.cart-head small{color:#64748b;letter-spacing:.7px}.cart-head h2{font-size:28px!important}.customer{border-radius:16px!important;background:linear-gradient(135deg,#eff6ff,#f2f0ff)!important;color:#233b61!important;padding:14px 15px!important}.cart{gap:10px!important}.line{border-radius:17px!important;border:1px solid #e2e8f0!important;padding:14px!important;background:#fff;box-shadow:0 4px 14px rgba(15,40,80,.035)}.line small{font-size:13px!important}.total{border-top:1px solid #e4eaf2!important}.total strong{font-size:31px!important;color:#172554}
.modal{backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px)}.modal-card{border-radius:28px!important;box-shadow:0 25px 70px rgba(11,28,60,.25)!important}.field input,.field select{min-height:52px!important;border-radius:15px!important;border-color:#dce4ef!important}.modal-actions button{border-radius:16px!important}
.complete{padding:40px!important}.complete h1{font-size:36px}
@media(max-width:820px){.shell{padding:8px 10px 28px!important}.top{padding:8px 2px 10px}.brand b{font-size:18px!important}.brand span{font-size:12px!important}.status{font-size:12px;padding:6px 9px}.layout{grid-template-columns:1fr!important}.panel{padding:16px!important;border-radius:24px!important}.hero{padding:16px!important;border-radius:22px!important}.hero .avatar{width:68px!important;height:68px!important;border-radius:21px!important;font-size:38px!important}.hero h2{font-size:20px!important}.prompt{font-size:27px!important}.layout>aside.panel{position:static}.start-wrap{min-height:75vh!important}.start-wrap h1{font-size:38px}.start{font-size:22px!important}.manual input{font-size:15px}}
@media(max-width:430px){.main-actions,.quick-tools{grid-template-columns:1fr 1fr}.prompt{font-size:25px!important}.hero{grid-template-columns:64px 1fr!important}.hero .avatar{width:60px!important;height:60px!important;font-size:34px!important}.hero h2{font-size:18px!important}.hero small{font-size:10px!important}.start-wrap{padding:22px 16px!important}.start-wrap .avatar{width:94px!important;height:94px!important}.start-wrap h1{font-size:36px}.start{min-height:76px!important}}
</style>
'''


def _page() -> str:
    page = _prev_page()
    if 'ai-desk-premium-200' not in page:
        page = page.replace('</head>', STYLE + '</head>', 1)
    return page


desk._desk_page_with_quantity_fix = _page
