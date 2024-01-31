bl_info = {
    "name": "Import Boxers Revenge MAP (.ms3d)",
    "author": "",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > Alligator Friends Software MAP (.ms3d)",
    "description": "Import a level file in the map format of the Boxers Revenge game",
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


TEXTURE_FILENAME_LENGTH = 128
NAME_LENGTH = 32


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
 
 
class Vector4UI16:
    def __init__(self, x = 0, y = 0, z = 0):    
        self.x = x
        self.y = y
        self.z = z
        self.u = 0
        
    def read(self, reader):
        self.u, self.x, self.y, self.z = struct.unpack('4H', reader.read(8)) 
        
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
        self.x, self.y, self.z = struct.unpack('3f', reader.read(12))  
        
    def getStorage(self):
        return (self.x, self.y, self.z) 
        
    def toBytes(self): 
        result = bytearray(noePack('3f', *self.getStorage()))
        
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
        

class BRMapMeshVertex: 
    def __init__(self):
        self.vertexCoordinates = Vector3F()
    
    def read(self, reader):  
        reader.seek(1, os.SEEK_CUR)     
        self.vertexCoordinates.read(reader)
        reader.seek(2, os.SEEK_CUR)         
      
      
class BRMapMeshFace:  
    def __init__(self):
        self.vertIndexes = Vector4UI16()
        self.uvs = []

    def getUVsStorage(self):
        uvs = []
        for uv in self.uvs: 
            uvs += [ uv.y, uv.x]
            
        return uvs
    
    def read(self, reader):       
        self.vertIndexes.read(reader)
        reader.seek(36, os.SEEK_CUR) 

        for i in range(3): 
            uv = Vector2F()
            uv.read(reader)
            self.uvs.append(uv)
            
        reader.seek(2, os.SEEK_CUR) 
       
       
class BRMapMaterial: 
    def __init__(self):
        self.name = ""
        self.textures = []
        
    def read(self, reader):
        self.name = str(reader.read(NAME_LENGTH), "ASCII").rstrip("\0")
        
        reader.seek(72, os.SEEK_CUR) 
        
        self.texCount = struct.unpack('B', reader.read(1))[0]        
        for i in range(self.texCount):
            data = reader.read(TEXTURE_FILENAME_LENGTH)        
            filtered = bytearray([x if x < 0x80 else 0x2D for x in data])
            name = str(filtered, "ASCII").rstrip("\0") 
             
            self.textures.append(name)             

        
class BRMapMesh:       
    def __init__(self):
        self.name = ""
        self.indexes = None
        self.meshIndex = 0
        
    def read(self, reader):
        reader.seek(1, os.SEEK_CUR)
        self.name = str(reader.read(NAME_LENGTH), "ASCII").rstrip("\0") 
        
        indexCount = struct.unpack('H', reader.read(2))[0]       
        self.indexes = struct.unpack('H'*indexCount, reader.read(2 * indexCount))
        
        self.meshIndex = struct.unpack('B', reader.read(1))[0]            
        

class BRMAP: 
    def __init__(self, reader):
        self.reader = reader
        self.meshes = []
        self.vertexes = []
        self.faces = []
        self.materials = []
        
    def readVertexes(self, reader):    
        self.vertexCount = struct.unpack('H', reader.read(2))[0] 

        for i in range(self.vertexCount):
            vert = BRMapMeshVertex() 
            vert.read(reader)
            
            self.vertexes.append(vert)         
           
    def readFaces(self, reader): 
        self.faceCount = struct.unpack('H', reader.read(2))[0]    
    
        for i in range(self.faceCount):
            face = BRMapMeshFace() 
            face.read(reader)
            
            self.faces.append(face)   

                    
    def readMeshes(self, reader):  
        self.meshCount = struct.unpack('H', reader.read(2))[0]    
           
        for i in range(self.meshCount):
            mesh = BRMapMesh() 
            mesh.read(reader)
            
            self.meshes.append(mesh)  
                    
    def readMaterials(self, reader): 
        self.matCount = struct.unpack('H', reader.read(2))[0]    
                
        for i in range(self.matCount):
            mat = BRMapMaterial() 
            mat.read(reader)
            
            self.materials.append(mat)   
                                   
    def readMapData(self, reader):    
        self.readVertexes(reader)
        self.readFaces(reader)
        self.readMeshes(reader)
        self.readMaterials(reader)
            
    def readHeader(self, reader): 
        reader.seek(14, os.SEEK_CUR)      
         
    def read(self):  
        self.readHeader(self.reader)
        self.readMapData(self.reader)                     
         

def find_in_folder(folder, name):
    for filename in os.listdir(folder):
        if filename.lower() == name.lower():
            return filename
    return None


def load_map_file(bhm_filename, context, BATCH_LOAD=False):
    fhandle = open(bhm_filename, "rb")
    
    map = BRMAP(fhandle)
    map.read()   
    
    fhandle.close()

    #meshes 
    verts = [vert.vertexCoordinates.getStorage() for vert in map.vertexes]          
    
    for msh in map.meshes:  
        uvs = []
        faces = []
        
        for i in msh.indexes:     
            faces += [map.faces[i].vertIndexes.getStorage()]
            uvs += map.faces[i].getUVsStorage()

        meshData = bpy.data.meshes.new(msh.name)    
        meshData.from_pydata(verts, [], faces)

        uvLayer = meshData.uv_layers.new(name="UVMap")
        uvLayer.data.foreach_set("uv", uvs) 
              
        meshData.update()           
      
        obj = bpy.data.objects.new(msh.name, meshData)
      
        scene = bpy.context.scene
        scene.collection.objects.link(obj)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj 
         
  
    os.chdir('C:\Games\Boxer')
    # materials
    for material in map.materials: 
        mat = bpy.data.materials.new('mat')
        mat.use_nodes = True
    
        principled = mat.node_tree.nodes["Principled BSDF"]  
        principled.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)    
        mappingNode = mat.node_tree.nodes.new('ShaderNodeMapping')
#        mappingNode.inputs["Rotation"].default_value = (-3.14159, 0, 0)

        texCoordNode = mat.node_tree.nodes.new('ShaderNodeTexCoord')
        mat.node_tree.links.new(mappingNode.inputs['Vector'], texCoordNode.outputs['UV'])
        
        texNode = mat.node_tree.nodes.new('ShaderNodeTexImage')   
                     
        image = bpy.data.images.load(os.path.abspath(material.textures[0]))

        image.alpha_mode = 'CHANNEL_PACKED' 
        texNode.image = image
        
        mixNode = mat.node_tree.nodes.new('ShaderNodeMixRGB')
        mixNode.blend_type='MIX'

        mixNode.inputs['Color2'].default_value = (0, 1.0, 0.0, 1.0)
        mat.node_tree.links.new(mixNode.inputs['Color2'], texNode.outputs['Color'])
        mat.node_tree.links.new(mixNode.inputs['Fac'], texNode.outputs['Alpha'])

        mat.node_tree.links.new(principled.inputs['Base Color'], mixNode.outputs['Color'])
        mat.node_tree.links.new(texNode.inputs['Vector'], mappingNode.outputs['Vector'])        
        
        bpy.data.objects[material.name].data.materials.append(mat)
         
    return
        

class ImportMAP(bpy.types.Operator, ImportHelper):
    bl_idname = "import_scene.ms3d"  
    bl_label = "Import map"
    bl_options = {"UNDO"}

    filter_glob : bpy.props.StringProperty(
        default = "*.ms3d",
        options = {"HIDDEN"},
    ) 
      
    def execute(self, context):
        if context.mode != "OBJECT":
            if not context.scene.objects.active:
                context.scene.objects.active = context.scene.objects[0]
            bpy.ops.object.mode_set(mode="OBJECT")
        bpy.ops.object.select_all(action="DESELECT")
        
        load_map_file(self.filepath, context)
        
        bpy.ops.object.select_all(action="DESELECT")
        return {"FINISHED"}


# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
    self.layout.operator(ImportMAP.bl_idname, text="Import Boxer Revenge MAP (.ms3d)")


def register():
    bpy.utils.register_class(ImportMAP)
    try:
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    except AttributeError:
        bpy.types.INFO_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(ImportMAP)
    try:
        bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    except AttributeError:
        bpy.types.INFO_MT_file_import.remove(menu_func_import)


if __name__ == "__main__":
    register()