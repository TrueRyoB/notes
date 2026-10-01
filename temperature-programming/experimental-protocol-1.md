# Experimental protocol 1
created 09/30/2026

## problem background

Temperature programming without a directional constraint has significant kinetic errors that at least its growth rate is abnormal: the lowerbound of the simulation matches the theoretical one but the upperbound is nearly the double of it.

Our goal is to address with this kinetic error rate and design a robust system.

## goal

- It is our goal to make a ribbon of stripe pattern of the arbitrary width comination by temperature programming governed by the hold duration.
- The system is considered robust iff 
    - the growth rate of simulation via rgrow matches to that of theory AND 
    - growth rate is not too slow AND 
    - the result is stable for the temperature fluctuation of 2 degrees in celsius while the hold.

## non-evident premises

- The minimum hold duration is 2 hours.
- In simulation, the temperature did not fluctuate at all in the simulation during the hold, and the temperature shift was instantaneous.


## current design

- There are two segments and two interfaces.
- One segment has the domain length of 9 units, while other has that of 10 units.
- Each interface serves as a connection between these two segments at the hold temperature shift.


### side notes

- Interface achieves different sticky end length among its edges by padding technique.


## diagonistic hypothesis

- I hypothesize the cause of the abnormal growth to be numerous interruptions of interfaces, leading to the situation of the doubled concentration compared to the original mass-wise.
- If interfaces independently propagate during the hold, then the final ribbon should produce a patchwork pattern across rows.


## tile design hypothesis

???


### rejected hypothesis

1. low detachment rate of interface contributing to the growth of unwanted segment

context:
- interface remaining long enough may allow unwanted segments to grow like normal

reason for rejection:
- this implicitly assumes the growth rate remains the same across at any point of the temperature window, which is obviously false


2. no-assembly-split constraint allowing a prefix secondary locking making the unwanted thermodynamic favorability

context:
- the only way to for a tile with very low affinity to achieve a low detachment rate by the relatively relevant chance

reason for rejection:
- rgrow kTAM description: "Zero-strength attachments events are ignored" and "G_link is set 0 by default"


## manipulation


## measurement

## prediction

## falsification



## other insights

- I realized that tile rotation tolerance may affect the growth size as well.
- I cannot really confirm it.

--- 


## assumption for the cause of abnormally high growth rate and how it results in the culminate output

- the binding strength of the interface is significant enough so that they proceed growing regardless, resulting in technically double the concentration of the original
- this is supported as the upperbound matches exactly
- If interfaces independently propagate during the hold, then abnormal growth should be spatially concentrated around the interfaces and should produce a patchwork pattern.

- I am not verifying this diagnosis assumption, as I could not come up with alternatives.

### diagnostics

A: H_{0, 0}
B: H_{0, 1} (only one interface)
C: H_{0, 1} {no interfaces}
D: H_{1, 0} (no segments)


## proposals (very speculative)

- It is important to reduce the contribution rate of interfaces significantly so that it becomes relevant only as needed
- the free energy is determined by an enthalpy subtracted by an entropy
- we are coming up with an idea to reduce the interface solely by looking at each term

1. Waffle - increase entropy by decrementing the number of bond attachment
2. Naive - reduce enthalpy by simply adjusting its concentration relative to the segment

### 1. Waffle Approach

Essentially, we take advantage of the difference in thermodynamic preference for 1-bond attachment and 2-bond attachment.

I am assuming that interfaces are messing the system up regardless of its small growth rate because their detachment rate is somehow quite low. I am addressing with this.

Essentially, every row between two segments are no longer guaranteed to be connected.

#### failure pattern

I am worried of the extreme plummet in the contribution rate, though. As you can see, this idea assumes that you can achieve both the spontaneous nucleation rate minimization and the relevant growth rate. 


### 2. Naive Approach

This should work. I am not sure if this operation is permitted, but I will proceed with it, as the idea 1 might no be viable.

#### failure pattern

the linear fix may not be significant enough to beat the benchmark. that being said, this should be combined with other methodologies to be effective. 

## other notes

- I am using kBlock model to say goodbye to unwanted cause of drop in growth rate
- 

## prospects
