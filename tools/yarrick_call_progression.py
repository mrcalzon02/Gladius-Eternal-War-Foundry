"""One purchased reinforcement skill; native, temporary rank routing.

The engine transfers an action's normalized rank to traits it applies. A
short-lived trait clamps movementMax to that rank (0..4), so native numeric
conditions can route exact steps without reading the hero's experience level.
The trait is removed synchronously before the action finishes.
"""
import xml.etree.ElementTree as E

CALL = 'Foundry/ArmageddonCalls'
PROXY = 'Foundry/ArmageddonCallRank'
PENDING = 'Foundry/ArmourPending'
RANKS = (
    {'rank': 1, 'infantry_experience': 0, 'tank_experience': None},
    {'rank': 2, 'infantry_experience': 0, 'tank_experience': 0},
    {'rank': 3, 'infantry_experience': 1, 'tank_experience': 1},
    {'rank': 4, 'infantry_experience': 2, 'tank_experience': 2},
    {'rank': 5, 'infantry_experience': 3, 'tank_experience': 3},
)


def rank_gate(modifier, internal_rank):
    unit = E.SubElement(E.SubElement(modifier, 'conditions'), 'unit')
    E.SubElement(unit, 'trait', name=PROXY)
    E.SubElement(unit, 'movementMax', greater=str(internal_rank - .5),
                 less=str(internal_rank + .5))


def install(actions, action, area, effects, condition, spawn_target, write):
    call = action('livingIncubator', 'ArmageddonCalls',
                  'Units/AstraMilitarum/Guardsman', 10,
                  rank='-1', rankMax='4', useConditionsForVisiblity='1')
    condition(call, 'unit', noTrait={'name': PENDING})

    # Reserve armour from the purchased rank, then remove the temporary stat
    # override. These are distinct areas so additions are applied in order.
    begin = E.SubElement(call, 'beginTargets')
    actor = E.SubElement(begin, 'selfTarget')
    E.SubElement(effects(area(actor)), 'addTrait', name=PROXY)
    routing = area(actor)
    modifiers = E.SubElement(routing, 'modifiers')
    for step in RANKS[1:]:
        modifier = E.SubElement(modifiers, 'modifier')
        rank_gate(modifier, step['rank'] - 1)
        result = E.SubElement(modifier, 'effects')
        E.SubElement(result, 'addTrait', name=PENDING)
        E.SubElement(result, 'addTrait',
                     name=PENDING + 'Tier' + str(step['tank_experience']))
    E.SubElement(effects(area(actor)), 'removeTrait', name=PROXY)

    # Place a standard Guardsman, then add the exact experience level increment
    # using the same purchased-rank marker. This avoids rounded interpolation
    # of addUnit's integer levelMin/levelMax and preserves difficulty bonuses.
    placement = spawn_target(call, 'Guardsman', 0)
    target = placement.find('target')
    E.SubElement(effects(area(target)), 'addTrait', name=PROXY)
    routing = area(target)
    modifiers = E.SubElement(routing, 'modifiers')
    for step in RANKS:
        modifier = E.SubElement(modifiers, 'modifier')
        rank_gate(modifier, step['rank'] - 1)
        E.SubElement(E.SubElement(modifier, 'effects'), 'level',
                     add=str(step['infantry_experience']))
    E.SubElement(effects(area(target)), 'removeTrait', name=PROXY)
    # Match vanilla paired target/selfTarget actions: finish the selected
    # placement before recording the caster's contextual completion state.
    begin.remove(actor)
    begin.append(actor)
    actions.append(call)

    # Contextual second placement, never another skill purchase. While pending,
    # the primary command is hidden and exactly one completion command replaces
    # it. The reservation freezes the cast's rank, even across skill upgrades.
    for experience in range(4):
        completion = action('livingIncubator',
                            'ArmageddonCallsArmour' + (str(experience) if experience else ''),
                            'Units/AstraMilitarum/LemanRussBattleTank', 0,
                            rank='0', rankMax='0', requiredActionPoints='0',
                            consumedActionPoints='0', consumedMovement='0',
                            useConditionsForVisiblity='1')
        gate = condition(completion, 'unit', trait={'name': PENDING})
        tier = PENDING + 'Tier' + str(experience)
        E.SubElement(gate, 'trait', name=tier)
        placement = spawn_target(completion, 'LemanRussBattleTank', experience)
        actor = E.SubElement(placement, 'selfTarget')
        result = effects(area(actor))
        for name in (PENDING, tier):
            E.SubElement(result, 'removeTrait', name=name)
        actions.append(completion)

    proxy = E.Element('trait', rankMax='4')
    E.SubElement(effects(proxy), 'movementMax',
                 minMin='0', minMax='4', maxMin='0', maxMax='4')
    from pathlib import Path
    write(Path('World/Traits/Foundry/ArmageddonCallRank.xml'), proxy)
