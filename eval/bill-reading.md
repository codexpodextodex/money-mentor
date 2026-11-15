# Reading bills from photos

1000 made-up bills, each sent through the app with the picture and the question a customer would ask ("get this bill ready to pay").
The bills are rendered, not photographed: three layouts, Finnish, Swedish and English, five typefaces, tilted up to 3.5 degrees, some
slightly blurred, JPEG quality 55 to 90. Every company, customer and account is invented. Produced by `python scripts/bill_reading_test.py`.
These are the bills of the set "fresh": made by the same generator as the bills the checks were tuned on, but other bills, which nobody had looked at before this run.

What is judged is the draft the customer would see: the account number, the reference, the amount and the due date on it, against what
was printed on the bill.

| | |
|---|---|
| Bills | 1000 |
| A draft was prepared | 1000 |
| Ready to confirm | 984 |
| ... and every payment field right | 984 |
| ... with a wrong payment field | 0 |
| Held back for the customer to check or photograph again | 16 |
| ... of which the draft was in fact right | 15 |
| The model was sent back to the photo after a failed check | 49 |
| Account number / reference / amount / due date right on the draft | 999 / 1000 / 1000 / 1000 |
| Payee's name exactly as printed (it has no check; the customer sees it) | 886 |
| Answers in which every number was traced to the tool result | 1000 |
| Median time for the whole answer, with eight bills in flight at once | 9.7 s |
| Ready and right, by language of the bill (fi / sv / en) | 590/600 / 213/214 / 181/186 |

How a draft becomes "ready":

1. The model reads the bill and passes the payee, the account number, the reference, the total and the due date to the engine.
2. The engine recalculates the check digits inside the account number and the reference.
3. The amount and the due date have no check digit, so the model is asked a second time, for something simpler: to copy the bill's
   text line by line. The engine finds the total and the due date in that text by their labels, and both readings must agree.
4. The total may not be smaller than another amount printed on the bill, and the due date must be after the bill's own date.
5. A draft that fails any of this goes back to the photo once. If it fails again, it is shown without a confirm button.

All answers came from Nemotron 3.5 Super VL: 233 by NVIDIA API, 767 by Verda, Finland. The run used our second host so that the public demo stayed fast, and that
host passed requests on to NVIDIA's hosted API when it was busy with eight bills at once.
Every draft that was not ready is listed in `eval/bill-reading.json`.
