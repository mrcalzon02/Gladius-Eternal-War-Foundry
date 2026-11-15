# Integrated builder AI construction

The former pilot is part of the original packages. Marine Techpriest actions
and strings live in Veteran Marines (`2175959340`); Guard Techpriest actions in
Penal Legion (`2525618649`); playable Grotpost construction in Proper wagh!
(`3038342810`). There is no separate runtime pilot.

Human construction retains its original handler. AI construction uses
`constructNoctilithCrown`, with the original spawned unit, builder, cost,
research gate, adjacent target range, animation and cooldown. AI must have
more than 60% health. Normal construction affordability still applies.
Guard/Marine defenses require a non-invulnerable enemy within three tiles;
Grotposts retain the installed v3 behavior without an enemy-proximity gate.
AI branches exclude the Neutral faction and preserve target restrictions.

The old extra reserve checks used unsupported player condition tags (`ore`,
`energy`, `requisitions`) and caused a startup abort when loaded from the parent
packages. They have been removed; the installed 1.18.3 engine's native player
condition parser has no equivalent stockpile checks for those resources.
Integration is not proof of construction frequency, placement
quality, economic recovery or combat correctness. Those require matched in-game
scenarios. See [installation and validation](MOD_INTEGRATION.md).

The old generator remains a development experiment tool; generated scratch
folders must not be installed alongside the integrated numeric packages.
