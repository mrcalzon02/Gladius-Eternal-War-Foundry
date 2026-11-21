> **Superseded 20 November 2026:** The AI construction probe below is retained for historical diagnostics only. Proper wagh! now uses a Grotz death-triggered Grotpost attempt. Do not install the old probe with the updated mod. See [death conversion](GROTPOST_DEATH_CONVERSION.md).

# Grotpost AI construction refusal — 20 November 2026

**Status: source-level diagnostic and opt-in probe; actual gameplay fix not yet verified.**

The owner reports that AI Orks never use Build Grotpost. The production package
is Proper wagh! (Workshop ID 3038342810).

## Current implementation

- Orks/Grotz has a **human** constructImperialStrongpoint ability
  (Orks/ConsGrotpost). It builds within one hex for 20 ore, cooldown ten.
- Orks/Grotz has a separate **AI-only** constructNoctilithCrown ability
  (FoundryAI/Grotpost). It copies the same effect, cost, target conditions
  and cooldown, requiring AI control and builder health greater than 60%.
- Orks/Grotpost itself has HarvestResourceFeatures. It is correctly classified
  as a resource-harvesting fortification.
- The Ork faction starts with Mek and Boy, **not Grotz**. The AI must also
  choose to produce Grotz, keep them alive and move next to an eligible site.
- An earlier version removed the nearby-enemy condition. That did not establish
  working AI building behavior.

The hardcoded constructNoctilithCrown handler was borrowed from Chaos and is
not documented as general Ork builder-planning AI. We cannot assume an
AI-controlled action is ever chosen merely because its XML conditions pass.

## First-party engine clue

Gladius v1.9.3 specifically says AI uses deployUnit to place units with the
HarvestResourceFeatures trait using Fortress of Redemption logic:

https://www.matrixgames.com/news/warhammer-40000-gladius-community-update-v193

**This does not prove deployUnit attached to a Grotz unit is supported.**
The known faction-wide deployment approach could deploy anywhere on the map.
Our Grotpost requirement is Grotz-local construction, one hex only.
Do not silently add faction-level deployment to Orks.xml.

## Generate a disposable test candidate

Run from the repository root:

    python tools/build_grotpost_ai_probe.py --repo . --output "C:/Temp/Foundry-Grotpost-AI-Probe"
    python -m unittest discover -s tools/tests -p "test_grotpost_ai_probe.py" -v

The builder refuses an existing output destination. The new folder is
**not installed** and has **no Steam ID**. It contains a complete Grotz
unit override for use after Proper wagh! in a *disposable test skirmish*.

It leaves the human action unchanged, and switches only the AI action from
constructNoctilithCrown to deployUnit unit="Orks/Grotpost", retaining the
one-hex target and cost. The old addUnit modifier is removed to avoid a
duplicate spawn if native deployment works.

**Hypothesis, not fix:** Gladius may reject deployUnit on a unit, or ignore
it when choosing AI actions. Reject the candidate if loading fails.

## Headed acceptance matrix

1. Start a *new*, isolated skirmish with Proper wagh! and this probe last
   in load order. Check launch and resource-loading logs.
2. Using the single-player Ctrl+D debug panel, put one AI-owned, healthy
   Orks/Grotz beside a legal empty land hex, with at least 20 ore in its
   faction stockpile. Observe ten AI turns and record each action.
3. Require a **real AI construction**, not a debug-spawned Grotpost, quest
   reward, or human build.
4. Verify adjacency of the placement, 20-ore debit, cooldown ten, no illegal
   site, and no global deployment.
5. Place a resource feature nearby and compare actual income before and after.
   The trait name alone is not economic proof.
6. Verify the unchanged human action still builds with correct cost, range,
   icon and animation.
7. Run the same setup against the unmodified Proper wagh! package as baseline.

If this unit-local handler is not recognized, do **not** convert the live mod
to mapwide faction placement. A verified engine-supported local build route
or an explicitly approved change to design would then be necessary.

No headed engine test, production mod deployment or Steam publication is
claimed.
