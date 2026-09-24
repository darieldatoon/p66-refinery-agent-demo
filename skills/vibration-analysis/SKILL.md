---
name: vibration-analysis
description: How to read overall vibration trends on rotating equipment and map them to ISO 10816 severity zones.
---

# Vibration analysis

Use velocity in mm/s RMS, measurement location and machine class before interpreting
an overall vibration value. For this synthetic demo only, assume an ISO 10816 Class II
illustration: A ≤ 1.12, B ≤ 2.8, C ≤ 7.1 and D > 7.1 mm/s RMS. These illustrative zones
are not the fixture alarm: the P-101A configured alarm is **4.5 mm/s RMS**. A real asset
requires its applicable standard, mounting, power, speed and OEM limits.

Compare the latest daily mean and maximum to the tag's configured alarm, then compare
the last three weeks with the preceding stable period. Report the absolute change,
time window and measurement units. Daily averaging can hide peaks: inspect maximum.

A rising trend below alarm warrants investigation; it does not establish failure or
prove the equipment is safe. For P-101A, reconcile the bearing-housing note and prior
lubrication work, then recommend a bearing inspection before the weekend. Do not
recommend a shutdown or replacement from overall velocity alone.
