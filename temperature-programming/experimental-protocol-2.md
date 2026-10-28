# Experimental protocol 2
created 10/28/2026

## problem background

Experimental protocol 1 failed without identifiable causes.

This aims to reduce the problem scope by addressing the tile design error possibility by making a nanotube tile design on aTAM to validate its logicla structure.


## goal

- It is our goal to make a nanotube by temperature programming governed by the hold duration.
- The system is considered successful if
    - it works at tau=1
    - it is visualized so that I can confirm that it is working

## current design

- the width of 4
- the height of 2 (for aTAM design)
- three layers in total
- tile edge for folding capability

```csv
,,,,,,,,
,,,,,,,,
,,,,,,,,
,,,,,,,,
,,,,(red4),green,,,
,,,(red3),blue,green,green,,
,,(red2),yellow,blue,blue,green,green,
,(red1),green,yellow,yellow,blue,blue,green,green
,blue,green,green,yellow,yellow,blue,blue,red1
,blue,blue,green,green,yellow,yellow,red3,
,,blue,blue,green,green,red2,,
,,,blue,blue,red1,,,
,,,,red3,,,,
```

