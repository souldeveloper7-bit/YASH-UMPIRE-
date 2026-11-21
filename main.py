import logging
from datetime import time
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import *
from database import init_db
from handlers import start, help_command, myorders, seller_panel, owner_panel, callback, text_handler, contact_handler, media_handler, flush_events
from backup import create_backup

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log=logging.getLogger('yash-umpire')
async def post_init(app):
    await init_db()
    app.job_queue.run_repeating(flush_events,interval=EVENT_BATCH_SECONDS,first=10)
    hh,mm=map(int,BACKUP_TIME_UTC.split(':'))
    async def daily(ctx):
        try: await create_backup(ctx.application);log.info('Daily encrypted backup completed')
        except Exception: log.exception('Daily backup failed')
    app.job_queue.run_daily(daily,time=time(hour=hh,minute=mm))
    log.info('YASH UMPIRE started')
async def error_handler(update,ctx): log.exception('Unhandled Telegram update',exc_info=ctx.error)
def main():
    app=Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler('start',start));app.add_handler(CommandHandler('help',help_command))
    app.add_handler(CommandHandler('myorders',myorders));app.add_handler(CommandHandler('sellerpanel',seller_panel));app.add_handler(CommandHandler('owner',owner_panel))
    app.add_handler(CallbackQueryHandler(callback))
    app.add_handler(MessageHandler(filters.CONTACT,contact_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO,media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text_handler))
    app.add_error_handler(error_handler)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__': main()
