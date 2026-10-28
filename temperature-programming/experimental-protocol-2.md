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
,,,,(red4),green1,,,
,,,(red3),blue1,green2,green3,,
,,(red2),yellow1,blue2,blue3,green4,green5,
,(red1),green1,yellow2,yellow3,blue4,blue5,green6,green7
,blue1,green2,green3,yellow4,yellow5,blue6,blue7,red1
,blue2,blue3,green4,green5,yellow6,yellow7,red3,
,,blue4,blue5,green6,green7,red2,,
,,,blue6,blue7,red1,,,
,,,,red3,,,,
```

seed: blue2, blue4, blue6