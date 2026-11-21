# Integrated builder AI construction

The former pilot's Marine and Guard construction branches remain integrated in
Veteran Marines (`2175959340`) and Penal Legion (`2525618649`). The Ork
Grotpost AI branch was retired in favor of a death-triggered Grotz trait in
Proper wagh! (`3038342810`). There is no separate runtime pilot.

Guard and Marine human construction retains its original handler. Their AI
construction uses `constructNoctilithCrown` with the original spawned unit,
builder, cost, research gate, adjacent range, animation and cooldown.
Their AI must have more than 60% health and a non-invulnerable enemy within
three tiles. Normal construction affordability applies. These AI branches
exclude the Neutral faction and preserve target restrictions.

Playable Orks/Grotz instead now carry `Orks/GrotpostOnDeath`: a native
`onUnitDisappeared` tile-area trigger attempting to spawn one `Orks/Grotpost`
on their own tile after disappearing, only on suitable unoccupied land. The
AI-only Grotpost construction action is removed; the 20-ore player construction
button is preserved. This death effect has no construction ore debit. Neutral
Grotz and Grotz Kamando are unchanged. Spawn timing, ownership, disbanding,
transport destruction and multiplayer behavior require a headed engine test.
See [Grotpost death conversion](GROTPOST_DEATH_CONVERSION.md).

The old extra reserve checks used unsupported player condition tags (`ore`,
`energy`, `requisitions`) and caused a startup abort when loaded from the parent
packages. They have been removed; the installed 1.18.3 engine's native player
condition parser has no equivalent stockpile checks for those resources.
Integration is not proof of construction frequency, placement
quality, economic recovery or combat correctness. Those require matched in-game
scenarios. See [installation and validation](MOD_INTEGRATION.md).

The old AI-construction generator and Grotpost deployUnit probe are archived
development experiments, not runtime requirements. Do not install generated
scratch folders alongside the integrated numeric packages.
