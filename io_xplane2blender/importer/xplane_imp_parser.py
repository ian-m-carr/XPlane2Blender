"""The starting point for the export process, the start of the addon.
Its purpose is to read strings and break them into chunks, filtering out
comments and deprecated OBJ directives.

It also gives prints errors to the logger
"""

import collections
import itertools
import math
import pathlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from pprint import pprint
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import bmesh
import bpy
from mathutils import Euler, Vector

from io_xplane2blender.importer.xplane_imp_cmd_builder import VT, ImpCommandBuilder
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.xplane_constants import (
    ANIM_TYPE_HIDE,
    ANIM_TYPE_SHOW,
    ANIM_TYPE_TRANSFORM,
)
from io_xplane2blender.xplane_helpers import (
    ExportableRoot,
    floatToStr,
    logger,
    vec_b_to_x,
    vec_x_to_b,
)


class UnrecoverableParserError(Exception):
    pass


def import_obj(filepath: Union[pathlib.Path, str]) -> str:
    """
    Attempts to import an OBJ, mutating the blender data of the current scene.
    The importer may
    - finish the whole import, returning "FINISHED"
    - stop early with partial results, returning "CANCELLED".
    - Raise an UnrecoverableParserError showing no results can be trusted
    """
    filepath = pathlib.Path(filepath)
    builder = ImpCommandBuilder(filepath)
    try:
        lines = pathlib.Path(filepath).read_text().splitlines()
    except OSError:
        raise OSError
    else:
        # pprint(lines)
        pass

    if not lines or not (lines[0] in {"A", "I"} and lines[1:3] == ["800", "OBJ"]):
        logger.error(
            ".obj file must start with exactly the OBJ header. Check filetype and content"
        )
        raise UnrecoverableParserError

    directives_white = {
        "VT",
        "IDX",
        "IDX10",
        "TRIS",
        "ATTR_LOD",
        "ANIM_begin",
        "ANIM_end",
        "ANIM_trans_begin",
        "ANIM_trans_key",
        "ANIM_trans_end",
        "ANIM_rotate_begin",
        "ANIM_rotate_key",
        "ANIM_rotate_end",
        "ANIM_keyframe_loop",
    }

    # TODO: This should be made later. We should start with our tree of intermediate structures then eventually make that into bpy structs when we know what is valid.
    # Otherwise, consider this a hack
    root_col = test_creation_helpers.create_datablock_collection(
        pathlib.Path(filepath).stem
    )
    # get the relative path to the imported file from the blend folder
    if bpy.data.filepath:
        # derive the path name relative to the blend file
        relpath = Path(filepath).relative_to(Path(bpy.data.filepath).parent)
        # remove the suffix and use as the export hint name
        root_col.xplane.layer.name = str(relpath.with_suffix(""))

    root_col.xplane.is_exportable_collection = True

    pattern = re.compile("([^#]*)(#.*)?")

    last_axis = None
    name_hint = ""
    skip = False
    for lineno, line in enumerate(map(str.strip, lines[3:]), start=1):
        to_parse, comment = re.match(pattern, line).groups()[0:2]
        try:
            if comment.startswith("# name_hint:"):
                name_hint = comment[12:].strip()
            elif comment.startswith(("# 1", "# 2", "# 3", "# 4")):
                name_hint = comment[2:].strip()
        except AttributeError:
            pass

        if not to_parse:
            continue
        else:
            directive, *components = to_parse.split()

        if directive == "SKIP":
            skip = not skip
        if directive == "STOP":
            break

        if skip:
            continue

        # print(lineno, directive, components)

        # TODO: Rewrite using giant switch-ish table and functions so it is more neat
        # Need scanf solution
        # scan_int, scan_float, scan_vec2, scan_vec3tobl, scan_str, scan_enum (where it scans a limited number of choices and has a mapping of strings for it)
        """
        def scan_int(s_itr:iter_of_enum, default=None, error_msg=None):
            s = ""
            try:
                i, c = next(s_itr)
            except StopIteration:
                return "expected, str, found end of line"
            while c in "-0123456789":
                s += c
                c = next(s_itr)
            try:
                return int(s)
            except ValueError:
                if default is not None:
                    return default

        def scan_float(s_itr:iter)
            pass
        """

        # if fails we can fallback to default value and print warning or just print a logger warning that it is skipping
        # itr = enumerate()
        # def scan_(last=False, msg_missing=f"Could not convert parameter {lineno} _true, default=None)->value:
        # Throws parser error if needed
        # def _try to swallow all exceptions if the only thing that should happen is the line getting ignored on bad data. Otherwise we can go into more crazy exception hanlding cases
        if directive == "TEXTURE":
            try:
                texture_path = (filepath.parent / Path(components[0])).resolve()
            except IndexError:
                logger.warn(f"TEXTURE directive given but was empty")
            else:
                if texture_path.exists():
                    builder.texture = texture_path
                    builder.material_name = "Material_" + Path(filepath).stem
                    builder.root_collection.xplane.layer.texture = str(texture_path)
                elif pathlib.Path(texture_path).suffix == ".png" and texture_path.with_suffix(".dds").exists():
                    # load the image from the alternative file
                    builder.texture = texture_path.with_suffix(".dds")
                    builder.material_name = "Material_" + Path(filepath).stem
                    # but leave the property with the png version - x-plane will substitute it itself
                    builder.root_collection.xplane.layer.texture = str(texture_path)
                else:
                    logger.warn(f"TEXTURE File: '{str(texture_path)}' does not exist and no alternative dds found")
        elif directive == "TEXTURE_LIT":
            try:
                texture_path = (filepath.parent / Path(components[0])).resolve()
            except IndexError:
                logger.warn(f"TEXTURE_LIT directive given but was empty")
            else:
                if texture_path.exists() or pathlib.Path(texture_path).suffix == ".png" and texture_path.with_suffix(".dds").exists():
                    builder.root_collection.xplane.layer.texture_lit = str(texture_path)
                else:
                    logger.warn(f"TEXTURE_LIT File: '{str(texture_path)}' does not exist and no alternative dds found")
        elif directive == "TEXTURE_NORMAL":
            try:
                texture_path = (filepath.parent / Path(components[0])).resolve()
            except IndexError:
                logger.warn(f"TEXTURE_NORMAL directive given but was empty")
            else:
                if texture_path.exists() or pathlib.Path(texture_path).suffix == ".png" and texture_path.with_suffix(".dds").exists():
                    builder.root_collection.xplane.layer.texture_normal = str(texture_path)
                else:
                    logger.warn(f"TEXTURE_NORMAL File: '{str(texture_path)}' does not exist and no alternative dds found")
        elif directive == "NORMAL_METALNESS":
            builder.root_collection.xplane.layer.normal_metalness = True
        elif directive == "BLEND_GLASS":
            builder.root_collection.xplane.layer.blend_glass = True
        elif directive == "GLOBAL_luminance":
            builder.root_collection.xplane.layer.luminance_override = True
            builder.root_collection.xplane.layer.luminance = int(components[0])
        elif directive == "VT":
            components[:3] = vec_x_to_b(list(map(float, components[:3])))
            components[3:6] = vec_x_to_b(list(map(float, components[3:6])))
            components[6:8] = list(map(float, components[6:8]))
            builder.build_cmd(directive, *components[:8])
        elif directive == "IDX":
            try:
                idx = int(*components[:1])
                if idx < -1:
                    raise ValueError(
                        f"IDX on line {lineno}'s is less than 0"
                    )  # Also, must be less than POINT_COUNTS reports?  # TODO yes?
            except ValueError:
                logger.warn(f"IDX table messed up, {idx} is not an int")
                print("what")
            except IndexError:
                # should have been at least 1
                print("index error")
                pass
            else:
                builder.build_cmd(directive, idx)
        elif directive == "IDX10":
            # idx error etc
            builder.build_cmd(directive, *map(int, components[:11]))
        elif directive == "TRIS":
            start_idx = int(components[0])
            count = int(components[1])
            builder.build_cmd(directive, start_idx, count, name_hint=name_hint)
            name_hint = ""
        elif directive == "ATTR_LOD":
            near = int(components[0])
            far = int(components[1])
            builder.build_cmd(directive, near, far)

        elif directive == "ANIM_begin":
            builder.build_cmd("ANIM_begin", name_hint=name_hint)
        elif directive == "ANIM_end":
            builder.build_cmd("ANIM_end")
        elif directive == "ANIM_trans_begin":
            dataref_path = components[0]
            builder.build_cmd("ANIM_trans_begin", dataref_path, name_hint=name_hint)
        elif directive == "ANIM_trans_key":
            value = float(components[0])
            location = vec_x_to_b(list(map(float, components[1:4])))
            builder.build_cmd(directive, value, location)
        elif directive == "ANIM_trans_end":
            pass
        elif directive in {"ANIM_hide", "ANIM_show"}:
            v1, v2 = map(float, components[:2])
            dataref_path = components[2]
            builder.build_cmd(directive, v1, v2, dataref_path)
        elif directive == "ANIM_rotate_begin":
            axis = vec_x_to_b(list(map(float, components[0:3])))
            dataref_path = components[3]
            builder.build_cmd(directive, axis, dataref_path, name_hint=name_hint)
        elif directive == "ANIM_rotate_key":
            value = float(components[0])
            degrees = float(components[1])
            builder.build_cmd(directive, value, degrees)
        elif directive == "ANIM_rotate_end":
            builder.build_cmd(directive)
        elif directive == "ANIM_keyframe_loop":
            loop = float(components[0])
            builder.build_cmd(directive, loop)
        elif directive == "ANIM_trans":
            xyz1 = vec_x_to_b(list(map(float, components[:3])))
            xyz2 = vec_x_to_b(list(map(float, components[3:6])))
            v1, v2 = (0, 0)
            path = "none"

            try:
                v1 = float(components[6])
                v2 = float(components[7])
                path = components[8]
            except IndexError as e:
                pass
            builder.build_cmd(directive, xyz1, xyz2, v1, v2, path, name_hint=name_hint)
        elif directive == "ANIM_rotate":
            dxyz = vec_x_to_b(list(map(float, components[:3])))
            r1, r2 = map(float, components[3:5])
            v1, v2 = (0, 0)
            path = "none"

            try:
                v1 = float(components[5])
                v2 = float(components[6])
                path = components[7]
            except IndexError:
                pass
            builder.build_cmd(
                directive, dxyz, r1, r2, v1, v2, path, name_hint=name_hint
            )

        # ============================
        # light_level state management
        # ============================
        elif directive == "ATTR_light_level":
            try:
                v1 = float(components[0])
                v2 = float(components[1])
                path = components[2]
            except IndexError:
                pass

            builder.build_cmd(
                directive, v1, v2, path, name_hint=name_hint
            )
        elif directive == "ATTR_light_level_reset":
            builder.build_cmd(directive)

        # ============================
        # Drawing state management
        # ============================
        elif directive == "ATTR_draw_disable":
            builder.build_cmd(directive)
        elif directive == "ATTR_draw_enable":
            builder.build_cmd(directive)

        # =================================
        # Camera collision state management
        # =================================
        elif directive =="ATTR_solid_camera":
            builder.build_cmd(directive)
        elif directive == "ATTR_no_solid_camera":
            builder.build_cmd(directive)

        #=============
        # MANIPULATORS
        #=============
        elif directive == "ATTR_manip_none":
            builder.build_cmd(directive)
        elif directive == "ATTR_manip_drag_xy":
            builder.build_cmd(directive, *components[0:9], ' '.join(components[9:]))
        elif directive == "ATTR_manip_drag_axis":
            builder.build_cmd(directive, *components[0:7], ' '.join(components[7:]))
        elif directive == "ATTR_manip_command":
            cursor = components[0]
            command = components[1]
            tooltip = ' '.join(components[2:])
            builder.build_cmd(directive, cursor, command, tooltip)
        elif directive == "ATTR_manip_command_axis":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_noop":
            builder.build_cmd(directive)
        elif directive == "ATTR_manip_push":
            builder.build_cmd(directive, *components[0:4], ' '.join(components[4:]))
        elif directive == "ATTR_manip_radio":
            builder.build_cmd(directive, *components[0:3], ' '.join(components[3:]))
        elif directive == "ATTR_manip_toggle":
            builder.build_cmd(directive, *components[0:4], ' '.join(components[4:]))
        elif directive == "ATTR_manip_delta":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_wrap":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_drag_axis_pix":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_command_knob":
            builder.build_cmd(directive, *components[0:3], ' '.join(components[3:]))
        elif directive == "ATTR_manip_command_knob2":
            builder.build_cmd(directive, *components[0:2], ' '.join(components[2:]))
        elif directive == "ATTR_manip_command_switch_up_down":
            builder.build_cmd(directive, *components[0:3], ' '.join(components[3:]))
        elif directive == "ATTR_manip_command_switch_up_down2":
            builder.build_cmd(directive, *components[0:2], ' '.join(components[2:]))
        elif directive == "ATTR_manip_command_switch_left_right":
            builder.build_cmd(directive, *components[0:3], ' '.join(components[3:]))
        elif directive == "ATTR_manip_command_switch_left_right2":
            builder.build_cmd(directive, *components[0:2], ' '.join(components[2:]))
        elif directive == "ATTR_manip_axis_knob":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_axis_switch_up_down":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_axis_switch_left_right":
            builder.build_cmd(directive, *components[0:6], ' '.join(components[6:]))
        elif directive == "ATTR_manip_drag_rotate":
            builder.build_cmd(directive, *components[0:16], ' '.join(components[16:]))

        # =====================
        # MANIPULATOR MODIFIERS
        # =====================
        elif directive == "ATTR_manip_keyframe":
            logger.warn(f"Manipulator modifier directive {directive} is not implemented yet")
        elif directive == "ATTR_manip_wheel":
            builder.build_cmd(directive, components[0])
        elif directive == "ATTR_axis_detented":
            builder.build_cmd(directive, *components[0:6])
        elif directive == "ATTR_axis_detent_range":
            builder.build_cmd(directive, *components[0:3])

        # =====================
        # cockpit attributes
        # =====================
        elif directive == "ATTR_cockpit":
            builder.build_cmd(directive) # on
        elif directive == "ATTR_cockpit_lit_only":
            builder.build_cmd(directive) # on
        elif directive == "ATTR_cockpit_region":
            logger.warn(f"Cockpit  modifier directive {directive} is not implemented yet")
        elif directive == "ATTR_no_cockpit": # off
            builder.build_cmd(directive)
        elif directive == "ATTR_cockpit_device":
            builder.build_cmd(directive, *components[0:4])

        # ====================
        # lights
        # ====================
        # elif directive == "LIGHTS":
        elif directive== "LIGHT_NAMED":
            builder.build_cmd(directive, components[0], vec_x_to_b(list(map(float, components[1:4]))))
        #elif directive == "LIGHT_CUSTOM":
        #    builder.build_cmd(directive, *components[0:12])
        elif directive == "LIGHT_PARAM":
            builder.build_cmd(directive, components[0], vec_x_to_b(list(map(float, components[1:4]))), ' '.join(components[4:]))
        #elif directive == "LIGHT_SPILL_CUSTOM":
        #    builder.build_cmd(directive, *components[0:12])

        elif directive == "POINT_COUNTS":
            # handled
            try:
                v1 = int(components[0])
                v2 = int(components[1])
                v3 = int(components[2])
                v4 = int(components[3])
            except IndexError:
                pass
            logger.info(f"{directive} {v1} {v2} {v3} {v4}")
        else:
            logger.warn(f"Directive {directive} is not parsed yet")
            pass

    builder.finalize_intermediate_blocks()
    if builder.encountered_ranges:
        root_layer = builder.root_collection.xplane.layer
        root_layer.lods = str(len(builder.encountered_ranges))

        for i, lod_range in enumerate(builder.encountered_ranges):
            r = root_layer.lod[i]
            r.near, r.far = lod_range
    return "FINISHED"
