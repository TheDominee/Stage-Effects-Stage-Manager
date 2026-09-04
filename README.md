# Stage Effects Stage Manager

A single-file HTML countdown timer for running live shows: a running order/cue list, an extendable presenter display, day/night themes, full-screen messages, and count-up/count-down modes.

## Files

`Stage_Effects_Stage_Manager.html` is the control panel. Open this on the show computer to run the timer and manage the running order.

`index.html` is the public viewer page. This is what gets deployed so remote viewers, with no login needed, can follow the live countdown via a shared link.

## Broadcasting

The control panel can broadcast the live countdown to the `index.html` viewer page over a Firebase Realtime Database, or the free jsonblob.com backend, so anyone with the viewer link can follow along from their phone or another screen.
