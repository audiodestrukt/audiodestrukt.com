---
title: "A bench that says where the model is wrong"
date: 2026-09-29T16:00:00-07:00
tags: measurement, physical modeling, circuit decimator, impulse responses, nonlinear
---

# A bench that says where the model is wrong

Every circuit in Circuit Decimator has been checked the same way: the realtime solver against ngspice running the same netlist. That proves the solver integrates the equations. It says nothing about whether the equations describe the pedal on the shelf. Nothing in that project has ever been compared to a measured signal, and the thing I actually want to model next is a vintage Marshall, which is not a circuit I can be casual about.

So I built a measurement harness where a simulation and a real box are the same kind of thing. One stimulus goes in, a response comes back, it gets aligned and measured, and any two responses are compared on the same axes. The device can be `ff_render` from Circuit Decimator, a VST, or an audio interface with a pedal cabled between its output and input. Nothing downstream knows which. It's on GitHub as [ir-harness](https://github.com/audiodestrukt/ir-harness).

## One signal, cut into pieces

The stimulus is a single long signal made of named segments, and the segment table travels with it. A device gets the whole thing and returns the whole thing. The response is aligned once, by finding the peak of the deconvolved sweep, which is a sharper landmark than any cross-correlation and survives heavy distortion. Then every measurement cuts the response at the same offsets as the stimulus. That's the whole trick. A sim run and a hardware run are cut in the same places, so their numbers are directly comparable.

What's in it, at 192 kHz:

- **An exponential sine sweep**, 20 Hz to 20 kHz, in Novak's synchronized form. Deconvolving the response gives the linear impulse response and, from the same pass, an impulse response for each harmonic order. The synchronized form keeps their phases coherent, which matters later.
- **Stepped tones**, five frequencies at six levels from -40 to 0 dBFS. THD, each harmonic, output level and DC offset versus drive.
- **A sustained tone for knob ramps.** Inert by itself. A run attaches a parameter ramp to it.
- **Tone bursts**: a loud burst followed immediately by a quiet probe at the same frequency. The burst's envelope shows sag setting in; the probe's shows recovery.
- **A DI clip.** The thing you'd actually listen to.

Silence around everything for noise floor and settling.

![The baseline Fuzz Face at -12 dBFS: linear IR, magnitude, and the harmonic distortion of each order across the band, all from one sweep](images/2026-09-29_ir-harness_baseline-sweep.png)

## What it found in the sim on day one

Before any hardware, running the Fuzz Face through it turned up two things.

The realtime DK solver against the reference MNA solver nulls to -92 dB on the DI clip. Whatever is wrong with the model, it isn't the realtime solver.

The DK solver also emits single-sample spikes at hard clipping edges. Sixteen of them in one 0 dBFS tone at 192 kHz. At 48 kHz without oversampling they reach 27 volts on a 9 volt circuit. Newton hits its iteration cap on the fast edge. The ngspice check never saw this because ngspice takes variable steps. A harness that counts isolated outliers catches it automatically, and it'll matter the moment a real pedal is on the other side, because those spikes would land in the residual and look like a modeling error.

Then the first comparison, baseline against a battery starved to 4.5 V:

![Baseline versus starved: level-matched magnitude, the difference, and H2 and H3 for both](images/2026-09-29_ir-harness_starve-sweep.png)

The starved circuit loses 40 dB by 20 kHz and its second harmonic climbs from -35 dB to -2 dB. It's nearly an octave fuzz. In the DI clip you can watch its bias point drift with the envelope:

![The DI clip, both responses and their residual, and the band-by-band level difference](images/2026-09-29_ir-harness_starve-clip.png)

## Does a sweep capture the nonlinearity?

Partly, and the honest answer took a detour that ended up shaping the whole tool.

The harmonic impulse responses from a synchronized sweep can be turned directly into a model: parallel branches of x, x², x³ and so on, each through its own filter. It's exact for anything that's a memoryless nonlinearity sitting between linear filters, at the sweep's drive level. So I made every run fit that model to its own sweep, push the entire stimulus through it, and subtract the prediction from what the device actually did.

The residual is the interesting object. Instead of one number, the harness localizes it: by frequency band, by input level in 10 ms windows, by what the signal was doing in the previous 300 ms (at a fixed current level, that axis is memory: sag, bias recovery, anything stateful), and per stepped tone. A `focus` line after every run says which of those is the hot spot and what to measure next.

![Where the sweep-derived model fails on the baseline fuzz: by band, by level, by history, and per tone](images/2026-09-29_ir-harness_residual.png)

That turned the feature list into answers to a question. Sweeps at several levels, because the residual grows with level:

![Four sweep levels. The fundamental drops 12 dB for every 12 dB of extra drive: fully compressed from -36 dBFS up](images/2026-09-29_ir-harness_levels.png)

Bursts, because a sweep is blind to memory. This one measured the fuzz's gating directly: after a 0 dBFS burst, a -30 dBFS probe starts 45 dB down and recovers in 40 ms, and the 110 Hz burst itself settles 0.34 dB as the bias moves.

![Burst envelope (sag) and probe envelope (recovery)](images/2026-09-29_ir-harness_bursts.png)

Knob ramps, because a model of one setting isn't a model of the pedal. I added breakpoint automation to `ff_render`, so a parameter is re-applied every 32 samples while the circuit keeps its state, the same thing a knob turn does in the plugin. The fuzz pot swept from 0.05 to 1 across four seconds of a 220 Hz tone gives THD, H2, H3 and level against knob position in one pass. For hardware the same schedule can run stepwise, pausing for a hand on the knob.

![The fuzz knob ramped 0.05 to 1: THD, H2 and H3, and level versus knob position](images/2026-09-29_ir-harness_knob-ramp.png)

And grids: every combination of a few knob values, each a full run, mapped onto the knob plane.

![Fuzz by battery voltage, nine cells: H3, H2, gain, treble loss, the model's residual on the clip, and sag](images/2026-09-29_ir-harness_grid.png)

## What the residual said

On the baseline Fuzz Face, the sweep-derived model explains only 2.7 dB of the DI clip. With all four sweep levels, 4.2 dB. Every tone above -16 dBFS is unexplained. Raising the model's order from 3 to 9 changes nothing, and 13 makes it worse.

That isn't the measurement. The harmonic impulse responses are clean out past the 20th order. It's the model class. A hard clipper's output is close to a square wave, and a square wave keeps 96 percent of its energy in harmonics up to the 9th, so a 9th-order polynomial cannot null it below about -14 dB no matter how well it's fitted. The level-indexed model reaches -16 dB where a sweep exists, which is that ceiling. Beyond order 9 the inversion's condition number grows like (2/A)^(N-1) and noise takes over.

The grid shows the same thing from the other side. At low fuzz on a fresh battery the circuit is nearly clean (H3 at -84 dB) and the polynomial model nulls the clip to -12.6 dB. At full fuzz on 4.5 V it's an octave fuzz with 13 dB of treble loss and 0.7 dB of sag, and the model explains nothing. The residual draws the boundary of where a polynomial is the right idea.

So the next model has to have a saturating shape rather than more terms. The multi-level sweeps already measure what that needs: the fundamental's gain versus level and the harmonic ratios versus level. That's the first item on the list, and now there's a number that says whether it worked.

## Hardware

There's nothing on the bench yet. The interface tops out at 192 kHz, which is why that's the default, and the scope and analyzer I have aren't USB, so instrument control is a slot in the design and not a feature. The order of business is the interface looped back on itself, to measure the floor everything else sits on. Then a real fuzz against the sim, where I expect the model to be wrong somewhere specific and the residual to say where. Then a reamp box and a reactive load, and the Marshall at line level, one setting and then the whole panel with the grid prompting me to turn knobs.

Everything above ran on the simulation. All of it runs on the box unchanged.
