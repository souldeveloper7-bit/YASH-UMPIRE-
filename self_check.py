"""Offline static sanity checks; does not connect to Telegram or MongoDB."""
from pathlib import Path
import ast
ROOT=Path(__file__).parent
required=['main.py','handlers.py','keyboards.py','database.py','services.py','security.py','backup.py','config.py','finance.py','test_logic.py','requirements.txt','.env.example','README.md','BUTTON-CHECKLIST.md']
missing=[x for x in required if not (ROOT/x).exists()]
if missing: raise SystemExit('Missing files: '+', '.join(missing))
for p in ROOT.glob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'),filename=p.name)
handlers=(ROOT/'handlers.py').read_text(encoding='utf-8')
keyboards=(ROOT/'keyboards.py').read_text(encoding='utf-8')
checks={
 'callback query handler':'CallbackQueryHandler(callback)' in (ROOT/'main.py').read_text(encoding='utf-8'),
 'buyer confirm callback':"d=='buyer:confirm'" in handlers,
 'payment approval callback':"d.startswith('payapprove:')" in handlers,
 'seller receive callback':"d.startswith('sellerreceive:')" in handlers,
 'delivery decision callback':"d.startswith('deliverydone:')" in handlers,
 'payout proof callback':"d.startswith('payoutpaid:')" in handlers,
 'seller rules acceptance':"d=='seller:accept_rules'" in handlers,
 'buyer phone collection':"flow')=='buyer_phone'" in handlers,
 'payout QR upload button':"payoutupload:{pid}" in handlers,
 'stock release review':"ownerrelease:{x['order_id']}" in handlers,
 'records batch job':'run_repeating(flush_events' in (ROOT/'main.py').read_text(encoding='utf-8'),
 'daily backup job':'run_daily(daily' in (ROOT/'main.py').read_text(encoding='utf-8'),
 'seller dashboard buttons':all(x in keyboards for x in ['seller:addstock','seller:stock','seller:price','seller:orders','seller:earnings','seller:payout']),
 'owner dashboard buttons':all(x in keyboards for x in ['owner:stats','owner:users','owner:apps','owner:listings','owner:orders','owner:payments','owner:disputes','owner:deliveries','owner:payouts','owner:finance','owner:settings','owner:backup']),
}
for name,ok in checks.items(): print(('PASS' if ok else 'FAIL')+' - '+name)
if not all(checks.values()): raise SystemExit(1)
print(f'PASS - {len(list(ROOT.glob("*.py")))} Python files parsed successfully')
