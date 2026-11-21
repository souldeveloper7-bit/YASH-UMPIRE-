from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGODB_URI, DATABASE_NAME
client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=10000, retryWrites=True)
db = client[DATABASE_NAME]
users=db.users; seller_apps=db.seller_applications; listings=db.listings; orders=db.orders
payments=db.payments; payouts=db.payouts; ledger=db.finance_ledger; audit=db.audit_logs
events=db.channel_events; media=db.encrypted_media; disputes=db.disputes; settings=db.settings

async def init_db():
    await client.admin.command('ping')
    indexes=[
      (users,[('telegram_id',1)],{'unique':True}),
      (seller_apps,[('telegram_id',1)],{}),
      (listings,[('listing_id',1)],{'unique':True}),
      (orders,[('order_id',1)],{'unique':True}),
      (payments,[('order_id',1)],{'unique':True}),
      (payments,[('utr',1)],{'unique':True,'sparse':True}),
      (payouts,[('payout_id',1)],{'unique':True}),
      (ledger,[('order_id',1)],{'unique':True}),
      (media,[('media_id',1)],{'unique':True}),
      (events,[('sent',1),('created_at',1)],{}),
      (audit,[('created_at',1)],{}),
      (disputes,[('order_id',1),('created_at',-1)],{}),
    ]
    for collection, keys, opts in indexes:
        await collection.create_index(keys, **opts)
