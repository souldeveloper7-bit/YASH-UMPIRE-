from datetime import datetime, timezone
from database import audit, events, listings, orders, ledger, users
from config import OWNER_ID
from finance import fee_split
import uuid

def now(): return datetime.now(timezone.utc)
def new_id(prefix): return f'{prefix}-{uuid.uuid4().hex[:10].upper()}'

async def log_action(actor, action, details=None):
    stamp=now(); details=details or {}
    await audit.insert_one({'actor_id':int(actor),'action':action,'details':details,'created_at':stamp})
    # Channel posts are short operational summaries; private phone/UTR/media are never broadcast.
    await events.insert_one({'actor_id':int(actor),'summary':action,'details':details,'created_at':stamp,'sent':False})

async def reserve_stock(listing_id, qty):
    r=await listings.update_one({'listing_id':listing_id,'status':'approved','available_qty':{'$gte':qty}},
      {'$inc':{'available_qty':-qty,'reserved_qty':qty}})
    return r.modified_count==1

async def release_stock(order):
    r=await orders.update_one({'order_id':order['order_id'],'stock_released':{'$ne':True}},
      {'$set':{'stock_released':True}})
    if r.modified_count:
        await listings.update_one({'listing_id':order['listing_id']},
          {'$inc':{'available_qty':int(order['qty']),'reserved_qty':-int(order['qty'])}})
        return True
    return False

async def consume_stock(order):
    r=await orders.update_one({'order_id':order['order_id'],'stock_consumed':{'$ne':True}},
      {'$set':{'stock_consumed':True}})
    if r.modified_count:
        await listings.update_one({'listing_id':order['listing_id']},
          {'$inc':{'reserved_qty':-int(order['qty']),'sold_qty':int(order['qty'])}})
        return True
    return False

async def seller_name(uid):
    u=await users.find_one({'telegram_id':uid}) or {}
    return u.get('display_name') or u.get('first_name') or f'Seller {uid}'

async def make_ledger(order):
    split=fee_split(order['total'])
    gross=split['gross']; fee=split['total_fee']; net=split['seller_net']
    p=split['platform_fee']; m=split['maintenance_fee']; o=split['owner_fee']
    await ledger.update_one({'order_id':order['order_id']},{'$setOnInsert':{
      'order_id':order['order_id'],'seller_id':order['seller_id'],'gross':gross,
      'platform_fee':p,'maintenance_fee':m,'owner_fee':o,'total_fee':fee,
      'seller_net':net,'created_at':now(),'entry_type':'sale'}},upsert=True)
    return gross,fee,net
