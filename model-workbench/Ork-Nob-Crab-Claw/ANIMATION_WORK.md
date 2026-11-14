# Regular Nob animation work

Open `Nob-Animation-Work.blend`. The final modeled source `Ork-Nob-Crab-Claw.blend` is unchanged. The animation file opens with `Nob - Crab claw attack` active at frame 1, 24 fps, frames 1-65. Press Space in Blender to preview. Select OrkBoy_rig and use the Action Editor to switch to `Nob - Crab claw mechanism` (frames 1-49).

Attack: frame 1 ready; 16 open wind-up; 20 anticipation hold; 27 downstroke; 30 snap/impact; 36 grip hold; 43 wrench; 52 release/recovery; 65 ready. This is a planted-foot heavy chop with torso twist and lean. The 2.67-second clip returns to its opening pose. The independent mechanism clip takes two seconds and demonstrates two open/snap cycles without moving the arm.

`Nob_ClawJaw` rotates about the actual transverse axle. Local Y: -42 degrees fully open, +9.939 degrees tip-to-tip closure, zero the original modeled rest gap. `Nob_ClawWrist` inherits the forearm directly so cuff and socket do not separate between samples. LeftHand copies this helper for the remaining body boundary weights. Jaw and ram bones follow the wrist. Barrel orientation changes with the pin endpoints while barrel length stays fixed; piston length changes with jaw motion. A seated clevis pin joins piston to the moving jaw side plate.

The original fifteen imported actions are retained unchanged as data. Apart from rebuilding the two small ram cylinders and adding the clevis pin, model geometry, native materials, hat, jaw guard and standard are preserved. New helper/hinge bones and the wrist constraint mean this is an authored animation rig, not yet a validated native engine skeleton.

`Nob-Claw-Attack-review.glb` contains the sampled skeletal attack with standard PBR preview materials derived from the native textures. It was independently reimported. Verification samples both clips at half-frame intervals for hinge/wrist/foot drift, verifies tip closure and travel, checks blades against the body at each whole frame, and compares reimported joints at representative poses. All checks pass; maximum reimport joint error is below 0.0001 world units. These are local animation and review artifacts. Native Gladius exporter, gameplay impact events and in-game timing remain unverified.

Reproduce animation construction with `tools/animate_nob_crab.py -- --skip-previews`, render with `tools/render_nob_animation.py`, and audit/export with `tools/verify_nob_animation.py` through Blender background mode. Avoid regenerating the modeling source when editing the animation working scene.
