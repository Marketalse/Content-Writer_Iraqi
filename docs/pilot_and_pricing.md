# Pilot control, cost, pricing, and revenue

Status: working plan. Prices are starting hypotheses to test in the pilot, not market research.

## 1. Cost per post (what the bot spends)

Each post runs three steps (see `bot/pipeline.py`):
- Analyst (Haiku 5.5): short, about 400 tokens out.
- Writer (Sonnet 5.5): reads the cached system prompt (about 19k tokens), writes about 2k tokens out.
- Dialect check (Haiku 5.5): short.

Rough estimate with list prices (Sonnet 5.5: $2 in, $10 out per million tokens):

| Item | Tokens | Cost |
|---|---|---|
| Writer output | about 2,200 | about $0.022 |
| Writer input, cached | about 19,000 | about $0.004 (cache read) |
| Writer input, first call or cache expired | about 19,000 | up to about $0.05 (cache write) |
| Analyst and dialect check (Haiku) | about 1,500 | about $0.001 |

**Planning figure: $0.03 to $0.06 per post.** A rewrite after a failed check roughly doubles the writer cost. Use the `cost_usd` values in `logs/posts.jsonl` to replace these estimates with measured costs after the first 10 pilot posts.

## 2. Controlling the pilot (implemented)

Access and caps are enforced in `bot/pilot.py` before any model call:

| Setting | Meaning | Default |
|---|---|---|
| `max_posts` | number of generated posts | 10 |
| `max_usd` | estimated model cost | $1.00 |
| `PER_POST_CAP_USD` | worst case reserved for one post | $0.25 |

A pilot is refused when `posts >= max_posts`, or when `cost + $0.25 > max_usd`. The owner is never limited.

### Start a pilot
1. The creator starts the bot and sends `/id`. The bot replies with their chat ID.
2. You add them on your Mac: `/pilot add <chat_id> <name> 10 1.00`. Only your own chat, from `OWNER_CHAT_ID`, can run `/pilot`.
3. Tell them: "Send /start, then choose a format, an angle, and a topic. Send /quota to see what's left."

### Watch and stop
- `/pilot list` shows posts used, cost used, and the caps for each pilot.
- `/pilot stop <chat_id>` stops a pilot immediately. `/pilot resume <chat_id>` turns it back on.
- The pilot stops by itself when either cap is reached. They get a message saying the trial is over.

### Backstop in the Anthropic Console
Set a monthly spend limit in the Console, so a bug can't spend more than planned. For more control, create a separate Workspace for the pilots with its own key and spend limit. Revoke that key to cut off all pilots at once.

### Budget per pilot
10 posts at $0.06 is about $0.60, so a $1.00 cap leaves room for a rewrite. Adjust `max_usd` after you measure real costs.

## 3. Pricing (starting hypothesis)

Target gross margin: at least 80% on model cost. At $0.05 per post, a post needs to sell for at least $0.25.

| Offer | Price | Includes | Model cost (planning) | Margin |
|---|---|---|---|---|
| Paid pilot | $29 once | 10 posts, all formats | about $0.60 | about 98% |
| Voice setup | $150 once | Your 10 corrected pieces, voice file, library update | your time | high |
| Starter | $19 / month | 60 posts | $2 to $4 | about 80% |
| Growth | $49 / month | 200 posts | $6 to $12 | about 75% |
| Studio | $149 / month | 600 posts, 3 brands | $18 to $36 | about 75% |
| Done-for-you | $300 / month | 30 posts, managed and reviewed by you | $1.50 + your time | your time is the cost |

Why a paid pilot: a free pilot attracts people who won't pay. A small fee filters for people who will.

## 4. Revenue streams

1. **Subscriptions.** Starter, Growth, Studio. Recurring income. The main stream.
2. **Setup and voice training.** One-time fee. It is the highest-value service: you turn 10 corrected posts into a voice file and grow the word library.
3. **Done-for-you content.** You run the bot for the client and review each post. Higher price, more of your time.
4. **Agency licence.** For marketing agencies: several brands under one account, with a monthly fee.
5. **Upsell.** Pilot to Starter, then to voice setup, then to Growth.

## 5. Metrics to track from day one

- Posts per user per week, and whether they use `/published`.
- Cost per post from the logs, against the margin target.
- Pilot-to-paid conversion. Target: 1 in 3 pilots.
- Monthly churn for subscribers.
- Support time per customer. Your time is the real cost of the done-for-you offer.

## 6. Before you sell

- **Anthropic and Nous terms.** Check that reselling access through your product is allowed under their commercial terms, and that you can name the provider in your terms.
- **Data.** Store only what the bot needs: topics, outputs, and usage logs. Tell customers that topics and outputs are kept for 90 days or until they delete them. Write your own retention rule before you take money.
- **Refunds and content ownership.** Customers own their outputs. Write a short refund rule for pilots and subscriptions.
- **Payments.** Check which payment methods work for your customers in Iraq and abroad before you publish prices. Don't assume a provider is available.
- **Claims.** Don't promise sales or reach results. Sell time saved and consistent drafts.

## 7. Next steps

1. Run the bot for the first pilot, then compare the logged costs with this document.
2. Update the cost and margin figures in section 1 and section 3 with the measured numbers.
3. Decide on the paid pilot price and the payment method, then update this document.
