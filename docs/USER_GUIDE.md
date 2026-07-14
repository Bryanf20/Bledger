# Bledger User Guide

*For shop owners, managers, and cashiers. No technical knowledge needed.*

Bledger is your shop's till, stock book, and sales record in one app. It works completely offline — no internet is required for daily use.

---

## 1. Who can do what

Bledger has three kinds of accounts:

| | Owner | Manager | Cashier |
|---|---|---|---|
| Sell at the POS | ✅ | ✅ | ✅ |
| See own sales history | ✅ | ✅ | ✅ (own sales only) |
| View stock levels | ✅ | ✅ | ✅ (view only) |
| Add/edit products, adjust stock | ✅ | ✅ | ❌ |
| Void (cancel) a sale | ✅ | ✅ | ❌ |
| Suppliers & purchases | ✅ | ✅ | ❌ |
| Dashboard (revenue, reports) | ✅ | ✅ | ❌ (stock alerts only) |
| Create staff accounts | ✅ | ❌ | ❌ |

Owners and managers log in with a **username and password**. Cashiers log in with a **4-digit PIN** — fast enough for shift changes at the till.

---

## 2. First-time setup

The first time Bledger opens on a new install, it walks you through a 3-step wizard:

1. **Business** — enter your business name, branch name, address, phone, and the message you'd like printed at the bottom of receipts.
2. **Products** — optionally pick a starter template (Provision Store, Boutique, Cosmetics, or Electronics) to pre-load common products and categories. You can also skip this and add products yourself later.
3. **Account** — create the owner account: your name, username, and password. You can also set an optional 4-digit PIN for quick access.

When you finish, you're logged in as the owner and ready to sell. The wizard only runs once — after that, the app always opens at the login screen.

### Adding staff

Only the owner can create staff accounts. A **cashier** account needs a name, username, and a 4-digit PIN. A **manager** account needs a name, username, and password.

---

## 3. Logging in and out

- **Owner / Manager:** enter your username and password.
- **Cashier:** enter your username, then your 4-digit PIN on the keypad.

To log out, open the user menu in the top bar of any screen and choose log out. Always log out when handing the till to someone else — every sale is recorded under the name of whoever is logged in.

---

## 4. Making a sale (POS)

1. Open **POS** from the navigation rail.
2. Tap products in the grid to add them to the cart. Tap again (or use the + / − controls in the cart) to change quantities. Products that are out of stock can't be sold.
3. **Bulk prices apply automatically** — if a product has a bulk price and the quantity reaches the bulk minimum, the lower price is used. You don't have to do anything.
4. Choose the payment method: **Cash**, **MTN MoMo**, **Orange Money**, or **Other**.
   - For Mobile Money, enter the **transaction reference** from the customer's phone and tick **"Payment confirmed on phone"**. The sale cannot be completed without both — this protects you from fake payment screens.
5. Complete the sale. Stock is reduced immediately and the receipt screen opens.

### Holding a sale

If a customer steps away mid-sale, use **Hold** — the cart is saved with an optional label (e.g. "Woman in red dress") and you can serve the next customer. Restore it later from the held-sales drawer. Held sales are temporary and disappear once restored.

### If the sale won't complete

- *"Insufficient stock"* — someone bought the last units while this cart was open. Adjust the quantity.
- Mobile Money fields missing — enter the reference and tick the confirmation box.

---

## 5. Receipts

After each sale, the receipt screen shows the sale with its reference number (e.g. **BLD-2026-0042**). From here you can print or download the receipt as a PDF (80mm format, made for receipt printers). Customers can be given the reference number for any later questions.

---

## 6. Sales history

Open **Sales** to see past sales. You can filter by date range, payment method, and status, or search by receipt reference. Cashiers see only their own sales; managers and owners see everything.

### Voiding (cancelling) a sale — manager/owner only

If a sale was a mistake, open it in Sales history and choose **Void**. You must give a reason. Voiding puts the stock back on the shelf and removes the sale from revenue figures, but the record itself is kept permanently, marked "Voided", with who voided it and why. A sale can only be voided once, and voids cannot be undone.

---

## 7. Inventory (stock)

Open **Inventory** to see all products, their prices, and stock levels. Each product shows a stock status: **OK**, **Low** (at or below its alert threshold), or **Out**.

Managers and owners can:

- **Add a product** — name, category, unit, retail price, and optionally a bulk price with its minimum quantity (both must be set together).
- **Edit a product** — prices, category, threshold, etc. Stock level can never be typed in directly; it only moves through adjustments, sales, and purchases, so the record always stays honest.
- **Adjust stock** — choose *Add* (restock), *Remove* (damage, expiry), or *Correction* (count discrepancy). A reason is always required. Every adjustment is saved permanently with before/after quantities and who made it — this is your audit trail.
- **Deactivate a product** — products are never deleted, so old receipts stay correct. A deactivated product disappears from the POS but stays in history. It can be reactivated later.

Cashiers can see everything on this screen but cannot change anything.

---

## 8. Suppliers & purchases (manager/owner only)

Open **Suppliers** to keep a directory of the people you buy from and a record of every purchase.

- **Add a supplier** — name, phone, area, notes.
- **Record a purchase** — pick the supplier, the date, and the products bought (quantity and unit cost). Recording a purchase **automatically adds the stock** — no separate stock adjustment needed.
- **Payment tracking** — enter what you paid at the time. The purchase is marked **Paid**, **Partial**, or **Credit** automatically. For partial/credit purchases, use **Record payment** later to log each installment; the balance owed updates and the full payment history is kept per purchase.

A recorded purchase can't be edited or deleted — like a sale, it's a permanent financial record.

---

## 9. Dashboard (manager/owner)

Open **Dashboard** for the business overview, switchable between **Today**, **This week**, and **This month**:

- Revenue, number of sales, and average sale — each compared to the previous period.
- Sales chart (by hour for today, by day for week/month).
- Payment breakdown — how much came in as Cash vs MTN MoMo vs Orange Money.
- Top products by revenue.
- **Stock alerts** — products at or below their low-stock threshold. This is the one dashboard item cashiers can also see.
- Exportable reports (sales, products, stock).

Voided sales never appear in any dashboard figure.

---

## 10. Good habits

- Log out (or switch cashier) at every shift change.
- Never share PINs or passwords.
- Only tick "Payment confirmed on phone" after seeing the confirmation on **your** phone, not the customer's screen.
- Give a clear reason for every stock adjustment and void — future you will thank present you.
- Check stock alerts daily so you restock before running out.
