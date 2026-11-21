from pathlib import Path
from datetime import datetime, timezone, timedelta
from bson import json_util
from config import BACKUP_DIR, BACKUP_KEEP_DAYS, RECORDS_CHANNEL_ID
from database import db
from security import encrypt

COLLECTIONS=['users','seller_applications','listings','orders','payments','payouts','finance_ledger','audit_logs','channel_events','encrypted_media','disputes','settings']
async def create_backup(application):
    folder=Path(BACKUP_DIR);folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload={'database':db.name,'created_at_utc':stamp,'collections':{}}
    for name in COLLECTIONS: payload['collections'][name]=await db[name].find({}).to_list(None)
    path=folder/f'yash_umpire_{stamp}.json.enc'
    path.write_bytes(encrypt(json_util.dumps(payload,ensure_ascii=False).encode()))
    if RECORDS_CHANNEL_ID:
        with path.open('rb') as f:
            await application.bot.send_document(int(RECORDS_CHANNEL_ID),f,filename=path.name,caption=f'Encrypted YASH UMPIRE backup {stamp} UTC')
    cutoff=datetime.now(timezone.utc)-timedelta(days=BACKUP_KEEP_DAYS)
    for old in folder.glob('yash_umpire_*.json.enc'):
        try:
            t=old.name.removeprefix('yash_umpire_').removesuffix('.json.enc')
            if datetime.strptime(t,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)<cutoff: old.unlink(missing_ok=True)
        except ValueError: pass
    return str(path)
