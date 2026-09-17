# What each measure means

The two [Olist marketing tables](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist)
are marketing-qualified leads (`mql_id`, first-contact date, origin) and won deals
(`mql_id`, `seller_id`, win date). The [Olist commerce tables](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
are order items (`order_id`, `seller_id`, item price) and orders (`order_id`,
status, purchase timestamp). All monetary quantities are Brazilian reais.

| Measure | Numerator / value | Denominator / eligibility |
| --- | --- | --- |
| 90-day lead conversion | Won deal with elapsed time 0–90 days from first contact | Qualified lead first contacted on or before 16 Aug 2018; win records through 14 Nov 2018 |
| 90-day recorded-sale share | Won sellers with one or more delivered item-linked orders in the following 90 days | Won within 90 days of first contact, by 2 June 2018, with full order observation through 31 Aug 2018 |
| Seller 90-day recorded item GMV | Sum of `price` on delivered order items with purchase timestamp from win inclusive to win + 90 days exclusive | Includes matured 90-day winners with no matched delivered item as zero observed; excludes freight |
| Observed GMV per won seller | Total recorded 90-day item GMV | Matured winners who closed within 90 days, including zero recorded sales |

Source audit records CSV SHA256 hashes, primary-key conflicts, absent joins and
the explicit cutoff. The order extract has 6,512 orders in August 2018 but only
16 in September and 4 in October, so these later 20 orders are excluded.
Using the observed last timestamp in October as a cohort cutoff would distort
activation. A seller with no recorded order might sell outside this extract;
zero is a measurement outcome, not proof of business failure.
Deals outside the 0–90 day lead-to-win window are not in the seller
comparison, because the planning model uses a 90-day *lead* conversion rate.
The audit also flags one deal dated before its lead's first contact; it is
excluded from the 90-day win cohort rather than silently correcting the date.

Conversion intervals use Wilson's score method at approximately 95% coverage.
Mean observed seller GMV intervals use 2,000 seeded bootstrap draws. These
describe sampled historical cohorts; they are neither causal confidence
intervals nor valid spending-optimization guarantees. Origin categories
`unknown` and `missing` cannot be assigned a marketing budget. Source mix,
seller product mix and acquisition spend are unavailable.

The scenario assumes future sellers look like historical matured won sellers,
and uses an editable fee rate, change in lead-to-win conversion, number of
additional leads and program cost. **Actual Olist fee rate, acquisition cost,
other operating costs and the incremental effect of a campaign are not in
these extracts.** The scenario is not Olist profit or a real company forecast.
