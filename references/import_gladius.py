"""
Gladius Blender Import Script
Extracted from Import_Script.blend
Imports .msh (mesh), .dds (textures), and .anm (animation) files from Warhammer 40K: Gladius.
"""

bl_info = {
    "name": "Gladius Import",
    "author": "toffster",
    "version": (1, 6, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > Gladius, File > Import",
    "description": "Import .msh, .dds, .anm from Warhammer 40K: Gladius",
    "category": "Import-Export",
}

import math
import os
import re
import json
import copy
import uuid
import xml.etree.ElementTree as ET

import bpy
import numpy as np
from struct import iter_unpack, unpack
from mathutils import Euler, Vector, Matrix, Quaternion
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import AddonPreferences, Operator, Panel


MSH_MAGIC = b"MSH1.0"
VERTEX_STRIDE_BONED = 80
VERTEX_STRIDE_UNBONED = 48
FACE_BLOCK_BONED = 240
FACE_BLOCK_UNBONED = 144
VERTS_PER_FACE = 3
VERTEX_TANGENT_SEARCH = b"\x76\x65\x72\x74\x65\x78\x54\x61\x6e\x67\x65\x6e\x74\x00\x04"
BBOX_ENTRY_SKIP = 49
BBOX_ENTRY_SIZE = 44

# Length of a bone with no joint to end at, sized from mesh bounds.
_DISPLAY_LENGTH_FRACTION = 0.06
_DISPLAY_LENGTH_MIN_FRACTION = 0.04
_DISPLAY_LENGTH_ABS_MIN = 0.07
_DISPLAY_LENGTH_MAX_FRACTION = 0.13

# A bone ends at the nearest bone head within this angle of its engine +X axis. Across the 9130
# bones of the shipped meshes with more than one bone, heads on the axis cluster below 0.001° (float
# rounding of exported chains) and chance alignments grow with the angle; the density between them
# is lowest from 0.05° to 0.1°.
_JOINT_AXIS_TOLERANCE = math.radians(0.1)
_PIVOT_COLLECTION = "Gladius Pivots"

_TEAM_COLOR_PROPERTY = "gladius_team_color"
# The Data root an import came from, whose FactionManager.xml lists the player colours.
_DATA_ROOT_PROPERTY = "gladius_data_root"
# FactionManager.xml "Teclis Blue", the engine's default colour for the first lobby player.
_DEFAULT_TEAM_COLOR = (0.19, 0.49, 0.76)
# WorldGenerator::createNeutralPlayer gives the neutral player, owner of Units/Neutral, this colour.
_NEUTRAL_TEAM_COLOR = (0.5, 0.5, 0.5)
# Model::Model's colour before a player owns it; objects without the property show it.
_MODEL_TEAM_COLOR = (1.0, 1.0, 1.0)
_UNIT_SIC_GROUP = "unit_sic/1"
_MATERIAL_GRAPH = "unit/2"


def _bone_tuple_from_floats(matrix_floats):
    """Rows of the engine bone matrix from its 16 MSH floats.

    proxy::core::Matrix is column-major and MeshLoader memcpys the floats, so file floats 0-2, 4-6
    and 8-10 are the bone's X, Y and Z axes in model space and 12-14 its head (Gladius.bin
    Mesh::transform and the Unit.spv `bones` uniform)."""
    return (
        (matrix_floats[0], matrix_floats[4], matrix_floats[8], matrix_floats[12]),
        (matrix_floats[1], matrix_floats[5], matrix_floats[9], matrix_floats[13]),
        (matrix_floats[2], matrix_floats[6], matrix_floats[10], matrix_floats[14]),
        (matrix_floats[3], matrix_floats[7], matrix_floats[11], matrix_floats[15]),
    )


def _rest_matrix_from_bind(bind):
    """Blender rest frame of an engine bind: bone +Y along engine +X, the axis each exported bone
    points down toward its next joint, and bone +Z along engine +Z made orthogonal to it, so bone +X
    is engine -Y. This is the inverse of the +90° Z turn in Proxy's getRotatedMatrix
    (proxy-studios-export/MeshExporter.py), so an orthonormal bind round-trips through the exporter.

    Blender rest frames carry no scale or shear. The engine never reads the bind's 3x3 when skinning,
    and attachments use the stored bind itself, so a scaled, sheared or mirrored bind loses nothing."""
    x_axis = bind.col[0].xyz
    z_axis = bind.col[2].xyz
    if x_axis.length <= 1e-12:
        x_axis = bind.col[1].xyz.cross(z_axis)
    x_axis = x_axis.normalized() if x_axis.length > 1e-12 else Vector((1.0, 0.0, 0.0))
    z_axis = z_axis - x_axis * z_axis.dot(x_axis)
    z_axis = z_axis.normalized() if z_axis.length > 1e-12 else x_axis.orthogonal().normalized()
    y_axis = z_axis.cross(x_axis)
    rest = Matrix.Identity(4)
    for row in range(3):
        rest[row][0], rest[row][1], rest[row][2], rest[row][3] = (
            -y_axis[row], x_axis[row], z_axis[row], bind[row][3])
    return rest


def _joint_bone_lengths(heads, axes, display_length):
    """Length of each bone: to the nearest head on its axis, else the length of a bone ending at its
    head (Blender's FBX importer sizes leaf bones from their parent), else the display length."""
    heads = np.asarray(heads, dtype=np.float64).reshape(-1, 3)
    axes = np.asarray(axes, dtype=np.float64).reshape(-1, 3)
    lengths = np.zeros(len(heads))
    ends = np.full(len(heads), -1)
    for index, (head, axis) in enumerate(zip(heads, axes)):
        offsets = heads - head
        along = offsets @ axis
        across = np.linalg.norm(offsets - np.outer(along, axis), axis=1)
        on_axis = (along > 1e-3 * display_length) & (np.arctan2(across, along) <= _JOINT_AXIS_TOLERANCE)
        if on_axis.any():
            ends[index] = np.flatnonzero(on_axis)[np.argmin(along[on_axis])]
            lengths[index] = along[ends[index]]
    for index in np.flatnonzero(ends < 0):
        incoming = lengths[ends == index]
        lengths[index] = incoming.max() if incoming.size else display_length
    return lengths.tolist()


def _mesh_rig_display_length(mesh_obj, fraction=_DISPLAY_LENGTH_FRACTION):
    """Viewport edit-bone segment length from mesh bounds (never from file scale)."""
    mesh = mesh_obj.data if mesh_obj else None
    if not mesh or not mesh.vertices:
        return max(_DISPLAY_LENGTH_ABS_MIN, 1.0)
    coords = [Vector(v.co) for v in mesh.vertices]
    mins = [min(c[i] for c in coords) for i in range(3)]
    maxs = [max(c[i] for c in coords) for i in range(3)]
    extent = max(maxs[i] - mins[i] for i in range(3))
    diagonal = Vector(
        (maxs[0] - mins[0], maxs[1] - mins[1], maxs[2] - mins[2])
    ).length
    ref = max(extent, diagonal)
    length = ref * fraction
    floor = max(_DISPLAY_LENGTH_ABS_MIN, ref * _DISPLAY_LENGTH_MIN_FRACTION)
    cap = ref * _DISPLAY_LENGTH_MAX_FRACTION
    return max(floor, min(length, cap))


def _gladius_global_matrix(parent_bone=None):
    """Shared parent transform for mesh and bones (game +X → Blender +X, no extra Z rotation)."""
    if parent_bone is None:
        return Matrix.Identity(4)
    return parent_bone.matrix_local.copy()


def _orient_position(vec, global_matrix=None):
    """Map MSH vertex positions to Blender space (game +X forward → Blender +X)."""
    gm = global_matrix if global_matrix is not None else Matrix.Identity(4)
    oriented = gm @ Vector(vec)
    return (oriented.x, oriented.y, oriented.z)


def _orient_direction(vec, global_matrix=None):
    """Map MSH normals/tangents to Blender space (same axis convention as positions)."""
    gm = global_matrix if global_matrix is not None else Matrix.Identity(4)
    rot = gm.to_3x3()
    v = rot @ Vector(vec)
    if v.length > 1e-6:
        v.normalize()
        return (v.x, v.y, v.z)
    return (0.0, 0.0, 1.0)


def _reset_gladius_rig_pose(rig, frame=0):
    """Clear unkeyed pose offsets and evaluate the requested frame without changing mode."""
    if rig is None or rig.type != "ARMATURE":
        return
    scene = bpy.context.scene
    for pose_bone in rig.pose.bones:
        pose_bone.matrix_basis.identity()
    scene.frame_set(int(frame))
    depsgraph = bpy.context.view_layer.depsgraph
    if depsgraph:
        depsgraph.update()


def _rig_name_mesh_stem(name):
    """The mesh stem in the `<mesh>_rig` name every importer version gives a rig, with Blender's
    `.NNN` on either part (`Guardsman.001_rig`, `Guardsman_rig.001`); None for any other name."""
    name = re.sub(r"\.\d{3}$", "", name)
    return re.sub(r"\.\d{3}$", "", name[:-4]) if name.endswith("_rig") else None


def _gladius_unit_name_from_object(obj):
    """Resolve source identity independently of Blender display names."""
    if not obj:
        return None
    if obj.get("gladius_source_unit"):
        return obj["gladius_source_unit"]
    if obj.type == "ARMATURE":
        return _rig_name_mesh_stem(obj.name)
    if obj.type == "MESH":
        for m in getattr(obj, "modifiers", []) or []:
            if getattr(m, "type", "") == "ARMATURE" and getattr(m, "object", None):
                arm = m.object
                if arm:
                    return _gladius_unit_name_from_object(arm)
        if obj.parent:
            return _gladius_unit_name_from_object(obj.parent)
    return None


def _cleanup_actions_for_unit(unit_name, import_id=None):
    """Explicit deletion only: keep every action still used by another object or strip."""
    if not unit_name:
        return
    to_remove = [
        a for a in bpy.data.actions
        if a.get("gladius_unit") == unit_name
        and (not import_id or a.get("gladius_import_id") == import_id)
        and a.users <= int(a.use_fake_user)
    ]
    for a in to_remove:
        bpy.data.actions.remove(a)


def get_addon_preferences(context):
    prefs = context.preferences.addons.get(__name__)
    return prefs.preferences if prefs else None


def _frame_viewport_on_selected(context):
    """Frame 3D viewport on selected objects. Uses temp_override to target a VIEW_3D area."""
    if not context.screen:
        return
    for area in context.screen.areas:
        if area.type == "VIEW_3D":
            for region in area.regions:
                if region.type == "WINDOW":
                    with context.temp_override(area=area, region=region):
                        try:
                            bpy.ops.view3d.view_selected()
                        except (RuntimeError, AttributeError):
                            pass
                    # After view_selected, show textures — but only upgrade from
                    # Wireframe/Solid so a user already in Rendered isn't downgraded.
                    # Workbench has no Material Preview; its Solid mode draws textures.
                    space = area.spaces.active
                    if hasattr(space, "shading") and space.type == "VIEW_3D":
                        if space.shading.type in ("WIREFRAME", "SOLID"):
                            if context.scene.render.engine == "BLENDER_WORKBENCH":
                                space.shading.type = "SOLID"
                                space.shading.color_type = "TEXTURE"
                            else:
                                space.shading.type = "MATERIAL"
                    return  # Only act on first 3D view


def _gladius_prefs_scale_preset_update(prefs, _context):
    if prefs.default_scale_preset == "HEX":
        prefs.default_import_scale = 0.4
    elif prefs.default_scale_preset == "FULL":
        prefs.default_import_scale = 1.0


def _gladius_prefs_scale_value_update(prefs, _context):
    if prefs.default_scale_preset != "CUSTOM":
        scale = prefs.default_import_scale
        preset = "HEX" if abs(scale - 0.4) < 0.001 else "FULL" if abs(scale - 1.0) < 0.001 else "CUSTOM"
        if prefs.default_scale_preset != preset:
            prefs.default_scale_preset = preset


class GLADIUS_AddonPreferences(AddonPreferences):
    bl_idname = __name__

    data_root: StringProperty(
        name="Data Root",
        description="Path to Gladius Data folder (game install or extracted). Used for texture fallbacks and XML unit animation imports",
        default="",
        subtype="DIR_PATH",
    )
    default_frame_viewport: BoolProperty(
        name="Frame Viewport (default)",
        description="When importing mesh/unit, zoom the 3D view to fit the imported object",
        default=True,
    )
    default_set_scene_frame_range: BoolProperty(
        name="Set Scene Frame Range (default)",
        description="When importing animation, set the timeline end to match the animation length",
        default=True,
    )
    default_auto_play_on_use: BoolProperty(
        name="Auto-play on Play",
        description="When clicking Play in the animation picker, start timeline playback immediately",
        default=True,
    )
    last_mesh_import_dir: StringProperty(default="", subtype="DIR_PATH", options={"HIDDEN"})
    last_anim_import_dir: StringProperty(default="", subtype="DIR_PATH", options={"HIDDEN"})
    last_texture_import_dir: StringProperty(default="", subtype="DIR_PATH", options={"HIDDEN"})

    default_scale_preset: EnumProperty(
        name="Default Scale",
        description="Default import scale for new imports. Hex (0.4) fits common Gladius+ hex maps",
        items=[
            ("FULL", "Full (1.0)", "Import at game scale"),
            ("HEX", "Hex (0.4)", "Scale for hex-board scenes"),
            ("CUSTOM", "Custom", "Use the custom scale value below"),
        ],
        default="FULL",
        update=_gladius_prefs_scale_preset_update,
    )
    default_import_scale: FloatProperty(
        name="Import Scale",
        description="Multiply imported mesh/rig size by this value (e.g. 0.4 to fit Gladius+ hex scale)",
        default=1.0,
        min=0.01,
        max=10.0,
        soft_min=0.1,
        soft_max=2.0,
        step=0.1,
        update=_gladius_prefs_scale_value_update,
    )
    negate_normals: BoolProperty(
        name="Negate normals",
        description="Flip normals (multiply by -1). Use if faces appear dark or inside-out after import",
        default=False,
    )
    recalculate_normals_and_tangents: BoolProperty(
        name="Recalculate normals and tangents",
        description="When off, uses MSH normals and tangents from file (preserves sharp edges). When on, Blender recalculates via calc_tangents (smooth shading)",
        default=False,
    )
    import_weld_modifier: BoolProperty(
        name="Weld modifier",
        description="Add Weld when recalculating normals (smooth workflow). Off by default with file normals to preserve sharp edges",
        default=False,
    )
    default_team_color: FloatVectorProperty(
        name="Default Team Colour",
        description="Player colour new imports start with, except neutral units, which take the neutral player's grey; the Gladius tab changes it per unit",
        subtype="COLOR_GAMMA",
        size=3,
        min=0.0,
        max=1.0,
        default=_DEFAULT_TEAM_COLOR,
    )
    show_mesh_quality: BoolProperty(
        name="Mesh Quality (Advanced)",
        description="Show advanced normal and weld import options",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        layout.label(text="Configure once, then use the Gladius tab in the 3D View sidebar.", icon="INFO")

        setup = layout.box()
        setup.label(text="Game Data", icon="FILE_FOLDER")
        setup.prop(self, "data_root")
        normalized = _normalize_data_root(self.data_root) if self.data_root else ""
        if _is_valid_data_root(normalized):
            setup.label(text="Data Root configured", icon="CHECKMARK")
        elif not self.data_root:
            col = setup.column(align=True)
            col.label(text="Set Data Root to Gladius .../Data (contains Video and World).", icon="INFO")
            col.label(text="Required for XML imports and texture fallbacks.")
        else:
            col = setup.column(align=True)
            col.label(text="Invalid Data Root — use .../Gladius Game Data/Data", icon="ERROR")
            col.label(text="Required for XML imports and texture fallbacks.")

        defaults = layout.box()
        defaults.label(text="Import Defaults", icon="IMPORT")
        defaults.prop(self, "default_scale_preset", expand=True)
        if self.default_scale_preset == "CUSTOM":
            defaults.prop(self, "default_import_scale")
        defaults.prop(self, "default_frame_viewport")
        defaults.prop(self, "default_set_scene_frame_range")
        defaults.prop(self, "default_auto_play_on_use")
        defaults.prop(self, "default_team_color")

        layout.separator()
        layout.prop(
            self,
            "show_mesh_quality",
            icon="TRIA_DOWN" if self.show_mesh_quality else "TRIA_RIGHT",
            emboss=False,
        )
        if self.show_mesh_quality:
            mesh = layout.box()
            mesh.label(text="Mesh Quality", icon="MESH_DATA")
            mesh.prop(self, "recalculate_normals_and_tangents")
            mesh.prop(self, "negate_normals")
            weld_col = mesh.column()
            weld_col.enabled = self.recalculate_normals_and_tangents
            weld_col.prop(self, "import_weld_modifier")
            if self.import_weld_modifier and not self.recalculate_normals_and_tangents:
                mesh.label(text="Weld only applies when recalculating normals.", icon="INFO")



def _anm_channel_targets(channel_names, bones):
    """Pose bone for each ANM channel in channel order, and (channel, bone) pairs where a
    positional bind drives a bone the channel does not name.

    The engine drives MSH bone i with channel i and checks only the count, so renumbered
    (Guardsman `AbdomenBone002`), repeated (TesseractVault) and renamed (HammerheadGunship
    `.Muzzle0`) channels bind by position. Only renumbering is expected: a channel that names
    another rig bone, or no bone its own name matches without trailing digits, is reported, which
    flags a clip from another skeleton with the same bone count. A clip whose names are unique and
    all on the rig binds by name; every shipped clip lists those in MSH order, and name binding
    survives bones a user adds to the rig. Rigs imported with 1.4 or earlier record no MSH order,
    so they bind only by name or by 1.4's rule for clips that add `001` to every name."""
    unique = len(set(channel_names)) == len(channel_names)
    if unique and all(name in bones for name in channel_names):
        return [bones[name] for name in channel_names], []
    missing = [name for name in channel_names if name not in bones]
    msh_bones = [bone for bone in bones.values() if "gladius_source_index" in bone.bone]
    if not msh_bones:
        stripped = [name[:-3] for name in channel_names]
        if (unique and not any(name in bones for name in channel_names)
                and all(name.endswith("001") for name in channel_names)
                and len(set(stripped)) == len(stripped) and all(name in bones for name in stripped)):
            return [bones[name] for name in stripped], []
        raise ValueError(
            f"ANM channels do not match armature: {', '.join(missing[:8]) or 'repeated channel names'}; "
            "re-import the unit with importer 1.6 or later to bind them by MSH position")
    if len(channel_names) != len(msh_bones):
        raise ValueError(
            f"ANM has {len(channel_names)} channels for {len(msh_bones)} armature bones "
            f"and names that do not match: {', '.join(missing[:8]) or 'repeated channel names'}")
    renamed = []
    for name, bone in zip(channel_names, msh_bones):
        source = bone.bone.get("gladius_source_name", bone.name)
        if bones.get(name, bone) != bone or (
                name not in bones and re.sub(r"\d+$", "", name) != re.sub(r"\d+$", "", source)):
            renamed.append((name, source))
    return msh_bones, renamed


def _parse_anm_bytes(data):
    """Validate a complete clip before allocating or changing Blender data."""
    if len(data) < 16 or data[:7] != b"ANM1.0\0":
        raise ValueError("Invalid or truncated ANM1.0 header")
    bone_count, frame_count, source_fps = unpack("<BLL", data[7:16])
    if not bone_count or not frame_count or not source_fps:
        raise ValueError("ANM channel count, frame count and sample rate must be positive")
    offset = 16
    channels = []
    for _ in range(bone_count):
        end = data.find(b"\0", offset)
        if end < 0:
            raise ValueError("Truncated ANM channel name")
        name = data[offset:end].decode("utf-8")
        if not name:
            raise ValueError("Empty ANM channel name")
        offset = end + 1
        sample_end = offset + frame_count * 40
        if sample_end > len(data):
            raise ValueError(f"Truncated ANM samples for {name}")
        samples = list(iter_unpack("<10f", data[offset:sample_end]))
        for frame, sample in enumerate(samples):
            if not all(math.isfinite(v) for v in sample):
                raise ValueError(f"Nonfinite ANM sample: {name}, frame {frame}")
            if sum(v * v for v in sample[3:7]) <= 1e-12:
                raise ValueError(f"Zero ANM quaternion: {name}, frame {frame}")
        channels.append((name, samples))
        offset = sample_end
    if offset != len(data):
        raise ValueError("ANM contains unexpected trailing bytes")
    return frame_count, source_fps, channels


def _source_pose_bones(rig):
    """Pose bones by source name in MSH order; bones the import did not create follow, except pivots."""
    result = {}
    for bone in sorted((item for item in rig.pose.bones if not item.bone.get("gladius_pivot")), key=lambda item: (
            "gladius_source_index" not in item.bone, item.bone.get("gladius_source_index", 0))):
        name = bone.bone.get("gladius_source_name", bone.name)
        if name in result:
            raise ValueError(f"Duplicate source bone name on armature: {name}")
        result[name] = bone
    return result


def _rig_layout(rig):
    """How clips key a rig: "pivot" rigs (1.6) key each bone's pivot and rotation in the bind's frame,
    "bone" rigs (1.4 and earlier) key the bone in another rest frame."""
    return "pivot" if any(bone.get("gladius_pivot") for bone in rig.data.bones) else "bone"


def _action_layout(action):
    """The rig layout an imported clip keys; importers before 1.6 keyed only "bone" rigs and left no
    tag. None for actions the importer did not make."""
    if not action.get("gladius_source_fps"):
        return None
    return action.get("gladius_rig_layout", "bone")


def _set_action_rotation_modes(rig, action):
    if action.get("gladius_source_fps"):
        bones = _source_pose_bones(rig)
        for name in action.get("gladius_channels", []):
            if name in bones:
                bones[name].rotation_mode = "QUATERNION"


def _load_anm_to_rig(filepath, rig, unit_name=None, anim_type=None, variant=None, set_active_action=True,
                     report_fn=None):
    """Return (action, source frame count); invalid files raise before scene mutation."""
    if rig is None or rig.type != "ARMATURE":
        raise ValueError("Select an armature to import animation")
    if rig.mode == "EDIT":
        raise ValueError("Leave armature Edit Mode before importing animation")
    with open(filepath, "rb") as f:
        frame_count, source_fps, channels = _parse_anm_bytes(f.read())
    targets, renamed = _anm_channel_targets([name for name, _ in channels], _source_pose_bones(rig))
    scene = bpy.context.scene
    frame_step = scene.render.fps / scene.render.fps_base / source_fps
    unit_name = unit_name or _gladius_unit_name_from_object(rig)
    action_name = os.path.splitext(os.path.basename(filepath))[0]
    if unit_name and anim_type:
        action_name = f"{unit_name}_{anim_type}"
        if variant is not None:
            action_name += f"_{variant}"
    had_animation_data = rig.animation_data is not None
    rig.animation_data_create()
    anim_data = rig.animation_data
    previous_action = anim_data.action
    previous_slot = anim_data.action_slot
    poses = [(bone, bone.rotation_mode, bone.matrix_basis.copy()) for bone in rig.pose.bones]
    action = bpy.data.actions.new(name=action_name)
    succeeded = False
    try:
        action.frame_range = (0, (frame_count - 1) * frame_step)
        action.use_fake_user = True
        action["gladius_source_fps"] = source_fps
        action["gladius_source_sample_count"] = frame_count
        action["gladius_channels"] = [bone.bone.get("gladius_source_name", bone.name) for bone in targets]
        action["gladius_rig_layout"] = _rig_layout(rig)
        if unit_name:
            action["gladius_unit"] = unit_name
        if rig.get("gladius_import_id"):
            action["gladius_import_id"] = rig["gladius_import_id"]
        if rig.get("gladius_component_id"):
            action["gladius_component_id"] = rig["gladius_component_id"]
        if anim_type:
            action["gladius_type"] = anim_type
        if variant is not None:
            action["gladius_variant"] = variant
        # keyframe_insert always writes to the active action, including batch imports.
        anim_data.action = action
        for (source_name, samples), bone in zip(channels, targets):
            bone.rotation_mode = "QUATERNION"
            rest = bone.bone.matrix_local
            rest_rotation = rest.to_quaternion()
            pivot = bone.parent if bone.parent and bone.parent.bone.get("gladius_pivot") else None
            if pivot:
                paths = [pivot.path_from_id("location"), pivot.path_from_id("scale"),
                         bone.path_from_id("rotation_quaternion")]
            else:
                paths = [bone.path_from_id(prop) for prop in ("location", "rotation_quaternion", "scale")]
            previous_rotation = None
            for frame, sample in enumerate(samples):
                # Animation::getTransformation: T(p)·S(s)·R(q) about the bind head, s along model axes.
                # Samples are not unit length (|q| 0.986-1.010) and Quaternion::getNlerp blends them
                # raw, so keys keep the raw norm; Blender normalizes the blend as getNlerp does.
                rotation = Quaternion((sample[6], *sample[3:6]))
                if pivot:
                    pivot.location = sample[:3]
                    pivot.scale = sample[7:10]
                    bone.rotation_quaternion = rest_rotation.inverted() @ rotation @ rest_rotation
                else:
                    # A rig without pivots holds only scale along its bone axes: exact for uniform scale.
                    bone.matrix = (Matrix.Translation(rest.translation + Vector(sample[:3]))
                                   @ Matrix.Diagonal((*sample[7:10], 1.0))
                                   @ (rotation.normalized() @ rest_rotation).to_matrix().to_4x4())
                    bone.rotation_quaternion = bone.rotation_quaternion * rotation.magnitude
                # getNlerp takes the short arc between neighbouring samples; make_compatible would
                # also rescale a raw key to the previous key's norm.
                if previous_rotation is not None and bone.rotation_quaternion.dot(previous_rotation) < 0:
                    bone.rotation_quaternion = -bone.rotation_quaternion
                previous_rotation = bone.rotation_quaternion.copy()
                for path in paths:
                    if not rig.keyframe_insert(data_path=path, frame=frame * frame_step, group=bone.name):
                        raise RuntimeError(f"Could not key ANM channel {source_name}")
        for layer in action.layers:
            for strip in layer.strips:
                for channelbag in strip.channelbags:
                    for curve in channelbag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation = "LINEAR"
        succeeded = True
    finally:
        if not succeeded or not set_active_action:
            anim_data.action = previous_action
            if previous_action is not None and previous_slot is not None:
                anim_data.action_slot = previous_slot
        for bone, mode, basis in poses:
            bone.rotation_mode = mode
            bone.matrix_basis = basis
        if not succeeded:
            bpy.data.actions.remove(action)
            if not had_animation_data:
                rig.animation_data_clear()
    if set_active_action:
        _set_action_rotation_modes(rig, action)
        scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
    if renamed and report_fn:
        pairs = ", ".join(f"{channel}→{bone}" for channel, bone in renamed[:4])
        report_fn({"WARNING"}, f"{os.path.basename(filepath)}: bound by MSH position as the game does; "
                               f"{len(renamed)} channel(s) drive bones they do not name ({pairs}"
                               f"{', …' if len(renamed) > 4 else ''})")
    return action, frame_count


def _read_cstring(data, offset, max_len=256):
    """Read a bounded UTF-8 string and return its next byte offset."""
    if offset < 0 or offset >= len(data):
        raise ValueError("Missing binary string")
    end = data.find(b"\0", offset, min(len(data), offset + max_len + 1))
    if end < 0:
        raise ValueError("Unterminated or overlong binary string")
    return data[offset:end].decode("utf-8"), end + 1


def read_string(data, offset, max_len=256):
    """Compatibility wrapper; parsers use _read_cstring for byte offsets."""
    return _read_cstring(data, offset, max_len)[0]


def _read_msh_bones(msh):
    bone_data = {}
    off = 8
    for _ in range(msh[7]):
        name, off = _read_cstring(msh, off)
        if not name or name in bone_data or off + 64 > len(msh):
            raise ValueError("Invalid or duplicate MSH bone record")
        values = unpack("<16f", msh[off:off + 64])
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Nonfinite MSH bind matrix")
        bone_data[name] = _bone_tuple_from_floats(values)
        off += 64
    return bone_data, off


def _validate_msh_influences(vertices, bone_count):
    for vertex in vertices:
        combined = {}
        for index, weight in vertex.influences():
            if weight > 0 and index >= bone_count:
                raise ValueError(f"MSH bone index {index} exceeds {bone_count} bones")
            if weight > 0:
                combined[index] = combined.get(index, 0.0) + weight
        if any(weight > 1.00001 for weight in combined.values()):
            raise ValueError("Combined MSH bone weight exceeds one")


def _vd_get_attr(vd, canonical_name, aliases, default):
    """Get attribute from vd, trying canonical name then aliases. Used for layout flexibility."""
    val = vd.get(canonical_name)
    if val is not None:
        return val
    for alt in aliases:
        val = vd.get(alt)
        if val is not None:
            return val
    return default


def _parse_msh_structured(msh):
    """Parse MSH1.0 vertex tables and optional uint32 triangle indices."""
    if len(msh) < 8:
        return None
    if msh[:6] != MSH_MAGIC or msh[6] != 0:
        return None
    bone_data, off = _read_msh_bones(msh)
    if off + 38 > len(msh):
        return None
    off += 37
    unk_type2 = msh[off]
    off += 1
    if off + 48 > len(msh):
        return None
    off += 48
    bounding_geo_header = None
    if unk_type2 == 2:
        if off >= len(msh):
            return None
        bg_name, off = _read_cstring(msh, off)
        if off + 44 > len(msh):
            return None
        bg_pos = unpack("<3f", msh[off:off + 12])
        bg_unk = unpack("<f", msh[off + 12:off + 16])[0]
        bg_quat_xyzw = unpack("<4f", msh[off + 16:off + 32])
        bg_scale = unpack("<3f", msh[off + 32:off + 44])
        off += 44
        if not all(math.isfinite(value) for value in (*bg_pos, *bg_quat_xyzw, *bg_scale)):
            raise ValueError("Nonfinite MSH bounding geometry")
        if not any(bg_quat_xyzw):
            raise ValueError("Zero MSH bounding quaternion")
        bounding_geo_header = {
            "name": bg_name,
            "position": bg_pos,
            "quaternion_wxyz": (bg_quat_xyzw[3], bg_quat_xyzw[0], bg_quat_xyzw[1], bg_quat_xyzw[2]),
            "scale": bg_scale,
        }
    if off + 26 > len(msh):
        return None
    off += 25
    layout_size = msh[off]
    off += 1
    if layout_size > 32:
        return None
    vertex_layout = {}
    for _ in range(layout_size):
        if off >= len(msh):
            return None
        attr_name, off = _read_cstring(msh, off)
        if off >= len(msh):
            return None
        attr_count = msh[off]
        off += 1
        if not attr_name or attr_name in vertex_layout or not 1 <= attr_count <= 16:
            return None
        vertex_layout[attr_name] = attr_count
    if off + 4 > len(msh):
        return None
    data_size = unpack("<L", msh[off : off + 4])[0]
    off += 4
    floats_per_vertex = sum(vertex_layout.values())
    if floats_per_vertex == 0 or data_size % floats_per_vertex:
        return None
    vertex_cnt = data_size // floats_per_vertex
    vertex_end = off + data_size * 4
    if vertex_end > len(msh):
        return None
    # Empty and zero-count index buffers both mean an unindexed triangle list.
    indices = range(vertex_cnt)
    if vertex_end < len(msh):
        if vertex_end + 4 > len(msh):
            return None
        index_count = unpack("<L", msh[vertex_end:vertex_end + 4])[0]
        if vertex_end + 4 + index_count * 4 != len(msh):
            return None
        if index_count:
            indices = unpack("<" + "L" * index_count, msh[vertex_end + 4:])
            if any(index >= vertex_cnt for index in indices):
                return None
    if len(indices) % 3:
        return None
    widths = (
        ("vertexPosition", ("position", "pos"), (2, 3), True),
        ("vertexTextureCoordinate", ("vertexUv", "texCoord", "uv"), (2,), False),
        ("vertexNormal", ("normal", "norm"), (3,), False),
        ("vertexTangent", ("tangent", "tang"), (4,), False),
        ("vertexBoneWeights", ("boneWeights",), (4,), False),
        ("vertexBoneIndices", ("boneIndices", "boneIndex"), (4,), False),
        ("vertexOrigin", (), (4,), False),
        ("vertexColor", (), (4,), False),
        ("vertexIntensity", (), (1,), False),
    )
    for name, aliases, allowed, required in widths:
        width = _vd_get_attr(vertex_layout, name, aliases, None)
        if (required and width is None) or (width is not None and width not in allowed):
            return None
    vertex_data = []
    for _ in range(vertex_cnt):
        vd = {}
        for name, count in vertex_layout.items():
            vd[name] = unpack("<" + "f" * count, msh[off:off + count * 4])
            off += count * 4
        px = _vd_get_attr(vd, "vertexPosition", ("position", "pos"), ())
        if len(px) == 2:
            px = (*px, 0.0)
        uv = _vd_get_attr(vd, "vertexTextureCoordinate", ("vertexUv", "texCoord", "uv"), (0, 0))
        nm = _vd_get_attr(vd, "vertexNormal", ("normal", "norm"), (0, 0, 1))
        tg = _vd_get_attr(vd, "vertexTangent", ("tangent", "tang"), (1, 0, 0, 1))
        bw = _vd_get_attr(vd, "vertexBoneWeights", ("boneWeights",), (0, 0, 0, 0))
        bi = _vd_get_attr(vd, "vertexBoneIndices", ("boneIndices", "boneIndex"), (-1, -1, -1, -1))
        extras = {name: vd[name] for name in ("vertexOrigin", "vertexColor", "vertexIntensity") if name in vd}
        vertex_data.append(GladiusVertex(*px, *uv, *nm, *tg, *bw, *bi, attributes=extras))
    _validate_msh_influences(vertex_data, len(bone_data))
    face_data = [GladiusFace(*(vertex_data[index] for index in indices[i:i + 3]))
                 for i in range(0, len(indices), 3)]
    return (face_data, vertex_data, bool(bone_data), bone_data, bounding_geo_header)


class GladiusVertex:
    def __init__(self,
                 position_x, position_y, position_z,
                 uv_x, uv_y,
                 normal_x, normal_y, normal_z,
                 tangent_1, tangent_2, tangent_3, tangent_4,
                 bone_weight_1=0, bone_weight_2=0, bone_weight_3=0, bone_weight_4=0,
                 bone_index_1=-1, bone_index_2=-1, bone_index_3=-1, bone_index_4=-1,
                 attributes=None):
        values = (position_x, position_y, position_z, uv_x, uv_y,
                  normal_x, normal_y, normal_z, tangent_1, tangent_2, tangent_3, tangent_4)
        self.attributes = attributes or {}
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Nonfinite MSH vertex attribute")
        if any(not math.isfinite(value) for attr in self.attributes.values() for value in attr):
            raise ValueError("Nonfinite MSH extra vertex attribute")
        weights = (bone_weight_1, bone_weight_2, bone_weight_3, bone_weight_4)
        indices = (bone_index_1, bone_index_2, bone_index_3, bone_index_4)
        for index, weight in zip(indices, weights):
            if not math.isfinite(weight) or not 0 <= weight <= 1.00001:
                raise ValueError("Invalid MSH bone weight")
            if weight > 0 and (not math.isfinite(index) or index < 0 or int(index) != index):
                raise ValueError("Invalid MSH bone index")
        self.position_x = position_x
        self.position_y = position_y
        self.position_z = position_z
        self.bone_weight_1 = bone_weight_1
        self.bone_weight_2 = bone_weight_2
        self.bone_weight_3 = bone_weight_3
        self.bone_weight_4 = bone_weight_4
        # assign bone indices, but ignore those with no weight data (file format doesn't distinguish between index 0 and null byte)
        self.bone_index_1 = int(bone_index_1) if self.bone_weight_1 > 0 else -1
        self.bone_index_2 = int(bone_index_2) if self.bone_weight_2 > 0 else -1
        self.bone_index_3 = int(bone_index_3) if self.bone_weight_3 > 0 else -1
        self.bone_index_4 = int(bone_index_4) if self.bone_weight_4 > 0 else -1
        self.uv_x = uv_x
        self.uv_y = uv_y
        self.normal_x = normal_x
        self.normal_y = normal_y
        self.normal_z = normal_z
        self.tangent_1 = tangent_1
        self.tangent_2 = tangent_2
        self.tangent_3 = tangent_3
        self.tangent_4 = tangent_4

    def influences(self):
        return zip(
            (self.bone_index_1, self.bone_index_2, self.bone_index_3, self.bone_index_4),
            (self.bone_weight_1, self.bone_weight_2, self.bone_weight_3, self.bone_weight_4),
        )

    def get_blender_vertex(self):
        return (self.position_x, self.position_y, self.position_z)

    def get_blender_vector(self):
        return Vector((self.position_x, self.position_y, self.position_z))

    def get_blender_normal(self):
        return (self.normal_x, self.normal_y, self.normal_z)

    def get_blender_tangent(self):
        """Return (Tx, Ty, Tz) for mesh attribute. tangent_4 is handedness."""
        return (self.tangent_1, self.tangent_2, self.tangent_3)

    def get_tangent_handedness(self):
        """Return tangent_4 (handedness, typically ±1)."""
        return self.tangent_4


class GladiusFace:
    def __init__(self, vertex1, vertex2, vertex3):
        self.vertex1 = vertex1
        self.vertex2 = vertex2
        self.vertex3 = vertex3

    def get_blender_vertices(self):
        return [self.vertex1.get_blender_vertex(), self.vertex2.get_blender_vertex(), self.vertex3.get_blender_vertex()]


def _pref_recalculate_normals(prefs):
    if not prefs:
        return False
    if hasattr(prefs, "recalculate_normals_and_tangents"):
        return prefs.recalculate_normals_and_tangents
    return getattr(prefs, "use_blender_normals", False)


def _pref_import_weld(prefs):
    if not prefs:
        return False
    return getattr(prefs, "import_weld_modifier", False)


def _should_add_weld_modifier(prefs):
    return _pref_import_weld(prefs) and _pref_recalculate_normals(prefs)


def _prepare_corner_normal(sv, negate=False, global_matrix=None):
    """Normalize a parsed corner normal; optional global flip and game orientation."""
    n = sv.get_blender_normal()
    if negate:
        n = (-n[0], -n[1], -n[2])
    return _orient_direction(n, global_matrix)


def _mark_sharp_edges_from_custom_normals(mesh, angle=1e-4):
    """Mark sharp_edge where corner normals differ (Blender 4.1+ shading model)."""
    if not getattr(mesh, "has_custom_normals", False):
        return
    try:
        mesh.set_sharp_from_angle(angle=angle)
    except (AttributeError, TypeError, ValueError):
        pass


def _apply_file_custom_normals(mesh, loop_normals):
    """Apply per-loop custom normals and mark sharp edges."""
    if not loop_normals or len(loop_normals) != len(mesh.loops):
        return
    mesh.normals_split_custom_set(loop_normals)
    _mark_sharp_edges_from_custom_normals(mesh)


def _write_msh_tangent_attributes(mesh, corner_tangents):
    """Store parsed MSH tangents on CORNER attributes for export round-trip."""
    if not corner_tangents or len(corner_tangents) != len(mesh.loops):
        return
    try:
        for name in ("gladius_tangent", "gladius_tangent_sign"):
            if name in mesh.attributes:
                mesh.attributes.remove(mesh.attributes[name])
        tangent_attr = mesh.attributes.new("gladius_tangent", "FLOAT_VECTOR", "CORNER")
        sign_attr = mesh.attributes.new("gladius_tangent_sign", "FLOAT", "CORNER")
        for i, (t1, t2, t3, t4) in enumerate(corner_tangents):
            tv = Vector((t1, t2, t3))
            if tv.length > 1e-6:
                tv.normalize()
            tangent_attr.data[i].vector = (tv.x, tv.y, tv.z)
            sign_attr.data[i].value = float(t4) if t4 else 1.0
    except (IndexError, AttributeError, TypeError):
        pass


def _apply_recalculated_tangents(mesh):
    """Recalculate tangents from UVs (smooth normals path)."""
    if not mesh.uv_layers or "UVMap" not in mesh.uv_layers or len(mesh.loops) == 0:
        return
    try:
        # mesh.calc_normals() was removed in Blender 4.0+; normals are auto-computed.
        mesh.calc_tangents(uvmap="UVMap")
        corner_tangents = []
        for loop in mesh.loops:
            t = loop.tangent
            corner_tangents.append((t[0], t[1], t[2], loop.bitangent_sign))
        _write_msh_tangent_attributes(mesh, corner_tangents)
    except (AttributeError, IndexError, RuntimeError):
        pass


def _write_msh_extra_attributes(mesh, vertices):
    """Retain game vertex data without pretending to reproduce its shaders."""
    fields = (
        ("vertexOrigin", "gladius_origin", "FLOAT_VECTOR", "vector", slice(0, 3)),
        ("vertexOrigin", "gladius_origin_w", "FLOAT", "value", 3),
        ("vertexColor", "gladius_color", "FLOAT_COLOR", "color", slice(None)),
        ("vertexIntensity", "gladius_intensity", "FLOAT", "value", 0),
    )
    for source, name, kind, prop, part in fields:
        if not vertices or source not in vertices[0].attributes:
            continue
        attribute = mesh.attributes.new(name, kind, "CORNER")
        for item, vertex in zip(attribute.data, vertices):
            setattr(item, prop, vertex.attributes[source][part])


class ParsedMsh:
    __slots__ = (
        "face_data",
        "vertex_data",
        "msh_has_bones",
        "bone_data",
        "bounding_geo",
        "used_structured_path",
        "face_structure_offset",
        "number_of_faces",
        "skipped_faces",
    )

    def __init__(
        self,
        face_data,
        vertex_data,
        msh_has_bones,
        bone_data,
        bounding_geo,
        used_structured_path,
        face_structure_offset=0,
        number_of_faces=0,
        skipped_faces=0,
    ):
        self.face_data = face_data
        self.vertex_data = vertex_data
        self.msh_has_bones = msh_has_bones
        self.bone_data = bone_data or {}
        self.bounding_geo = bounding_geo
        self.used_structured_path = used_structured_path
        self.face_structure_offset = face_structure_offset
        self.number_of_faces = number_of_faces
        self.skipped_faces = skipped_faces


def _read_binary_vertex(msh, vertex_start, stride, msh_has_bones):
    if vertex_start + stride > len(msh):
        return None
    [vertex_position_x] = unpack("<f", msh[vertex_start : vertex_start + 4])
    [vertex_position_y] = unpack("<f", msh[vertex_start + 4 : vertex_start + 8])
    [vertex_position_z] = unpack("<f", msh[vertex_start + 8 : vertex_start + 12])
    if msh_has_bones:
        [bone_weight_1] = unpack("<f", msh[vertex_start + 12 : vertex_start + 16])
        [bone_weight_2] = unpack("<f", msh[vertex_start + 16 : vertex_start + 20])
        [bone_weight_3] = unpack("<f", msh[vertex_start + 20 : vertex_start + 24])
        [bone_weight_4] = unpack("<f", msh[vertex_start + 24 : vertex_start + 28])
        [bone_index_1] = unpack("<f", msh[vertex_start + 28 : vertex_start + 32])
        [bone_index_2] = unpack("<f", msh[vertex_start + 32 : vertex_start + 36])
        [bone_index_3] = unpack("<f", msh[vertex_start + 36 : vertex_start + 40])
        [bone_index_4] = unpack("<f", msh[vertex_start + 40 : vertex_start + 44])
        [vertex_uv_x] = unpack("<f", msh[vertex_start + 44 : vertex_start + 48])
        [vertex_uv_y] = unpack("<f", msh[vertex_start + 48 : vertex_start + 52])
        [vertex_normal_x] = unpack("<f", msh[vertex_start + 52 : vertex_start + 56])
        [vertex_normal_y] = unpack("<f", msh[vertex_start + 56 : vertex_start + 60])
        [vertex_normal_z] = unpack("<f", msh[vertex_start + 60 : vertex_start + 64])
        [vertex_tangent_1] = unpack("<f", msh[vertex_start + 64 : vertex_start + 68])
        [vertex_tangent_2] = unpack("<f", msh[vertex_start + 68 : vertex_start + 72])
        [vertex_tangent_3] = unpack("<f", msh[vertex_start + 72 : vertex_start + 76])
        [vertex_tangent_4] = unpack("<f", msh[vertex_start + 76 : vertex_start + 80])
        return GladiusVertex(
            vertex_position_x, vertex_position_y, vertex_position_z,
            vertex_uv_x, vertex_uv_y,
            vertex_normal_x, vertex_normal_y, vertex_normal_z,
            vertex_tangent_1, vertex_tangent_2, vertex_tangent_3, vertex_tangent_4,
            bone_weight_1, bone_weight_2, bone_weight_3, bone_weight_4,
            bone_index_1, bone_index_2, bone_index_3, bone_index_4,
        )
    [vertex_uv_x] = unpack("<f", msh[vertex_start + 12 : vertex_start + 16])
    [vertex_uv_y] = unpack("<f", msh[vertex_start + 16 : vertex_start + 20])
    [vertex_normal_x] = unpack("<f", msh[vertex_start + 20 : vertex_start + 24])
    [vertex_normal_y] = unpack("<f", msh[vertex_start + 24 : vertex_start + 28])
    [vertex_normal_z] = unpack("<f", msh[vertex_start + 28 : vertex_start + 32])
    [vertex_tangent_1] = unpack("<f", msh[vertex_start + 32 : vertex_start + 36])
    [vertex_tangent_2] = unpack("<f", msh[vertex_start + 36 : vertex_start + 40])
    [vertex_tangent_3] = unpack("<f", msh[vertex_start + 40 : vertex_start + 44])
    [vertex_tangent_4] = unpack("<f", msh[vertex_start + 44 : vertex_start + 48])
    return GladiusVertex(
        vertex_position_x, vertex_position_y, vertex_position_z,
        vertex_uv_x, vertex_uv_y,
        vertex_normal_x, vertex_normal_y, vertex_normal_z,
        vertex_tangent_1, vertex_tangent_2, vertex_tangent_3, vertex_tangent_4,
    )


def _parse_msh_binary(msh):
    """Legacy binary parser for non-MSH1.0 files. Returns ParsedMsh or None."""
    idx = msh.rfind(VERTEX_TANGENT_SEARCH)
    if idx < 0 or len(msh) < 8:
        return None
    data_size_offset = idx + 15
    if data_size_offset + 4 > len(msh):
        return None
    data_size_val = unpack("<L", msh[data_size_offset : data_size_offset + 4])[0]
    face_structure_offset = data_size_offset + 4
    msh_has_bones = msh[7] > 0
    stride = VERTEX_STRIDE_BONED if msh_has_bones else VERTEX_STRIDE_UNBONED
    face_block = FACE_BLOCK_BONED if msh_has_bones else FACE_BLOCK_UNBONED
    floats_per_vert = stride // 4
    if data_size_val == 0 or data_size_val % floats_per_vert != 0:
        return None
    number_of_vertices = data_size_val // floats_per_vert
    if number_of_vertices % VERTS_PER_FACE != 0:
        return None
    number_of_faces = number_of_vertices // VERTS_PER_FACE
    if face_structure_offset + data_size_val * 4 > len(msh):
        return None
    bone_data, bone_end = _read_msh_bones(msh)
    if bone_end > idx:
        return None

    face_data = []
    vertex_data = []
    skipped_faces = 0
    for face_id in range(number_of_faces):
        vertices = []
        face_start = face_structure_offset + face_block * face_id
        for vertex_id in range(VERTS_PER_FACE):
            vertex_start = face_start + stride * vertex_id
            new_vertex = _read_binary_vertex(msh, vertex_start, stride, msh_has_bones)
            if new_vertex is None:
                break
            vertices.append(new_vertex)
            vertex_data.append(new_vertex)
        if len(vertices) == VERTS_PER_FACE:
            face_data.append(GladiusFace(vertices[0], vertices[1], vertices[2]))
        else:
            skipped_faces += 1

    _validate_msh_influences(vertex_data, len(bone_data))
    return ParsedMsh(
        face_data,
        vertex_data,
        msh_has_bones,
        bone_data,
        None,
        False,
        face_structure_offset,
        number_of_faces,
        skipped_faces,
    )


def _parse_msh_bytes(msh):
    """Parse .msh bytes. Returns ParsedMsh or None."""
    if len(msh) < 8:
        return None
    try:
        is_msh10 = msh[:6] == MSH_MAGIC and msh[6] == 0
        if is_msh10:
            result = _parse_msh_structured(msh)
            if result is None:
                return None
            face_data, vertex_data, msh_has_bones, bone_data, bounding_geo = result
            return ParsedMsh(face_data, vertex_data, msh_has_bones, bone_data, bounding_geo, True)
        return _parse_msh_binary(msh)
    except (ValueError, OverflowError):
        return None


def build_gladius_mesh_from_face_data(face_data, prefs=None):
    """
    Build a Blender mesh from parsed GladiusFace list (flat topology, amorgun-style).
    Used by ImportGladiusMesh and headless tests. Returns (mesh, vertex_data, nan_count).
    """
    negate = prefs and getattr(prefs, "negate_normals", False)
    recalculate = _pref_recalculate_normals(prefs)
    global_matrix = _gladius_global_matrix()

    vertex_positions = []
    loop_normals = []
    corner_tangents = []
    flat_uvs = []
    face_list = []
    vertex_data = []
    nan_count = 0

    for face_idx, face in enumerate(face_data):
        base = face_idx * 3
        corners = (face.vertex1, face.vertex2, face.vertex3)
        # Two ways to invert facing:
        #  - file-normal path (recalculate=False): keep winding, negate the custom
        #    corner normals below (handled via _prepare_corner_normal negate flag).
        #  - recalculate path: reverse winding once, keeping every corner attribute
        #    paired with its vertex.
        if recalculate and negate:
            corners = (face.vertex1, face.vertex3, face.vertex2)
        for sv in corners:
            vertex_data.append(sv)
            pos = sv.get_blender_vertex()
            if not all(math.isfinite(c) for c in pos):
                nan_count += 1
                pos = (0.0, 0.0, 0.0)
            vertex_positions.append(list(_orient_position(pos, global_matrix)))
            loop_normals.append(_prepare_corner_normal(sv, negate=negate and not recalculate, global_matrix=global_matrix))
            t_orient = _orient_direction((sv.tangent_1, sv.tangent_2, sv.tangent_3), global_matrix)
            corner_tangents.append((t_orient[0], t_orient[1], t_orient[2], sv.tangent_4))
            flat_uvs.extend((sv.uv_x, 1.0 - sv.uv_y))
        face_list.append([base, base + 1, base + 2])

    mesh = bpy.data.meshes.new("gladius_import_mesh")
    mesh.from_pydata(vertex_positions, [], face_list)

    if not recalculate:
        _apply_file_custom_normals(mesh, loop_normals)
    else:
        for polygon in mesh.polygons:
            polygon.use_smooth = True

    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_layer.data.foreach_set("uv", flat_uvs)

    if recalculate:
        _apply_recalculated_tangents(mesh)
    else:
        _write_msh_tangent_attributes(mesh, corner_tangents)
    _write_msh_extra_attributes(mesh, vertex_data)

    try:
        mesh.validate(verbose=False, clean_customdata=False)
    except TypeError:
        mesh.validate()

    return mesh, vertex_data, nan_count


def _parse_bone_data_from_binary_header(msh):
    return _read_msh_bones(msh)[0]


def _build_armature_for_mesh(rig, mesh_obj, bone_data, vertex_data, report_fn=None):
    """Build one deform bone per MSH bone, in MSH order, under a hidden pivot bone.

    The engine skins with Pose_i = T(head)·T(p)·S(s)·R(q)·T(-head) per ANM sample, scaling along
    model axes after the rotation. One Blender bone scales only along its own axes, so each bone's
    pivot carries the sample's location and scale in armature axes and the bone its rotation; with
    full scale inheritance their product is the engine pose, shear included."""
    _validate_msh_influences(vertex_data, len(bone_data))
    display_length = _mesh_rig_display_length(mesh_obj)
    binds = [Matrix(rows) for rows in bone_data.values()]
    rests = [_rest_matrix_from_bind(bind) for bind in binds]
    lengths = _joint_bone_lengths([rest.translation for rest in rests],
                                  [rest.col[1].xyz for rest in rests], display_length)
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT", toggle=False)
    edit_bones = rig.data.edit_bones
    groups = []
    names = []
    deform_bones = []
    for bone_name, rest, length in zip(bone_data, rests, lengths):
        new_bone = edit_bones.new(bone_name)
        new_bone.tail = (0.0, length, 0.0)
        new_bone.matrix = rest
        names.append(new_bone.name)
        deform_bones.append(new_bone)
        groups.append(mesh_obj.vertex_groups.new(name=new_bone.name))
    pivots = rig.data.collections.new(_PIVOT_COLLECTION)
    pivots.is_visible = False
    pivot_names = []
    for bone, rest, length in zip(deform_bones, rests, lengths):
        pivot = edit_bones.new(f"{bone.name}_pivot")
        pivot.head = rest.translation
        pivot.tail = rest.translation + Vector((0.0, length, 0.0))
        pivot.use_deform = False
        pivots.assign(pivot)
        bone.parent = pivot
        pivot_names.append(pivot.name)
    bpy.ops.object.mode_set(mode="OBJECT")
    for index, (actual_name, pivot_name, (source_name, source_bind)) in enumerate(
            zip(names, pivot_names, bone_data.items())):
        bone = rig.data.bones[actual_name]
        bone["gladius_source_name"] = source_name
        bone["gladius_source_index"] = index
        bone["gladius_source_bind"] = [value for row in source_bind for value in row]
        rig.data.bones[pivot_name]["gladius_pivot"] = True
    for vert_idx, sv in enumerate(vertex_data):
        combined = {}
        for index, weight in sv.influences():
            if weight > 0:
                combined[index] = combined.get(index, 0.0) + weight
        for index, weight in combined.items():
            groups[index].add([vert_idx], min(weight, 1.0), "REPLACE")


def _is_local(datablock):
    """Owned by this file: neither linked from a library nor a library override."""
    return datablock.library is None and datablock.override_library is None


def _import_structured_bounding_geo(bg, coll, parent_obj):
    gm = _gladius_global_matrix()
    pos = _orient_position(bg["position"], gm)
    bounding_geo = bpy.data.objects.new(bg["name"], None)
    bounding_geo.empty_display_type = "CUBE"
    bounding_geo.location = pos
    bounding_geo.scale = bg["scale"]
    bounding_geo.rotation_mode = "QUATERNION"
    q = Quaternion(bg["quaternion_wxyz"])
    q.normalize()
    rot_mat = gm.to_3x3() @ q.to_matrix()
    bounding_geo.rotation_quaternion = rot_mat.to_quaternion()
    coll.objects.link(bounding_geo)
    bounding_geo.parent = parent_obj
    return bounding_geo


def _import_binary_bboxes(msh, parsed, coll, parent_obj):
    bounds = []
    face_stride = FACE_BLOCK_BONED if parsed.msh_has_bones else FACE_BLOCK_UNBONED
    vertex_block_end = parsed.face_structure_offset + parsed.number_of_faces * face_stride
    bbox_offset = vertex_block_end
    if bbox_offset + 4 <= len(msh):
        bbox_offset += 4
    if bbox_offset >= len(msh) or msh[bbox_offset] <= 1:
        return bounds
    for _i in range(msh[bbox_offset] - 1):
        bbox_offset += BBOX_ENTRY_SKIP
        if bbox_offset + BBOX_ENTRY_SIZE > len(msh):
            break
        bounding_geo_name, bbox_offset = _read_cstring(msh, bbox_offset)
        if bbox_offset + BBOX_ENTRY_SIZE > len(msh):
            break
        pos = unpack("<3f", msh[bbox_offset : bbox_offset + 12])
        bbox_offset += 16
        quat_xyzw = unpack("<4f", msh[bbox_offset : bbox_offset + 16])
        bbox_offset += 16
        scale = unpack("<3f", msh[bbox_offset : bbox_offset + 12])
        bbox_offset += 12
        if not all(math.isfinite(value) for value in (*pos, *quat_xyzw, *scale)) or not any(quat_xyzw):
            raise ValueError("Invalid legacy MSH bounding geometry")
        bounds.append(_import_structured_bounding_geo({
            "name": bounding_geo_name, "position": pos, "scale": scale,
            "quaternion_wxyz": (quat_xyzw[3], *quat_xyzw[:3]),
        }, coll, parent_obj))
    return bounds


def _mesh_stem_from_path(path):
    """Object/collection name stem from a mesh file path (no .msh extension)."""
    return os.path.splitext(os.path.basename(path))[0]


def _rig_name_for_mesh_stem(stem):
    return f"{stem}_rig"


def _legacy_rig_name_for_mesh_stem(stem):
    """Pre-v1.3.25 imports used stem.msh_rig."""
    return f"{stem}.msh_rig"


def _find_imported_mesh_and_rig(mesh_path):
    """Resolve mesh and armature after MSH import. Supports legacy .msh object names."""
    stem = _mesh_stem_from_path(mesh_path)
    mesh_obj = bpy.data.objects.get(stem)
    if not mesh_obj:
        mesh_obj = bpy.data.objects.get(stem + ".msh")
    if not mesh_obj:
        mesh_obj = next(
            (o for o in bpy.data.objects if o.type == "MESH" and stem in o.name),
            None,
        )
    rig = bpy.data.objects.get(_rig_name_for_mesh_stem(stem))
    if not rig:
        rig = bpy.data.objects.get(_legacy_rig_name_for_mesh_stem(stem))
    if not rig and mesh_obj and mesh_obj.parent and mesh_obj.parent.type == "ARMATURE":
        rig = mesh_obj.parent
    return stem, mesh_obj, rig


def _is_valid_data_root(path):
    if not path or not os.path.isdir(path):
        return False
    return os.path.isdir(os.path.join(path, "Video")) and (
        os.path.isdir(os.path.join(path, "World"))
        or os.path.isdir(os.path.join(path, "Video", "Meshes"))
    )


def _normalize_data_root(path):
    """Accept Gladius install folder or Data folder; return Data path when valid."""
    path = (path or "").strip()
    if not path:
        return ""
    path = os.path.abspath(os.path.expanduser(path))
    if _is_valid_data_root(path):
        return path
    nested = os.path.join(path, "Data")
    if _is_valid_data_root(nested):
        return nested
    if os.path.isdir(os.path.join(nested, "World")) and not os.path.isdir(os.path.join(path, "World")):
        return nested
    return path


def _sync_scale_preset_from_value(operator):
    scale = getattr(operator, "import_scale", 1.0)
    if abs(scale - 0.4) < 0.001:
        operator.scale_preset = "HEX"
    elif abs(scale - 1.0) < 0.001:
        operator.scale_preset = "FULL"
    else:
        operator.scale_preset = "CUSTOM"


def _resolve_import_scale(operator):
    properties = getattr(operator, "properties", operator)
    is_set = getattr(properties, "is_property_set", None)
    if is_set and is_set("import_scale") and not is_set("scale_preset"):
        return operator.import_scale
    preset = getattr(operator, "scale_preset", "CUSTOM")
    if preset == "HEX":
        return 0.4
    if preset == "FULL":
        return 1.0
    return getattr(operator, "import_scale", 1.0)


def _draw_import_scale_options(layout, operator):
    layout.prop(operator, "scale_preset", expand=True)
    if operator.scale_preset == "CUSTOM":
        layout.prop(operator, "import_scale")


def _import_msh_component(context, filepath, *, scale=1.0, frame_viewport=False, report_fn=None):
    """Import one validated component and return its actual collection/mesh/rig/bounds."""
    with open(filepath, "rb") as source:
        msh = source.read()
    parsed = _parse_msh_bytes(msh)
    if parsed is None:
        raise ValueError("Invalid .msh: malformed or unsupported mesh data")
    if not parsed.face_data and not parsed.bone_data:
        raise ValueError("No geometry or bones found in .msh")
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("Import scale must be finite and positive")
    previous_active = context.view_layer.objects.active
    previous_selected = list(context.selected_objects)
    previous_mode = previous_active.mode if previous_active else "OBJECT"
    kinds = ("objects", "meshes", "armatures", "materials", "collections")
    before = {kind: set(getattr(bpy.data, kind)) for kind in kinds}
    try:
        if previous_active and previous_active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        prefs = get_addon_preferences(context)
        mesh, vertices, _ = build_gladius_mesh_from_face_data(parsed.face_data, prefs)
        name = _mesh_stem_from_path(filepath)
        collection = bpy.data.collections.new(name)
        context.scene.collection.children.link(collection)
        obj = bpy.data.objects.new(name, mesh)
        obj["gladius_source_mesh"] = name
        collection.objects.link(obj)
        rig = None
        if parsed.msh_has_bones:
            rig = bpy.data.objects.new(obj.name + "_rig", bpy.data.armatures.new(obj.name + "_bones"))
            rig["gladius_source_mesh"] = name
            collection.objects.link(rig)
            obj.parent = rig
            rig.show_in_front = True
            obj.modifiers.new(type="ARMATURE", name="Armature").object = rig
            _build_armature_for_mesh(rig, obj, parsed.bone_data, vertices, report_fn=report_fn)
        bounds = []
        if parsed.bounding_geo:
            bounds.append(_import_structured_bounding_geo(parsed.bounding_geo, collection, obj))
        elif not parsed.used_structured_path:
            bounds = _import_binary_bboxes(msh, parsed, collection, obj)
        if _should_add_weld_modifier(prefs):
            obj.modifiers.new("Weld", "WELD")
        if mesh.polygons:
            mesh.materials.append(_create_fallback_material())
        (rig or obj).scale = (scale, scale, scale)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        if rig:
            rig.select_set(True)
        context.view_layer.objects.active = rig or obj
        if frame_viewport:
            _frame_viewport_on_selected(context)
        if report_fn:
            report_fn({"INFO"}, f"Imported {name}: {len(mesh.vertices)} verts, {len(mesh.polygons)} faces, {len(parsed.bone_data)} bones")
        return collection, obj, rig, bounds
    except Exception:
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for kind in kinds:
            data = getattr(bpy.data, kind)
            for item in set(data) - before[kind]:
                data.remove(item, do_unlink=True)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in previous_selected:
            obj.select_set(True)
        context.view_layer.objects.active = previous_active
        if previous_active and previous_mode != "OBJECT":
            bpy.ops.object.mode_set(mode=previous_mode)
        raise


class ImportGladiusMesh(Operator, ImportHelper):
    bl_idname = "import_mesh.gladius_msh"
    bl_label = "Import Gladius Mesh (.msh)"
    bl_description = "Import mesh geometry and armature from a Gladius .msh file (skeleton, skinning, UVs, normals)"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".msh"
    filter_glob: StringProperty(default="*.msh", options={"HIDDEN"}, maxlen=255)
    frame_viewport: BoolProperty(
        name="Frame Viewport",
        description="Zoom the 3D view to fit the imported mesh/rig in view",
        default=True,
        options={"SKIP_SAVE"},
    )
    import_scale: FloatProperty(
        name="Import Scale",
        description="Multiply imported mesh/rig size by this value for this import",
        default=1.0,
        min=0.01,
        max=10.0,
        soft_min=0.1,
        soft_max=2.0,
        step=0.1,
        options={"SKIP_SAVE"},
    )
    scale_preset: EnumProperty(
        name="Scale",
        description="Import scale preset. Hex board (0.4) fits common Gladius+ hex maps",
        items=[
            ("FULL", "Full (1.0)", "Import at game scale"),
            ("HEX", "Hex (0.4)", "Scale for hex-board scenes"),
            ("CUSTOM", "Custom", "Use a custom scale value"),
        ],
        default="FULL",
        options={"SKIP_SAVE"},
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_viewport")
        _draw_import_scale_options(layout, self)

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        if prefs:
            self.frame_viewport = prefs.default_frame_viewport
            self.import_scale = prefs.default_import_scale
            _sync_scale_preset_from_value(self)
        if prefs and prefs.last_mesh_import_dir and os.path.isdir(prefs.last_mesh_import_dir):
            self.filepath = os.path.join(prefs.last_mesh_import_dir, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            _import_msh_component(
                context, self.filepath, scale=_resolve_import_scale(self),
                frame_viewport=self.frame_viewport, report_fn=self.report,
            )
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        prefs = get_addon_preferences(context)
        if prefs:
            prefs.last_mesh_import_dir = os.path.dirname(self.filepath)
        return {"FINISHED"}


def _create_fallback_material():
    """Return a shared gray material for meshes without textures (reused to avoid
    Gladius_Untextured.001/.002 proliferation). Responds to lighting in viewport."""
    existing = bpy.data.materials.get(("Gladius_Untextured", None))
    if existing and existing.use_nodes and _is_local(existing):
        return existing
    mat = bpy.data.materials.new(name="Gladius_Untextured")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
    return mat


def _material_key(paths):
    """Use every input and the graph version; a shared diffuse does not imply a shared material."""
    files = []
    for role in ("diffuse", "normal", "sic"):
        path = paths.get(role)
        if path and os.path.isfile(path):
            stamp = os.stat(path)
            files.append((role, os.path.realpath(path), stamp.st_size, stamp.st_mtime_ns))
    return json.dumps((_MATERIAL_GRAPH, files))


def _find_existing_gladius_material(paths):
    key = _material_key(paths)
    return next((mat for mat in bpy.data.materials
                 if mat.use_nodes and mat.get("gladius_material_key") == key and _is_local(mat)), None)


def _set_gladius_image_colorspace(image, name):
    """Diffuse is sRGB colour; Normal and the SIC channel pack are data the shader reads raw."""
    if image is None:
        return
    try:
        image.colorspace_settings.name = name
    except (AttributeError, TypeError):
        pass


def _socket(sockets, identifier):
    return next(socket for socket in sockets if socket.identifier == identifier)


def _srgb_transfer(tree, color, encode):
    """Exact piecewise sRGB (IEC 61966-2-1) per component, the curve Blender's sRGB images decode
    with. Encoding a decoded image returns its stored values; decoding returns them to linear."""
    nodes, links = tree.nodes, tree.links

    def vector_math(operation, *operands):
        node = nodes.new("ShaderNodeVectorMath")
        node.operation = operation
        for socket, value in zip(node.inputs, operands):
            if isinstance(value, bpy.types.NodeSocket):
                links.new(socket, value)
            else:
                socket.default_value = (value,) * 3
        return node.outputs[0]

    if encode:
        knee, linear = 0.0031308, vector_math("MULTIPLY", color, 12.92)
        curve = vector_math("MULTIPLY_ADD", vector_math("POWER", color, 1 / 2.4), 1.055, -0.055)
    else:
        knee, linear = 0.04045, vector_math("MULTIPLY", color, 1 / 12.92)
        curve = vector_math("POWER", vector_math("MULTIPLY_ADD", color, 1 / 1.055, 0.055 / 1.055), 2.4)
    above_knee = vector_math("MULTIPLY_ADD", vector_math("SIGN", vector_math("SUBTRACT", color, knee)), 0.5, 0.5)
    select = nodes.new("ShaderNodeMix")
    select.data_type = "VECTOR"
    select.factor_mode = "NON_UNIFORM"
    links.new(_socket(select.inputs, "Factor_Vector"), above_knee)
    links.new(_socket(select.inputs, "A_Vector"), linear)
    links.new(_socket(select.inputs, "B_Vector"), curve)
    return _socket(select.outputs, "Result_Vector")


def _gladius_unit_sic_group():
    """Fragment/Unit.spv's SIC terms as one shared group. The engine samples every texture as UNORM
    and lights the raw stored values: rgb = mix(albedo, albedo * color * 1.5, sic.b). The group
    re-encodes Blender's linear diffuse, tints it there and decodes, so Base Color is the engine's
    albedo exactly. Alpha picks the Blinn exponent n = 2^(8a), or 4 at a = 1, as GGX roughness.
    Red scales an unnormalised Blinn lobe cos^n that the engine adds, in gamma space, on top of the
    diffuse. Decoded like every other term, it is decode(sic.r) * cos^(2.2n) in linear light. A
    single-scatter GGX Glossy BSDF of colour C peaks at C / (4 * alpha^2) of a white Lambert
    surface, so Specular = 8 * decode(sic.r) / (2.2n + 2) matches that peak. Green floors the
    diffuse term at albedo * sic.g, which Emission shows."""
    group = next((tree for tree in bpy.data.node_groups
                  if tree.get("gladius_node_group") == _UNIT_SIC_GROUP and _is_local(tree)), None)
    if group:
        return group
    group = bpy.data.node_groups.new("Gladius Unit SIC", "ShaderNodeTree")
    group["gladius_node_group"] = _UNIT_SIC_GROUP
    interface = group.interface
    for name, kind, default in (("Diffuse", "NodeSocketColor", (0.8, 0.8, 0.8, 1.0)),
                                ("SIC", "NodeSocketColor", (0.0, 0.0, 0.0, 1.0)),
                                ("SIC Alpha", "NodeSocketFloat", 1.0),
                                ("Team Colour", "NodeSocketColor", (*_MODEL_TEAM_COLOR, 1.0))):
        interface.new_socket(name, in_out="INPUT", socket_type=kind).default_value = default
    for name, kind in (("Base Color", "NodeSocketColor"), ("Specular", "NodeSocketColor"),
                       ("Roughness", "NodeSocketFloat"), ("Emission", "NodeSocketColor")):
        interface.new_socket(name, in_out="OUTPUT", socket_type=kind)
    nodes, links = group.nodes, group.links
    inputs, outputs = nodes.new("NodeGroupInput"), nodes.new("NodeGroupOutput")

    channels = nodes.new("ShaderNodeSeparateColor")
    links.new(channels.inputs[0], inputs.outputs["SIC"])
    team = nodes.new("ShaderNodeVectorMath")
    team.operation = "SCALE"
    team.inputs["Scale"].default_value = 1.5
    links.new(team.inputs[0], inputs.outputs["Team Colour"])
    tint = nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    links.new(_socket(tint.inputs, "Factor_Float"), channels.outputs["Blue"])
    links.new(_socket(tint.inputs, "A_Color"), _srgb_transfer(group, inputs.outputs["Diffuse"], True))
    links.new(_socket(tint.inputs, "B_Color"), team.outputs[0])
    tinted = _socket(tint.outputs, "Result_Color")
    links.new(outputs.inputs["Base Color"], _srgb_transfer(group, tinted, False))
    glow = nodes.new("ShaderNodeVectorMath")
    glow.operation = "SCALE"
    links.new(glow.inputs[0], tinted)
    links.new(glow.inputs["Scale"], channels.outputs["Green"])
    links.new(outputs.inputs["Emission"], _srgb_transfer(group, glow.outputs[0], False))

    def math_node(operation, first, second):
        node = nodes.new("ShaderNodeMath")
        node.operation = operation
        for socket, value in zip(node.inputs, (first, second)):
            if isinstance(value, bpy.types.NodeSocket):
                links.new(socket, value)
            else:
                socket.default_value = value
        return node.outputs[0]

    alpha = inputs.outputs["SIC Alpha"]
    authored = math_node("POWER", 2.0, math_node("MULTIPLY", alpha, 8.0))
    exponent = nodes.new("ShaderNodeMix")
    exponent.data_type = "FLOAT"
    _socket(exponent.inputs, "A_Float").default_value = 4.0
    links.new(_socket(exponent.inputs, "Factor_Float"), math_node("LESS_THAN", alpha, 1.0))
    links.new(_socket(exponent.inputs, "B_Float"), authored)
    # sRGB decode is close to x^2.2, so the gamma-space lobe cos^n is cos^(2.2n) in linear light.
    # Walter et al. 2007: Blinn exponent m matches GGX alpha sqrt(2 / (m + 2)); roughness = sqrt(alpha).
    linear_exponent_plus_two = math_node(
        "ADD", math_node("MULTIPLY", _socket(exponent.outputs, "Result_Float"), 2.2), 2.0)
    links.new(outputs.inputs["Roughness"],
              math_node("POWER", math_node("DIVIDE", 2.0, linear_exponent_plus_two), 0.25))
    specular = _srgb_transfer(group, channels.outputs["Red"], False)
    links.new(outputs.inputs["Specular"],
              math_node("DIVIDE", math_node("MULTIPLY", specular, 8.0), linear_exponent_plus_two))

    for index, node in enumerate(sorted(nodes, key=lambda item: item.bl_idname)):
        node.location = (200 * (index % 6), -180 * (index // 6))
    inputs.location, outputs.location = (-300, 0), (1400, 0)
    return group


def create_gladius_material(paths, name_hint=None, *, error_out=None):
    """Create Gladius material from diffuse/normal/sic paths. Uses only available paths. Requires diffuse.
    Each object's `gladius_team_color` property tints it. Public API for render scripts and external callers."""
    if not paths.get("diffuse") or not os.path.isfile(paths["diffuse"]):
        if error_out is not None:
            error_out.append(f"Diffuse texture not found: {paths.get('diffuse')}")
        return None
    existing = _find_existing_gladius_material(paths)
    if existing:
        return existing
    mat_name = f"{name_hint}_Gladius" if name_hint else "Gladius_Textures"
    material = bpy.data.materials.new(name=mat_name)
    material.use_nodes = True
    bsdf = material.node_tree.nodes["Principled BSDF"]
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    old_images = set(bpy.data.images)
    try:
        def load_image(role, required=False):
            path = paths.get(role)
            if not path or not os.path.isfile(path):
                if required:
                    raise ValueError(f"Diffuse texture not found: {path}")
                if path and error_out is not None:
                    error_out.append(f"Optional {role} texture not found: {path}")
                return None
            image = None
            try:
                image = bpy.data.images.load(path)
                if min(image.size) <= 0:
                    raise ValueError("image could not be decoded")
                return image
            except Exception as exc:
                if image is not None and image not in old_images and image.users == 0:
                    bpy.data.images.remove(image)
                if required:
                    raise ValueError(f"Cannot load diffuse texture {path}: {exc}") from exc
                if error_out is not None:
                    error_out.append(f"Cannot load optional {role} texture {path}: {exc}")
                return None

        def image_node(role, image, colorspace, location):
            node = nodes.new("ShaderNodeTexImage")
            node.label = role
            node.image = image
            node.location = location
            _set_gladius_image_colorspace(image, colorspace)
            # The engine samples each UNORM channel on its own; alpha never scales colour.
            image.alpha_mode = "CHANNEL_PACKED"
            return node

        bsdf.location = (300, 300)
        nodes["Material Output"].location = (800, 300)
        diffuse = image_node("diffuse", load_image("diffuse", required=True), "sRGB", (-700, 500))
        base_color = diffuse.outputs["Color"]
        alpha_test = nodes.new("ShaderNodeMath")
        alpha_test.label = "Gladius alpha >= 0.5"
        alpha_test.operation = "GREATER_THAN"
        alpha_test.inputs[1].default_value = 0.499999
        alpha_test.location = (0, 60)
        links.new(alpha_test.inputs[0], diffuse.outputs["Alpha"])
        # Fragment/Unit.spv discards texels with diffuse alpha below 0.5.
        links.new(bsdf.inputs["Alpha"], alpha_test.outputs[0])
        normal_map = None
        normal_image = load_image("normal")
        if normal_image:
            normal = image_node("normal", normal_image, "Non-Color", (-700, -300))
            normal_map = nodes.new("ShaderNodeNormalMap")
            normal_map.location = (0, -300)
            links.new(normal_map.inputs["Color"], normal.outputs["Color"])
            links.new(bsdf.inputs["Normal"], normal_map.outputs["Normal"])
        sic_image = load_image("sic")
        if sic_image:
            sic = image_node("sic", sic_image, "Non-Color", (-700, 220))
            # Objects without the property (not imported by this addon) show the engine's model default.
            team_attribute = nodes.new("ShaderNodeAttribute")
            team_attribute.label = "Team colour (object)"
            team_attribute.attribute_type = "OBJECT"
            team_attribute.attribute_name = _TEAM_COLOR_PROPERTY
            team_attribute.location = (-700, -60)
            team = nodes.new("ShaderNodeMix")
            team.label = "Team colour"
            team.data_type = "RGBA"
            team.location = (-400, -60)
            _socket(team.inputs, "A_Color").default_value = (*_MODEL_TEAM_COLOR, 1.0)
            links.new(_socket(team.inputs, "Factor_Float"), team_attribute.outputs["Alpha"])
            links.new(_socket(team.inputs, "B_Color"), team_attribute.outputs["Color"])
            unit_sic = nodes.new("ShaderNodeGroup")
            unit_sic.node_tree = _gladius_unit_sic_group()
            unit_sic.location = (-150, 300)
            links.new(unit_sic.inputs["Diffuse"], diffuse.outputs["Color"])
            links.new(unit_sic.inputs["SIC"], sic.outputs["Color"])
            links.new(unit_sic.inputs["SIC Alpha"], sic.outputs["Alpha"])
            links.new(unit_sic.inputs["Team Colour"], _socket(team.outputs, "Result_Color"))
            base_color = unit_sic.outputs["Base Color"]
            links.new(bsdf.inputs["Emission Color"], unit_sic.outputs["Emission"])
            bsdf.inputs["Emission Strength"].default_value = 1.0
            # The engine adds its highlight to an undimmed diffuse, so the specular lobe is a
            # separate single-scatter Glossy BSDF instead of Principled's energy-conserving layer.
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
            # The discard removes the highlight too; Principled Alpha stays the cutout glTF exports.
            specular = nodes.new("ShaderNodeVectorMath")
            specular.operation = "SCALE"
            specular.location = (100, -100)
            links.new(specular.inputs[0], unit_sic.outputs["Specular"])
            links.new(specular.inputs["Scale"], alpha_test.outputs[0])
            glossy = nodes.new("ShaderNodeBsdfGlossy")
            glossy.distribution = "GGX"
            glossy.location = (300, -100)
            links.new(glossy.inputs["Color"], specular.outputs[0])
            links.new(glossy.inputs["Roughness"], unit_sic.outputs["Roughness"])
            if normal_map:
                links.new(glossy.inputs["Normal"], normal_map.outputs["Normal"])
            add = nodes.new("ShaderNodeAddShader")
            add.location = (550, 200)
            links.new(add.inputs[0], bsdf.outputs["BSDF"])
            links.new(add.inputs[1], glossy.outputs["BSDF"])
            links.new(nodes["Material Output"].inputs["Surface"], add.outputs["Shader"])
        links.new(bsdf.inputs["Base Color"], base_color)
        material["gladius_material_key"] = _material_key(paths)
    except Exception as exc:
        if error_out is not None:
            error_out.append(f"{type(exc).__name__}: {exc}")
        bpy.data.materials.remove(material)
        for image in set(bpy.data.images) - old_images:
            if image.users == 0:
                bpy.data.images.remove(image)
        return None
    return material


def _containing_data_root(path):
    parent = os.path.dirname(os.path.abspath(path))
    while parent != os.path.dirname(parent):
        if _is_valid_data_root(parent):
            return parent
        parent = os.path.dirname(parent)
    return ""


def _source_roots_for_xml(filepath, prefs):
    roots = [root for root in (_containing_data_root(filepath),) if root]
    configured = _normalize_data_root(getattr(prefs, "data_root", ""))
    if _is_valid_data_root(configured) and configured not in roots:
        roots.append(configured)
    if not roots:
        raise ValueError("No Gladius Data root found beside XML or in addon preferences")
    return roots


def _resolve_asset(roots, folder, relative, extension):
    """Resolve a game-relative asset against the selected overlay, then base Data."""
    if not relative:
        raise ValueError(f"Missing {folder} asset name")
    relative = relative.replace("\\", "/")
    if relative.lower().endswith(extension.lower()):
        relative = relative[:-len(extension)]
    relative = os.path.normpath(relative)
    if os.path.isabs(relative) or relative == ".." or relative.startswith(".." + os.sep):
        raise ValueError(f"Asset path escapes Gladius Data: {relative}")
    candidates = [os.path.join(root, folder, relative + extension) for root in roots]
    return next((candidate for candidate in candidates if os.path.isfile(candidate)), candidates[0])


def _merge_unit_element(base, overlay):
    """Merge only the XML sections consumed by the importer."""
    base.attrib.update(overlay.attrib)
    for child in overlay:
        candidates = [old for old in base if old.tag == child.tag]
        for key in ("name", "slotName", "weaponSlotName"):
            ident = child.get(key)
            if ident:
                candidates = [old for old in candidates if old.get(key) == ident]
                break
        if len(candidates) == 1:
            _merge_unit_element(candidates[0], child)
        elif not candidates:
            base.append(copy.deepcopy(child))
        else:
            raise ValueError(f"Ambiguous XML extension element <{child.tag}>")


def _load_effective_unit_xml(filepath, roots):
    try:
        overlay = ET.parse(filepath).getroot()
        if not filepath.lower().endswith(".xml.ext"):
            return overlay
        source_root = next((root for root in roots
                            if os.path.commonpath((os.path.abspath(filepath), root)) == root), None)
        if source_root is None:
            raise ValueError(f"XML extension is outside Data roots: {filepath}")
        rel = os.path.relpath(filepath, os.path.join(source_root, "World", "Units"))[:-4]
        base_path = next((os.path.join(root, "World", "Units", rel) for root in roots
                          if os.path.isfile(os.path.join(root, "World", "Units", rel))), None)
        if base_path is None:
            raise ValueError(f"Base unit XML for extension not found: {rel}")
        base = ET.parse(base_path).getroot()
        for section in ("model", "weapons", "actions"):
            incoming = overlay.find(section)
            if incoming is None:
                continue
            existing = base.find(section)
            if existing is None:
                base.append(copy.deepcopy(incoming))
            else:
                _merge_unit_element(existing, incoming)
        return base
    except (OSError, ET.ParseError) as exc:
        raise ValueError(f"Cannot read unit XML {filepath}: {exc}") from exc


def _texture_paths_for_material(roots, material_name):
    """Read the material's actual texture references; use stem convention as fallback."""
    descriptor = _resolve_asset(roots, "Video/Materials", material_name, ".xml")
    if os.path.isfile(descriptor):
        try:
            root = ET.parse(descriptor).getroot()
        except (OSError, ET.ParseError) as exc:
            raise ValueError(f"Cannot read material {descriptor}: {exc}") from exc
        references = [tex.get("name", "") for tex in root.findall("./textures/texture")]
        return {role: (_resolve_asset(roots, "Video/Textures", references[index], ".dds")
                       if index < len(references) and references[index] else "")
                for index, role in enumerate(("diffuse", "normal", "sic"))}
    return {role: _resolve_asset(roots, "Video/Textures", material_name + suffix, ".dds")
            for role, suffix in (("diffuse", "Diffuse"), ("normal", "Normal"), ("sic", "SIC"))}


def _texture_paths_for_mesh(mesh_path, roots):
    roots = list(roots)
    parent = os.path.dirname(os.path.abspath(mesh_path))
    while parent != os.path.dirname(parent):
        if _is_valid_data_root(parent):
            if parent in roots:
                roots.remove(parent)
            roots.insert(0, parent)
            break
        parent = os.path.dirname(parent)
    stem = _mesh_stem_from_path(mesh_path)
    sibling = os.path.join(os.path.dirname(mesh_path), stem)
    mesh_abs = os.path.abspath(mesh_path)
    rel = next((os.path.relpath(mesh_abs, os.path.join(root, "Video", "Meshes"))
                for root in roots
                if os.path.commonpath((mesh_abs, os.path.join(root, "Video", "Meshes")))
                == os.path.join(root, "Video", "Meshes")), None)
    paths = {}
    for role, suffix in (("diffuse", "Diffuse"), ("normal", "Normal"), ("sic", "SIC")):
        nearby = sibling + suffix + ".dds"
        inferred = (_resolve_asset(roots, "Video/Textures",
                                  os.path.splitext(rel)[0] + suffix, ".dds") if rel else "")
        paths[role] = next((path for path in (nearby, inferred)
                            if path and os.path.isfile(path)), inferred or nearby)
    return paths


def _assign_gladius_material(mesh, paths, report_fn=None, *, required=False):
    errors = []
    material = create_gladius_material(paths, name_hint=mesh.name, error_out=errors)
    if material is None and required:
        raise ValueError(errors[0] if errors else f"Cannot create material for {mesh.name}")
    mesh.data.materials.clear()
    mesh.data.materials.append(material or _create_fallback_material())
    if report_fn:
        for error in errors:
            report_fn({"WARNING"}, error)
    return material


def _tag_gladius_component(mesh, rig, source_unit, import_id, team_color):
    component_id = uuid.uuid4().hex
    for obj in (mesh, rig):
        if obj:
            obj["gladius_source_unit"] = source_unit
            obj["gladius_import_id"] = import_id
            obj["gladius_component_id"] = component_id
    _set_team_color([obj for obj in (mesh, rig) if obj], team_color)


def _default_team_color(context, source_path):
    """Units/Neutral, artefacts included, belongs to the engine's neutral player; every other unit
    starts at the preference."""
    folders = os.path.normpath(os.path.dirname(os.path.abspath(source_path))).split(os.sep)
    if ("Units", "Neutral") in zip(folders, folders[1:]):
        return _NEUTRAL_TEAM_COLOR
    prefs = get_addon_preferences(context)
    return tuple(prefs.default_team_color) if prefs else _DEFAULT_TEAM_COLOR


def _set_team_color(objects, color):
    """Store the engine's team colour where Gladius materials read it: a custom property, so a
    .blend keeps its colours without the addon. update_tag refreshes the evaluated objects."""
    color = tuple(float(channel) for channel in color)
    for obj in objects:
        obj[_TEAM_COLOR_PROPERTY] = color
        obj.id_properties_ui(_TEAM_COLOR_PROPERTY).update(
            subtype="COLOR_GAMMA", min=0.0, max=1.0, default=_DEFAULT_TEAM_COLOR,
            description="Gladius team colour; the SIC blue areas of this object's materials take it")
        obj.update_tag()


def _get_unit_team_color(obj):
    stored = obj.get(_TEAM_COLOR_PROPERTY)
    return tuple(stored) if stored is not None and len(stored) == 3 else _MODEL_TEAM_COLOR


def _record_data_root(objects, source_path):
    root = _containing_data_root(source_path)
    for obj in objects if root else ():
        obj[_DATA_ROOT_PROPERTY] = root


def _player_color_roots(context):
    """The active unit's import Data root, then the Data Root preference."""
    roots, obj = [], context.active_object
    while obj and not obj.get(_DATA_ROOT_PROPERTY):
        obj = obj.parent
    if obj:
        roots.append(obj[_DATA_ROOT_PROPERTY])
    roots.append(_normalize_data_root(getattr(get_addon_preferences(context), "data_root", "")))
    return roots


def _player_colors(data_roots):
    """FactionManager.xml's player colours in lobby order, which FactionManager::deserializeNode
    reads as raw 0..1 values, from the first root that has it, then the neutral player's."""
    colors = []
    for root in data_roots:
        path = os.path.join(root, "World", "Blueprints", "FactionManager.xml")
        if _is_valid_data_root(root) and os.path.isfile(path):
            for element in ET.parse(path).getroot().iter("color"):
                colors.append((element.get("name"), tuple(float(value) for value in element.get("value").split())))
            break
    colors.append(("Neutral", _NEUTRAL_TEAM_COLOR))
    return colors


# Blender needs Python to hold dynamic enum strings while the menu is open.
_PLAYER_COLOR_ITEMS = []


def _player_color_items(self, context):
    _PLAYER_COLOR_ITEMS[:] = [(name, name, "RGB {:.2f} {:.2f} {:.2f}".format(*value))
                              for name, value in _player_colors(_player_color_roots(context))]
    return _PLAYER_COLOR_ITEMS


def _set_unit_team_color(obj, value):
    """Every part of a unit shares its player's colour in game, so one edit recolours them all."""
    _, _, _, objects = _get_gladius_unit_objects(obj)
    _set_team_color({obj, *objects}, value)


def _attach_to_bone_bind(obj, rig, bone, scale=(1.0, 1.0, 1.0)):
    """Parent a weapon part where Unit::refreshWeaponTransformation places it: at the unit bone's
    Pose·Bind, with Bind the stored MSH matrix including its scale (19.7 on the Wraithknight chest),
    and the weapon model's scale applied along the unit's axes before the bone translation.

    The bone's pose is Pose·rest in every frame, so the parent inverse rest⁻¹·Bind stays exact while
    animations play; a non-uniform weapon scale is exact only at rest, because the engine applies it
    after the bone's animated rotation. Blender bone parenting starts at the bone tail, so the parent
    inverse also steps back one bone length along +Y; editing that bone's length afterwards moves
    the part."""
    stored = bone["gladius_source_bind"]
    bind = Matrix([stored[0:4], stored[4:8], stored[8:12], stored[12:16]])
    placed = Matrix.Translation(bind.translation) @ Matrix.Diagonal((*scale, 1.0)) @ bind.to_3x3().to_4x4()
    obj.parent = rig
    obj.parent_type = "BONE"
    obj.parent_bone = bone.name
    obj.matrix_parent_inverse = (Matrix.Translation((0.0, -bone.length, 0.0))
                                 @ bone.matrix_local.inverted() @ placed)
    obj.matrix_basis = Matrix.Identity(4)


class ImportGladiusUnit(Operator, ImportHelper):
    bl_idname = "import_mesh.gladius_unit"
    bl_label = "Import Gladius Unit (.msh + textures)"
    bl_description = "Import mesh from .msh and apply Diffuse/Normal/SIC textures from matching DDS files in the same folder or Data Root"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".msh"
    filter_glob: StringProperty(default="*.msh", options={"HIDDEN"}, maxlen=255)
    frame_viewport: BoolProperty(
        name="Frame Viewport",
        description="Zoom the 3D view to fit the imported mesh/rig in view",
        default=True,
        options={"SKIP_SAVE"},
    )
    import_scale: FloatProperty(
        name="Import Scale",
        description="Multiply imported mesh/rig size by this value for this import",
        default=1.0,
        min=0.01,
        max=10.0,
        soft_min=0.1,
        soft_max=2.0,
        step=0.1,
        options={"SKIP_SAVE"},
    )
    scale_preset: EnumProperty(
        name="Scale",
        description="Import scale preset. Hex board (0.4) fits common Gladius+ hex maps",
        items=[
            ("FULL", "Full (1.0)", "Import at game scale"),
            ("HEX", "Hex (0.4)", "Scale for hex-board scenes"),
            ("CUSTOM", "Custom", "Use a custom scale value"),
        ],
        default="FULL",
        options={"SKIP_SAVE"},
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_viewport")
        _draw_import_scale_options(layout, self)

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        if prefs:
            self.frame_viewport = prefs.default_frame_viewport
            self.import_scale = prefs.default_import_scale
            _sync_scale_preset_from_value(self)
        if prefs and prefs.last_mesh_import_dir and os.path.isdir(prefs.last_mesh_import_dir):
            self.filepath = os.path.join(prefs.last_mesh_import_dir, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        prefs = get_addon_preferences(context)
        configured = _normalize_data_root(getattr(prefs, "data_root", ""))
        roots = [configured] if _is_valid_data_root(configured) else []
        try:
            coll, mesh, rig, _ = _import_msh_component(
                context, self.filepath, scale=_resolve_import_scale(self),
                frame_viewport=self.frame_viewport, report_fn=self.report)
        except (OSError, ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        import_id = uuid.uuid4().hex
        coll["gladius_import_id"] = import_id
        _tag_gladius_component(mesh, rig, _mesh_stem_from_path(self.filepath), import_id,
                               _default_team_color(context, self.filepath))
        _record_data_root([obj for obj in (mesh, rig) if obj], self.filepath)
        paths = _texture_paths_for_mesh(self.filepath, roots)
        _assign_gladius_material(mesh, paths, self.report)
        if prefs:
            prefs.last_mesh_import_dir = os.path.dirname(self.filepath)
        self.report({"INFO"}, f"Imported {mesh.name} with available textures.")
        return {"FINISHED"}


class ImportGladiusUnitFromXml(Operator, ImportHelper):
    bl_idname = "import_mesh.gladius_unit_from_xml"
    bl_label = "Import Gladius Unit from XML"
    bl_description = "Import mesh, textures, and all animations (including MoveBegin/MoveEnd) from a unit XML file"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".xml"
    filter_glob: StringProperty(default="*.xml;*.xml.ext", options={"HIDDEN"}, maxlen=255)
    frame_viewport: BoolProperty(
        name="Frame Viewport",
        description="Zoom the 3D view to fit the imported unit",
        default=True,
        options={"SKIP_SAVE"},
    )
    import_scale: FloatProperty(
        name="Import Scale",
        description="Multiply imported mesh/rig size by this value for this import",
        default=1.0,
        min=0.01,
        max=10.0,
        soft_min=0.1,
        soft_max=2.0,
        step=0.1,
        options={"SKIP_SAVE"},
    )
    scale_preset: EnumProperty(
        name="Scale",
        description="Import scale preset. Hex board (0.4) fits common Gladius+ hex maps",
        items=[
            ("FULL", "Full (1.0)", "Import at game scale"),
            ("HEX", "Hex (0.4)", "Scale for hex-board scenes"),
            ("CUSTOM", "Custom", "Use a custom scale value"),
        ],
        default="FULL",
        options={"SKIP_SAVE"},
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "frame_viewport")
        _draw_import_scale_options(layout, self)

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        if prefs:
            self.frame_viewport = prefs.default_frame_viewport
            self.import_scale = prefs.default_import_scale
            _sync_scale_preset_from_value(self)
        if prefs and prefs.data_root.strip():
            data_root = _normalize_data_root(prefs.data_root)
            if _is_valid_data_root(data_root):
                units_dir = os.path.join(data_root, "World", "Units")
                if os.path.isdir(units_dir):
                    self.filepath = os.path.join(units_dir, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        prefs = get_addon_preferences(context)
        created_collections = []
        prior_actions = set(bpy.data.actions)
        prior_materials = set(bpy.data.materials)
        prior_images = set(bpy.data.images)
        prior_active = context.view_layer.objects.active
        prior_selected = list(context.selected_objects)
        prior_mode = prior_active.mode if prior_active else "OBJECT"
        scene = context.scene
        prior_frames = (scene.frame_start, scene.frame_end, scene.frame_current, scene.frame_subframe)
        try:
            roots = _source_roots_for_xml(self.filepath, prefs)
            definition = _load_effective_unit_xml(self.filepath, roots)
            model = next((definition.find("model/" + tag)
                          for tag in ("unit", "structureUnit", "webwayGate")
                          if definition.find("model/" + tag) is not None), None)
            if model is None or not model.get("mesh") or not model.get("material"):
                raise ValueError(f"Unit XML has no supported mesh and material: {self.filepath}")
            source_unit = os.path.basename(self.filepath).split(".xml")[0]
            import_id = uuid.uuid4().hex
            mesh_path = _resolve_asset(roots, "Video/Meshes", model.get("mesh"), ".msh")
            if not os.path.isfile(mesh_path):
                raise ValueError(f"Body mesh not found: {mesh_path}")
            body_paths = _texture_paths_for_material(roots, model.get("material"))
            specs = _parse_unit_xml_animations(self.filepath, roots, root=definition)
            animation_suffixes = _xml_animation_suffixes(definition)

            def vector_attribute(element, name, default):
                value = element.get(name)
                if not value:
                    return default
                items = [float(item) for item in value.split()]
                if len(items) != 3 or not all(math.isfinite(item) for item in items):
                    raise ValueError(f"Invalid {element.tag} {name} in {self.filepath}: {value}")
                if name == "scale" and 0.0 in items:
                    raise ValueError(f"Zero {element.tag} scale in {self.filepath}")
                return tuple(items)

            # Resolve every declared component before creating any scene objects.
            model_position = vector_attribute(model, "position", (0.0, 0.0, 0.0))
            model_scale = vector_attribute(model, "scale", (1.0, 1.0, 1.0))
            components = []
            for weapon in definition.findall("./weapons/weapon"):
                for component in weapon.findall("./model/*"):
                    mesh_name = component.get("mesh")
                    material_name = component.get("material")
                    if not mesh_name:
                        continue
                    if not material_name:
                        raise ValueError(f"Weapon {weapon.get('name', '')} has a mesh but no material")
                    # Unit::refreshWeaponTransformation scales the weapon along the unit's axes.
                    part_scale = vector_attribute(component, "scale", (1.0, 1.0, 1.0))
                    upgraded = bool(weapon.get("requiredUpgrade"))
                    enabled = weapon.get("enabled", "1") != "0"
                    variants = []
                    if upgraded and component.get("unavailableMesh"):
                        variants.append((component.get("unavailableMesh"),
                                         component.get("unavailableMaterial") or material_name, True))
                    variants.append((mesh_name, material_name, not upgraded and enabled))
                    for part_mesh, part_material, visible in variants:
                        path = _resolve_asset(roots, "Video/Meshes", part_mesh, ".msh")
                        if not os.path.isfile(path):
                            raise ValueError(f"Weapon mesh not found: {path}")
                        paths = _texture_paths_for_material(roots, part_material)
                        components.append((weapon, component, path, paths, visible, part_scale))

            coll, mesh, rig, _ = _import_msh_component(
                context, mesh_path, frame_viewport=False, report_fn=self.report)
            created_collections.append(coll)
            coll["gladius_import_id"] = import_id
            team_color = _default_team_color(context, self.filepath)
            _tag_gladius_component(mesh, rig, source_unit, import_id, team_color)
            _assign_gladius_material(mesh, body_paths, self.report, required=True)

            assembly = bpy.data.objects.new(source_unit + "_assembly", None)
            coll.objects.link(assembly)
            assembly["gladius_source_unit"] = source_unit
            assembly["gladius_import_id"] = import_id
            assembly.scale = (_resolve_import_scale(self),) * 3
            model_root = bpy.data.objects.new(source_unit + "_model", None)
            coll.objects.link(model_root)
            model_root.parent = assembly
            model_root["gladius_source_unit"] = source_unit
            model_root["gladius_import_id"] = import_id
            model_root.location = model_position
            model_root.scale = model_scale
            _set_team_color((assembly, model_root), team_color)
            _record_data_root((assembly,), self.filepath)
            (rig or mesh).parent = model_root

            imported_parts = 0
            hidden_parts = 0
            max_animation_end = 0.0
            for weapon, component, path, paths, visible, part_scale in components:
                part_coll, part_mesh, part_rig, _ = _import_msh_component(
                    context, path, frame_viewport=False, report_fn=self.report)
                created_collections.append(part_coll)
                part_coll["gladius_import_id"] = import_id
                _tag_gladius_component(part_mesh, part_rig, source_unit, import_id, team_color)
                _assign_gladius_material(part_mesh, paths, self.report, required=True)
                part_root = part_rig or part_mesh
                bone_name = component.get("bone")
                if bone_name:
                    if rig is None:
                        raise ValueError(f"Weapon attachment {bone_name} needs a body armature")
                    bone = next((item for item in rig.data.bones
                                 if item.get("gladius_source_name", item.name) == bone_name), None)
                    if bone is None:
                        raise ValueError(f"Attachment bone {bone_name} not found in {mesh_path}")
                    _attach_to_bone_bind(part_root, rig, bone, part_scale)
                    if len(set(part_scale)) > 1:
                        self.report({"WARNING"}, f"{part_mesh.name}: non-uniform weapon scale "
                                    f"{component.get('scale')} matches the game only at rest")
                else:
                    part_root.parent = model_root
                    part_root.scale = part_scale

                suffix = component.get("animationSuffix")
                if (part_rig and suffix and
                        os.path.basename(path).lower() ==
                        os.path.basename(_resolve_asset(roots, "Video/Meshes",
                                                       component.get("mesh"), ".msh")).lower()):
                    part_rig["gladius_animation_suffix"] = suffix
                    suffix_specs = _specs_for_rig(part_rig, specs, animation_suffixes)
                    if suffix_specs:
                        _, failures, part_end = _import_animation_specs(
                            part_rig, suffix_specs, source_unit, report_fn=self.report)
                        max_animation_end = max(max_animation_end, part_end)
                        for failed_path, error in failures:
                            self.report({"WARNING"}, f"{failed_path}: {error}")
                if not visible:
                    part_coll.name = f"{source_unit} alternative {weapon.get('name', part_mesh.name)}"
                    part_coll.hide_viewport = True
                    part_coll.hide_render = True
                    hidden_parts += 1
                imported_parts += 1

            loaded = {}
            failures = []
            body_specs = _specs_for_rig(rig, specs, animation_suffixes) if rig is not None else []
            if body_specs:
                loaded, failures, body_end = _import_animation_specs(
                    rig, body_specs, source_unit, report_fn=self.report)
                max_animation_end = max(max_animation_end, body_end)
            for failed_path, error in failures:
                self.report({"WARNING"}, f"{failed_path}: {error}")
            if max_animation_end:
                scene.frame_start = 0
                scene.frame_end = max(scene.frame_end, math.ceil(max_animation_end))
                scene.frame_set(0)
            bpy.ops.object.select_all(action="DESELECT")
            mesh.select_set(True)
            if rig:
                rig.select_set(True)
            context.view_layer.objects.active = rig or mesh
            if self.frame_viewport:
                _frame_viewport_on_selected(context)
            if prefs:
                prefs.last_mesh_import_dir = os.path.dirname(mesh_path)
            self.report({"INFO"}, f"Imported {source_unit}: {imported_parts} attachment(s), "
                        f"{hidden_parts} hidden variant(s), {sum(loaded.values())} body animation(s)")
            return {"FINISHED"}
        except Exception as exc:
            if context.object and context.object.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            for coll in reversed(created_collections):
                data_blocks = [obj.data for obj in coll.objects if obj.data]
                for obj in list(coll.objects):
                    bpy.data.objects.remove(obj, do_unlink=True)
                if coll.name in bpy.data.collections:
                    bpy.data.collections.remove(coll)
                for datablock in data_blocks:
                    if datablock.users == 0:
                        if isinstance(datablock, bpy.types.Mesh):
                            bpy.data.meshes.remove(datablock)
                        elif isinstance(datablock, bpy.types.Armature):
                            bpy.data.armatures.remove(datablock)
            for action in set(bpy.data.actions) - prior_actions:
                bpy.data.actions.remove(action)
            for material in set(bpy.data.materials) - prior_materials:
                if material.users == 0:
                    bpy.data.materials.remove(material)
            for image in set(bpy.data.images) - prior_images:
                if image.users == 0:
                    bpy.data.images.remove(image)
            bpy.ops.object.select_all(action="DESELECT")
            for obj in prior_selected:
                if obj.name in bpy.data.objects:
                    obj.select_set(True)
            if prior_active and prior_active.name in bpy.data.objects:
                context.view_layer.objects.active = prior_active
                if prior_mode != "OBJECT":
                    bpy.ops.object.mode_set(mode=prior_mode)
            scene.frame_start, scene.frame_end = prior_frames[:2]
            scene.frame_set(prior_frames[2], subframe=prior_frames[3])
            self.report({"ERROR"}, f"{type(exc).__name__}: {exc}")
            return {"CANCELLED"}


class ImportGladiusTextures(Operator, ImportHelper):
    bl_idname = "import_mesh.gladius_dds"
    bl_label = "Import Gladius Textures (.dds)"
    bl_description = "Apply Diffuse, Normal, and SIC (specular) textures to the selected mesh. Select a mesh and pick any of its DDS files."
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".dds"
    filter_glob: StringProperty(default="*.dds", options={"HIDDEN"}, maxlen=255)

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        if prefs and prefs.last_texture_import_dir and os.path.isdir(prefs.last_texture_import_dir):
            self.filepath = os.path.join(prefs.last_texture_import_dir, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        obj = context.view_layer.objects.active
        if not obj or obj.type != "MESH":
            self.report({"ERROR"}, "Select a mesh object before importing textures.")
            return {"CANCELLED"}
        stem, extension = os.path.splitext(os.path.basename(self.filepath))
        if extension.lower() != ".dds":
            self.report({"ERROR"}, f"Expected a DDS file: {self.filepath}")
            return {"CANCELLED"}
        for suffix in ("Diffuse", "Normal", "SIC"):
            if stem.lower().endswith(suffix.lower()):
                stem = stem[:-len(suffix)]
                break
        directory = os.path.dirname(self.filepath)
        prefs = get_addon_preferences(context)
        configured = _normalize_data_root(getattr(prefs, "data_root", ""))
        roots = [configured] if _is_valid_data_root(configured) else []
        relative = None
        for root in roots:
            textures = os.path.join(root, "Video", "Textures")
            if os.path.commonpath((os.path.abspath(self.filepath), textures)) == textures:
                relative = os.path.relpath(os.path.join(directory, stem), textures)
                break
        paths = {}
        for role, suffix in (("diffuse", "Diffuse"), ("normal", "Normal"), ("sic", "SIC")):
            nearby = os.path.join(directory, stem + suffix + ".dds")
            inferred = (_resolve_asset(roots, "Video/Textures", relative + suffix, ".dds")
                        if relative else "")
            paths[role] = next((candidate for candidate in (nearby, inferred)
                                if candidate and os.path.isfile(candidate)), inferred or nearby)
        if not os.path.isfile(paths["diffuse"]):
            self.report({"ERROR"}, f"Diffuse texture not found: {paths['diffuse']}")
            return {"CANCELLED"}
        errors = []
        material = create_gladius_material(paths, name_hint=stem, error_out=errors)
        if material is None:
            self.report({"ERROR"}, errors[0] if errors else f"Cannot load {paths['diffuse']}")
            return {"CANCELLED"}
        for error in errors:
            self.report({"WARNING"}, error)
        obj.data.materials.clear()
        obj.data.materials.append(material)
        if _TEAM_COLOR_PROPERTY not in obj:
            _set_team_color((obj,), _default_team_color(context, self.filepath))
            _record_data_root((obj,), self.filepath)
        if prefs:
            prefs.last_texture_import_dir = directory
        self.report({"INFO"}, f"Applied textures to {obj.name}.")
        return {"FINISHED"}


class ImportGladiusAnm(Operator, ImportHelper):
    bl_idname = "import_anim.gladius_anm"
    bl_label = "Import Gladius Animation (.anm)"
    bl_description = "Load a single .anm file onto the selected armature. Use Replace to overwrite the current action, or Add to NLA for a strip."
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={"HIDDEN"}, maxlen=255)
    set_scene_frame_range: BoolProperty(
        name="Set Scene Frame Range",
        description="Extend the timeline end to at least the animation length so you can scrub the full range",
        default=True,
        options={"SKIP_SAVE"},
    )
    mode: EnumProperty(
        name="Mode",
        description="Replace overwrites the current action. Add to NLA creates a strip in the Gladius NLA track",
        items=[
            ("REPLACE", "Replace", "Replace the armature's current action (direct playback)"),
            ("NLA", "Add to NLA", "Add as a strip in the NLA editor for blending/mixing"),
        ],
        default="REPLACE",
        options={"SKIP_SAVE"},
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "mode", expand=True)
        layout.prop(self, "set_scene_frame_range")

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        if prefs:
            self.set_scene_frame_range = prefs.default_set_scene_frame_range
        if prefs and prefs.last_anim_import_dir and os.path.isdir(prefs.last_anim_import_dir):
            self.filepath = os.path.join(prefs.last_anim_import_dir, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        action = None
        try:
            rig = _animation_rig(context)
            unit_name = _gladius_unit_name_from_object(rig)
            spec = _animation_spec_from_path(self.filepath, unit_name) or _animation_spec_from_path(self.filepath)
            anim_type, _, variant = spec
            action, frame_count = _load_anm_to_rig(
                self.filepath, rig, unit_name, anim_type, variant,
                set_active_action=False, report_fn=self.report,
            )
            if self.mode == "REPLACE":
                start, end = _set_direct_animation(rig, action, self.report)
            else:
                start, end = _add_synchronized_strips(rig, action, self.report)
        except (OSError, ValueError, RuntimeError) as exc:
            if action is not None and action.users <= int(action.use_fake_user):
                bpy.data.actions.remove(action)
            self.report({"ERROR"}, f"{os.path.basename(self.filepath)}: {exc}")
            return {"CANCELLED"}
        message = f"Imported {action.name} ({frame_count} source frames)."
        if self.set_scene_frame_range:
            scene = context.scene
            scene.frame_start = 0
            scene.frame_end = max(scene.frame_end, math.ceil(end))
            scene.frame_set(math.floor(start))
            message += f" Timeline: {scene.frame_start}-{scene.frame_end}."
        _frame_viewport_on_selected(context)
        prefs = get_addon_preferences(context)
        if prefs:
            prefs.last_anim_import_dir = os.path.dirname(self.filepath)
        self.report({"INFO"}, message)
        return {"FINISHED"}


def _resolve_data_root_from_xml(filepath, prefs):
    """Resolve Gladius Data folder from prefs or XML path. Returns (data_root, used_fallback)."""
    if prefs and prefs.data_root.strip():
        normalized = _normalize_data_root(prefs.data_root)
        if _is_valid_data_root(normalized):
            return normalized, False
    xml_dir = os.path.dirname(os.path.abspath(filepath))
    for _ in range(12):
        if _is_valid_data_root(xml_dir):
            return xml_dir, True
        parent = os.path.dirname(xml_dir)
        if not parent or parent == xml_dir:
            break
        xml_dir = parent
    return "", True


def _normalize_animation_type(name):
    aliases = {"die": "Death", "death": "Death", "walk": "Move", "run": "Move"}
    return aliases.get(name.lower(), name[:1].upper() + name[1:] or "Anim")


# Action model attributes the engine loads as clips; flags such as suppressDieAnimation are not.
_UNIT_ACTION_ANIMATION_ATTRIBUTES = frozenset((
    "animation", "chargeAnimation", "chargeDefenseAnimation", "meleeAnimation", "meleeDefenseAnimation",
))


def _xml_animation_suffixes(root):
    """Suffixes a unit's weapon parts add to its clip names; Unit::playAnimation plays
    `<clip><suffix>.anm` on each part model that declares one."""
    return sorted({model.get("animationSuffix") for model in root.findall("./weapons/weapon/model/*")
                   if model.get("animationSuffix")})


def _specs_for_rig(rig, specs, part_suffixes):
    """A weapon part plays only the clips with its animationSuffix; the body plays none of those."""
    suffix = rig.get("gladius_animation_suffix")
    if suffix:
        return [spec for spec in specs if spec[0].endswith(suffix)]
    return [spec for spec in specs if not spec[0].endswith(tuple(part_suffixes))]


def _unit_body_rig(part):
    """The body armature whose clip names a weapon part's clips extend. The XML import hangs a
    bone-attached part from it and a boneless part beside it under the unit's model root."""
    parent = part.parent
    if parent is not None and parent.type == "ARMATURE":
        return parent
    bodies = [child for child in (parent.children if parent else ())
              if child.type == "ARMATURE" and not child.get("gladius_animation_suffix")
              and child.get("gladius_import_id") == part.get("gladius_import_id")]
    if len(bodies) != 1:
        raise ValueError(f"{part.name} plays its unit body's clips; import them from the unit XML")
    return bodies[0]


def _parse_unit_xml_animations(filepath, data_root, root=None):
    """Return expanded (type, full ANM path, variant) specs across source roots."""
    roots = list(data_root) if isinstance(data_root, (list, tuple)) else [data_root]
    if root is None:
        root = _load_effective_unit_xml(filepath, roots)
    result = []
    seen = set()
    suffixes = _xml_animation_suffixes(root)

    def add(atype, relative, count_text=1, optional=False):
        try:
            count = int(count_text or 1)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid animation count for {relative}: {count_text}") from exc
        if not 1 <= count <= 100:
            raise ValueError(f"Animation count out of range for {relative}: {count}")
        base = relative[:-4] if relative.lower().endswith(".anm") else relative
        for suffix in [""] + suffixes:
            for variant in range(count):
                stem = f"{base}{variant if count > 1 else ''}{suffix}"
                path = _resolve_asset(roots, "Video/Animations", stem, ".anm")
                if (optional or suffix) and not os.path.isfile(path):
                    continue
                spec = (_normalize_animation_type(atype) + suffix, path, variant if count > 1 else None)
                if spec not in seen:
                    seen.add(spec)
                    result.append(spec)

    for model in root.findall("./model/unit") + root.findall("./model/structureUnit"):
        if model.get("idleAnimation"):
            add("Idle", model.get("idleAnimation"), model.get("idleAnimationCount", 1))
    for action in root.findall("./actions/*"):
        for model_action in action.findall("./model/action"):
            for key, value in model_action.attrib.items():
                if key not in _UNIT_ACTION_ANIMATION_ATTRIBUTES or not value:
                    continue
                suffix = key[:-len("animation")]
                atype = action.tag + suffix[:1].upper() + suffix[1:]
                add(atype, value, model_action.get(key + "Count", 1))
                base = value[:-4] if value.lower().endswith(".anm") else value
                if base.lower().endswith(("move", "levitate")):
                    add(atype + "Begin", base + "Begin", optional=True)
                    add(atype + "End", base + "End", optional=True)
    return result


def _parse_unit_xml_assets(filepath, data_root):
    """Compatibility helper for callers that need the resolved body asset paths."""
    roots = []
    parent = os.path.dirname(os.path.abspath(filepath))
    while parent != os.path.dirname(parent):
        if _is_valid_data_root(parent):
            roots.append(parent)
            break
        parent = os.path.dirname(parent)
    normalized = _normalize_data_root(data_root)
    if _is_valid_data_root(normalized) and normalized not in roots:
        roots.append(normalized)
    try:
        root = _load_effective_unit_xml(filepath, roots)
        model = next((root.find("model/" + tag) for tag in
                      ("unit", "structureUnit", "webwayGate")
                      if root.find("model/" + tag) is not None), None)
        if model is None or not model.get("mesh") or not model.get("material"):
            return {}
        material_name = model.get("material")
        return {
            "mesh_path": _resolve_asset(roots, "Video/Meshes", model.get("mesh"), ".msh"),
            "material_base": os.path.join(roots[0], "Video", "Textures", material_name),
            "texture_paths": _texture_paths_for_material(roots, material_name),
            "scale": model.get("scale"),
            "position": model.get("position"),
        }
    except (ValueError, OSError, ET.ParseError):
        return {}


def _animation_spec_from_path(filepath, unit_name=None):
    stem = os.path.splitext(os.path.basename(filepath))[0]
    if unit_name:
        if not stem.startswith(unit_name):
            return None
        stem = stem[len(unit_name):]
    match = re.fullmatch(r"(.*?)(\d+)([A-Za-z_].*)?", stem)
    if match:
        name, number, suffix = match.groups()
        return _normalize_animation_type(name) + (suffix or ""), filepath, int(number)
    return _normalize_animation_type(stem), filepath, None


def _longer_sibling_meshes(dirpath, mesh_name, roots=()):
    """Other meshes whose names extend this one (Mek → MekGun): their clips share the mesh's name
    prefix but not its skeleton. They are listed from the Video/Meshes folder that mirrors this
    Video/Animations folder, in the clip's own Data root and in each of roots."""
    folder, relative = os.path.abspath(dirpath), []
    while not (os.path.basename(folder) == "Animations"
               and os.path.basename(os.path.dirname(folder)) == "Video"):
        parent = os.path.dirname(folder)
        if parent == folder:
            folder = None
            break
        relative.append(os.path.basename(folder))
        folder = parent
    if folder is None:
        return ()
    siblings = set()
    for root in (os.path.dirname(os.path.dirname(folder)), *roots):
        meshes = os.path.join(root, "Video", "Meshes", *reversed(relative))
        if os.path.isdir(meshes):
            siblings.update(entry.name[:-4] for entry in os.scandir(meshes)
                            if entry.is_file() and entry.name.lower().endswith(".msh")
                            and len(entry.name) - 4 > len(mesh_name) and entry.name.startswith(mesh_name))
    return tuple(sorted(siblings))


def _scan_folder_animations(dirpath, mesh_name=None, roots=()):
    """Group every clip named after the mesh, including numbered weapon-suffix variants."""
    result = []
    siblings = _longer_sibling_meshes(dirpath, mesh_name, roots) if mesh_name else ()
    for entry in os.scandir(dirpath):
        if entry.is_file() and entry.name.lower().endswith(".anm") and not entry.name.startswith(siblings):
            spec = _animation_spec_from_path(entry.path, mesh_name)
            if spec is not None:
                result.append(spec)
    return sorted(result, key=lambda spec: (spec[0], spec[2] if spec[2] is not None else -1, spec[1]))


def _source_mesh_name(rig):
    """The MSH stem a rig was built from; clips are named after it, not after the unit XML
    (CanoptekScarab.xml renders CanoptekScarabs.msh and plays CanoptekScarabs*.anm)."""
    if rig.get("gladius_source_mesh"):
        return rig["gladius_source_mesh"]
    # Rigs from importer 1.4 record only the unit XML; their name keeps the MSH stem.
    return _rig_name_mesh_stem(rig.name) or _gladius_unit_name_from_object(rig)


def _animation_rig(context):
    active = context.view_layer.objects.active
    if active and active.type == "ARMATURE":
        return active
    if active and active.type == "MESH":
        for modifier in active.modifiers:
            if modifier.type == "ARMATURE" and modifier.object in context.view_layer.objects.values():
                return modifier.object
        if active.parent and active.parent.type == "ARMATURE" and active.parent in context.view_layer.objects.values():
            return active.parent
    armatures = [obj for obj in context.view_layer.objects if obj.type == "ARMATURE"]
    if len(armatures) == 1:
        return armatures[0]
    raise ValueError("Select the unit's mesh or armature in the current view layer.")


class ImportGladiusUnitAnimations(Operator, ImportHelper):
    bl_idname = "import_anim.gladius_unit_animations"
    bl_label = "Import Gladius Unit Animations"
    bl_description = "Import animations from unit XML or a folder as NLA strips"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".xml"
    filter_glob: StringProperty(default="*.xml;*.xml.ext;*.anm", options={"HIDDEN"}, maxlen=255)

    def draw(self, context):
        self.layout.label(text="Pick a unit XML or any ANM in its animation folder.", icon="INFO")

    def invoke(self, context, event):
        prefs = get_addon_preferences(context)
        try:
            rig = _animation_rig(context)
        except ValueError:
            rig = None
        unit_name = _gladius_unit_name_from_object(rig)
        xml_path = _guess_unit_xml_path(unit_name, prefs) if unit_name else ""
        if xml_path:
            self.filepath = xml_path
        elif prefs and prefs.last_anim_import_dir and os.path.isdir(prefs.last_anim_import_dir):
            self.filepath = os.path.join(prefs.last_anim_import_dir, "")
        return ImportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            rig = _animation_rig(context)
            unit_name = _gladius_unit_name_from_object(rig)
            if self.filepath.lower().endswith((".xml", ".xml.ext")):
                roots = _source_roots_for_xml(self.filepath, get_addon_preferences(context))
                root = _load_effective_unit_xml(self.filepath, roots)
                specs = _parse_unit_xml_animations(self.filepath, roots, root=root)
                part_suffixes = _xml_animation_suffixes(root)
            else:
                directory = self.filepath if os.path.isdir(self.filepath) else os.path.dirname(self.filepath)
                configured = _normalize_data_root(getattr(get_addon_preferences(context), "data_root", ""))
                named_by = _unit_body_rig(rig) if rig.get("gladius_animation_suffix") else rig
                specs = _scan_folder_animations(directory, _source_mesh_name(named_by),
                                                (configured,) if _is_valid_data_root(configured) else ())
                part_suffixes = [obj["gladius_animation_suffix"] for obj in _get_gladius_unit_objects(rig)[3]
                                 if obj.type == "ARMATURE" and obj.get("gladius_animation_suffix")]
            specs = _specs_for_rig(rig, specs, part_suffixes)
        except (OSError, ValueError, ET.ParseError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        if not specs:
            self.report({"WARNING"}, "No animation files were found for this unit.")
            return {"CANCELLED"}

        loaded_by_type, failures, max_end = _import_animation_specs(rig, specs, unit_name, report_fn=self.report)
        for path, message in failures:
            self.report({"WARNING"}, f"{os.path.basename(path)}: {message}")
        loaded = sum(loaded_by_type.values())
        if not loaded:
            self.report({"WARNING"}, "No compatible animations imported; the previous animation is unchanged.")
            return {"CANCELLED"}
        context.scene.frame_start = 0
        context.scene.frame_end = max(context.scene.frame_end, math.ceil(max_end))
        context.scene.frame_set(0)
        summary = ", ".join(f"{kind}({count})" for kind, count in sorted(loaded_by_type.items()))
        self.report({"INFO"}, f"Imported {loaded} animation(s): {summary}; {len(failures)} failed.")
        prefs = get_addon_preferences(context)
        if prefs:
            prefs.last_anim_import_dir = os.path.dirname(self.filepath)
        return {"FINISHED"}


def _ensure_track(rig, name):
    tracks = rig.animation_data.nla_tracks
    for track in tracks:
        if track.name == name:
            return track
    track = tracks.new()
    track.name = name
    return track


def _next_start(track):
    return math.ceil(max((strip.frame_end + 1 for strip in track.strips), default=0))


def _animation_state(rig):
    data = rig.animation_data
    return (data is not None, data.action if data else None,
            data.action_slot if data else None, data.use_nla if data else True,
            [(bone, bone.rotation_mode, bone.matrix_basis.copy()) for bone in rig.pose.bones])


def _restore_animation_state(rig, state):
    had_data, action, slot, use_nla, poses = state
    if had_data:
        rig.animation_data_create()
        rig.animation_data.action = action
        if action is not None and slot is not None:
            rig.animation_data.action_slot = slot
        rig.animation_data.use_nla = use_nla
    elif rig.animation_data:
        rig.animation_data_clear()
    for bone, mode, basis in poses:
        bone.rotation_mode = mode
        bone.matrix_basis = basis


def _validate_animation_target(rig, action):
    if action.is_empty:
        raise ValueError(f"Action has no animation data: {action.name}")
    if rig.mode == "EDIT":
        raise ValueError("Leave armature Edit Mode before playing animation")
    if action.get("gladius_source_fps"):
        if _action_layout(action) != _rig_layout(rig):
            raise ValueError(f"{action.name} keys a rig from another importer version; "
                             f"import its ANM onto {rig.name} again")
        bones = _source_pose_bones(rig)
        missing = set(action.get("gladius_channels", [])) - bones.keys()
        if missing:
            raise ValueError(f"Action channels no longer match {rig.name}: {', '.join(sorted(missing))}")


def _add_action_strip(rig, action, track_name="Gladius", *, library=False, start=None):
    """Commit NLA playback only after Blender accepts the populated action."""
    _validate_animation_target(rig, action)
    state = _animation_state(rig)
    rig.animation_data_create()
    tracks = rig.animation_data.nla_tracks
    existing_track = next((track for track in tracks if track.name == track_name), None)
    track = existing_track or _ensure_track(rig, track_name)
    previous_mute = track.mute
    strip = None
    try:
        strip = track.strips.new(action.name, _next_start(track) if start is None else int(start), action)
        strip.extrapolation = "NOTHING"
        if library:
            if existing_track is None:
                track.mute = True
            elif not track.mute:
                strip.mute = True
        else:
            track.mute = False
            _set_action_rotation_modes(rig, action)
            rig.animation_data.action = None
            rig.animation_data.use_nla = True
    except Exception:
        if strip is not None:
            track.strips.remove(strip)
        track.mute = previous_mute
        if existing_track is None:
            tracks.remove(track)
        _restore_animation_state(rig, state)
        raise
    return strip


def _import_animation_specs(rig, specs, unit_name=None, report_fn=None):
    """Import expanded file specs independently; retain successful clips and report failures."""
    loaded_by_type, failures, max_end = {}, [], 0.0
    for anim_type, filepath, variant in specs:
        action = None
        try:
            action, _ = _load_anm_to_rig(
                filepath, rig, unit_name, anim_type, variant, set_active_action=False, report_fn=report_fn
            )
            strip = _add_action_strip(rig, action, anim_type, library=True)
        except (OSError, ValueError, RuntimeError) as exc:
            if action is not None and action.users <= int(action.use_fake_user):
                bpy.data.actions.remove(action)
            failures.append((filepath, str(exc)))
            continue
        max_end = max(max_end, strip.frame_end)
        loaded_by_type[anim_type] = loaded_by_type.get(anim_type, 0) + 1
    return loaded_by_type, failures, max_end


def _collect_unit_objects_for_rig(rig):
    """All objects to delete for a rig: the rig, its child hierarchy, and every mesh
    bound to it via an armature modifier (plus those meshes' children)."""
    to_delete = list(rig.children_recursive) + [rig]
    for o in bpy.data.objects:
        if o.type != "MESH" or o in to_delete:
            continue
        for m in getattr(o, "modifiers", []) or []:
            if getattr(m, "type", "") == "ARMATURE" and getattr(m, "object", None) == rig:
                to_delete.append(o)
                for c in o.children_recursive:
                    if c not in to_delete:
                        to_delete.append(c)
                break
    return to_delete


def _get_gladius_unit_objects(obj):
    """Resolve the selected import's assembly hierarchy without following global IDs."""
    if obj is None:
        return None, None, None, []
    unit_name = _gladius_unit_name_from_object(obj)
    if not unit_name:
        return None, None, None, []
    mesh = obj if obj.type == "MESH" else None
    rig = obj if obj.type == "ARMATURE" else None
    if mesh:
        rig = next((modifier.object for modifier in mesh.modifiers
                    if modifier.type == "ARMATURE" and modifier.object), None)
        if rig is None and mesh.parent and mesh.parent.type == "ARMATURE":
            rig = mesh.parent
    import_id = obj.get("gladius_import_id") or (rig.get("gladius_import_id") if rig else None)
    ancestor = obj
    assembly = None
    while ancestor:
        if (ancestor.type == "EMPTY" and import_id
                and ancestor.get("gladius_import_id") == import_id
                and ancestor.get("gladius_source_unit") == unit_name):
            assembly = ancestor
        ancestor = ancestor.parent
    if assembly is not None:
        return rig, mesh, unit_name, list(assembly.children_recursive) + [assembly]
    if rig and _is_gladius_rig(rig):
        if mesh is None:
            mesh = next((child for child in rig.children_recursive if child.type == "MESH"), None)
        return rig, mesh, unit_name, _collect_unit_objects_for_rig(rig)
    if obj.get("gladius_source_unit"):
        return None, mesh, unit_name, list(obj.children_recursive) + [obj]
    return None, None, None, []


def _playback_targets(rig, action, report_fn=None):
    """Pair body/weapon clips only when source type and variant match exactly."""
    targets = [(rig, action)]
    if rig.get("gladius_animation_suffix"):
        return targets
    _, _, _, objects = _get_gladius_unit_objects(rig)
    for attachment in objects:
        suffix = attachment.get("gladius_animation_suffix") if attachment.type == "ARMATURE" else None
        if attachment == rig or not suffix:
            continue
        kind = action.get("gladius_type")
        matches = [
            candidate for candidate in bpy.data.actions
            if kind and candidate.get("gladius_type") == kind + suffix
            and candidate.get("gladius_variant") == action.get("gladius_variant")
            and _action_matches_rig(candidate, attachment)
            and not candidate.is_empty
        ]
        if len(matches) == 1:
            targets.append((attachment, matches[0]))
        elif report_fn:
            report_fn({"WARNING"}, f"{attachment.name}: expected one matching {kind or 'animation'}"
                      f"{suffix} clip, found {len(matches)}; previous animation retained.")
    return targets


def _set_direct_animation(rig, action, report_fn=None):
    targets = _playback_targets(rig, action, report_fn)
    for target, clip in targets:
        _validate_animation_target(target, clip)
    states = [(target, _animation_state(target)) for target, _ in targets]
    try:
        for target, clip in targets:
            target.animation_data_create()
            target.animation_data.action = clip
            target.animation_data.use_nla = False
            _set_action_rotation_modes(target, clip)
        scene = bpy.context.scene
        scene.frame_set(scene.frame_current, subframe=scene.frame_subframe)
    except Exception:
        for target, state in states:
            _restore_animation_state(target, state)
        raise
    return min(clip.frame_range[0] for _, clip in targets), max(clip.frame_range[1] for _, clip in targets)


def _add_synchronized_strips(rig, action, report_fn=None):
    targets = _playback_targets(rig, action, report_fn)
    for target, clip in targets:
        _validate_animation_target(target, clip)
    states, strips = [], []
    start = 0
    for target, clip in targets:
        data = target.animation_data
        tracks = {track: track.mute for track in data.nla_tracks} if data else {}
        states.append((target, _animation_state(target), tracks))
        track = next((track for track in tracks if track.name == "Gladius"), None)
        if track is not None:
            start = max(start, _next_start(track))
    try:
        for target, clip in targets:
            strip = _add_action_strip(target, clip, start=start)
            track = target.animation_data.nla_tracks["Gladius"]
            strips.append((track, strip))
    except Exception:
        for track, strip in reversed(strips):
            track.strips.remove(strip)
        for target, state, tracks in states:
            data = target.animation_data
            for track in list(data.nla_tracks) if data else []:
                if track in tracks:
                    track.mute = tracks[track]
                elif not track.strips:
                    data.nla_tracks.remove(track)
            _restore_animation_state(target, state)
        raise
    return start, max(strip.frame_end for _, strip in strips)


class GLADIUS_OT_clear_anim_filter(bpy.types.Operator):
    bl_idname = "gladius.clear_anim_filter"
    bl_label = "Clear Animation Search"
    bl_description = "Clear the animation search filter"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        context.window_manager.gladius_anim_filter = ""
        return {"FINISHED"}


class GLADIUS_OT_select_rig(bpy.types.Operator):
    bl_idname = "gladius.select_rig"
    bl_label = "Select Gladius Rig"
    bl_description = "Select this unit's armature for animation playback"
    bl_options = {"REGISTER", "UNDO"}

    rig_name: StringProperty(name="Rig", default="")

    @classmethod
    def poll(cls, context):
        return bool(context.view_layer)

    def execute(self, context):
        rig = bpy.data.objects.get(self.rig_name)
        if (not _is_gladius_rig(rig) or rig.name not in context.view_layer.objects
                or rig.hide_select or not rig.visible_get(view_layer=context.view_layer)):
            self.report({"WARNING"}, "Armature is not selectable in the current view layer.")
            return {"CANCELLED"}
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        rig.select_set(True)
        context.view_layer.objects.active = rig
        unit = _gladius_unit_name_from_object(rig)
        context.window_manager.gladius_anim_filter = ""
        context.window_manager.gladius_anim_show_all = False
        self.report({"INFO"}, f"Selected {unit}.")
        return {"FINISHED"}


class GLADIUS_OT_set_player_color(bpy.types.Operator):
    bl_idname = "gladius.set_player_color"
    bl_label = "Player Colour"
    bl_description = "Give the active unit a player colour from FactionManager.xml in its Data root, or the neutral player's"
    bl_options = {"REGISTER", "UNDO"}

    color: EnumProperty(name="Player Colour", items=_player_color_items)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and _TEAM_COLOR_PROPERTY in context.active_object

    def execute(self, context):
        colors = dict(_player_colors(_player_color_roots(context)))
        context.active_object.gladius_unit_team_color = colors[self.color]
        return {"FINISHED"}


class GLADIUS_OT_delete_unit(bpy.types.Operator):
    bl_idname = "gladius.delete_unit"
    bl_label = "Delete Gladius Unit"
    bl_description = "Remove the Gladius unit: mesh, armature, and associated animations"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.view_layer.objects.active
        if not obj:
            return False
        _, _, unit_name, to_delete = _get_gladius_unit_objects(obj)
        return bool(unit_name and to_delete)

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        obj = context.view_layer.objects.active
        rig, mesh, unit_name, to_delete = _get_gladius_unit_objects(obj)
        if not unit_name or not to_delete:
            self.report({"WARNING"}, "Select a Gladius mesh or armature.")
            return {"CANCELLED"}
        import_id = obj.get("gladius_import_id") or (rig.get("gladius_import_id") if rig else None)
        collections = {coll for item in to_delete for coll in item.users_collection
                       if import_id and coll.get("gladius_import_id") == import_id}
        data_blocks = {item.data for item in to_delete if item.data}
        for o in reversed(to_delete):
            if o.name in bpy.data.objects:
                try:
                    bpy.data.objects.remove(o, do_unlink=True)
                except ReferenceError:
                    pass

        _cleanup_actions_for_unit(unit_name, import_id=import_id)
        for coll in collections:
            if not coll.objects and not coll.children:
                bpy.data.collections.remove(coll)
        for data in data_blocks:
            if data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Armature):
                    bpy.data.armatures.remove(data)

        self.report({"INFO"}, f"Deleted {unit_name}.")
        return {"FINISHED"}


def _deferred_animation_play(window=None):
    """Run animation_play with valid context after operator finishes."""
    if bpy.app.background:
        return None
    window = window or bpy.context.window
    if window is None or window.screen.is_animation_playing:
        return None
    for area in window.screen.areas:
        if area.type in ("DOPESHEET_EDITOR", "VIEW_3D"):
            with bpy.context.temp_override(window=window, area=area):
                bpy.ops.screen.animation_play()
            return None
    return None


class GLADIUS_OT_assign_action(bpy.types.Operator):
    bl_idname = "gladius.assign_action"
    bl_label = "Play Action"
    bl_description = "Assign this action to the armature for direct playback (NLA disabled)"
    bl_options = {"REGISTER", "UNDO"}
    action_name: StringProperty(name="Action", description="Name of the action to assign", default="")

    @classmethod
    def poll(cls, context):
        return _is_gladius_rig(context.view_layer.objects.active)

    def execute(self, context):
        rig = context.view_layer.objects.active
        if not rig or rig.type != "ARMATURE" or not self.action_name:
            return {"CANCELLED"}
        action = bpy.data.actions.get(self.action_name)
        if not action:
            return {"CANCELLED"}
        mismatch = _action_mismatch(action, rig)
        if mismatch:
            self.report({"WARNING"}, mismatch)
            return {"CANCELLED"}
        try:
            start, end = _set_direct_animation(rig, action, self.report)
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        scn = context.scene
        f0 = math.floor(start)
        f1 = max(math.ceil(end), f0 + 1)
        scn.frame_start = f0
        scn.frame_end = int(f1)
        scn.frame_set(int(f0))
        prefs = get_addon_preferences(context)
        if not bpy.app.background and prefs and getattr(prefs, "default_auto_play_on_use", True):
            window = context.window
            bpy.app.timers.register(lambda: _deferred_animation_play(window), first_interval=0.05)
        self.report({"INFO"}, f"Playing {action.name}")
        return {"FINISHED"}


class GLADIUS_OT_assign_action_nla(bpy.types.Operator):
    bl_idname = "gladius.assign_action_nla"
    bl_label = "Add to NLA"
    bl_description = "Add this action as a strip in the Gladius NLA track. Enables NLA so you can layer multiple animations."
    bl_options = {"REGISTER", "UNDO"}
    action_name: StringProperty(name="Action", description="Name of the action to add to NLA", default="")

    @classmethod
    def poll(cls, context):
        return _is_gladius_rig(context.view_layer.objects.active)

    def execute(self, context):
        rig = context.view_layer.objects.active
        if not rig or rig.type != "ARMATURE" or not self.action_name:
            return {"CANCELLED"}
        action = bpy.data.actions.get(self.action_name)
        if not action:
            return {"CANCELLED"}
        mismatch = _action_mismatch(action, rig)
        if mismatch:
            self.report({"WARNING"}, mismatch)
            return {"CANCELLED"}
        try:
            start, end = _add_synchronized_strips(rig, action, self.report)
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        scn = context.scene
        scn.frame_start = 0
        scn.frame_end = max(scn.frame_end, math.ceil(end))
        scn.frame_set(math.floor(start))
        self.report({"INFO"}, f"Added {action.name} to NLA track")
        return {"FINISHED"}


def _data_root_configured(prefs):
    return bool(prefs and prefs.data_root.strip() and _is_valid_data_root(_normalize_data_root(prefs.data_root)))


def _is_gladius_rig(obj):
    return bool(obj and obj.type == "ARMATURE" and _gladius_unit_name_from_object(obj))


_ANIM_TYPE_LABELS = {
    "Idle": "Idle",
    "Move": "Move",
    "MoveBegin": "Move Begin",
    "MoveEnd": "Move End",
    "Attack": "Attack",
    "Death": "Death",
    "Hit": "Hit",
    "Ability": "Ability",
    "Work": "Work",
    "Spawn": "Spawn",
    "Transport": "Transport",
    "Embark": "Embark",
    "Disembark": "Disembark",
}

_COMMON_ANIM_TYPES = frozenset(
    {"Idle", "Move", "MoveBegin", "MoveEnd", "Attack", "Death", "Hit", "Ability"}
)


def _format_anim_type_label(atype):
    if atype in _ANIM_TYPE_LABELS:
        return _ANIM_TYPE_LABELS[atype]
    label = []
    for i, ch in enumerate(atype):
        if ch.isupper() and i > 0:
            label.append(" ")
        label.append(ch)
    return "".join(label)


def _format_anim_variant_label(aname, unit_name, atype):
    parts = aname.split("_")
    if parts and parts[-1].isdigit():
        return f"Variant {parts[-1]}"
    prefix = f"{unit_name}_{atype}_"
    if aname.startswith(prefix):
        return aname[len(prefix) :] or aname
    return aname


def _action_mismatch(action, rig):
    """Why an action cannot play on rig, or None when it can."""
    unit_name = _gladius_unit_name_from_object(rig)
    action_unit = action.get("gladius_unit")
    if action_unit and action_unit != unit_name:
        return "This action belongs to another imported unit."
    import_id = rig.get("gladius_import_id")
    action_id = action.get("gladius_import_id")
    component_id = rig.get("gladius_component_id")
    action_component = action.get("gladius_component_id")
    if (import_id and action_id and import_id != action_id) or (
            component_id and action_component and component_id != action_component):
        return "This action belongs to another imported unit."
    layout = _action_layout(action)
    if layout and rig.type == "ARMATURE" and layout != _rig_layout(rig):
        return (f"{action.name} keys a rig from another importer version; "
                f"import its ANM onto {rig.name} again.")
    return None


def _action_matches_rig(action, rig):
    return _action_mismatch(action, rig) is None


def _collect_gladius_actions_for_unit(unit_name, rig=None):
    actions_by_type = {}
    for action in bpy.data.actions:
        if rig is not None and not _action_matches_rig(action, rig):
            continue
        gunit = action.get("gladius_unit")
        gtype = action.get("gladius_type")
        if gunit and gtype and gunit == unit_name:
            actions_by_type.setdefault(gtype, []).append(action.name)
        elif not gunit and action.name.startswith(unit_name + "_"):
            remainder = action.name[len(unit_name) + 1 :]
            atype = remainder.split("_")[0] if "_" in remainder else remainder or "Anim"
            if atype and atype[0].isalpha():
                actions_by_type.setdefault(atype, []).append(action.name)
    for atype in actions_by_type:
        actions_by_type[atype] = sorted(actions_by_type[atype])
    return actions_by_type


def _filter_gladius_actions(actions_by_type, unit_name, filter_text):
    """Narrow animation list by type or variant name (choice overload / cognitive load)."""
    needle = (filter_text or "").strip().lower()
    if not needle:
        return actions_by_type
    filtered = {}
    for atype, names in actions_by_type.items():
        type_label = _format_anim_type_label(atype).lower()
        if needle in atype.lower() or needle in type_label:
            filtered[atype] = names
            continue
        matching = [
            name
            for name in names
            if needle in name.lower()
            or needle in _format_anim_variant_label(name, unit_name, atype).lower()
        ]
        if matching:
            filtered[atype] = matching
    return filtered


def _apply_anim_type_visibility(actions_by_type, show_all):
    """Show common animation types first; hide rare types until expanded (Pareto / Hick's Law)."""
    if show_all or len(actions_by_type) <= 6:
        return actions_by_type, False
    common = {k: v for k, v in actions_by_type.items() if k in _COMMON_ANIM_TYPES}
    if len(common) >= 3:
        return common, True
    return actions_by_type, False


def _draw_quick_play_actions(layout, actions_by_type):
    """One-click play for the most common animation types (Pareto principle)."""
    row = layout.row(align=True)
    row.scale_y = 1.2
    added = False
    for atype in ("Idle", "Move", "Attack"):
        names = actions_by_type.get(atype)
        if not names:
            continue
        op = row.operator(
            GLADIUS_OT_assign_action.bl_idname,
            text=f"Play {_format_anim_type_label(atype)}",
            icon="PLAY",
        )
        op.action_name = names[0]
        added = True


def _gladius_rigs_in_scene(context=None):
    context = context or bpy.context
    return [obj for obj in context.view_layer.objects if _is_gladius_rig(obj)]


def _count_gladius_actions(unit_name, rig=None):
    return sum(len(names) for names in _collect_gladius_actions_for_unit(unit_name, rig).values())


def _guess_unit_xml_path(unit_name, prefs):
    """Best-effort unit XML path under Data Root/World/Units."""
    if not _data_root_configured(prefs):
        return ""
    units_dir = os.path.join(_normalize_data_root(prefs.data_root), "World", "Units")
    if not os.path.isdir(units_dir):
        return ""
    for root, _, files in os.walk(units_dir):
        for fn in files:
            lower = fn.lower()
            if lower.endswith(".xml.ext"):
                stem = fn[: -len(".xml.ext")]
            elif lower.endswith(".xml"):
                stem = fn[: -len(".xml")]
            else:
                continue
            if stem == unit_name:
                return os.path.join(root, fn)
    return ""


def _workflow_needs_attention(context):
    """Hide workflow banner once setup is complete (selective attention)."""
    prefs = get_addon_preferences(context)
    if not _data_root_configured(prefs):
        return True
    if not _gladius_rigs_in_scene():
        return True
    rig = context.view_layer.objects.active
    if not _is_gladius_rig(rig):
        return True
    unit_name = _gladius_unit_name_from_object(rig)
    return _count_gladius_actions(unit_name, rig) == 0


def _draw_workflow_status(layout, context):
    """Setup checklist: goal-gradient and Zeigarnik effect for incomplete workflows."""
    prefs = get_addon_preferences(context)
    box = layout.box()
    root_ok = _data_root_configured(prefs)

    if not root_ok:
        box.label(text="Setup required", icon="ERROR")
        col = box.column(align=True)
        col.label(text="1. Set Data Root to your Gladius Data folder")
        col.label(text="2. Import a unit from XML")
        col.label(text="3. Play animations on the rig")
        op = box.operator("preferences.addon_show", text="Open Gladius Settings", icon="PREFERENCES")
        op.module = __name__
        return

    box.label(text="Workflow", icon="CHECKMARK")
    rigs = _gladius_rigs_in_scene()
    if not rigs:
        col = box.column(align=True)
        col.label(text="Data Root ready", icon="CHECKMARK")
        col.operator(
            ImportGladiusUnitFromXml.bl_idname,
            text="Import Unit from XML…",
            icon="FILE",
        )
        return

    box.label(text=f"{len(rigs)} unit(s) in scene", icon="OUTLINER_OB_ARMATURE")
    rig = context.view_layer.objects.active
    if _is_gladius_rig(rig):
        unit_name = _gladius_unit_name_from_object(rig)
        anim_count = _count_gladius_actions(unit_name, rig)
        if anim_count:
            box.label(text=f"{unit_name}: {anim_count} animation(s)", icon="ANIM")
        else:
            col = box.column(align=True)
            col.label(text=f"{unit_name}: no animations yet", icon="INFO")
            col.operator(
                ImportGladiusUnitAnimations.bl_idname,
                text="Import Animations…",
                icon="IMPORT",
            )
    else:
        if not _draw_rig_picker(box, context):
            box.label(text="Select a *_rig armature for animations", icon="INFO")


def _draw_rig_picker(layout, context, max_items=10):
    """Quick-select among Gladius rigs (working memory / Fitts's Law for multi-unit scenes)."""
    rigs = _gladius_rigs_in_scene()
    if not rigs:
        return False
    active = context.view_layer.objects.active
    if len(rigs) == 1 and active != rigs[0]:
        layout.label(text=f"Tip: select {rigs[0].name}", icon="INFO")
        op = layout.operator(GLADIUS_OT_select_rig.bl_idname, text=rigs[0].name, icon="ARMATURE_DATA")
        op.rig_name = rigs[0].name
        return True
    if len(rigs) == 1:
        return True
    col = layout.column(align=True)
    col.label(text="Select a unit rig", icon="OUTLINER_OB_ARMATURE")
    for rig in rigs[:max_items]:
        unit = rig.name
        icon = "CHECKMARK" if active == rig else "ARMATURE_DATA"
        op = col.operator(GLADIUS_OT_select_rig.bl_idname, text=unit, icon=icon)
        op.rig_name = rig.name
    if len(rigs) > max_items:
        col.label(text=f"+ {len(rigs) - max_items} more in Outliner", icon="INFO")
    return True


def _draw_version_footer(layout):
    v = bl_info["version"]
    row = layout.row()
    row.alignment = "RIGHT"
    row.scale_y = 0.8
    row.label(text=f"v{v[0]}.{v[1]}.{v[2]}")


class GLADIUS_PT_animation_picker(Panel):
    bl_idname = "GLADIUS_PT_animation_picker"
    bl_label = "Gladius Animations"
    bl_description = "Play or NLA-stack animations on the selected Gladius rig"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Gladius"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        return context.area and context.area.type == "VIEW_3D"

    def draw(self, context):
        layout = self.layout
        rig = context.view_layer.objects.active

        if not rig or rig.type != "ARMATURE":
            box = layout.box()
            box.label(text="No armature selected", icon="INFO")
            if _gladius_rigs_in_scene():
                _draw_rig_picker(box, context)
            else:
                col = box.column(align=True)
                col.label(text="1. Import a unit from XML")
                col.label(text="2. Select the unit's *_rig armature")
                col.label(text="3. Play animations here")
                box.operator(
                    ImportGladiusUnitFromXml.bl_idname,
                    text="Import Unit from XML…",
                    icon="FILE",
                )
            return

        if not _is_gladius_rig(rig):
            box = layout.box()
            box.label(text="Select a Gladius rig", icon="INFO")
            box.label(text=f"Active: {rig.name}")
            _draw_rig_picker(box, context)
            return

        unit_name = _gladius_unit_name_from_object(rig)
        wm = context.window_manager
        header = layout.box()
        header.label(text=unit_name, icon="ARMATURE_DATA")
        use_nla = rig.animation_data and rig.animation_data.use_nla
        header.label(
            text="Playback: NLA tracks" if use_nla else "Playback: direct action",
            icon="NLA" if use_nla else "PLAY",
        )
        header.label(text="Play = preview now · NLA = layer strips", icon="INFO")
        if rig.animation_data and rig.animation_data.action:
            now = rig.animation_data.action.name
            if now.startswith(unit_name + "_"):
                now = now[len(unit_name) + 1 :]
            header.label(text=f"Now playing: {now}", icon="CHECKMARK")

        actions_by_type = _collect_gladius_actions_for_unit(unit_name, rig)

        if not actions_by_type:
            box = layout.box()
            box.label(text="No animations for this unit", icon="INFO")
            box.label(text="Import .anm files or batch-import from XML.")
            box.operator(
                ImportGladiusUnitAnimations.bl_idname,
                text="Import Unit Animations…",
                icon="IMPORT",
            )
            return

        _draw_quick_play_actions(header, actions_by_type)

        total_actions = sum(len(names) for names in actions_by_type.values())
        if total_actions > 3 or wm.gladius_anim_filter:
            row = layout.row(align=True)
            row.prop(wm, "gladius_anim_filter", text="Search", icon="VIEWZOOM")
            if wm.gladius_anim_filter:
                row.operator(GLADIUS_OT_clear_anim_filter.bl_idname, text="", icon="X")

        filtered_actions = _filter_gladius_actions(
            actions_by_type,
            unit_name,
            wm.gladius_anim_filter,
        )
        show_all = wm.gladius_anim_show_all
        visible_actions, truncated = _apply_anim_type_visibility(filtered_actions, show_all)
        if truncated:
            layout.prop(wm, "gladius_anim_show_all", text="Show all animation types", icon="DOWNARROW_HLT")
        elif show_all and len(filtered_actions) > 6:
            layout.prop(wm, "gladius_anim_show_all", text="Show common types only", icon="UPARROW_HLT")
        if not visible_actions:
            layout.label(text="No animations match your search.", icon="INFO")
            return

        for atype in sorted(visible_actions.keys()):
            box = layout.box()
            box.label(text=_format_anim_type_label(atype), icon="ANIM")
            for aname in visible_actions[atype]:
                variant = _format_anim_variant_label(aname, unit_name, atype)
                is_active = (
                    rig.animation_data
                    and rig.animation_data.action
                    and rig.animation_data.action.name == aname
                )
                row = box.row(align=True)
                row.label(text=variant)
                btns = row.row(align=True)
                btns.scale_x = 1.2
                op = btns.operator(
                    GLADIUS_OT_assign_action.bl_idname,
                    text="Play",
                    icon="CHECKMARK" if is_active else "PLAY",
                )
                op.action_name = aname
                op = btns.operator(
                    GLADIUS_OT_assign_action_nla.bl_idname,
                    text="NLA",
                    icon="NLA",
                )
                op.action_name = aname

        layout.separator()
        layout.operator(
            ImportGladiusUnitAnimations.bl_idname,
            text="Import More Animations…",
            icon="IMPORT",
        )
        if GLADIUS_OT_delete_unit.poll(context):
            row = layout.row()
            row.scale_y = 0.9
            row.alert = True
            row.operator(
                GLADIUS_OT_delete_unit.bl_idname,
                text="Delete Gladius Unit",
                icon="TRASH",
            )


class GLADIUS_PT_import_panel(Panel):
    bl_idname = "GLADIUS_PT_import_panel"
    bl_label = "Gladius Import"
    bl_description = "Import mesh, unit (mesh + textures), textures, and animations from Warhammer 40K: Gladius"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Gladius"
    bl_order = 0

    def draw(self, context):
        layout = self.layout
        if _workflow_needs_attention(context):
            _draw_workflow_status(layout, context)

        quick = layout.box()
        quick.label(text="Quick Start", icon="SOLO_ON")
        row = quick.row()
        row.scale_y = 1.3
        row.operator(
            ImportGladiusUnitFromXml.bl_idname,
            text="Import Unit from XML…",
            icon="FILE",
        )
        quick.operator(
            ImportGladiusUnit.bl_idname,
            text="Import Unit (mesh + textures)…",
            icon="IMPORT",
        )

        obj = context.active_object
        if obj is not None and _TEAM_COLOR_PROPERTY in obj:
            unit = layout.box()
            unit.label(text=_gladius_unit_name_from_object(obj) or obj.name, icon="MATERIAL")
            row = unit.row(align=True)
            row.prop(obj, "gladius_unit_team_color")
            row.operator_menu_enum(GLADIUS_OT_set_player_color.bl_idname, "color", text="", icon="COLOR")

        batch = layout.box()
        batch.label(text="Animations", icon="ANIM")
        batch.operator(
            ImportGladiusUnitAnimations.bl_idname,
            text="Import Unit Animations…",
            icon="IMPORT",
        )
        if not _gladius_rigs_in_scene():
            batch.label(text="Import a unit first, then batch-import its animations.", icon="INFO")

        layout.separator()
        if GLADIUS_OT_delete_unit.poll(context):
            row = layout.row()
            row.scale_y = 0.9
            row.alert = True
            row.operator(
                GLADIUS_OT_delete_unit.bl_idname,
                text="Delete Gladius Unit",
                icon="TRASH",
            )
        _draw_version_footer(layout)


class GLADIUS_PT_import_advanced(Panel):
    bl_idname = "GLADIUS_PT_import_advanced"
    bl_label = "Individual Files"
    bl_description = "Import a single mesh, texture set, or animation file"
    bl_parent_id = "GLADIUS_PT_import_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Gladius"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        obj = context.view_layer.objects.active
        layout.operator(ImportGladiusMesh.bl_idname, text="Import Mesh (.msh)…", icon="MESH_DATA")

        tex_col = layout.column()
        tex_col.enabled = bool(obj and obj.type == "MESH")
        tex_col.operator(ImportGladiusTextures.bl_idname, text="Import Textures (.dds)…", icon="TEXTURE")
        if not obj or obj.type != "MESH":
            layout.label(text="Select a mesh to apply textures.", icon="INFO")

        anim_col = layout.column()
        anim_col.enabled = bool(obj and obj.type == "ARMATURE")
        anim_col.operator(ImportGladiusAnm.bl_idname, text="Import Animation (.anm)…", icon="ANIM")
        if not obj or obj.type != "ARMATURE":
            layout.label(text="Select an armature to import animation.", icon="INFO")


def menu_func_import_mesh(self, context):
    self.layout.operator(ImportGladiusUnitFromXml.bl_idname, text="Gladius Unit from XML (.xml)", icon="FILE")
    self.layout.operator(ImportGladiusUnit.bl_idname, text="Gladius Unit (.msh + textures)", icon="IMPORT")
    self.layout.operator(ImportGladiusMesh.bl_idname, text="Gladius Mesh (.msh)", icon="MESH_DATA")


def menu_func_import_textures(self, context):
    self.layout.operator(ImportGladiusTextures.bl_idname, text="Gladius Textures (.dds)", icon="TEXTURE")


def menu_func_import_anim(self, context):
    self.layout.operator(ImportGladiusUnitAnimations.bl_idname, text="Gladius Unit Animations", icon="IMPORT")
    self.layout.operator(ImportGladiusAnm.bl_idname, text="Gladius Animation (.anm)", icon="ANIM")


def context_menu_gladius(self, context):
    obj = context.active_object
    if not obj:
        return
    if obj.type == "ARMATURE":
        self.layout.separator()
        self.layout.operator(ImportGladiusAnm.bl_idname, text="Import Gladius Animation", icon="ANIM")
        row = self.layout.row()
        row.alert = True
        row.operator(GLADIUS_OT_delete_unit.bl_idname, text="Delete Gladius Unit", icon="TRASH")
    elif obj.type == "MESH":
        rig, _, _, _ = _get_gladius_unit_objects(obj)
        if rig:
            self.layout.separator()
            row = self.layout.row()
            row.alert = True
            row.operator(GLADIUS_OT_delete_unit.bl_idname, text="Delete Gladius Unit", icon="TRASH")


def _safe_unregister_class(cls):
    try:
        bpy.utils.unregister_class(cls)
    except RuntimeError:
        pass


def register():
    bpy.utils.register_class(GLADIUS_AddonPreferences)
    bpy.utils.register_class(ImportGladiusMesh)
    bpy.utils.register_class(ImportGladiusUnit)
    bpy.utils.register_class(ImportGladiusUnitFromXml)
    bpy.utils.register_class(ImportGladiusTextures)
    bpy.utils.register_class(ImportGladiusAnm)
    bpy.utils.register_class(ImportGladiusUnitAnimations)
    bpy.utils.register_class(GLADIUS_OT_clear_anim_filter)
    bpy.utils.register_class(GLADIUS_OT_select_rig)
    bpy.utils.register_class(GLADIUS_OT_set_player_color)
    bpy.utils.register_class(GLADIUS_OT_delete_unit)
    bpy.utils.register_class(GLADIUS_OT_assign_action)
    bpy.utils.register_class(GLADIUS_OT_assign_action_nla)
    bpy.utils.register_class(GLADIUS_PT_animation_picker)
    bpy.utils.register_class(GLADIUS_PT_import_panel)
    bpy.utils.register_class(GLADIUS_PT_import_advanced)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mesh)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_textures)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_anim)
    bpy.types.VIEW3D_MT_object_context_menu.append(context_menu_gladius)
    bpy.types.WindowManager.gladius_anim_filter = StringProperty(
        name="Search Animations",
        description="Filter animations by type or variant name",
        default="",
        options={"TEXTEDIT_UPDATE"},
    )
    bpy.types.Object.gladius_unit_team_color = FloatVectorProperty(
        name="Team Colour",
        description="Gladius team colour for every part of this unit; SIC blue areas take it",
        subtype="COLOR_GAMMA",
        size=3,
        min=0.0,
        max=1.0,
        get=_get_unit_team_color,
        set=_set_unit_team_color,
    )
    bpy.types.WindowManager.gladius_anim_show_all = BoolProperty(
        name="Show All Animation Types",
        description="Show all animation types, not just the common ones",
        default=False,
    )


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_mesh)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_textures)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_anim)
    bpy.types.VIEW3D_MT_object_context_menu.remove(context_menu_gladius)
    if hasattr(bpy.types.WindowManager, "gladius_anim_filter"):
        del bpy.types.WindowManager.gladius_anim_filter
    if hasattr(bpy.types.WindowManager, "gladius_anim_show_all"):
        del bpy.types.WindowManager.gladius_anim_show_all
    if hasattr(bpy.types.Object, "gladius_unit_team_color"):
        del bpy.types.Object.gladius_unit_team_color
    _safe_unregister_class(GLADIUS_PT_import_advanced)
    _safe_unregister_class(GLADIUS_PT_import_panel)
    _safe_unregister_class(GLADIUS_PT_animation_picker)
    _safe_unregister_class(GLADIUS_OT_assign_action_nla)
    _safe_unregister_class(GLADIUS_OT_assign_action)
    _safe_unregister_class(GLADIUS_OT_delete_unit)
    _safe_unregister_class(GLADIUS_OT_set_player_color)
    _safe_unregister_class(GLADIUS_OT_select_rig)
    _safe_unregister_class(GLADIUS_OT_clear_anim_filter)
    _safe_unregister_class(ImportGladiusUnitAnimations)
    _safe_unregister_class(ImportGladiusAnm)
    _safe_unregister_class(ImportGladiusTextures)
    _safe_unregister_class(ImportGladiusUnit)
    _safe_unregister_class(ImportGladiusUnitFromXml)
    _safe_unregister_class(ImportGladiusMesh)
    _safe_unregister_class(GLADIUS_AddonPreferences)


if __name__ == "__main__":
    register()
    if not getattr(bpy.app, "background", False):
        bpy.ops.import_mesh.gladius_msh("INVOKE_DEFAULT")
