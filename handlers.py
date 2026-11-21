import io, uuid, re, json
from urllib.parse import quote
import qrcode
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as K, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes
from config import *
from database import *
from keyboards import main_menu, cancel_kb, seller_kb, owner_kb
from services import now, new_id, log_action, reserve_stock, release_stock, consume_stock, seller_name, make_ledger
from finance import fee_split
from security import encrypt

OWNER_ACTIONS={'owner:open','owner:stats','owner:users','owner:apps','owner:listings','owner:orders','owner:payments','owner:disputes','owner:deliveries','owner:payouts','owner:finance','owner:settings','owner:pause','owner:resume','owner:backup','owner:broadcast'}
def is_owner(uid): return int(uid)==OWNER_ID
async def force_join_ok(update,ctx):
    if not FORCE_JOIN_CHANNEL: return True
    try:
        m=await ctx.bot.get_chat_member(FORCE_JOIN_CHANNEL,update.effective_user.id)
        return m.status in ('member','administrator','creator')
    except Exception: return False
async def ensure_user(user):
    await users.update_one({'telegram_id':user.id},{'$set':{'username':user.username,'first_name':user.first_name,'last_seen':now()},'$setOnInsert':{'telegram_id':user.id,'role':'buyer','created_at':now()}},upsert=True)
async def send_home(msg,uid): await msg.reply_text('YASH UMPIRE — BGMI Mix Popularity Store',reply_markup=main_menu(is_owner(uid)))
async def start(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    await ensure_user(update.effective_user)
    u=await users.find_one({'telegram_id':update.effective_user.id}) or {}
    if u.get('suspended'): await update.message.reply_text('Account temporarily restricted. Owner se contact karo.');return
    if not await force_join_ok(update,ctx):
        await update.message.reply_text('Bot use karne ke liye Force Join channel join karo.',reply_markup=K([[B('📢 Join Channel',url=FORCE_JOIN_URL or 'https://t.me/')],[B('✅ I Joined — Check',callback_data='join:check')]])); return
    await send_home(update.message,update.effective_user.id)
async def help_command(update,ctx):
    await update.message.reply_text('Commands: /start /myorders /sellerpanel /owner\nSaare main features buttons se available hain.')
async def seller_panel(update,ctx):
    u=await users.find_one({'telegram_id':update.effective_user.id}) or {}
    if u.get('seller_status')!='approved': await update.message.reply_text('Seller panel ke liye owner approval required hai.'); return
    await update.message.reply_text('Seller Dashboard',reply_markup=seller_kb())
async def owner_panel(update,ctx):
    if not is_owner(update.effective_user.id): return
    ctx.user_data['owner_authenticated']=False;ctx.user_data['flow']='owner_password'
    await update.message.reply_text('Owner panel password enter karo:',reply_markup=cancel_kb())
async def myorders(update,ctx):
    uid=update.effective_user.id
    rows=await orders.find({'$or':[{'buyer_id':uid},{'seller_id':uid}]}).sort('created_at',-1).to_list(20)
    await update.message.reply_text('\n'.join([f"{o['order_id']} | {o['qty']}K | ₹{o['total']:.2f} | {o['status']}" for o in rows]) or 'Abhi koi order nahi.')

async def owner_text(msg,ctx,uid,value):
    flow=ctx.user_data.get('flow')
    if flow=='owner_password' and is_owner(uid):
        if value!=OWNER_PANEL_PASSWORD: await msg.reply_text('Password incorrect.'); return True
        ctx.user_data['owner_authenticated']=True;ctx.user_data.pop('flow',None)
        await msg.reply_text('Owner Panel',reply_markup=owner_kb());return True
    if flow=='delivery_reason' and is_owner(uid):
        oid=ctx.user_data.get('review_order');o=await orders.find_one({'order_id':oid,'status':'delivery_review'})
        if o:
            await orders.update_one({'order_id':oid,'status':'delivery_review'},{'$set':{'status':'delivery_not_right','owner_reason':value,'reviewed_at':now()}})
            await ctx.bot.send_message(o['seller_id'],f'Order {oid}: NOT RIGHT. Owner reason: {value}',reply_markup=K([[B('🔁 Re-deliver & Submit Proof',callback_data=f'redeliver:{oid}')]]))
            await log_action(uid,'delivery_not_right',{'order_id':oid})
        ctx.user_data.clear();await msg.reply_text('Reason seller ko bhej diya.');return True
    if flow=='dispute_reason':
        oid=ctx.user_data.get('dispute_order');o=await orders.find_one({'order_id':oid,'$or':[{'buyer_id':uid},{'seller_id':uid}]})
        if o:
            await disputes.insert_one({'order_id':oid,'raised_by':uid,'reason':value,'status':'open','created_at':now()})
            await ctx.bot.send_message(OWNER_ID,f'Dispute {oid}\nRaised by: {uid}\nReason: {value}')
            await log_action(uid,'dispute_opened',{'order_id':oid})
        ctx.user_data.clear();await msg.reply_text('Dispute owner ko submit ho gaya.');return True
    return False

async def text_handler(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    msg=update.message;uid=update.effective_user.id;v=(msg.text or '').strip();f=ctx.user_data.get('flow')
    if await owner_text(msg,ctx,uid,v): return
    if f=='seller_name':
        if len(v)<2 or len(v)>80: await msg.reply_text('Valid full name bhejo.');return
        ctx.user_data['seller_name']=v;ctx.user_data['flow']='seller_phone'
        await msg.reply_text('Apna phone number share karo:',reply_markup=ReplyKeyboardMarkup([[KeyboardButton('📱 Share My Phone',request_contact=True)]],resize_keyboard=True,one_time_keyboard=True));return
    if f in ('buyer_qty','stock_qty'):
        try: qty=int(v.upper().replace('K','').replace(',','')); assert 0<qty<=1000000
        except Exception: await msg.reply_text('Quantity K mein bhejo. Example: 20K');return
        if f=='buyer_qty':
            ctx.user_data['buyer_qty']=qty
            rows=await listings.find({'status':'approved','available_qty':{'$gte':qty}}).to_list(60)
            if not rows: await msg.reply_text('Is quantity ke liye approved seller stock nahi mila.');ctx.user_data.clear();return
            buttons=[]
            for x in rows:
                name=await seller_name(x['seller_id'])
                buttons.append([B(f"{name} — ₹{x['price_per_k']}/1K ({x['available_qty']}K)",callback_data=f"listing:{x['listing_id']}")])
            buttons.append([B('Cancel',callback_data='flow:cancel')])
            await msg.reply_text('Seller aur rate select karo:',reply_markup=K(buttons));return
        ctx.user_data['stock_qty']=qty;ctx.user_data['flow']='stock_price'
        await msg.reply_text('Apna price per 1K (₹) bhejo:',reply_markup=cancel_kb());return
    if f=='stock_price':
        try: price=round(float(v),2);assert 0<price<=100000
        except Exception: await msg.reply_text('Valid price bhejo, example 5.50');return
        ctx.user_data['stock_price']=price;ctx.user_data['flow']='stock_video'
        await msg.reply_text(f"Stock: {ctx.user_data['stock_qty']}K\nRate: ₹{price}/1K\nAb full stock proof video upload karo.");return
    if f=='buyer_uid':
        if not v.isdigit() or not 5<=len(v)<=20: await msg.reply_text('Valid numeric BGMI UID bhejo.');return
        ctx.user_data['bgmi_uid']=v;ctx.user_data['flow']='buyer_ign';await msg.reply_text('In-game name (IGN) bhejo:');return
    if f=='buyer_ign':
        if not 2<=len(v)<=40: await msg.reply_text('Valid IGN bhejo.');return
        ctx.user_data['ign']=v;ctx.user_data['flow']='buyer_phone'
        await msg.reply_text('Apna phone number Telegram contact button se share karo:',reply_markup=ReplyKeyboardMarkup([[KeyboardButton('📱 Share My Phone',request_contact=True)]],resize_keyboard=True,one_time_keyboard=True));return
    if f=='payment_utr':
        if not 6<=len(v)<=40: await msg.reply_text('Valid UTR/reference number bhejo.');return
        oid=ctx.user_data['order_id']
        try:
            await payments.update_one({'order_id':oid,'status':'awaiting_utr'},{'$set':{'utr':v,'status':'awaiting_screenshot','utr_submitted_at':now()}})
            await log_action(uid,'payment_utr_submitted',{'order_id':oid})
        except Exception: await msg.reply_text('UTR already used or invalid. Owner se contact karo.');return
        ctx.user_data['flow']='payment_screenshot';await msg.reply_text('Ab full payment screenshot PHOTO ke roop mein bhejo.');return
    if f=='payout_qr_wait':
        await msg.reply_text('Payout ke liye QR image bhejo, text nahi.');return
    if f=='price_listing_id':
        if not await listings.find_one({'listing_id':v,'seller_id':uid,'status':'approved'}): await msg.reply_text('Apni approved listing ka exact ID bhejo.');return
        ctx.user_data['price_listing']=v;ctx.user_data['flow']='price_new';await msg.reply_text('Naya per-1K price ₹ mein bhejo:');return
    if f=='price_new':
        try: price=round(float(v),2);assert 0<price<=100000
        except Exception: await msg.reply_text('Valid positive price bhejo.');return
        lid=ctx.user_data['price_listing'];await listings.update_one({'listing_id':lid,'seller_id':uid,'status':'approved'},{'$set':{'price_per_k':price,'price_updated_at':now()}})
        await log_action(uid,'seller_price_updated',{'listing_id':lid});ctx.user_data.clear();await msg.reply_text('Price update ho gaya. New orders par apply hoga.');return
    if f=='broadcast' and is_owner(uid) and ctx.user_data.get('owner_authenticated'):
        all_users=await users.find({}, {'telegram_id':1}).to_list(None);sent=0
        for u in all_users:
            try: await ctx.bot.send_message(u['telegram_id'],v);sent+=1
            except Exception: pass
        ctx.user_data.clear();await msg.reply_text(f'Broadcast sent: {sent} users.');await log_action(uid,'broadcast_sent',{'sent':sent});return
    await msg.reply_text('Menu ke liye /start use karo.')

async def contact_handler(update,ctx):
    uid=update.effective_user.id;c=update.message.contact
    if c.user_id!=uid:
        await update.message.reply_text('Sirf apna Telegram contact share karo.',reply_markup=ReplyKeyboardRemove());return
    if ctx.user_data.get('flow')=='buyer_phone':
        await users.update_one({'telegram_id':uid},{'$set':{'phone':c.phone_number}},upsert=True)
        ctx.user_data['buyer_phone']=c.phone_number;ctx.user_data['flow']='buyer_confirm'
        await update.message.reply_text(f"Confirm your order details:\nUID: {ctx.user_data['bgmi_uid']}\nIGN: {ctx.user_data['ign']}\nPhone: {c.phone_number}",reply_markup=K([[B('✅ Confirm',callback_data='buyer:confirm')],[B('❌ Cancel',callback_data='flow:cancel')]]),)
        return
    if ctx.user_data.get('flow')!='seller_phone':
        await update.message.reply_text('Abhi contact share step active nahi hai.',reply_markup=ReplyKeyboardRemove());return
    app={'telegram_id':uid,'full_name':ctx.user_data['seller_name'],'phone':c.phone_number,'status':'pending','created_at':now()}
    await seller_apps.insert_one(app);await users.update_one({'telegram_id':uid},{'$set':{'seller_status':'pending','display_name':app['full_name'],'phone':c.phone_number}},upsert=True)
    await ctx.bot.send_message(OWNER_ID,f"Seller application pending\nID: {uid}\nName: {app['full_name']}\nPhone: {c.phone_number}",reply_markup=K([[B('Approve',callback_data=f'sellerapprove:{uid}'),B('Reject',callback_data=f'sellerreject:{uid}')]]))
    await log_action(uid,'seller_application_submitted');ctx.user_data.clear();await update.message.reply_text('Application owner ko submit ho gayi.',reply_markup=ReplyKeyboardRemove())

async def media_handler(update,ctx):
    uid=update.effective_user.id;f=ctx.user_data.get('flow');m=update.message
    if f=='stock_video' and m.video:
        lid=new_id('LS');qty=ctx.user_data['stock_qty'];price=ctx.user_data['stock_price']
        file=await m.video.get_file();raw=bytes(await file.download_as_bytearray())
        await media.insert_one({'media_id':new_id('MED'),'kind':'stock_video','owner_id':uid,'encrypted_data':encrypt(raw),'created_at':now(),'listing_id':lid})
        await listings.insert_one({'listing_id':lid,'seller_id':uid,'total_qty':qty,'available_qty':qty,'reserved_qty':0,'sold_qty':0,'price_per_k':price,'status':'pending_review','created_at':now()})
        await ctx.bot.send_video(OWNER_ID,video=raw,caption=f'Stock review {lid}\nSeller: {uid}\nQuantity: {qty}K\nPrice: ₹{price}/1K',reply_markup=K([[B('Approve stock',callback_data=f'listingapprove:{lid}'),B('Reject stock',callback_data=f'listingreject:{lid}')]]))
        ctx.user_data.clear();await m.reply_text(f'Stock listing {lid} review ke liye bhej di. Approval ke baad buyer list mein dikhegi.');await log_action(uid,'stock_submitted',{'listing_id':lid});return
    if f=='payment_screenshot' and m.photo:
        oid=ctx.user_data['order_id'];raw=bytes(await (await m.photo[-1].get_file()).download_as_bytearray())
        mid=new_id('MED');await media.insert_one({'media_id':mid,'order_id':oid,'kind':'payment_screenshot','encrypted_data':encrypt(raw),'created_at':now()})
        await payments.update_one({'order_id':oid,'status':'awaiting_screenshot'},{'$set':{'media_id':mid,'status':'payment_review','screenshot_at':now()}})
        await orders.update_one({'order_id':oid,'buyer_id':uid,'status':'awaiting_payment_proof'},{'$set':{'status':'payment_review'}})
        o=await orders.find_one({'order_id':oid});pay=await payments.find_one({'order_id':oid}) or {}
        await ctx.bot.send_photo(OWNER_ID,photo=raw,caption=order_details(o,'PAYMENT REVIEW')+f'\nBuyer phone: {o.get("buyer_phone","not shared")}\nUTR: {pay.get("utr","not submitted")}',reply_markup=K([[B('✅ Approve Payment',callback_data=f'payapprove:{oid}'),B('❌ Reject',callback_data=f'payreject:{oid}')]]))
        ctx.user_data.clear();await m.reply_text('Payment proof owner ko bhej diya. Owner actual UPI credit verify karega.');await log_action(uid,'payment_screenshot_submitted',{'order_id':oid});return
    if f=='seller_delivery_video' and m.video:
        oid=ctx.user_data['delivery_order'];o=await orders.find_one({'order_id':oid,'seller_id':uid,'status':'seller_received'})
        if not o: await m.reply_text('Order ab delivery proof ke liye ready nahi hai.');return
        raw=bytes(await (await m.video.get_file()).download_as_bytearray());mid=new_id('MED')
        await media.insert_one({'media_id':mid,'order_id':oid,'kind':'delivery_video','encrypted_data':encrypt(raw),'created_at':now()})
        await orders.update_one({'order_id':oid,'status':'seller_received'},{'$set':{'delivery_media_id':mid,'status':'delivery_review','delivery_submitted_at':now()}})
        await ctx.bot.send_video(OWNER_ID,video=raw,caption=order_details(o,'DELIVERY REVIEW')+f'\nBuyer phone: {o.get("buyer_phone","not shared")}',reply_markup=K([[B('✅ DONE',callback_data=f'deliverydone:{oid}'),B('⚠️ NOT RIGHT',callback_data=f'deliverywrong:{oid}')]]))
        ctx.user_data.clear();await m.reply_text('Delivery video owner ko review ke liye bhej diya.');return
    if f=='payout_qr_wait' and m.photo:
        pid=ctx.user_data['payout_id'];p=await payouts.find_one({'payout_id':pid,'seller_id':uid,'status':'pending_qr'})
        if not p: await m.reply_text('Payout request nahi mili.');return
        raw=bytes(await (await m.photo[-1].get_file()).download_as_bytearray());mid=new_id('MED')
        await media.insert_one({'media_id':mid,'kind':'seller_payout_qr','payout_id':pid,'encrypted_data':encrypt(raw),'created_at':now()})
        await payouts.update_one({'payout_id':pid},{'$set':{'qr_media_id':mid,'status':'owner_payment_pending'}})
        await ctx.bot.send_photo(OWNER_ID,photo=raw,caption=f"PAYOUT REQUEST\n{pid}\nSeller: {uid}\nAmount: ₹{p['amount']:.2f}",reply_markup=K([[B('✅ DONE — I HAVE PAID',callback_data=f'payoutpaid:{pid}')],[B('Reject payout',callback_data=f'payoutreject:{pid}')]]))
        ctx.user_data.clear();await m.reply_text('QR owner ko bhej diya. Payment ke baad owner proof upload karega.');await log_action(uid,'seller_payout_qr_submitted',{'payout_id':pid,'amount':p['amount']});return
    if f=='owner_payout_proof' and m.photo and is_owner(uid):
        pid=ctx.user_data['payout_id'];p=await payouts.find_one({'payout_id':pid,'status':'awaiting_owner_proof'})
        if not p: await m.reply_text('Payout state invalid.');return
        raw=bytes(await (await m.photo[-1].get_file()).download_as_bytearray());mid=new_id('MED')
        await media.insert_one({'media_id':mid,'kind':'payout_receipt','payout_id':pid,'encrypted_data':encrypt(raw),'created_at':now()})
        await payouts.update_one({'payout_id':pid,'status':'awaiting_owner_proof'},{'$set':{'receipt_media_id':mid,'status':'paid','paid_at':now()}})
        await ctx.bot.send_photo(p['seller_id'],photo=raw,caption=f"Payout completed: {pid}\nAmount: ₹{p['amount']:.2f}")
        await log_action(uid,'payout_receipt_submitted',{'payout_id':pid,'amount':p['amount']})
        await ctx.bot.send_message(OWNER_ID,f'Payout {pid} marked paid and proof delivered to seller.')
        ctx.user_data.clear();await m.reply_text('Payout proof seller ko bhej diya aur payout paid mark ho gaya.');await log_action(uid,'payout_paid',{'payout_id':pid});return
    await m.reply_text('Is step par required media type bhejo (video/photo as instructed).')

def order_details(o,heading='ORDER'):
    return (f'{heading}\nOrder: {o["order_id"]}\nBuyer: {o["buyer_id"]}\nSeller: {o["seller_id"]}\n'
      f'Quantity: {o["qty"]}K\nRate: ₹{o["price_per_k"]}/1K\nTotal: ₹{o["total"]:.2f}\n'
      f'BGMI UID: {o["bgmi_uid"]}\nIGN: {o["ign"]}\nStatus: {o["status"]}')

def upi_qr(amount,oid):
    if not UPI_ID: raise RuntimeError('UPI_ID not configured')
    uri=f'upi://pay?pa={quote(UPI_ID)}&pn={quote(UPI_PAYEE_NAME)}&am={amount:.2f}&cu=INR&tn={quote("YASH UMPIRE "+oid)}'
    im=qrcode.make(uri);buf=io.BytesIO();im.save(buf,format='PNG');buf.seek(0);return buf

async def callback(update:Update,ctx:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query;await q.answer();uid=q.from_user.id;d=q.data
    user_doc=await users.find_one({'telegram_id':uid}) or {}
    if user_doc.get('suspended') and not is_owner(uid): await q.message.reply_text('Account restricted. Owner se contact karo.');return
    if d!='join:check' and not is_owner(uid) and not await force_join_ok(update,ctx):
        await q.message.reply_text('Pehle Force Join channel join karo.',reply_markup=K([[B('📢 Join Channel',url=FORCE_JOIN_URL or 'https://t.me/')],[B('✅ Check Join',callback_data='join:check')]]));return
    if d=='join:check':
        if await force_join_ok(update,ctx): await q.message.reply_text('Welcome!',reply_markup=main_menu(is_owner(uid)))
        else: await q.answer('Pehle channel join karo.',show_alert=True)
        return
    if d=='flow:cancel':
        ctx.user_data.clear();await q.message.reply_text('Current process cancel kar diya.',reply_markup=main_menu(is_owner(uid)));return
    if d=='menu:main': await q.message.reply_text('Main Menu',reply_markup=main_menu(is_owner(uid)));return
    if d=='buyer:begin':
        s=await settings.find_one({'key':'paused'})
        if s and s.get('value'): await q.message.reply_text('Marketplace temporarily paused hai.');return
        ctx.user_data.clear();ctx.user_data['flow']='buyer_qty';await q.message.reply_text('Kitni K Mix Popularity chahiye? Example 20K',reply_markup=cancel_kb());return
    if d=='seller:accept_rules':
        await users.update_one({'telegram_id':uid},{'$set':{'seller_rules_accepted_at':now()}},upsert=True)
        ctx.user_data['flow']='seller_name';await q.message.reply_text('Seller registration ke liye full name bhejo:');return
    if d=='seller:begin':
        u=await users.find_one({'telegram_id':uid}) or {}
        if u.get('seller_status')=='approved': await q.message.reply_text('Seller Dashboard',reply_markup=seller_kb());return
        if u.get('seller_status')=='pending': await q.message.reply_text('Tumhari seller application owner review mein hai.');return
        ctx.user_data.clear();await q.message.reply_text('Seller Rules\n1. Fake stock/scam strictly prohibited.\n2. Har stock registration aur additional stock par full proof video compulsory.\n3. Owner approval ke baad hi stock buyers ko dikhega.\n4. BGMI password/OTP kabhi share ya collect nahi karna.\n5. Payment/delivery disputes owner review karega.',reply_markup=K([[B('✅ I Accept Rules',callback_data='seller:accept_rules')],[B('❌ Cancel',callback_data='flow:cancel')]]));return
    if d=='buyer:confirm':
        lid=ctx.user_data.get('listing_id');qty=ctx.user_data.get('buyer_qty');listing=await listings.find_one({'listing_id':lid,'status':'approved'})
        if not listing or not await reserve_stock(lid,qty): await q.message.reply_text('Stock ab available nahi. Dobara seller list dekho.');ctx.user_data.clear();return
        total=round(qty*float(listing['price_per_k']),2);oid=new_id('YU')
        o={'order_id':oid,'buyer_id':uid,'seller_id':listing['seller_id'],'listing_id':lid,'qty':qty,'price_per_k':float(listing['price_per_k']),'bgmi_uid':ctx.user_data['bgmi_uid'],'ign':ctx.user_data['ign'],'buyer_phone':ctx.user_data.get('buyer_phone',''),'total':total,'status':'awaiting_payment_proof','stock_released':False,'stock_consumed':False,'created_at':now()}
        await orders.insert_one(o);await payments.insert_one({'order_id':oid,'amount':total,'status':'awaiting_utr','created_at':now()})
        try: qr=upi_qr(total,oid)
        except Exception as e:
            await release_stock(o);await orders.update_one({'order_id':oid},{'$set':{'status':'setup_error'}});await q.message.reply_text('Owner UPI configuration missing. Owner ko contact karo.');return
        ctx.user_data.update({'flow':'payment_confirm','order_id':oid})
        await q.message.reply_photo(qr,caption=f'Order {oid}\n{qty}K × ₹{listing["price_per_k"]}/1K = ₹{total:.2f}\nPayee: {UPI_PAYEE_NAME}\nUPI: {UPI_ID}\nPayment ke baad Confirm tap karo. QR payment success ka proof nahi hai.',reply_markup=K([[B('❌ Cancel',callback_data=f'buycancel:{oid}'),B('✅ Confirm Payment',callback_data=f'buyconfirm:{oid}')]]))
        await log_action(uid,'order_created',{'order_id':oid,'qty':qty,'seller_id':listing['seller_id'],'total':total});return
    if d.startswith('buycancel:'):
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'buyer_id':uid,'status':'awaiting_payment_proof'})
        if not o: await q.message.reply_text('Order cancel nahi ho sakta; owner se contact karo.');return
        await orders.update_one({'order_id':oid,'status':'awaiting_payment_proof'},{'$set':{'status':'cancelled','cancelled_at':now(),'cancelled_by':uid}})
        await release_stock(o)
        await ctx.bot.send_message(OWNER_ID,f'Buyer cancelled order {oid}. Check whether any payment reached the owner account; refund, if due, requires manual verification.')
        await q.message.reply_text('Order cancelled and reserved stock released. Agar tumne payment already kar di thi, turant owner se contact karo; refund manually verify hoga.')
        await log_action(uid,'buyer_cancelled_order',{'order_id':oid});return
    if d.startswith('buyconfirm:'):
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'buyer_id':uid,'status':'awaiting_payment_proof'})
        if not o: await q.answer('Order not in payment stage.',show_alert=True);return
        ctx.user_data.update({'flow':'payment_utr','order_id':oid});await q.message.reply_text('UTR/reference number bhejo:');return
    if d.startswith('listing:'):
        lid=d.split(':',1)[1];x=await listings.find_one({'listing_id':lid,'status':'approved','available_qty':{'$gte':ctx.user_data.get('buyer_qty',1)}})
        if not x: await q.message.reply_text('Listing unavailable.');return
        ctx.user_data.update({'listing_id':lid,'flow':'buyer_uid'});await q.message.reply_text('BGMI UID bhejo. Password/OTP kabhi mat bhejna.');return
    if d=='seller:addstock':
        u=await users.find_one({'telegram_id':uid}) or {}
        if u.get('seller_status')!='approved': await q.message.reply_text('Seller approval required.');return
        ctx.user_data.clear();ctx.user_data['flow']='stock_qty';await q.message.reply_text('Kitni K popularity available hai? Example 100K');return
    if d=='seller:stock':
        rows=await listings.find({'seller_id':uid}).sort('created_at',-1).to_list(50)
        await q.message.reply_text('\n'.join([f"{x['listing_id']} | {x['available_qty']}K available | {x['reserved_qty']}K reserved | ₹{x['price_per_k']}/1K | {x['status']}" for x in rows]) or 'No stock listings.');return
    if d=='seller:price':
        rows=await listings.find({'seller_id':uid,'status':'approved'}).to_list(50)
        if not rows: await q.message.reply_text('No approved listings.');return
        await q.message.reply_text('Jis listing ka price change karna hai uska ID bhejo:\n'+'\n'.join(f"{x['listing_id']} — {x['available_qty']}K — ₹{x['price_per_k']}/1K" for x in rows));ctx.user_data['flow']='price_listing_id';return
    if d=='seller:orders':
        rows=await orders.find({'seller_id':uid}).sort('created_at',-1).to_list(20)
        if not rows: await q.message.reply_text('No orders.');return
        for x in rows:
            kb=None
            if x.get('status')=='seller_received': kb=K([[B('🎥 Submit Delivery Proof',callback_data=f"proofstart:{x['order_id']}")]])
            elif x.get('status')=='delivery_not_right': kb=K([[B('🔁 Re-deliver & Submit Proof',callback_data=f"redeliver:{x['order_id']}")]])
            await q.message.reply_text(f"{x['order_id']} | {x['qty']}K | {x['status']}",reply_markup=kb)
        return
    if d=='seller:earnings':
        rows=await ledger.find({'seller_id':uid}).to_list(1000);gross=sum(x['gross'] for x in rows);fee=sum(x['total_fee'] for x in rows);net=sum(x['seller_net'] for x in rows)
        await q.message.reply_text(f'Total approved sales: ₹{gross:.2f}\nTotal fees (5%): ₹{fee:.2f}\nSeller eligible: ₹{net:.2f}');return
    if d=='seller:payout':
        rows=await ledger.find({'seller_id':uid}).to_list(1000);earned=sum(x['seller_net'] for x in rows)
        p=await payouts.find({'seller_id':uid,'status':{'$in':['pending_qr','owner_payment_pending','awaiting_owner_proof','paid']}}).to_list(1000)
        used=sum(x['amount'] for x in p);amount=round(earned-used,2)
        if amount<=0: await q.message.reply_text('Abhi payout-eligible balance nahi hai.');return
        pid=new_id('PO');await payouts.insert_one({'payout_id':pid,'seller_id':uid,'amount':amount,'status':'pending_qr','created_at':now()})
        ctx.user_data.update({'payout_id':pid});await q.message.reply_text(f'Payout request {pid}: ₹{amount:.2f}. QR bhejne ke liye button tap karo.',reply_markup=K([[B('📤 Send QR Code',callback_data=f'payoutupload:{pid}')]]));return
    if d.startswith('payoutupload:'):
        pid=d.split(':',1)[1];p=await payouts.find_one({'payout_id':pid,'seller_id':uid,'status':'pending_qr'})
        if not p: await q.message.reply_text('Payout QR request expire ya invalid hai.');return
        ctx.user_data.update({'flow':'payout_qr_wait','payout_id':pid});await q.message.reply_text('Apna payout QR image bhejo.');return
    if d=='profile':
        u=await users.find_one({'telegram_id':uid}) or {};await q.message.reply_text(f"Telegram ID: {uid}\nName: {u.get('display_name',u.get('first_name',''))}\nPhone: {u.get('phone','Not shared')}\nRole: {u.get('role','buyer')}\nSeller status: {u.get('seller_status','not applied')}");return
    if d=='contact':
        if OWNER_CONTACT.startswith('https://') or OWNER_CONTACT.startswith('http://'):
            await q.message.reply_text('Owner se contact karo:',reply_markup=K([[B('☎️ Contact Owner',url=OWNER_CONTACT)]]))
        else: await q.message.reply_text(f'Owner contact: {OWNER_CONTACT or "Not configured"}')
        return
    if d=='orders:mine':
        rows=await orders.find({'$or':[{'buyer_id':uid},{'seller_id':uid}]}).sort('created_at',-1).to_list(20)
        
        if not rows: await q.message.reply_text('No orders.');return
        for x in rows:
            await q.message.reply_text(f"{x['order_id']} | {x['qty']}K | ₹{x['total']:.2f} | {x['status']}",reply_markup=K([[B('Open dispute',callback_data=f"dispute:{x['order_id']}")]]))
        return
    # Every owner callback is guarded by Telegram owner ID and panel password session.
    if d in OWNER_ACTIONS:
        if not is_owner(uid): return
        if d=='owner:open': ctx.user_data['flow']='owner_password';await q.message.reply_text('Owner password enter karo:');return
        if not ctx.user_data.get('owner_authenticated'): await q.message.reply_text('Pehle /owner se authenticate karo.');return
        await owner_callback(q,ctx,d);return
    if d.startswith(('sellerapprove:','sellerreject:','listingapprove:','listingreject:','payapprove:','payreject:','sellerreceive:','sellercancel:','deliverydone:','deliverywrong:','payoutpaid:','payoutreject:','ownerrelease:','redeliver:','proofstart:','usersuspend:')):
        if not is_owner(uid) and not d.startswith(('sellerreceive:','sellercancel:','redeliver:','proofstart:')): return
        await action_callback(q,ctx,d,uid);return
    if d.startswith('sellerreceive:') or d.startswith('sellercancel:'):
        await action_callback(q,ctx,d,uid);return
    if d.startswith('dispute:'):
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'$or':[{'buyer_id':uid},{'seller_id':uid}]})
        if not o: await q.message.reply_text('Order not found.');return
        ctx.user_data.update({'flow':'dispute_reason','dispute_order':oid});await q.message.reply_text('Dispute ka reason bhejo:');return
    await q.answer('Unknown button. /start try karo.',show_alert=True)

async def owner_callback(q,ctx,d):
    if d=='owner:stats':
        vals={'Users':await users.count_documents({}),'Sellers':await users.count_documents({'seller_status':'approved'}),'Pending applications':await seller_apps.count_documents({'status':'pending'}),'Pending stock':await listings.count_documents({'status':'pending_review'}),'Orders':await orders.count_documents({}),'Payment reviews':await orders.count_documents({'status':'payment_review'}),'Delivery reviews':await orders.count_documents({'status':'delivery_review'}),'Payouts':await payouts.count_documents({'status':{'$in':['pending_qr','owner_payment_pending','awaiting_owner_proof']}})}
        await q.message.reply_text('\n'.join(f'{k}: {v}' for k,v in vals.items()));return
    if d=='owner:users':
        rows=await users.find({}).sort('created_at',-1).to_list(25);
        if not rows: await q.message.reply_text('No users.');return
        for x in rows:
            suspended=bool(x.get('suspended'))
            await q.message.reply_text(f"{x['telegram_id']} | {x.get('display_name',x.get('first_name',''))} | {x.get('seller_status','buyer')} | phone={x.get('phone','-')} | suspended={suspended}",reply_markup=K([[B('Restore' if suspended else 'Suspend',callback_data=f"usersuspend:{x['telegram_id']}")]]))
        return
    if d=='owner:apps':
        rows=await seller_apps.find({'status':'pending'}).to_list(30)
        if not rows: await q.message.reply_text('No pending applications.');return
        for x in rows: await q.message.reply_text(f"Seller {x['telegram_id']}\n{x['full_name']}\nPhone: {x['phone']}",reply_markup=K([[B('Approve',callback_data=f"sellerapprove:{x['telegram_id']}"),B('Reject',callback_data=f"sellerreject:{x['telegram_id']}")]]))
        return
    if d=='owner:listings':
        rows=await listings.find({'status':'pending_review'}).to_list(30)
        if not rows: await q.message.reply_text('No pending listings.');return
        for x in rows: await q.message.reply_text(f"{x['listing_id']} | seller {x['seller_id']} | {x['total_qty']}K | ₹{x['price_per_k']}/1K",reply_markup=K([[B('Approve',callback_data=f"listingapprove:{x['listing_id']}"),B('Reject',callback_data=f"listingreject:{x['listing_id']}")]]))
        return
    if d=='owner:orders':
        rows=await orders.find({}).sort('created_at',-1).to_list(25)
        if not rows: await q.message.reply_text('No orders.');return
        for x in rows:
            buttons=[]
            if x.get('status') in ('awaiting_payment_proof','cancellation_requested','payment_rejected','seller_cancel_requested','seller_cancelled') and not x.get('stock_released'):
                buttons.append([B('Release reserved stock',callback_data=f"ownerrelease:{x['order_id']}")])
            await q.message.reply_text(order_details(x),reply_markup=K(buttons) if buttons else None)
        return
    if d=='owner:payments':
        rows=await orders.find({'status':'payment_review'}).to_list(25)
        for x in rows: await q.message.reply_text(order_details(x,'PAYMENT REVIEW'),reply_markup=K([[B('Approve',callback_data=f"payapprove:{x['order_id']}"),B('Reject',callback_data=f"payreject:{x['order_id']}")]]))
        if not rows: await q.message.reply_text('No payment reviews.');return
    if d=='owner:disputes':
        rows=await disputes.find({'status':'open'}).sort('created_at',-1).to_list(30)
        await q.message.reply_text('\n\n'.join(f"{x['order_id']} | by {x['raised_by']}\n{x['reason']}" for x in rows) or 'No open disputes.');return
    if d=='owner:deliveries':
        rows=await orders.find({'status':'delivery_review'}).to_list(25)
        for x in rows: await q.message.reply_text(order_details(x,'DELIVERY REVIEW'),reply_markup=K([[B('DONE',callback_data=f"deliverydone:{x['order_id']}"),B('NOT RIGHT',callback_data=f"deliverywrong:{x['order_id']}")]]))
        if not rows: await q.message.reply_text('No delivery reviews.');return
    if d=='owner:payouts':
        rows=await payouts.find({'status':{'$in':['pending_qr','owner_payment_pending','awaiting_owner_proof']}}).to_list(30)
        await q.message.reply_text('\n'.join(f"{x['payout_id']} | seller {x['seller_id']} | ₹{x['amount']:.2f} | {x['status']}" for x in rows) or 'No pending payouts.');return
    if d=='owner:finance':
        rows=await ledger.find({}).to_list(10000);gross=sum(x['gross'] for x in rows);fees=sum(x['total_fee'] for x in rows);net=sum(x['seller_net'] for x in rows)
        await q.message.reply_text(f'Gross approved sales: ₹{gross:.2f}\nFees: ₹{fees:.2f}\nSeller net: ₹{net:.2f}');return
    if d=='owner:settings': await q.message.reply_text(f'Force Join: {FORCE_JOIN_CHANNEL or "OFF"}\nRecords channel: {RECORDS_CHANNEL_ID or "OFF"}\nUPI: {UPI_ID or "NOT SET"}\nContact: {OWNER_CONTACT or "NOT SET"}');return
    if d=='owner:pause': await settings.update_one({'key':'paused'},{'$set':{'value':True}},upsert=True);await q.message.reply_text('Marketplace paused.');return
    if d=='owner:resume': await settings.update_one({'key':'paused'},{'$set':{'value':False}},upsert=True);await q.message.reply_text('Marketplace resumed.');return
    if d=='owner:backup':
        from backup import create_backup
        try: await q.message.reply_text(f'Encrypted backup: {await create_backup(ctx.application)}')
        except Exception as e: await q.message.reply_text(f'Backup failed: {type(e).__name__}')
        return
    if d=='owner:broadcast': ctx.user_data['flow']='broadcast';await q.message.reply_text('Broadcast message bhejo:');return

async def action_callback(q,ctx,d,uid):
    if d.startswith('usersuspend:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        target=int(d.split(':',1)[1])
        if target==OWNER_ID: await q.message.reply_text('Owner account suspend nahi kar sakte.');return
        user=await users.find_one({'telegram_id':target}) or {};new_state=not bool(user.get('suspended'))
        await users.update_one({'telegram_id':target},{'$set':{'suspended':new_state,'suspended_at':now() if new_state else None}})
        await q.message.reply_text(f'User {target}: '+('suspended' if new_state else 'restored'));await log_action(uid,'user_suspended' if new_state else 'user_restored',{'user_id':target});return
    if d.startswith('ownerrelease:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'status':{'$in':['awaiting_payment_proof','cancellation_requested','payment_rejected','seller_cancel_requested','seller_cancelled']}})
        if not o: await q.message.reply_text('Order release review state mein nahi hai.');return
        released=await release_stock(o)
        await orders.update_one({'order_id':oid},{'$set':{'stock_release_approved_by':uid,'stock_released_at':now()}})
        await q.message.reply_text('Reserved stock release ho gaya.' if released else 'Stock pehle hi release ho chuka hai.')
        await log_action(uid,'stock_released_after_review',{'order_id':oid});return
    if d.startswith('proofstart:'):
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'seller_id':uid,'status':'seller_received'})
        if not o: await q.message.reply_text('Order proof stage mein nahi hai.');return
        ctx.user_data.update({'flow':'seller_delivery_video','delivery_order':oid});await q.message.reply_text('Delivery video proof upload karo.');return
    if d.startswith('redeliver:'):
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'seller_id':uid,'status':'delivery_not_right'})
        if not o: await q.message.reply_text('Re-delivery request available nahi.');return
        await orders.update_one({'order_id':oid,'status':'delivery_not_right'},{'$set':{'status':'seller_received','redelivery_requested_at':now()}})
        ctx.user_data.update({'flow':'seller_delivery_video','delivery_order':oid})
        await q.message.reply_text(f'Order {oid} ke liye popularity re-deliver karo, phir naya video proof bhejo.');return
    if d.startswith('sellerapprove:') or d.startswith('sellerreject:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        approve=d.startswith('sellerapprove:');sid=int(d.split(':',1)[1]);status='approved' if approve else 'rejected'
        r=await seller_apps.update_one({'telegram_id':sid,'status':'pending'},{'$set':{'status':status,'reviewed_at':now(),'reviewed_by':uid}})
        if r.modified_count:
            await users.update_one({'telegram_id':sid},{'$set':{'seller_status':status,'role':'seller' if approve else 'buyer'}})
            await ctx.bot.send_message(sid,'Seller application approved. /sellerpanel open karo.' if approve else 'Seller application rejected.')
            await q.message.reply_text(f'Seller {status}.');await log_action(uid,'seller_'+status,{'seller_id':sid})
        return
    if d.startswith('listingapprove:') or d.startswith('listingreject:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        lid=d.split(':',1)[1];status='approved' if d.startswith('listingapprove:') else 'rejected'
        r=await listings.update_one({'listing_id':lid,'status':'pending_review'},{'$set':{'status':status,'reviewed_at':now()}})
        await q.message.reply_text(f'Listing {status}.' if r.modified_count else 'Listing not pending.');await log_action(uid,'listing_'+status,{'listing_id':lid});return
    if d.startswith('buy'): return
    if d.startswith('payapprove:') or d.startswith('payreject:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'status':'payment_review'})
        if not o: await q.message.reply_text('Payment review no longer pending.');return
        approve=d.startswith('payapprove:')
        if approve:
            await orders.update_one({'order_id':oid,'status':'payment_review'},{'$set':{'status':'payment_verified','payment_verified_at':now()}})
            await payments.update_one({'order_id':oid},{'$set':{'status':'owner_verified','verified_by':uid,'verified_at':now()}})
            await ctx.bot.send_message(o['seller_id'],order_details(o,'NEW PAID ORDER'),reply_markup=K([[B('📥 Receive Order',callback_data=f'sellerreceive:{oid}'),B('❌ Cancel / Report',callback_data=f'sellercancel:{oid}')]]))
            await ctx.bot.send_message(o['buyer_id'],f'Payment verified for {oid}. Seller ko order bhej diya.')
            await q.message.reply_text('Payment verified; seller notified.')
        else:
            await orders.update_one({'order_id':oid,'status':'payment_review'},{'$set':{'status':'payment_rejected','payment_rejected_at':now()}})
            await payments.update_one({'order_id':oid},{'$set':{'status':'rejected'}})
            await ctx.bot.send_message(o['buyer_id'],f'Payment not approved for {oid}. Owner se contact karo. Stock owner review ke baad release hoga.')
            await q.message.reply_text('Payment rejected.');
        await log_action(uid,'payment_'+('approved' if approve else 'rejected'),{'order_id':oid});return
    if d.startswith('sellerreceive:') or d.startswith('sellercancel:'):
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'seller_id':uid,'status':'payment_verified'})
        if not o: await q.message.reply_text('Order ab receive/cancel state mein nahi hai.');return
        if d.startswith('sellerreceive:'):
            await orders.update_one({'order_id':oid,'status':'payment_verified'},{'$set':{'status':'seller_received','received_at':now()}})
            await log_action(uid,'seller_received_order',{'order_id':oid})
            await ctx.bot.send_message(o['buyer_id'],f'Seller ne order {oid} receive kar liya hai.')
            await q.message.reply_text('Order received. Popularity deliver karne ke baad delivery video submit karo.')
            ctx.user_data.update({'flow':'seller_delivery_video','delivery_order':oid})
            await q.message.reply_text('Delivery video proof upload karo.');return
        await orders.update_one({'order_id':oid,'status':'payment_verified'},{'$set':{'status':'seller_cancel_requested'}})
        await log_action(uid,'seller_cancel_requested',{'order_id':oid})
        await ctx.bot.send_message(OWNER_ID,f'Seller cancel/report requested: {oid}. Review required.')
        await q.message.reply_text('Cancel/report owner ko bhej diya.');return
    if d.startswith('deliverydone:') or d.startswith('deliverywrong:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        oid=d.split(':',1)[1];o=await orders.find_one({'order_id':oid,'status':'delivery_review'})
        if not o: await q.message.reply_text('Delivery review no longer pending.');return
        if d.startswith('deliverywrong:'):
            ctx.user_data.update({'flow':'delivery_reason','review_order':oid});await q.message.reply_text('NOT RIGHT ka reason likho:');return
        r=await orders.update_one({'order_id':oid,'status':'delivery_review'},{'$set':{'status':'delivered','delivery_approved_at':now()}})
        if not r.modified_count: return
        await consume_stock(o);gross,fee,net=await make_ledger(o)
        await ctx.bot.send_message(o['buyer_id'],f'✅ Delivered your order!\nOrder: {oid}\nQuantity: {o["qty"]}K\nTotal: ₹{gross:.2f}\nYour order is confirmed and done.')
        await ctx.bot.send_message(o['seller_id'],f'Delivery approved.\nGross: ₹{gross:.2f}\nPlatform 1%: ₹{fee_split(gross)['platform_fee']:.2f}\nMaintenance 1%: ₹{fee_split(gross)['maintenance_fee']:.2f}\nOwner 3%: ₹{fee_split(gross)['owner_fee']:.2f}\nTotal fees: ₹{fee:.2f}\nYour eligible earning: ₹{net:.2f}\nPayout request dashboard se karo.')
        await q.message.reply_text(f'DONE. Seller eligible ₹{net:.2f}.');await log_action(uid,'delivery_done',{'order_id':oid,'seller_net':net});return
    if d.startswith('payoutpaid:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        pid=d.split(':',1)[1];p=await payouts.find_one({'payout_id':pid,'status':'owner_payment_pending'})
        if not p: await q.message.reply_text('Payout not ready.');return
        await payouts.update_one({'payout_id':pid,'status':'owner_payment_pending'},{'$set':{'status':'awaiting_owner_proof','payment_marked_by':uid,'payment_marked_at':now()}})
        ctx.user_data.update({'flow':'owner_payout_proof','payout_id':pid});await q.message.reply_text(f'Payout {pid}: transfer verify karne ke baad payment screenshot upload karo.');return
    if d.startswith('payoutreject:'):
        if not is_owner(uid) or not ctx.user_data.get('owner_authenticated'): return
        pid=d.split(':',1)[1];p=await payouts.find_one({'payout_id':pid,'status':{'$in':['pending_qr','owner_payment_pending']}})
        if p:
            await payouts.update_one({'payout_id':pid},{'$set':{'status':'rejected','rejected_at':now()}})
            await ctx.bot.send_message(p['seller_id'],f'Payout {pid} rejected. Contact owner.')
        return

async def flush_events(ctx):
    if not RECORDS_CHANNEL_ID:return
    batch=await events.find({'sent':False}).sort('created_at',1).to_list(40)
    if not batch:return
    lines=['YASH UMPIRE — ADMIN ACTIVITY BATCH']
    for x in batch: lines.append(f"{x['created_at'].strftime('%Y-%m-%d %H:%M UTC')} | actor {x['actor_id']} | {x['summary']} | {json.dumps(x.get('details',{}),ensure_ascii=False,default=str)[:700]}")
    try:
        await ctx.bot.send_message(int(RECORDS_CHANNEL_ID),'\n'.join(lines))
        await events.update_many({'_id':{'$in':[x['_id'] for x in batch]}},{'$set':{'sent':True}})
    except Exception: pass
