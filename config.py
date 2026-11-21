import os
from dotenv import load_dotenv
load_dotenv()

def required(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise RuntimeError(f'Missing required .env setting: {name}')
    return value

BOT_TOKEN = required('BOT_TOKEN')
MONGODB_URI = required('MONGODB_URI')
OWNER_ID = int(required('OWNER_ID'))
OWNER_PANEL_PASSWORD = required('OWNER_PANEL_PASSWORD')
ENCRYPTION_KEY = required('ENCRYPTION_KEY')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'yash_umpire')
OWNER_CONTACT = os.getenv('OWNER_CONTACT', '')
FORCE_JOIN_CHANNEL = os.getenv('FORCE_JOIN_CHANNEL', '')
FORCE_JOIN_URL = os.getenv('FORCE_JOIN_URL', '')
RECORDS_CHANNEL_ID = os.getenv('RECORDS_CHANNEL_ID', '')
UPI_ID = os.getenv('UPI_ID', '')
UPI_PAYEE_NAME = os.getenv('UPI_PAYEE_NAME', 'YASH UMPIRE')
BACKUP_DIR = os.getenv('BACKUP_DIR', './backups')
BACKUP_TIME_UTC = os.getenv('BACKUP_TIME_UTC', '20:00')
BACKUP_KEEP_DAYS = int(os.getenv('BACKUP_KEEP_DAYS', '30'))
EVENT_BATCH_SECONDS = int(os.getenv('EVENT_BATCH_SECONDS', '60'))
