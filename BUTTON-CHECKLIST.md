# Button and workflow checklist

## Main menu
- Buy Popularity → quantity → seller/rate list → UID → IGN → confirm → UPI QR → Cancel/Confirm → UTR → screenshot.
- Sell Popularity → name → own contact → pending owner approval.
- My Orders → list + dispute action.
- My Profile.
- Contact Owner.
- Owner Panel (owner account only) → password.

## Seller dashboard
- Register Your Popularity / Add More Stock → quantity → price per 1K → video proof → owner approve/reject.
- My Stock.
- Update Price.
- My Orders → Submit Delivery Proof / Re-deliver when applicable.
- My Earnings.
- Payout Request → seller QR → owner manually pays → owner proof upload → seller receives proof.
- My Profile / Contact Owner / Main Menu.

## Owner panel
- Dashboard.
- Users → suspend/restore.
- Seller Applications → approve/reject.
- Stock Reviews → approve/reject.
- Orders → release reserved stock after owner reconciliation for eligible cancelled/rejected cases.
- Payments → approve/reject after actual payment verification.
- Disputes.
- Delivery Reviews → DONE / NOT RIGHT → reason → seller re-delivery.
- Payouts.
- Finance.
- Settings.
- Pause / Resume.
- Backup Now.
- Broadcast.

## Manual acceptance test sequence
1. Start as buyer; confirm Telegram user record in MongoDB.
2. Verify Force Join blocks non-members and allows joined users.
3. Register a seller, share own contact, approve from owner panel.
4. Register stock with video; approve it; verify listing appears to buyers.
5. Buyer requests quantity; confirm only sellers with sufficient stock are shown.
6. Select seller; confirm UID/IGN; inspect generated amount QR with a test payment setup.
7. Submit UTR and screenshot; verify owner receives full order details and proof.
8. Owner approves; verify only selected seller receives order.
9. Seller taps Receive; submit delivery video; owner reviews.
10. Test NOT RIGHT reason and seller re-delivery; then DONE.
11. Verify 1% + 1% + 3% fee math and stock quantity deduction.
12. Seller requests payout, submits QR; owner completes test transfer and uploads proof.
13. Test cancellation/rejection stock release, disputes, suspend/restore, pause/resume, backup and records batching.

This checklist describes test steps; it does not claim those live tests have already been run.
