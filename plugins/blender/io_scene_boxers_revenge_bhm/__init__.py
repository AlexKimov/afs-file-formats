bl_info = {
    "name": "Import BHM (.bhm)",
    "author": "",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > Alligator Friends Software BHM (.bhm)",
    "description": "Import a file in the bhm format",
    # "warning": "",
    # "wiki_url": "",
    # "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Import-Export",
}

import bpy, bmesh
from mathutils import Vector
from bpy_extras.io_utils import ImportHelper

import os
import sys
import math
import struct
import itertools
from struct import calcsize, unpack


VERTEX_SHORT_TO_FLOAT_CONST = 960.0
PACKED_VERTEX_DATA_SIZE = 8
MORPH_FRAME_VERTEX_COORDINATE_COEFF = 1


try:
    os.SEEK_SET
except AttributeError:
    os.SEEK_SET, os.SEEK_CUR, os.SEEK_END = range(3)


class StdOutOverride:
    buffer = []
    def write(self, text):
        sys.__stdout__.write(text)
        
        if text == '\n':
            self.print_to_console()

        else:
            for line in text.replace('\t', '    ').split('\n'):
                if len(self.buffer) > 0:
                    self.print_to_console()
                self.buffer.append(line)
    def print_to_console(self):
        buffer_str = ''.join(map(str, self.buffer))
        if hasattr(bpy.context, 'screen') and bpy.context.screen:
            for area in bpy.context.screen.areas:
                if area.type == 'CONSOLE':
                    with bpy.context.temp_override(area=area):
                        try:
                            bpy.ops.console.scrollback_append(text=buffer_str, type='OUTPUT')
                        except Exception as ex:
                            pass
        self.buffer = []


sys.stdout = StdOutOverride() 
 
 
class Vector3UI16:
    def __init__(self, x = 0, y = 0, z = 0):    
        self.x = x
        self.y = y
        self.z = z
        
    def read(self, reader):
        self.x, self.y, self.z = struct.unpack('=HHH', reader.read(8))
        
        reader.seek(2, os.SEEK_CUR)  
        
    def getStorage(self):
        return (self.x, self.y, self.z)    
   
    def toBytes(self):
        data = self.getStorage()
        result = bytearray(struct.pack('3f', *data))
        
        return result 
        
    
class Vector3F:
    def __init__(self, x = 0, y = 0, z = 0):    
        self.x = x
        self.y = y
        self.z = z
        
    def read(self, reader):
        self.x, self.y, self.z = struct.unpack('3f', reader.readBytes(12))  
        
    def getStorage(self):
        return (self.x, self.y, self.z) 
        
    def toBytes(self): 
        result = bytearray(noePack('3f', *self.getStorage()))
        
        return result         
   
   
class Vector3UI:
    def __init__(self):    
        self.i1 = 0
        self.i2 = 0
        self.i3 = 0
        
    def read(self, reader):
        self.i1, self.i2, self.i3 = struct.unpack('=3I', reader.read(12))
        
    def getStorage(self):
        return (self.i1, self.i2, self.i3)    
        
    def toBytes(self):
        result = bytearray(struct.pack('3I', *self.getStorage()))
        
        return result    
   
   
class Vector2F:
    def __init__(self):    
        self.x = 0
        self.y = 0
        
    def read(self, reader):
        self.x, self.y = struct.unpack('2f', reader.read(8))  
        
    def getStorage(self):
        return (self.x, self.y)  
        
    def toBytes(self):
        result = bytearray(struct.pack('2f', *self.getStorage()))
        
        return result   
        

class BRMesh:       
    def __init__(self):
        self.meshFrameCount = 0
        self.meshCount = 0
        self.vertexCount = 0       
        self.faceCount = 0
        
        self.facesIndexes = []
        self.uvs = []
        self.morphFrames = []
        self.name = ""
        
    def readGeometryData(self, reader):
        for i in range(self.faceCount):
            faceIndexes = Vector3UI() 
            faceIndexes.read(reader)
            
            self.facesIndexes.append(faceIndexes)
               
        for i in range(self.vertexCount):
            uv = Vector2F() 
            uv.read(reader)
            
            self.uvs.append(uv)   

    def convertVertexIntToFloat(self, data):
        result = []
        
        for vi in range(self.vertexCount):
            vrtxs = data[(vi * PACKED_VERTEX_DATA_SIZE) : (vi * PACKED_VERTEX_DATA_SIZE + 6)]
            x, y, z = struct.unpack('=3h', vrtxs)
            x = x / VERTEX_SHORT_TO_FLOAT_CONST
            y = y / VERTEX_SHORT_TO_FLOAT_CONST
            z = z / VERTEX_SHORT_TO_FLOAT_CONST
            
            result.append(Vector3F(x, y, z)) 

        return result            
          
    def readMorphFrames(self, reader):   
        for i in range(self.frameCount): 
            frameDataBytes = reader.read(8*self.vertexCount)               
            self.morphFrames.append(self.convertVertexIntToFloat(frameDataBytes))                 
       
    def readHeader(self, reader): 
        self.frameCount, self.meshCount, self.vertexCount, self.faceCount = \
            struct.unpack('=IIII', reader.read(16))             
 
        reader.seek(20, os.SEEK_CUR)      
        data = reader.read(68)        
        
        filtered = bytearray([x if x < 0x80 else 0x2D for x in data])
        self.name = str(filtered, "ASCII").rstrip("\0")        
         
    def read(self, reader):  
        self.readHeader(reader)
        self.readGeometryData(reader)         
        self.readMorphFrames(reader)              


class BRCharacterModel: 
    def __init__(self, reader):
        self.reader = reader
        self.frameCount = 0
        self.meshes = []
        
    def readHeader(self, reader):
        reader.seek(76, os.SEEK_CUR)
        self.frameCount = struct.unpack('I', reader.read(4))[0] 

        reader.seek(28, os.SEEK_CUR)
        
    def readModelData(self, reader):
        reader.seek(56*self.frameCount, os.SEEK_CUR) 
        reader.seek(72, os.SEEK_CUR)
        
        mesh = BRMesh()
        mesh.read(reader)
         
        self.meshes.append(mesh)
            
    def read(self):
        self.readHeader(self.reader)         
        self.readModelData(self.reader)          


def find_in_folder(folder, name):
    for filename in os.listdir(folder):
        if filename.lower() == name.lower():
            return filename
    return None



def load_bhm_file(bhm_filename, context, texture, BATCH_LOAD=False):
    fhandle = open(bhm_filename, "rb")
    
    model = BRCharacterModel(fhandle)
    model.read()   
    
    fhandle.close()
    
    collection = None
    
    for brmesh in model.meshes:       
        bm = bmesh.new()
        morphFrameVerts = brmesh.morphFrames[0]
        for brvertex in morphFrameVerts:
            bm.verts.new(brvertex.getStorage())
            bm.verts.ensure_lookup_table()
        for brfaceIndexes in brmesh.facesIndexes:                                  
            face = [bm.verts[i] for i in brfaceIndexes.getStorage()]
            bm.faces.new(face)
            bm.faces.ensure_lookup_table()
            
            uv_layer = bm.loops.layers.uv.verify()
            for i, loop in enumerate(bm.faces[-1].loops):
                uv = loop[uv_layer].uv
                uv[0] = brmesh.uvs[brfaceIndexes.getStorage()[i]].x
                uv[1] = brmesh.uvs[brfaceIndexes.getStorage()[i]].y
                #print(uv[0], uv[1])
           
        mesh = bpy.data.meshes.new(brmesh.name)
        bm.to_mesh(mesh)
        ob = bpy.data.objects.new(brmesh.name, mesh)

        try:
            collection = collection or bpy.context.scene.collection
            collection.objects.link(ob)
        except AttributeError:
            bpy.context.scene.objects.link(ob)
        try:
            bpy.context.scene.update()
        except AttributeError:
            pass
     
    # material
    mat = bpy.data.materials.new('mat')
    mat.use_nodes = True
    
    texsdir = os.path.dirname(os.path.abspath(bhm_filename))
    
    principled = mat.node_tree.nodes["Principled BSDF"]
    principled.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)   
    mapping_node = mat.node_tree.nodes.new('ShaderNodeMapping')
    mapping_node.inputs["Rotation"].default_value = (-3.14159, 0, 0)

    tex_coord_node = mat.node_tree.nodes.new('ShaderNodeTexCoord')
    mat.node_tree.links.new(mapping_node.inputs['Vector'], \
        tex_coord_node.outputs['UV'])
                                
    fname = find_in_folder(texsdir, texture)
  
    tex_node = mat.node_tree.nodes.new('ShaderNodeTexImage') 
    
    if fname:
        image = bpy.data.images.load(os.path.join(texsdir, fname))
        image.alpha_mode = 'CHANNEL_PACKED' 
        tex_node.image = image       

    mix_node = mat.node_tree.nodes.new('ShaderNodeMixRGB')
    mix_node.blend_type='MIX'

    mix_node.inputs['Color2'].default_value = (0, 1.0, 0.0, 1.0)
    mat.node_tree.links.new(mix_node.inputs['Color2'], tex_node.outputs['Color'])
    mat.node_tree.links.new(mix_node.inputs['Fac'], tex_node.outputs['Alpha'])

    mat.node_tree.links.new(principled.inputs['Base Color'], mix_node.outputs['Color'])
    mat.node_tree.links.new(tex_node.inputs['Vector'], mapping_node.outputs['Vector'])
    
    ob.data.materials.append(mat)     
    polygons = ob.data.polygons
    polygons.foreach_set('use_smooth', [True] * len(polygons))  
      
    # animation  
    action = bpy.data.actions.new("MeshAnimation")

    mesh.animation_data_create()
    mesh.animation_data.action = action

    data_path = "vertices[%d].co"
    
    frames = range(0, model.meshes[0].frameCount)
    
    for idx, v in enumerate(mesh.vertices):       
        for i in range(3):
            # create fcurve, each index - vertex component x, y, z
            fc = action.fcurves.new(data_path % v.index, index =  i)
            fc.keyframe_points.add(count = model.meshes[0].frameCount)

            # get vertex component list           
            co = [frame[idx].getStorage()[i] for frame in model.meshes[0].morphFrames]

            fc.keyframe_points.foreach_set("co", [x for co in zip(frames, co) for x in co])  

    bpy.context.scene.frame_end = model.meshes[0].frameCount
    bpy.context.space_data.shading.type = 'MATERIAL'
        
    return
        

class ImportBHM(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.bhm"  
    bl_label = "Import bhm"
    bl_options = {"UNDO"}

    filter_glob : bpy.props.StringProperty(
        default = "*.bhm",
        options = {"HIDDEN"},
    ) 
    
    texture_path : bpy.props.StringProperty(
        name = "Texture: ",
        description = "Choose a texture",
        default = "tex30.bmp",
        maxlen = 1024,
        subtype = 'FILE_NAME'
    )
      
    def execute(self, context):
        if context.mode != "OBJECT":
            if not context.scene.objects.active:
                context.scene.objects.active = context.scene.objects[0]
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        
        load_bhm_file(self.filepath, context, self.texture_path)
        
        bpy.ops.object.select_all(action="DESELECT")
        return {"FINISHED"}


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportBHM.bl_idname, text="Import Boxer Revenge BHM (.bhm)")


def register():
    bpy.utils.register_class(ImportBHM)
    try:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    except AttributeError:
        bpy.types.INFO_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportBHM)
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except AttributeError:
        bpy.types.INFO_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()