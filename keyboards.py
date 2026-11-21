from telegram import InlineKeyboardButton as B, InlineKeyboardMarkup as K

def main_menu(owner=False):
    rows=[[B('🛒 Buy Popularity',callback_data='buyer:begin')],
          [B('🏪 Sell Popularity',callback_data='seller:begin')],
          [B('📦 My Orders',callback_data='orders:mine'),B('👤 My Profile',callback_data='profile')],
          [B('☎️ Contact Owner',callback_data='contact')]]
    if owner: rows.append([B('🔐 Owner Panel',callback_data='owner:open')])
    return K(rows)
def cancel_kb(): return K([[B('❌ Cancel',callback_data='flow:cancel')]])
def seller_kb():
    return K([[B('➕ Register Your Popularity',callback_data='seller:addstock')],
      [B('➕ Add More Stock',callback_data='seller:addstock')],
      [B('📦 My Stock',callback_data='seller:stock'),B('💰 Update Price',callback_data='seller:price')],
      [B('🧾 My Orders',callback_data='seller:orders'),B('💵 My Earnings',callback_data='seller:earnings')],
      [B('🏧 Payout Request',callback_data='seller:payout')],
      [B('👤 My Profile',callback_data='profile'),B('☎️ Contact Owner',callback_data='contact')],
      [B('⬅️ Main Menu',callback_data='menu:main')]])
def owner_kb():
    return K([[B('📊 Dashboard',callback_data='owner:stats'),B('👥 Users',callback_data='owner:users')],
      [B('📝 Seller Applications',callback_data='owner:apps'),B('📦 Stock Reviews',callback_data='owner:listings')],
      [B('🧾 Orders',callback_data='owner:orders'),B('💳 Payments',callback_data='owner:payments')],
      [B('⚖️ Disputes',callback_data='owner:disputes')],
      [B('🎥 Delivery Reviews',callback_data='owner:deliveries'),B('🏧 Payouts',callback_data='owner:payouts')],
      [B('💰 Finance',callback_data='owner:finance'),B('⚙️ Settings',callback_data='owner:settings')],
      [B('⏸ Pause',callback_data='owner:pause'),B('▶️ Resume',callback_data='owner:resume')],
      [B('💾 Backup Now',callback_data='owner:backup'),B('📢 Broadcast',callback_data='owner:broadcast')],
      [B('⬅️ Main Menu',callback_data='menu:main')]])
