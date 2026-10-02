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

- I hypothesized the cause of the abnormal gap between the target programmed length and the mean simulated length to be the presence of interface interruptions

### current hypothesis

- interruption causes a decrease in the growth rate
- target programmed length was underestimating the expected growth rate

### rejected hypothesis

- interruption causes an increase in the growth rate
- the final ribbon should produce the patchwork pattern

## method proposal

H_{0, 0}: two segments and interface for each
H_{0, 1}: one segment and its interface
H_{1, 0}: another pair


### manipulation

- the temperature hold rule is the same for all (2 hours each)

### measurement

- the tube length per timeline

### prediction

- G(H_{0, 0}, t) = G(H_{0, 1}, t) + G(H_{1, 0}, t)

### falsification

- abnormal difference evident by gradient that suggests interruptions by inactive segment or interface

### rejected tile design hypothesis

#### 1. low detachment rate of interface contributing to the growth of unwanted segment

context: interface remaining long enough may allow unwanted segments to grow like normal

reason for rejection: this implicitly assumes the growth rate remains the same across at any point of the temperature window, which is obviously false


#### 2. no-assembly-split constraint allowing a prefix secondary locking making the unwanted thermodynamic favorability

context: the only way to for a tile with very low affinity to achieve a low detachment rate by the relatively relevant chance

reason for rejection: rgrow kTAM description: "Zero-strength attachments events are ignored" and "G_link is set 0 by default"

