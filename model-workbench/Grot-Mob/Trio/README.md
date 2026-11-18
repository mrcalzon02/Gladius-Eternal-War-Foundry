# Grot trio

The Proper wagh! mod uses this formation for regular Grotz and Grotz Kamando, both Ork and Neutral. The Mek and Cutter flank the slugga Gunner. Each Grot has its own 17-bone skeleton, and the three share one game member slot.

[Native animation preview](Grot-Trio-Preview.mp4) · [Editable Blender scene](Grot-Trio.blend) · [Animated GLB](Grot-Trio.glb)

The Blender timeline plays the eleven named clips in order. Use the timeline markers to jump to an action. The GLB has one separately selectable take per action. All timings use 24 frames per second.

| Action | Animation |
| --- | --- |
| Movement | Each Grot marches on a different phase. MoveBegin and MoveEnd ease into and out of the looping march. Run provides a faster gait. |
| Melee | The Mek swings the spanner, the Cutter slashes and the Gunner pistol-whips. Frame 18 is the contact pose. |
| Ranged | The flankers brace while the Gunner fires from the slugga muzzle on frames 17, 23 and 29. |
| Death | The Gunner falls sideways at the front, the Mek tips back, and the Cutter spills outward. The last frames hold each Grot on the ground. |
| Other actions | Idle, hit reaction, grenade release from the Gunner’s free hand and construction. |

The preview reads the native meshes, DDS diffuse atlas and animations and reconstructs the weapon attachments. It supplies forward travel for the walking shot. [Native frame checks](native-validation.json) · [Interchange checks](glb-validation.json)

[Runtime files, gameplay effects and installation](../../../docs/GROT_REPLACEMENT.md) · [Rebuilding the assets](build/README.md)
