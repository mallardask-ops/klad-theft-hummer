"""Original 2001-style skinned human meshes; run with Blender --background."""

import bpy
import json
import math
import random
import struct
import sys
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models"
SOURCE = ROOT / "assets/source"
OUT.mkdir(parents=True, exist_ok=True)
SOURCE.mkdir(parents=True, exist_ok=True)

PROFILES = {
    "podro": dict(width=1.0, height=1.0, torso=1.0, face=1.0, jacket=(.095,.105,.095), pants=(.14,.205,.27), shirt=(.42,.42,.36), hair=(.060,.057,.046), skin=(.63,.455,.32), shoe=(.070,.068,.054)),
    "npc_worker": dict(width=.95, height=1.015, torso=.97, face=.99, jacket=(.29,.25,.17), pants=(.24,.245,.205), shirt=(.47,.45,.36), hair=(.14,.105,.062), skin=(.61,.445,.30), shoe=(.11,.105,.085)),
    "edik": dict(width=.83, height=1.04, torso=.89, face=.96, jacket=(.105,.26,.44), pants=(.18,.235,.31), shirt=(.105,.26,.44), hair=(.049,.052,.041), skin=(.67,.49,.34), shoe=(.36,.37,.32)),
    "serhiy": dict(width=1.09, height=1.02, torso=1.12, face=1.07, jacket=(.31,.245,.145), pants=(.12,.125,.115), shirt=(.52,.50,.41), hair=(.10,.08,.045), skin=(.59,.41,.27), shoe=(.08,.075,.058)),
    "cyber": dict(width=.89, height=1.012, torso=.96, face=.98, jacket=(.065,.080,.096), pants=(.13,.165,.195), shirt=(.17,.18,.165), hair=(.055,.048,.041), skin=(.71,.57,.435), shoe=(.13,.14,.145)),
    "podrina": dict(width=.86, height=.974, torso=.89, face=.95, jacket=(.245,.265,.185), pants=(.15,.205,.265), shirt=(.66,.585,.43), hair=(.19,.086,.036), skin=(.72,.535,.38), shoe=(.14,.115,.075)),
}


def reset():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for action in list(bpy.data.actions):
        bpy.data.actions.remove(action)
    bpy.context.scene.render.fps = 24
    bpy.context.scene.frame_start=1
    bpy.context.scene.frame_end=25


def material(name, color, rough=.85, texture=True, metallic=0):
    mat=bpy.data.materials.new(name)
    mat.diffuse_color=(*color,1)
    mat.use_nodes=True
    node=mat.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value=(*color,1)
    node.inputs["Roughness"].default_value=rough
    node.inputs["Metallic"].default_value=metallic
    if texture:
        image=bpy.data.images.new(name+"_128px",width=128,height=128)
        rng=random.Random(name)
        pixels=[]
        for y in range(128):
            for x in range(128):
                # Narrow textile grain and broad wear; bilinear-filtered like PC games of 2001.
                grain=rng.uniform(-.075,.075)
                wear=.055*math.sin(x*.073+y*.026)+.035*math.cos(y*.093-x*.037)
                weave=.017 if (x+y)%3==0 else -.008
                pixels.extend([max(.008,min(1,c*(1+grain+wear+weave))) for c in color]+[1])
        image.pixels=pixels
        image.pack()
        tex=mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex.image=image
        tex.interpolation="Linear"
        mat.node_tree.links.new(tex.outputs["Color"],node.inputs["Base Color"])
    return mat


def mesh_object(name, verts, faces, mat=None):
    data=bpy.data.meshes.new(name+"_Geometry")
    data.from_pydata(verts,[],faces)
    data.update()
    obj=bpy.data.objects.new(name,data)
    bpy.context.collection.objects.link(obj)
    if mat:
        data.materials.append(mat)
    return obj


def loft(name, rings, sides=12, mat=None, cap=True, phase=0):
    """Z-ordered elliptical anatomical cross-sections: x, y, z, rx, ry."""
    verts=[]
    for x,y,z,rx,ry in rings:
        for k in range(sides):
            angle=math.tau*k/sides+phase
            verts.append((x+math.cos(angle)*rx,y+math.sin(angle)*ry,z))
    faces=[]
    for row in range(len(rings)-1):
        for k in range(sides):
            nxt=(k+1)%sides
            faces.append((row*sides+k,row*sides+nxt,(row+1)*sides+nxt,(row+1)*sides+k))
    if cap:
        faces.extend([tuple(range(sides-1,-1,-1)),tuple((len(rings)-1)*sides+k for k in range(sides))])
    return mesh_object(name,verts,faces,mat)


def ellipsoid(name, loc, scale, mat=None, segments=12, rings=6):
    x,y,z=loc
    rx,ry,rz=scale
    sections=[]
    for j in range(rings+1):
        t=-math.pi/2+math.pi*j/rings
        r=max(.005,math.cos(t))
        sections.append((x,y,z+math.sin(t)*rz,rx*r,ry*r))
    return loft(name,sections,segments,mat)


def join_objects(objects, name):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    if len(objects)>1:
        bpy.ops.object.join()
    obj=bpy.context.object
    obj.name=name
    return obj


def smooth_mesh(obj):
    for face in obj.data.polygons:
        face.use_smooth=True


def body_volume(profile):
    w=profile["width"]
    t=profile["torso"]
    female=profile is PROFILES["podrina"]
    parts=[]
    torso=[(0,0,.905,.179*w,.106), (0,0,.987,(.151 if female else .190)*w,.109*t),
           (0,-.004,1.08,(.167 if female else .205)*w,.117*t),
           (0,.003,1.215,.224*w,.127*t),(0,0,1.315,.235*w,.115*t),
           (0,-.006,1.372,.216*w,.095*t),(0,-.005,1.409,.066,.060)]
    parts.append(loft("Torso_Volume",torso,16))
    parts.append(loft("Pelvis_Volume",[(0,0,.790,.162*w,.100),(0,-.009,.846,.199*w,.116),
                                     (0,-.009,.916,.199*w,.114),(0,0,.971,.181*w,.105)],16))
    parts.append(loft("Neck_Volume",[(0,-.005,1.365,.065,.068),(0,-.005,1.468,.060,.063),(0,.006,1.505,.052,.061)],12))
    f=profile["face"]
    parts.append(loft("Head_Volume",[(0,.022,1.472,.051*f,.055),(0,.024,1.495,.069*f,.071),
                                    (0,.022,1.525,.085*f,.086),(0,.024,1.560,.094*f,.091),
                                    (0,.026,1.605,.098*f,.087),(0,.019,1.647,.092*f,.086),
                                    (0,.009,1.685,.077*f,.071),(0,.003,1.715,.035*f,.035),
                                    (0,0,1.724,.009,.009)],16))
    for side in [-1,1]:
        # The sleeve welds directly into the sloping shoulder, without a spherical deltoid cap.
        parts.append(loft("Arm_Volume",[(side*.326*w,.035,.895,.041*w,.047),
                                        (side*.322*w,.031,.972,.051*w,.062),
                                        (side*.312*w,.022,1.072,.055*w,.065),
                                        (side*.307*w,.020,1.117,.056*w,.061),
                                        (side*.287*w,.014,1.235,.063*w,.073),
                                        (side*.245*w,0,1.333,.067*w,.074)],12))
        parts.append(loft("Hand_Volume",[(side*.328*w,.044,.758,.025*w,.013),
                                         (side*.331*w,.046,.779,.034*w,.020),
                                         (side*.330*w,.042,.822,.040*w,.028),
                                         (side*.328*w,.038,.855,.039*w,.025),
                                         (side*.326*w,.035,.901,.034*w,.033)],10))
        parts.append(ellipsoid("Thumb_Volume",(side*.289*w,.081,.827),(.021*w,.020,.038),segments=8,rings=4))
        parts.append(loft("Leg_Volume",[(side*.108*w,-.012,.176,.043*w,.048),
                                        (side*.111*w,-.013,.250,.046*w,.057),
                                        (side*.112*w,-.008,.344,.057*w,.068),
                                        (side*.111*w,.008,.425,.065*w,.074),
                                        (side*.110*w,.031,.519,.066*w,.072),
                                        (side*.108*w,.017,.592,.073*w,.080),
                                        (side*.105*w,.001,.711,.082*w,.094),
                                        (side*.105*w,-.007,.814,.092*w,.098),
                                        (side*.099*w,-.007,.891,.095*w,.103)],12))
        # Heel, toe box and ankle are curved anatomical volumes, not beveled cubes.
        parts.append(loft("Foot_Volume",[(side*.109*w,.046,.021,.061*w,.139),
                                         (side*.109*w,.046,.045,.063*w,.142),
                                         (side*.109*w,.043,.078,.062*w,.139),
                                         (side*.109*w,.037,.107,.060*w,.136),
                                         (side*.109*w,-.006,.149,.050*w,.087),
                                         (side*.109*w,-.016,.186,.043*w,.055),
                                         (side*.109*w,-.016,.216,.041*w,.049)],12))
    obj=join_objects(parts,"Anatomical_Surface")
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    remesh=obj.modifiers.new("Weld anatomy volumes","REMESH")
    remesh.mode="VOXEL"
    remesh.voxel_size=.013
    remesh.use_smooth_shade=True
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    soften=obj.modifiers.new("Relax seams","SMOOTH")
    soften.factor=.58
    soften.iterations=3
    bpy.ops.object.modifier_apply(modifier=soften.name)
    triangulate=obj.modifiers.new("Triangles before reduction","TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=triangulate.name)
    decimate=obj.modifiers.new("2001 polygon budget","DECIMATE")
    decimate.ratio=min(1,1470/max(1,len(obj.data.polygons)))
    bpy.ops.object.modifier_apply(modifier=decimate.name)
    smooth_mesh(obj)
    return obj


def make_materials(name, profile):
    mats={}
    for key in ["jacket","pants","shirt","skin","hair","shoe"]:
        mats[key]=material(name+"_"+key.title(),profile[key],rough=.72 if key=="jacket" else .90)
    mats["seam"]=material(name+"_Seam",tuple(c*.70 for c in profile["jacket"]),texture=False)
    mats["sole"]=material(name+"_Sole",(.035,.038,.030),texture=True)
    mats["eye_white"]=material(name+"_Eye_White",(.72,.70,.59),texture=False)
    mats["eye_dark"]=material(name+"_Eyes",(.045,.052,.045),texture=False)
    mats["crease"]=material(name+"_Skin_Creases",tuple(c*.67 for c in profile["skin"]),texture=False)
    mats["lip"]=material(name+"_Lips",(.33,.125,.105) if name=="podrina" else (.34,.23,.165),texture=False)
    for kind in ["jacket","pants","skin"]:
        paint_texture(mats[kind],kind,name,profile)
    return mats


def line_distance(x,z,x1,z1,x2,z2):
    dx,dz=x2-x1,z2-z1
    t=max(0,min(1,((x-x1)*dx+(z-z1)*dz)/(dx*dx+dz*dz+1e-9)))
    return math.hypot(x-x1-t*dx,z-z1-t*dz)


def paint_texture(mat, kind, name, profile):
    """Paint original 256px front/back clothes and a 128px face region."""
    image=bpy.data.images.new(mat.name+"_Painted_256px",width=256,height=128)
    rng=random.Random(mat.name+"paint")
    pixels=[]
    base=profile[kind]
    for py in range(128):
        v=py/127
        for px in range(256):
            u=px/255
            front=u<.5
            center=.25 if front else .75
            x=(u-center)*(.44 if kind=="skin" else 1.5)
            z=v*(.28 if kind=="skin" else 1.75)+(1.46 if kind=="skin" else 0)
            color=base
            noise=rng.uniform(-.060,.060)
            value=1+noise+.022*math.sin(px*.27+py*.09)
            if kind=="jacket":
                value*=1-.11*abs(math.sin(x*8))
                if .951<z<.981:
                    value*=.60
                if 1.354<z<1.405 and abs(x)<.17:
                    value*=.70
                if front and name not in ["edik","cyber"] and 1.09<z<1.414:
                    opening=min(.075,max(.008,.008+(z-1.10)*.30))*profile["width"]
                    if abs(x)<opening:
                        color=profile["shirt"]
                        value=1+noise*.65-.15*math.cos(z*47+x*12)**6
                    elif abs(abs(x)-opening)<.007:
                        value*=.43
                    elif abs(abs(x)-opening-.014)<.005:
                        value*=1.18
                for sign in [-1,1]:
                    crease=line_distance(x,z,sign*.092,1.057,sign*.182,1.091)
                    crease=min(crease,line_distance(x,z,sign*.104,1.137,sign*.185,1.177))
                    crease=min(crease,line_distance(x,z,sign*.241,1.240,sign*.318,1.217))
                    crease=min(crease,line_distance(x,z,sign*.269,1.128,sign*.342,1.097))
                    if crease<.012:
                        value*=.64+.36*min(1,crease/.012)
                if front and abs(x-.018)<.004 and 1.00<z<1.14:
                    value*=1.32 if py%2 else .40
            elif kind=="pants":
                value*=1+.025*math.sin(px*2+py)-.13*math.cos(z*25+x*7)**8
                if .825<z<.94:
                    if front:
                        for sign in [-1,1]:
                            d=line_distance(x,z,sign*.067,.908,sign*.154,.876)
                            if d<.008:
                                value*=.59
                    else:
                        for sign in [-1,1]:
                            local_x=x-sign*.108*profile["width"]
                            if abs(local_x)<.040 and .807<z<.901:
                                value*=.91
                                if abs(abs(local_x)-.037)<.005 or abs(z-.811)<.006 or abs(z-.897)<.005:
                                    value*=1.36
                if abs(abs(x)-.166*profile["width"])<.005 and .23<z<.79:
                    value*=1.2
            elif kind=="skin":
                value*=.94+.09*math.cos(x*22)
                if front:
                    # Painted brow / cheek shading and irregular stubble are carried by the skin UV.
                    value*=1-.11*math.exp(-((abs(x)-.058)/.026)**2)
                    if name in ["podro","serhiy","npc_worker"] and 1.488<z<1.567 and abs(x)<.078:
                        stubble=(1-min(1,abs(x)/.09))*.22
                        value*=1-stubble-rng.uniform(0,.10)
                    if 1.606<z<1.618 and .020<abs(x)<.053:
                        value*=.80
                    if 1.638<z<1.651 and .018<abs(x)<.056:
                        value*=.70
                    for zz in [1.651,1.667]:
                        if abs(z-zz)<.0028 and abs(x)<.052:
                            value*=.89
                    if 1.536<z<1.598:
                        xx=.023+(1.59-z)*.36
                        if abs(abs(x)-xx)<.003:
                            value*=.87
            pixels.extend([max(.009,min(1,c*value)) for c in color]+[1])
    image.pixels=pixels
    image.pack()
    tex=next(n for n in mat.node_tree.nodes if n.type=="TEX_IMAGE")
    tex.image=image


def final_uv(obj, name):
    uv=obj.data.uv_layers.active or obj.data.uv_layers.new(name="Painted_Atlas_UV")
    for face in obj.data.polygons:
        mat=obj.data.materials[face.material_index]
        is_skin=mat.name==name+"_Skin"
        front=face.center.y>=0
        for index in face.loop_indices:
            v=obj.data.vertices[obj.data.loops[index].vertex_index].co
            if is_skin and v.z>1.454:
                u=(.25 if front else .75)+v.x/.44*(1 if front else -1)
                vv=(v.z-1.46)/.28
            elif is_skin:
                u=.70+v.x*.14
                vv=(v.z*.33)%1
            else:
                u=(.25 if front else .75)+v.x/1.5*(1 if front else -1)
                vv=v.z/1.75
            uv.data[index].uv=(max(.002,min(.998,u)),max(.002,min(.998,vv)))


def shade_body(obj, name, profile, mats):
    slots=["jacket","pants","skin","shoe","sole","seam"]
    for key in slots:
        obj.data.materials.append(mats[key])
    w=profile["width"]
    for face in obj.data.polygons:
        x,y,z=face.center
        arm=abs(x)>.231*w and z>.73
        if z<.041:
            key="sole"
        elif z<.204:
            key="shoe"
        elif z<.951 and not arm:
            key="pants"
        elif z>1.424 and abs(x)<.15:
            key="skin"
        elif arm and (z<.906 or name=="edik" and z<1.259):
            key="skin"
        elif arm and z<.936 or not arm and .941<z<.977:
            key="seam"
        else:
            key="jacket"
        face.material_index=slots.index(key)
    uv=obj.data.uv_layers.new(name="Wear_UV")
    for face in obj.data.polygons:
        for index in face.loop_indices:
            v=obj.data.vertices[obj.data.loops[index].vertex_index].co
            uv.data[index].uv=((math.atan2(v.y,v.x)/math.tau+.5)%1,v.z/1.75)


def panel(name, points, mat):
    return mesh_object(name,points,[tuple(range(len(points)-1,-1,-1))],mat)


def ribbon(name, points, width, mat):
    verts=[]
    for x,y,z in points:
        verts.extend([(x-width/2,y,z),(x+width/2,y,z)])
    faces=[((i+1)*2,(i+1)*2+1,i*2+1,i*2) for i in range(len(points)-1)]
    return mesh_object(name,verts,faces,mat)


def facial_details(name, p, mats):
    f=p["face"]
    objs=[]
    # Shallow eyelid surfaces retain an adult face rather than bulging cartoon eyes.
    for side in [-1,1]:
        x=side*.036*f
        objs.append(panel("Eye_White",[(x-.015,.112,1.618),(x+.015,.112,1.618),(x+.013,.114,1.628),(x-.013,.114,1.628)],mats["eye_white"]))
        objs.append(ellipsoid("Iris",(x,.1155,1.623),(.0047,.0028,.0050),mats["eye_dark"],segments=8,rings=3))
        objs.append(ribbon("Upper_Eyelid",[(x-.016,.116,1.628),(x,.119,1.631),(x+.016,.116,1.628)],.0026,mats["crease"]))
        objs.append(panel("Brow",[(x-.019,.119,1.637),(x+.019,.120,1.640),(x+.020,.119,1.647),(x-.018,.118,1.644)],mats["hair"]))
        objs.append(ellipsoid("Ear",(side*.098*f,-.008,1.595),(.012,.024,.036),mats["skin"],segments=8,rings=4))
        objs.append(panel("Ear_Inner",[(side*.108*f,.005,1.578),(side*.112*f,.012,1.591),(side*.109*f,.006,1.614)],mats["crease"]))
        if name in ["podro","serhiy","npc_worker"]:
            objs.append(ribbon("Cheek_Crease",[(side*.029,.113,1.569),(side*.041,.109,1.551),(side*.047,.101,1.540)],.002,mats["crease"]))
    noseverts=[(-.010,.112,1.640),(.010,.112,1.640),(-.011,.142,1.586),(.011,.142,1.586),
               (0,.169,1.574),(-.018,.144,1.560),(.018,.144,1.560),(0,.151,1.558)]
    objs.append(mesh_object("Nose",noseverts,[(0,1,3,2),(2,3,4),(2,4,5),(3,6,4),(5,4,7),(4,6,7),(0,2,5),(1,6,3)],mats["skin"]))
    objs.append(panel("Mouth",[(-.021,.112,1.540),(.021,.112,1.540),(.014,.114,1.536),(-.014,.114,1.536)],mats["lip"]))
    objs.append(ribbon("Lower_Lip",[(-.015,.112,1.534),(0,.115,1.532),(.015,.112,1.534)],.002,mats["crease"]))
    if name=="serhiy":
        objs.append(panel("Moustache",[(-.027,.117,1.550),(.027,.117,1.550),(.024,.118,1.543),(-.024,.118,1.543)],mats["hair"]))
    if name=="cyber":
        frames=[]
        for side in [-1,1]:
            x=side*.037
            for z in [1.613,1.635]:
                frames.append(ribbon("Glasses_Frame",[(x-.020,.119,z),(x+.020,.119,z)],.003,mats["eye_dark"]))
            for x2 in [x-.020,x+.020]:
                frames.append(ribbon("Glasses_Frame",[(x2,.119,1.613),(x2,.119,1.635)],.003,mats["eye_dark"]))
        frames.append(ribbon("Glasses_Bridge",[(-.015,.123,1.629),(.015,.123,1.629)],.003,mats["eye_dark"]))
        objs.extend(frames)
    return objs


def hair_details(name, p, mats):
    f=p["face"]
    verts=[]
    sides=16
    levels=[(1.651,.093,.084),(1.685,.080,.073),(1.717,.038,.038),(1.729,.006,.007)]
    for row,(z,rx,ry) in enumerate(levels):
        for k in range(sides):
            a=k*math.tau/sides
            # Crew-cut hairline: lower behind the ears, higher over the forehead.
            hz=z+(max(0,math.sin(a))*.014 if row==0 else 0)
            verts.append((math.cos(a)*rx*f,.010+math.sin(a)*ry,hz))
    faces=[]
    for row in range(3):
        for k in range(sides):
            if name=="serhiy" and row>0:
                continue
            faces.append((row*sides+k,row*sides+(k+1)%sides,(row+1)*sides+(k+1)%sides,(row+1)*sides+k))
    if name!="serhiy":
        faces.append(tuple(range(48,64)))
    objs=[mesh_object("Hair_Cap",verts,faces,mats["hair"])]
    if name=="podrina":
        # Curved back sheet, open around the face; additional strands frame the cheeks.
        hv=[]
        for z,rx,ry in [(1.339,.100,.064),(1.440,.110,.078),(1.560,.109,.095),(1.662,.092,.092)]:
            for k in range(11):
                a=math.pi*(.93+k*.114)
                hv.append((math.cos(a)*rx,.014+math.sin(a)*ry,z))
        hf=[]
        for row in range(3):
            for k in range(10):
                hf.append((row*11+k,row*11+k+1,(row+1)*11+k+1,(row+1)*11+k))
        objs.append(mesh_object("Long_Hair_Back",hv,hf,mats["hair"]))
        for side in [-1,1]:
            objs.append(loft("Hair_Strand",[(side*.083,.065,1.393,.015,.019),(side*.091,.074,1.498,.021,.026),
                                           (side*.094,.061,1.614,.022,.027),(side*.077,.071,1.667,.022,.025)],8,mats["hair"]))
    if name=="cyber":
        hv=[]
        sides=16
        sections=[(1.397,.106,.091),(1.483,.124,.115),(1.612,.133,.121),(1.718,.109,.107),(1.764,.044,.044)]
        for z,rx,ry in sections:
            for k in range(sides):
                a=k*math.tau/sides
                hv.append((math.cos(a)*rx,-.020+math.sin(a)*ry,z))
        hf=[]
        for row in range(4):
            for k in range(sides):
                a=(k+.5)*math.tau/sides
                if row<3 and math.sin(a)>.66:
                    continue
                hf.append((row*sides+k,row*sides+(k+1)%sides,(row+1)*sides+(k+1)%sides,(row+1)*sides+k))
        hf.append(tuple(range(64,80)))
        hood=mesh_object("Curved_Hood",hv,hf,mats["jacket"])
        smooth_mesh(hood)
        objs.append(hood)
    if name=="npc_worker":
        cap=loft("Worker_Cap",[(0,0,1.658,.104,.095),(0,-.004,1.712,.094,.087),(0,-.006,1.733,.036,.034)],12,mats["pants"])
        objs.append(cap)
        objs.append(panel("Cap_Visor",[(-.080,.056,1.680),(.080,.056,1.680),(.078,.155,1.674),(-.078,.155,1.674)],mats["pants"]))
    return objs


def clothing_details(name, p, mats):
    w=p["width"]
    t=p["torso"]
    objs=[]
    if name not in ["edik","cyber"]:
        collar=loft("Jacket_Collar",[(0,-.004,1.377,.082,.081),(0,-.004,1.409,.071,.072)],12,mats["seam"],cap=False)
        # Open at the front so the undershirt and throat remain visible.
        to_remove=[face for face in collar.data.polygons if face.center.y>.053]
        if to_remove:
            import bmesh
            bm=bmesh.new()
            bm.from_mesh(collar.data)
            bmesh.ops.delete(bm,geom=[face for face in bm.faces if face.calc_center_median().y>.053],context="FACES")
            bm.to_mesh(collar.data)
            bm.free()
        objs.append(collar)
        for side in [-1,1]:
            objs.append(ribbon("Pocket_Seam",[(side*.084*w,.123*t,1.10),(side*.160*w,.101*t,1.11)],.003,mats["seam"]))
            objs.append(ribbon("Lapel_Seam",[(side*.064*w,.082,1.396),(side*.112*w,.124*t,1.334),(side*.044*w,.148*t,1.242)],.002,mats["seam"]))
        objs.append(ribbon("Zip",[(.014,.119*t,1.005),(.022,.134*t,1.116),(.044,.140*t,1.242)],.003,mats["sole"]))
    elif name=="cyber":
        objs.append(panel("Hoodie_Pocket",[(-.11*w,.117,1.046),(.11*w,.117,1.046),(.10*w,.134,1.137),(-.10*w,.134,1.137)],mats["seam"]))
        for side in [-1,1]:
            objs.append(ribbon("Hoodie_Drawstring",[(side*.030,.084,1.386),(side*.036,.130,1.295),(side*.036,.131,1.261)],.003,mats["shirt"]))
    for side in [-1,1]:
        x=side*.109*w
        objs.append(ribbon("Jeans_Outer_Seam",[(x+side*.069*w,.003,.782),(x+side*.062*w,.052,.540),(x+side*.037*w,.018,.264)],.002,mats["seam"]))
        # Three narrow lace lines follow the sloping vamp rather than rectangular shoe blocks.
        for y,z in [(.015,.143),(.041,.122),(.065,.109)]:
            objs.append(ribbon("Shoe_Lace",[(x-.022*w,y,z),(x+.022*w,y,z)],.002,mats["shirt"]))
        objs.append(ribbon("Toe_Cap_Seam",[(x-.049*w,.104,.104),(x-.025*w,.123,.107),(x+.025*w,.123,.107),(x+.049*w,.104,.104)],.002,mats["sole"]))
        objs.append(ribbon("Jeans_Pocket",[(x-side*.042*w,.114,.889),(x+side*.037*w,.100,.861),(x+side*.046*w,.088,.817)],.003,mats["seam"]))
    return objs


def hand_and_sole_details(profile, mats):
    w=profile["width"]
    objs=[]
    for side,label in [(-1,"L"),(1,"R")]:
        cx=side*.109*w
        shape=[(-.76,-1),(.76,-1),(1,-.62),(1,.62),(.76,1),(-.76,1),(-1,.62),(-1,-.62)]
        verts=[]
        for z,scale in [(0,.98),(.013,1.0),(.034,.98)]:
            verts += [(cx+sx*.064*w*scale,.046+sy*.145*scale,z) for sx,sy in shape]
        faces=[tuple(range(7,-1,-1)),tuple(range(16,24))]
        faces += [(row*8+k,row*8+(k+1)%8,(row+1)*8+(k+1)%8,(row+1)*8+k) for row in range(2) for k in range(8)]
        sole=mesh_object("Sole_"+label,verts,faces,mats["sole"])
        objs.append((sole,"Foot_"+label))
        for finger in range(4):
            x=side*.330*w+(finger-1.5)*.014*w
            digit=loft("Finger_"+label,[(x,.047,.744,.006*w,.008),(x,.049,.781,.007*w,.012)],6,mats["skin"])
            smooth_mesh(digit)
            objs.append((digit,"Hand_"+label))
            crease=ribbon("Finger_Crease_"+label,[(x,.065,.771),(x,.073,.791)],.0015,mats["crease"])
            objs.append((crease,"Hand_"+label))
    return objs


def hammer_parts(mats, width):
    wood=material("Podro_Hammer_Wood",(.32,.20,.095),texture=True)
    steel=material("Podro_Hammer_Steel",(.27,.29,.27),rough=.54,metallic=.55)
    x=.331*width
    objs=[]
    objs.append(loft("Hammer_Handle",[(x,.044,.516,.016,.017),(x,.044,.588,.017,.018),
                                     (x,.044,.815,.016,.017),(x,.044,.881,.019,.019)],8,wood))
    bpy.ops.mesh.primitive_cube_add(size=1,location=(x,.044,.507))
    obj=bpy.context.object
    obj.name="Hammer_Head"
    obj.dimensions=(.204,.063,.071)
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    bevel=obj.modifiers.new("Hammer edge wear","BEVEL")
    bevel.width=.009
    bevel.segments=1
    bpy.ops.object.modifier_apply(modifier=bevel.name)
    obj.data.materials.append(steel)
    objs.append(obj)
    objs.append(mesh_object("Hammer_Claw",[(x+.068,.015,.538),(x+.136,.015,.478),(x+.136,.030,.478),(x+.068,.030,.538),
                                          (x+.068,.058,.538),(x+.136,.058,.478),(x+.136,.074,.478),(x+.068,.074,.538)],[(0,1,2,3),(4,5,6,7)],steel))
    return objs


def create_rig(profile):
    w=profile["width"]
    data=bpy.data.armatures.new("Humanoid_2001_Skeleton")
    rig=bpy.data.objects.new("Armature",data)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active=rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    defs={"Hips":((0,0,.865),(0,0,.994),None),
          "Spine":((0,0,.994),(0,0,1.205),"Hips"),
          "Chest":((0,0,1.205),(0,0,1.377),"Spine"),
          "Neck":((0,0,1.377),(0,0,1.481),"Chest"),
          "Head":((0,0,1.481),(0,0,1.722),"Neck")}
    for side,label in [(-1,"L"),(1,"R")]:
        defs["Clavicle_"+label]=((side*.034*w,0,1.321),(side*.246*w,0,1.321),"Chest")
        defs["UpperArm_"+label]=((side*.246*w,0,1.321),(side*.309*w,.022,1.111),"Clavicle_"+label)
        defs["Forearm_"+label]=((side*.309*w,.022,1.111),(side*.326*w,.035,.895),"UpperArm_"+label)
        defs["Hand_"+label]=((side*.326*w,.035,.895),(side*.330*w,.045,.765),"Forearm_"+label)
        defs["Thigh_"+label]=((side*.101*w,-.004,.865),(side*.110*w,.031,.519),"Hips")
        defs["Shin_"+label]=((side*.110*w,.031,.519),(side*.109*w,-.013,.182),"Thigh_"+label)
        defs["Foot_"+label]=((side*.109*w,-.013,.182),(side*.109*w,.156,.053),"Shin_"+label)
    for name,(head,tail,parent) in defs.items():
        bone=data.edit_bones.new(name)
        bone.head=head
        bone.tail=tail
        if parent:
            bone.parent=data.edit_bones[parent]
        bone.use_deform=True
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.show_in_front=True
    return rig


def blend(a,b,t):
    t=max(0,min(1,t))
    return {a:1-t,b:t}


def weights_for(co, profile):
    x,y,z=co
    w=profile["width"]
    label="R" if x>=0 else "L"
    if z>1.425 and abs(x)<.16:
        return blend("Neck","Head",(z-1.43)/.070)
    if abs(x)>.222*w and z>.735:
        if z<.924:
            return blend("Hand_"+label,"Forearm_"+label,(z-.865)/.075)
        if z<1.153:
            return blend("Forearm_"+label,"UpperArm_"+label,(z-1.068)/.085)
        if z>1.302 and abs(x)<.28*w:
            return blend("UpperArm_"+label,"Chest",min(.7,(z-1.30)*3.4))
        return {"UpperArm_"+label:1}
    if z<.94:
        if z<.237:
            return blend("Foot_"+label,"Shin_"+label,(z-.174)/.063)
        if z<.570:
            return blend("Shin_"+label,"Thigh_"+label,(z-.476)/.094)
        if z>.798:
            if abs(x)<.048*w:
                return {"Hips":1}
            return blend("Thigh_"+label,"Hips",(z-.798)/.123)
        return {"Thigh_"+label:1}
    if z<1.170:
        return blend("Hips","Spine",(z-.954)/.165)
    if z<1.337:
        return blend("Spine","Chest",(z-1.168)/.133)
    return blend("Chest","Neck",(z-1.370)/.095)


def skin(obj, rig, profile, override=None):
    groups={name:obj.vertex_groups.new(name=name) for name in rig.data.bones.keys()}
    for v in obj.data.vertices:
        weights={override:1} if override else weights_for(v.co,profile)
        for name,amount in weights.items():
            if amount>.0001:
                groups[name].add([v.index],amount,"REPLACE")
    modifier=obj.modifiers.new("Humanoid skin","ARMATURE")
    modifier.object=rig
    obj.parent=rig


def add_animation(rig, name):
    rig.animation_data_create()
    rig.animation_data.action=None
    frames=[1,4,7,10,13,16,19,22,25]
    walking=[.32,.18,0,-.20,-.32,-.18,0,.20,.32]
    knees=[-.10,-.06,-.08,-.14,-.45,-.60,-.40,-.20,-.10]
    running=[.62,.38,.05,-.38,-.62,-.38,-.05,.38,.62]
    runknees=[-.13,-.08,-.12,-.50,-.90,-1.10,-.78,-.40,-.13]
    axis_cache={bone.name:bone.matrix_local.to_3x3().inverted() for bone in rig.data.bones}
    for index,frame in enumerate(frames):
        for bone in rig.pose.bones:
            bone.rotation_mode="QUATERNION"
            bone.rotation_quaternion=Quaternion((1,0,0,0))
            bone.location=(0,0,0)
        rotations={"Spine":(-.030,0,0),"Chest":(-.010,0,0)}
        bob=math.sin(index*math.pi/2)*.0025
        if name in ["walk","run"]:
            thigh=running if name=="run" else walking
            knee=runknees if name=="run" else knees
            rotations["Spine"]=(-.145 if name=="run" else -.055,0,0)
            rotations["Chest"]=(-.035 if name=="run" else -.017,0,math.sin(index*math.pi/4)*.020)
            bob=.018*(1-math.cos(index*math.pi)) if name=="run" else .009*(1-math.cos(index*math.pi))
            for label,offset in [("R",0),("L",4)]:
                k=(index+offset)%8
                a=thigh[k]
                b=knee[k]
                rotations["Thigh_"+label]=(a,0,0)
                rotations["Shin_"+label]=(b,0,0)
                rotations["Foot_"+label]=(-a-b+.03,0,0)
                rotations["UpperArm_"+label]=(-a*.82,0,0)
                rotations["Forearm_"+label]=(.52 if name=="run" else .14,0,0)
                rotations["Hand_"+label]=(-.08,0,0)
        elif name=="attack":
            right=[.02,-.72,-1.90,-2.15,.94,.60,.22,.03,.02]
            elbow=[.05,.30,.75,.83,.20,.13,.08,.05,.05]
            trunk=[-.03,.015,.08,.11,-.22,-.13,-.05,-.03,-.03]
            rotations["UpperArm_R"]=(right[index],0,-.10 if index in [2,3] else 0)
            rotations["Forearm_R"]=(elbow[index],0,0)
            rotations["UpperArm_L"]=(.35 if index in [2,3] else -.25 if index in [4,5] else .02,0,0)
            rotations["Spine"]=(trunk[index],0,.12 if index==3 else -.10 if index==4 else 0)
            rotations["Chest"]=(trunk[index]*.5,0,0)
            rotations["Head"]=(.05 if index in [3,4] else 0,0,0)
            bob=0
        else:
            rotations["Spine"]=(-.030+math.sin(index*math.pi/4)*.006,0,0)
            rotations["Head"]=(.012,0,math.sin(index*math.pi/4)*.015)
            rotations["UpperArm_R"]=(.025,0,0)
            rotations["UpperArm_L"]=(.016,0,0)
        for bone_name,angles in rotations.items():
            inv=axis_cache[bone_name]
            q=Quaternion(inv@Vector((1,0,0)),angles[0]) @ Quaternion(inv@Vector((0,1,0)),angles[1]) @ Quaternion(inv@Vector((0,0,1)),angles[2])
            rig.pose.bones[bone_name].rotation_quaternion=q
        rig.pose.bones["Hips"].location=axis_cache["Hips"]@Vector((0,0,bob))
        for bone in rig.pose.bones:
            bone.keyframe_insert(data_path="rotation_quaternion",frame=frame)
            bone.keyframe_insert(data_path="location",frame=frame)
    action=rig.animation_data.action
    action.name=name
    track=rig.animation_data.nla_tracks.new()
    track.name=name
    track.strips.new(name,1,action)
    rig.animation_data.action=None


def create_character(name):
    p=PROFILES[name]
    mats=make_materials(name,p)
    body=body_volume(p)
    shade_body(body,name,p,mats)
    rig=create_rig(p)
    skin(body,rig,p)
    details=facial_details(name,p,mats)+hair_details(name,p,mats)+clothing_details(name,p,mats)
    for obj in details:
        override="Head" if obj.name.startswith(("Eye","Iris","Upper_Eyelid","Brow","Ear","Cheek","Nose","Mouth","Lower_Lip","Moustache","Glasses","Hair_Cap","Long_Hair","Hair_Strand","Worker_Cap","Cap_Visor","Curved_Hood")) else None
        skin(obj,rig,p,override)
    for obj,override in hand_and_sole_details(p,mats):
        skin(obj,rig,p,override)
        details.append(obj)
    if name=="podro":
        hammer=hammer_parts(mats,p["width"])
        for obj in hammer:
            skin(obj,rig,p,"Hand_R")
        details+=hammer
    # Vertex groups survive joining; one continuous body surface plus facial/garment detail.
    character=join_objects([body]+details,"Character_Mesh")
    final_uv(character,name)
    for mod in list(character.modifiers):
        if mod.type=="ARMATURE" and mod.object!=rig:
            character.modifiers.remove(mod)
    character.parent=rig
    if not any(mod.type=="ARMATURE" for mod in character.modifiers):
        mod=character.modifiers.new("Humanoid skin","ARMATURE")
        mod.object=rig
    for animation in ["idle","walk","run","attack"]:
        add_animation(rig,animation)
    for track in rig.animation_data.nla_tracks:
        track.mute=track.name!="idle"
    root=bpy.data.objects.new(name.title(),None)
    bpy.context.collection.objects.link(root)
    rig.parent=root
    root.scale=(1,1,p["height"])
    bpy.context.scene.frame_set(1)
    return root,rig,character


def export_character(name):
    root,rig,mesh=create_character(name)
    bpy.ops.wm.save_as_mainfile(filepath=str(SOURCE/(name+".blend")))
    for track in rig.animation_data.nla_tracks:
        track.mute=False
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+".glb")),export_format="GLB",export_yup=True,
                             export_animations=True,export_animation_mode="NLA_TRACKS",export_nla_strips=True,
                             export_anim_slide_to_zero=True,export_force_sampling=True,
                             export_cameras=False,export_lights=False,export_materials="EXPORT")
    b=(OUT/(name+".glb")).read_bytes()
    size=struct.unpack_from("<I",b,12)[0]
    doc=json.loads(b[20:20+size])
    clips=[a["name"] for a in doc.get("animations",[])]
    assert all(clip in clips for clip in ["idle","walk","run","attack"]),clips
    assert len(doc.get("skins",[]))>0,"Skin not exported"
    tris=sum(doc["accessors"][pr["indices"]]["count"]//3 for m in doc["meshes"] for pr in m["primitives"] if "indices" in pr)
    info=dict(asset=name,nodes=len(doc["nodes"]),meshes=len(doc["meshes"]),skins=len(doc["skins"]),
              joints=len(doc["skins"][0]["joints"]),triangles=tris,animations=clips,bytes=len(b))
    print("SKINNED_CHARACTER_VERIFIED",json.dumps(info),flush=True)
    return info


def preview(name, animation="idle", frame=1):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/(name+".blend")))
    scene=bpy.context.scene
    for obj in scene.objects:
        if obj.animation_data:
            for track in obj.animation_data.nla_tracks:
                track.mute=track.name!=animation
    scene.frame_set(frame)
    ground=material("Preview_Ground",(.19,.20,.18),texture=False)
    bpy.ops.mesh.primitive_plane_add(size=20,location=(0,0,0))
    bpy.context.object.data.materials.append(ground)
    bpy.ops.object.camera_add(location=(3.5,5.5,2.6))
    camera=bpy.context.object
    camera.rotation_euler=(Vector((0,0,.87))-camera.location).to_track_quat("-Z","Y").to_euler()
    camera.data.type="ORTHO"
    camera.data.ortho_scale=2.18
    scene.camera=camera
    bpy.ops.object.light_add(type="AREA",location=(-3,4,6))
    light=bpy.context.object
    light.data.energy=550
    light.data.size=4
    light.rotation_euler=(Vector((0,0,1))-light.location).to_track_quat("-Z","Y").to_euler()
    scene.world.color=(.20,.20,.20)
    scene.render.engine="CYCLES"
    scene.cycles.samples=32
    scene.render.resolution_x=640
    scene.render.resolution_y=640
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform="Standard"
    scene.render.filepath=str(SOURCE/(name+"_"+animation+"_preview.png"))
    bpy.ops.render.render(write_still=True)


if __name__=="__main__":
    args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if "--preview" in args:
        idx=args.index("--preview")
        preview(args[idx+1],args[idx+2] if len(args)>idx+2 else "idle",int(args[idx+3]) if len(args)>idx+3 else 1)
    else:
        # Podro has his own pipeline (tools/build_podro.py); never overwrite podro.glb from here.
        names=[args[args.index("--only")+1]] if "--only" in args else [n for n in PROFILES if n!="podro"]
        assert "podro" not in names, "use tools/build_podro.py for Podro"
        records=[]
        for name in names:
            reset()
            records.append(export_character(name))
        manifest=SOURCE/"character_manifest.json"
        prior=json.loads(manifest.read_text()) if manifest.exists() else []
        prior=[r for r in prior if r["asset"] not in names]
        manifest.write_text(json.dumps(prior+records,indent=2)+"\n")
