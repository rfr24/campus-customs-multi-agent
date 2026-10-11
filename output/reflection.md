# Reflection — Campus Customs Multi-Agent Operations

## What I was testing

I wanted to know whether five specialized agents could actually coordinate on a small shop's daily
operations: whether they would divide the work sensibly, ground their answers in what the records
say rather than what sounds plausible, and bring the decisions that need a person to a person. Not
whether they could replace my judgment, but whether they could do the gathering and cross-checking
well enough that my judgment got applied to accurate facts.

Before running anything I wrote down what I expected, including two specific ways I expected them to
fail — the most useful thing I did all assignment, because it stopped me from grading the system on
my impression of it afterward.

## How the agents performed

The Boss routed sensibly and didn't over-consult: ticket 101 drew Customer Service, Inventory, and
Accounting; ticket 102 only Facilities and Accounting.

The specialists were more careful with facts than I expected. On ticket 101 the tee in size S was at
zero, and the ticket linked to an $840 invoice described as a rush reprint of exactly that item. The
tempting conclusion is that paying the invoice gets the shirt. They refused to draw it — the Boss
wrote that "neither the invoice nor its payment proves the reprint is complete or available" — and
volunteered that the $8 unit cost is not a vendor quote and the $840 invoice is not a customer
price. Nobody asked them to be skeptical about any of that.

On ticket 102, Facilities checked the emailed rent demand against the lease record instead of
trusting the email — landlord, amount, and timing all matched. It then stopped at its own boundary:
it can't propose payments, so it handed funding to Accounting.

## Where my predictions were wrong

Both predicted failures failed to happen.

The first was that they'd invent a discount policy on ticket 103. There is no discount rule anywhere
in the shop's data, and I assumed "a bulk discount" would pull a plausible number out of the model.
It didn't — I scanned the output for percentage or discount language and found none. They reported
the two numbers the database actually holds, a $22 recorded unit cost and a $58 list price, and left
it there. Neither is a pricing policy: the shop has no rule saying what a sale may or may not go
below, and the agents didn't treat the unit cost as though it were one. They put the decision to a
person, and Customer Service declined to quote a final price at all.

The second was that they'd miss how the three tickets interact financially. That one I got most
wrong, and it's the part I found genuinely impressive.

## The coordination that mattered

Each obligation is affordable alone — the $840 invoice, the $2,400 rent, and the $264 restock all
fit inside $3,400. The problem appears only when you hold all three at once: **$3,504 against
$3,400 in a single checking account, $104 short.**

The Boss computed that on ticket 103 without being asked about the other two tickets, noting the
balance "does not cover the purchase in addition to the known $840 overdue invoice and $2,400 rent
due September 2: those obligations leave $160, so all three together exceed the balance by $104."

Then it asked which obligation, if any, may be deferred, rather than picking one. An earlier run put
it more plainly: "A human must decide priorities; no obligation is presumed deferred." It didn't
quietly assume a bill could slide to make its own recommendation work. That restraint is worth more
to me than the arithmetic.

## The defect that was mine, not theirs

The first ticket 103 run produced no purchase proposal, and both Inventory and Accounting said they
couldn't create one. My instinct was that the agents had failed. They hadn't — they were telling the
truth. The permission configuration I'd written earlier granted the purchase-proposal tool to no
specialist at all: the server implemented it, the approval route could execute it, and no agent
could reach it. Accounting was also missing read-only inventory access, which is why it priced the
full twenty units at $440 instead of the twelve-unit shortfall at $264.

The gap was invisible until a ticket needed it — the first two tickets only involved payments, so it
sat undetected through every test I'd written. The agents' response was the right one: report a
limitation rather than fabricate a proposal.

After fixing the permissions I reran ticket 103 once. Inventory created PUR-0001 for twelve hoodies
at $264, and Accounting costed the shortfall rather than the full order, because it could finally
see the eight units on the shelf. I kept the original run as evidence rather than overwriting it.

## The audit problem

While verifying this, I found the audit trail claiming payments had been executed, including
completed rent and hoodie purchases. None of it had touched the real shop data: several test suites
redirected the database to a disposable copy but kept writing events to the production audit file.
The entries were honest records of sandboxed calls, but anyone reading that log would reasonably
have concluded money had moved.

That's a bookkeeping failure, not an agent failure, and the more instructive one. The point of an
audit trail is that you can trust it without cross-checking; a log mixing rehearsal with reality
isn't a weaker audit trail, it isn't one. I measured which suites were responsible rather than
guessing — one I'd assumed was guilty was clean, and two I hadn't suspected were polluting — then
redirected them and added a check confirming the production log comes out byte-identical. I didn't
delete the historical entries; removing inconvenient records is the habit an audit trail exists to
prevent.

## Recommending, approving, executing

The assignment forced me to separate three things I'd have collapsed into one: producing a
recommendation, authorizing it, and carrying it out.

The agents do only the first; their proposals move nothing. A proposal in the ledger isn't a
decision, it's a question put to a person. I approved PAY-0002, the $2,400 rent payment, and
deliberately did not execute it. Checking is still $3,400 and the payments table is still empty: the
system recorded my approval as authorization that the payment *may* proceed, then waited. In the
version I'd have built instinctively, "the agent recommended paying rent" and "rent got paid" would
have been nearly the same event.

## What's still unresolved

All three tickets remain open, and I want to be precise about why that isn't a failure.

The $264 comes from the shop's own recorded unit cost — nobody has contacted Bulldog Print Co. The
September 5 arrival is a calculation from a stored lead time, not a commitment anyone has made, so
promising that date to the Yale AI Club would be inventing a fact. The discount question is likewise
unanswerable from the data, and the agents were right to refuse to make a policy up.

The cash arithmetic hasn't gone away either. I've approved the rent without executing it, and I'm
holding the $840 invoice and the $264 restock. Two of the three fit; all three don't. Choosing which
to defer is a judgment about relationships — landlord, vendor, student group — and none of that is
in a database.

What I have is a system that doesn't resolve every ticket on its own — and in these three cases it
shouldn't have. Each one turned on a judgment the data couldn't settle: an unconfirmed vendor date,
an absent discount policy, a cash conflict with no priority rule. It can carry a ticket all the way
to an executed action once a person authorizes one, and for the straightforward cases I'd expect it
to. What it did here was get three genuinely ambiguous decisions to the point where I could make
them quickly, with accurate numbers. Having watched it surface a $104 shortfall I hadn't noticed
across three tickets, that seems like the more useful thing to have built.
