# Medal overlay — offline evidence

Local FileDiver datalibrary, parsed by `go run ./cmd/overlay-info`:
- ExplorationReward entity `147bd99513726f88`: reward=2, destroy=1.
- Its UnitComponent model resource is `773c4184e4bad0df`.
- Generated enum `explorationrewardtype_string.go` identifies reward 2 as exploration_medals; reward 3 is exploration_credit_card.

The model query reuses the credit path: gameplay world only, live-unit deduplication, bounded enumeration, interact node (e4a4586d), rejection of unresolved origin offsets. No game data writes. Disabled by default in both runtime and menu; disabled means no medal query. Query failures clear only medal results. Pickup destruction removes markers on the next 30-frame refresh.

Icon: complete hollow gold octagon with all eight edges visible, and blue ribbons above and below, based on the supplied model. Per-part colors use the existing rectangle renderer; the outline pass remains black. Offline tests cover position, pickup, default-off filtering, runtime query gating/failure isolation and all 32 menu combinations. Actual medal interact-node placement and pickup lifecycle still require in-game confirmation on supported build 1.8.46015.0.
