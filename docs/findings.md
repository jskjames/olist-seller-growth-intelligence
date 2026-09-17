# Historical findings and possible action

The reproducible run used 8,000 qualified seller leads, 842 recorded won deals,
112,650 order-item rows and 99,441 order rows. A fixed 90-day window shows
690 observed wins (8.625% of qualified leads). Among 635 sellers who won
within 90 days and have a full order-observation window, 276 (43.5%) have a
recorded delivered sale within 90 days. They have a combined R$328,334.48 in recorded item GMV; this
is not marketplace revenue or company profit.

| Origin | Qualified leads | Won within 90 days | Conversion | Matured wins | Recorded-sale share | Mean item GMV / matured win |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Paid search | 1,586 | 150 | 9.46% | 134 | 54.5% | R$534.34 |
| Organic search | 2,296 | 217 | 9.45% | 200 | 40.0% | R$449.11 |
| Social | 1,350 | 58 | 4.30% | 51 | 45.1% | R$248.40 |

Paid and organic search have nearly identical observed 90-day lead conversion
rates; paid search has a higher recorded-sale share among fully matured wins.
Those differences are **associations**, not a causal estimate of the value of
marketing spend. The true costs of all three sources are missing. Another
1,099 leads have an `unknown` origin and 60 lack an origin; attribution
coverage should be reviewed before any channel-budget decision.
One recorded deal predates its lead contact and is excluded from win-window
comparisons; the order extract ends too sparsely after August 2018 to compare
later seller cohorts fairly.

Suggested stakeholder discussion: test a seller onboarding intervention
targeted to a clearly defined cohort, collect channel-level cost and complete
seller-order coverage, and compare outcomes only after matched observation
windows. If randomization is feasible, pre-register a 90-day activation
outcome and compare treatment with control rather than treating this dashboard
as proof that one acquisition channel causes better sellers.

Example résumé language (only after the student independently reviews and can
explain the project):

> Built a SQL/Python seller-acquisition mart linking 8K Olist leads to 99K
> marketplace orders; audited 90-day cohorts and delivered an interactive
> channel dashboard and assumption-driven revenue model.

This case study was developed from public data and is not Olist employment,
a deployed company system or a proven campaign outcome.
