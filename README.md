# YASH UMPIRE — BGMI Mix Popularity Telegram Bot

Telegram-only Python bot with MongoDB storage. There is **no website** and the only buyer product currently enabled is **Mix Popularity**.

## Included workflows

### Buyer
- `/start` registration, force-join check, Buy Popularity → Mix Popularity.
- Quantity-based search of approved stock that can fulfil the full order.
- Seller name, available quantity and per-1K price shown as buttons.
- BGMI UID + IGN + buyer phone contact collection and buyer confirmation.
- UPI QR generated for the exact amount using configured owner UPI ID.
- Buyer taps Confirm, submits UTR and payment screenshot.
- Owner independently verifies actual payment credit before approving.
- Buyer can request cancellation before payment; owner reviews before releasing reserved stock.
- My Orders and dispute request button.

### Seller
- Registration with full name and Telegram contact-share phone number; owner approval required.
- Seller rules and stock video proof requirement.
- Register stock / add stock with quantity, per-1K price and video proof.
- Owner approves stock before it appears to buyers.
- My Stock, price update, My Orders, My Earnings and Payout Request.
- Seller receives paid order with Receive and Cancel/Report buttons.
- Delivery proof video; owner DONE / NOT RIGHT review; reason and re-delivery flow.
- Payout QR submission; owner manually pays, then submits payment screenshot for seller.

### Owner
- Password-protected panel plus Telegram owner-ID check.
- Dashboard, user list and suspend/restore, seller applications, stock review, orders, payment reviews, disputes, delivery reviews, payouts, finance, settings, pause/resume, backup and broadcast.
- Payment approval only after checking the actual authorized payment account.
- Delivery approval calculates 1% platform + 1% maintenance + 3% owner fees (5% total).
- Stock reservation prevents the same available quantity being offered twice; stock is consumed after owner-approved delivery.
- Cancellation/rejection stock release requires owner action.

### Records and backup
- MongoDB stores structured user, seller, stock, order, payment, payout, media metadata and audit records.
- Activity summaries are batched to the private records channel every 60 seconds. Summaries include operational event details but intentionally do not publish phone numbers, UTRs, screenshots or videos to the channel.
- Payment screenshots, stock videos, delivery videos, payout QR images and payout receipts are encrypted before being stored in MongoDB.
- Daily encrypted database export is uploaded to the records channel when configured.

## Phone-friendly setup

1. Create a Telegram bot using BotFather and copy the bot token.
2. Create a MongoDB Atlas database and copy its connection URI. Add your hosting provider's IP access as required by your Atlas setup.
3. Create two private/public Telegram channels as appropriate: Force Join and private Records. Add the bot as admin in both. Give it permission to check membership in the Force Join channel and post documents/messages in the Records channel.
4. Upload this folder to a private GitHub repository from your phone. Do **not** upload `.env`, backups, encryption keys or payment screenshots.
5. On a Python hosting service, set the start command to `python main.py` and install from `requirements.txt`.
6. Add environment variables from `.env.example` in the host's secret/environment settings. Never paste secrets into source files or public chat.
7. Generate a Fernet key in a trusted Python terminal:

   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

   Put the generated key into `ENCRYPTION_KEY`. Keep a separate offline copy. If this key is lost, encrypted media/backups cannot be decrypted.
8. Start the bot. Check the host logs for `YASH UMPIRE started`.
9. From the owner Telegram account, run `/owner`, enter `OWNER_PANEL_PASSWORD`, then use the owner panel to review applications and stock.
10. Test with dummy data and a test UPI arrangement before considering any real transaction.

## Required environment variables

See `.env.example`. `BOT_TOKEN`, `MONGODB_URI`, `OWNER_ID`, `OWNER_PANEL_PASSWORD`, and `ENCRYPTION_KEY` are required. Configure `UPI_ID`, `FORCE_JOIN_CHANNEL`, `FORCE_JOIN_URL`, `RECORDS_CHANNEL_ID`, and `OWNER_CONTACT` before enabling the marketplace.

## Important operational and security limits

- This code has not been tested against your live Telegram bot, MongoDB cluster, hosting provider or real UPI account. Syntax/static checks do not prove live end-to-end correctness.
- Telegram bots do not have end-to-end encrypted chats. When media is sent to the owner for review, Telegram carries a plaintext copy even though a separately stored MongoDB copy is encrypted at rest.
- The records channel receives activity summaries, not a transcript of every private message. Telegram bots cannot read users' other private conversations. Keep personal phone numbers, UTRs and evidence restricted to the owner and database.
- UPI QR generation only creates a payment request. It cannot independently verify payment. Owner must check the actual authorized account transaction record. Do not rely on screenshot/UTR alone.
- MongoDB multi-document workflows are not a full distributed transaction. The code uses conditional state changes and idempotent stock/ledger guards, but production use needs a live concurrency/security audit and failure-recovery tests.
- Backup creation is implemented; automatic restore is deliberately not exposed as a one-tap bot command. Restore must be tested offline against a separate database by a competent operator.
- A human owner must supervise disputes, cancellations, refunds, payout and seller evidence. Never collect BGMI passwords or OTPs.
- Real-money operation, UPI accounts and seller payouts require parent/guardian supervision and compliance with applicable platform, payment-provider and local rules.

## Quick checks

Run:

```bash
python -m py_compile *.py
python self_check.py
python -m unittest test_logic.py
```

A passing static check is not a substitute for a Telegram/MongoDB staging test.
