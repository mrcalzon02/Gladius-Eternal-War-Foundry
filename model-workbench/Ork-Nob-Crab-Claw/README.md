# Regular Nob with crab claw

Current editable source: Ork-Nob-Crab-Claw.blend. Derived from the mod Nob in Ork-Nob-current, not the stock Boy. Original donor remains untouched.

The two-jaw crab pincer replaces 76 organic hand triangles. The original LeftHand joint drives the claw; the original action library remains in the editable source. Forearm ends within the mechanical cuff. Fitted faceted upper-arm shells, heavy wraparound jaw, and a back-mounted standard reuse the native OrkBoy3 diffuse, normal and SIC atlas. Body/skin and gun retain their original material assignments.

Surface plan: native ochre scratched armour patches on shell/casing/standard; native grey steel patches on jaw, claw and pole; dark patches on cuffs, hinge and saddle; original blue cloth, green skin and red leather retained. New UV regions are authored per part. Review GLB uses a baked preview team colour and native normal map; it is a static inspection artifact, not an engine-ready skeletal export.

Final static GLB: 2,544 triangles. Reimport audit found no missing UVs, unreadable image maps, nonfinite vertices or degenerate faces. Front, rear, side, clay, shoulder and claw views were inspected. Textures are deliberately coarse; atlas patch wear can appear stretched in closeup. Ground bounds are inherited. Native exporter round trip, animation clearance and in-game integration remain unverified.

Earlier Mega-Nob folder is a superseded multi-talon study. Use this folder for the current regular Nob. See verification.json and review.json for current hashes and local visual scores; these are agent review evidence, not user acceptance.

## Final modeling handoff

Claw now continues downward along the elbow-to-wrist direction. Its tapered octagonal socket receives the forearm through the rear steel ferrule; the square housing has been removed. Regular Nob two-jaw pincer retained. A bent eight-sided brim, flared scrap crown, ochre riveted band, two crown repair panels and jagged metal feather form the top hat. All ten hat parts are weighted to Head. Source reopened successfully: all six used native image maps packed and readable, original 15 actions retained. Static export audit reports no failures. Animation changes have not started.

## Animation pass

Use Nob-Animation-Work.blend for the articulated claw and melee attack; see ANIMATION_WORK.md. The modeling source above remains the preserved baseline. Animated review export: Nob-Claw-Attack-review.glb. Native game integration remains unverified.

## Claw-side pauldron fit correction

The extra yellow claw-side shell and its two rivets have been removed. A thin dark inner liner follows the native pauldron rim, fully inset under the original armour. It shares the original Torso attachment so both layers remain nested while the arm moves. Both editable source and animation scenes were updated without changing action keys or the other meshes. The opposite shoulder retains its fitted shell. Source and reimported animated GLB checks find zero liner/pauldron triangle intersections, with at least 0.629 world units of vertex-to-surface clearance across half-frame samples. See pauldron-fit-rest.png, pauldron-fit-raised.png and pauldron-fit-source.json.
