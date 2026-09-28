# Objective completion state (runtime build 1.8.46015.0)

The objective manager at game.dll+0x3326da0 stores count at +0x24, coordinate/network records pointer at +0x68 (stride0x64), and native cached state pointer at +0x60 (stride0x1078). Each coordinate/network record stores objective state at +0x20. The native cached state at +0x1018 copies this field:

* 0x5d0f89 reads coordinate record+0x20; 0x5d0f8d stores cache+0x1018.
* 0x5d2e63-0x5d2e78, 0x5d32a0-0x5d32b1 repeat that synchronization.
* 0x5d9110-0x5d915d returns success only when the primary objective cached state equals2.
* 0x62fa68-0x62fa80 produces a boolean report field from cached state ==2.
* 0x5d34dd-0x5d3529 is the state2 completion event path. State3 has a separate path and propagates3 to unresolved objectives, so it is not treated as successful completion.
* Native map renderer reads cache+0x1018 at 0x18b4578. Its discovery/render record fields +0x40/+0x44 are independent from +0x20.

0.2.2 uses already-read coordinate/network record+0x20, avoiding additional memory access or state writes. Only equality with2 turns objective glyphs gray. State changes participate in the GUI draw key, so unchanged positions still repaint after completion. Normal map markers have no objective state and stay cyan. Cache refresh remains30frames. Tests cover 0,1,2,3,unknown state, projection propagation and color-only redraw keys. User confirmed0.2.1 alignment;0.2.2 completion colors need live verification.
