import bpy
import os
import platform
from collections import OrderedDict
from ..xplane_helpers import floatToStr
from .xplane_attributes import XPlaneAttributes
from .xplane_attribute import XPlaneAttribute

# Class: XPlaneHeader
# Create an OBJ header.
class XPlaneHeader():
    # Property: version
    # OBJ format version

    # Property: mode
    # The OBJ xplaneFile mode. ("default" or "cockpit"). This is currently not in use, I think.

    # Property: attributes
    # OrderedDict - Key value pairs of all Header attributes

    # Constructor: __init__
    #
    # Parameters:
    #   XPlaneFile xplaneFile - A <XPlaneFile>.
    #   int version - OBJ format version.
    def __init__(self, xplaneFile, version):
        self.version = version
        self.mode = "default"
        self.xplaneFile = xplaneFile

        self.attributes = XPlaneAttributes()
        self.attributes.add(XPlaneAttribute("TEXTURE", None))
        self.attributes.add(XPlaneAttribute("TEXTURE_LIT", None))
        self.attributes.add(XPlaneAttribute("TEXTURE_NORMAL", None))
        self.attributes.add(XPlaneAttribute("POINT_COUNTS", None))
        self.attributes.add(XPlaneAttribute("slung_load_weight", None))
        self.attributes.add(XPlaneAttribute("COCKPIT_REGION", None))
        self.attributes.add(XPlaneAttribute("GLOBAL_no_blend", None))
        self.attributes.add(XPlaneAttribute("GLOBAL_shadow_blend", None))
        self.attributes.add(XPlaneAttribute("GLOBAL_specular", None))
        self.attributes.add(XPlaneAttribute("GLOBAL_no_shadow", None))
        self.attributes.add(XPlaneAttribute("SLOPE_LIMIT", None))
        self.attributes.add(XPlaneAttribute("TILTED", None))
        self.attributes.add(XPlaneAttribute("REQUIRE_WET", None))
        self.attributes.add(XPlaneAttribute("REQUIRE_DRY", None))
        self.attributes.add(XPlaneAttribute("GLOBAL_cockpit_lit", None))
        self.attributes.add(XPlaneAttribute("COCKPIT_REGION", None))

    def init(self):
        # set slung load
        if self.xplaneFile.options.slungLoadWeight > 0:
            self.attributes['slung_load_weight'].setValue(self.xplaneFile.options.slungLoadWeight)

        # set Texture
        blenddir = os.path.dirname(bpy.context.blend_data.filepath)

        # normalize the exporpath
        if os.path.isabs(self.xplaneFile.filename):
            exportdir = os.path.dirname(os.path.normpath(self.xplaneFile.filename))
        else:
            exportdir = os.path.dirname(os.path.abspath(os.path.normpath(os.path.join(blenddir, self.xplaneFile.filename))))

        if self.xplaneFile.options.texture != '':
            self.attributes['TEXTURE'].setValue(self.getTexturePath(self.xplaneFile.options.texture, exportdir, blenddir))

        if self.xplaneFile.options.texture_lit!='':
            self.attributes['TEXTURE_LIT'].setValue(self.getTexturePath(self.xplaneFile.options.texture_lit, exportdir, blenddir))

        if self.xplaneFile.options.texture_normal!='':
            self.attributes['TEXTURE_NORMAL'].setValue(self.getTexturePath(self.xplaneFile.options.texture_normal, exportdir, blenddir))

        # set cockpit regions
        num_regions = int(self.xplaneFile.options.cockpit_regions)

        if num_regions > 0:
            self.attributes['COCKPIT_REGION'].removeValues()
            for i in range(0, num_regions):
                cockpit_region = self.xplaneFile.options.cockpit_region[i]
                self.attributes['COCKPIT_REGION'].addValue((
                    cockpit_region.left,
                    cockpit_region.top,
                    cockpit_region.left + (2 ** cockpit_region.width),
                    cockpit_region.top + (2 ** cockpit_region.height)
                ))

        # get point counts
        tris = len(self.xplaneFile.mesh.vertices)
        lines = 0
        lights = len(self.xplaneFile.lights.items)
        indices = len(self.xplaneFile.mesh.indices)

        self.attributes['POINT_COUNTS'].setValue((tris, lines, lights, indices))

        xplane_version = int(bpy.context.scene.xplane.version)

        # v1000
        if xplane_version >= 1000:
            # blend
            if self.xplaneFile.options.blend == "off":
                self.attributes['GLOBAL_no_blend'].setValue(self.xplaneFile.options.blendRatio)
            elif self.xplaneFile.options.blend == 'shadow':
                self.attributes['GLOBAL_shadow_blend'].setValue(True)

            # specular
            if self.xplaneFile.options.overrideSpecularity == True:
                self.attributes['GLOBAL_specular'].setValue(self.xplaneFile.options.specular)

            # tilted
            if self.xplaneFile.options.tilted == True:
                self.attributes['TILTED'].setValue(True)

            # slope_limit
            if self.xplaneFile.options.slope_limit == True:
                self.attributes['SLOPE_LIMIT'].setValue((
                    self.xplaneFile.options.slope_limit_min_pitch,
                    self.xplaneFile.options.slope_limit_max_pitch,
                    self.xplaneFile.options.slope_limit_min_roll,
                    self.xplaneFile.options.slope_limit_max_roll
                ))

            # require surface
            if self.xplaneFile.options.require_surface == 'wet':
                self.attributes['REQUIRE_WET'].setValue(True)
            elif self.xplaneFile.options.require_surface == 'dry':
                self.attributes['REQUIRE_DRY'].setValue(True)

        # v1010
        if xplane_version >= 1010:
            # shadow
            if self.xplaneFile.options.shadow == False:
                self.attributes['GLOBAL_no_shadow'].setValue(True)

            # cockpit_lit
            if self.xplaneFile.options.cockpit == True and self.xplaneFile.options.cockpit_lit == True:
                self.attributes['GLOBAL_cockpit_lit'].setValue(True)

        # add custom attributes
        for attr in self.xplaneFile.options.customAttributes:
            self.attributes.add(XPlaneAttribute(attr.name, attr.value))

    # Method: getTexturePath
    # Returns the texture path relative to the exported OBJ
    #
    # Parameters:
    #   string texpath - the relative or absolute texture path as chosen by the user
    #   string exportdir - the absolute export directory
    #   string blenddir - the absolute path to the directory the blend is in
    #
    # Returns:
    #   string - the texture path relative to the exported OBJ
    def getTexturePath(self, texpath, exportdir, blenddir):
        # blender stores relative paths on UNIX with leading double slash
        if texpath[0:2] == '//':
            texpath = texpath[2:]

        if os.path.isabs(texpath):
            texpath = os.path.abspath(os.path.normpath(texpath))
        else:
            texpath = os.path.abspath(os.path.normpath(os.path.join(blenddir, texpath)))

        texpath = os.path.relpath(texpath, exportdir)

        return texpath

    # Method: write
    # Returns the OBJ header.
    #
    # Returns:
    #   string - OBJ header
    def write(self):
        self.init()

        system = platform.system()

        # line ending types (I = UNIX/DOS, A = MacOS)
        if 'Mac OS' in system:
            o = 'A\n'
        else:
            o = 'I\n'

        # version number
        if self.version >= 8:
            o += '800\n'

        o += 'OBJ\n\n'

        # attributes
        for name in self.attributes:
            attr = self.attributes[name]
            values = attr.getValues()

            if values[0] != None:
                if len(values) > 1:
                    for vi in range(0, len(values)):
                        o += '%s\t%s\n' % (attr.name, attr.getValueAsString(vi))

                else:
                    o += '%s\t%s\n' % (attr.name, attr.getValueAsString())

        return o
