---
name: work-order-standards
description: Required fields, priority codes, and approval rules for a maintenance work order draft.
---

# Work order standards

Required fields: exact asset tag, short action title, priority, evidence-based
justification and a nonempty list of specific tasks. Cite sensor/work-order/note IDs
and the evidence window. State uncertainty and conflicting records.

| Priority | Demo response target | Use |
| --- | --- | --- |
| P1 | Immediate review | Confirmed urgent hazard or alarm requiring human assessment |
| P2 | Within 48 hours | Deteriorating critical asset; inspect before weekend |
| P3 | Within 7 days | Stable nonurgent corrective work |
| P4 | Next planned outage | Planned improvement or nonurgent overhaul |

For rising P-101A vibration below alarm, normally recommend P2 inspection: verify
vibration at the bearing, inspect lubrication and temperature, check alignment, and
have the engineer review findings before deciding on replacement.

Call `draft_work_order` once the fields are ready. The platform requires human
approval before the tool runs. Reject/edit decisions belong to the human. Do not
substitute prose for the approval step or imply the draft is a submitted CMMS order.
