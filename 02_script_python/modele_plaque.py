# -*- coding: mbcs -*-
from abaqus import *
from abaqusConstants import *
import sketch, part, material, section, assembly, step, mesh, job
import regionToolset
import odbAccess
import os, math

# ============ 1. PARAMETRES (mm, N, MPa) ============
W = 100.0                 # largeur plaque entiere
L = 300.0                 # longueur plaque entiere (3 W)
t = 2.0                   # epaisseur
E = 71700.0               # MPa : A REMPLACER par la valeur lue dans le .inp
NU = 0.33                 # A REMPLACER par la valeur lue dans le .inp
SIGMA_CIBLE = 100.0       # contrainte brute imposee (MPa)
RATIOS = [0.1, 0.2, 0.3, 0.4, 0.5]   # d/W balayes
K_ZONE = 3.0              # zone fine = K_ZONE * r (plafonnee)
ZONE_X = 0.8              # plafond de zx : ZONE_X * L/2
ZONE_Y = 0.8              # plafond de zy : ZONE_Y * W/2 (test d/W=0,4 : 0.9)
H_ARC = 0.5               # taille cible sur l'arc (mm)
N_ARC_MAX = 30            # plafond d'elements sur l'arc
H_GLOBAL = 15.0           # taille loin du trou (mm)
NODES_MAX = 950           # marge sous la limite de 1000 noeuds
DEBUG = False
TAG = 'v3_howland'        # nom de la serie : a changer a chaque nouvelle serie
DOSSIER = 'C:/Users/trist/plaque_resultats'

if not os.path.exists(DOSSIER):
    os.makedirs(DOSSIER)
os.chdir(DOSSIER)

delta = SIGMA_CIBLE / E * (L / 2.0)     # deplacement impose


def kt_howland(dw):
    # Reference : Peterson's Stress Concentration Factors (Pilkey),
    # Chart 4.1, p. 256 (Howland) : Ktn, section nette. A completer : edition.
    a = 1.0 - dw
    return 2.0 + 0.284 * a - 0.600 * a**2 + 1.32 * a**3


def kt_plan(dw):
    # Formule de depart du plan de travail (non sourcee)
    return 3.00 - 3.14 * dw + 3.667 * dw**2 - 1.527 * dw**3


def construire(d, n_arc):
    r = d / 2.0
    assert 0.0 < d < W, "Le trou doit tenir dans la plaque (0 < d < W)"
    nom = 'plaque_dW%03d' % int(round(100 * d / W))
    if nom in mdb.models:
        del mdb.models[nom]
    m = mdb.Model(name=nom)

    # --- Croquis du quart de plaque, trou centre en (0,0) ---
    s = m.ConstrainedSketch(name='profil', sheetSize=2.0 * L)
    s.Line(point1=(0.0, r), point2=(0.0, W / 2.0))
    s.Line(point1=(0.0, W / 2.0), point2=(L / 2.0, W / 2.0))
    s.Line(point1=(L / 2.0, W / 2.0), point2=(L / 2.0, 0.0))
    s.Line(point1=(L / 2.0, 0.0), point2=(r, 0.0))
    s.ArcByCenterEnds(center=(0.0, 0.0), point1=(r, 0.0),
                      point2=(0.0, r), direction=COUNTERCLOCKWISE)
    p = m.Part(name='plaque-trouee', dimensionality=TWO_D_PLANAR,
               type=DEFORMABLE_BODY)
    p.BaseShell(sketch=s)

    # --- Partition : zone fine autour du trou ---
    zx = min(K_ZONE * r, ZONE_X * L / 2.0)
    zy = min(K_ZONE * r, ZONE_Y * W / 2.0)
    assert zx > r and zy > r, "Zone fine plus petite que le trou"
    edge_ref = p.edges.findAt(((L / 2.0, W / 4.0, 0.0),))
    face = p.faces.findAt(((L / 4.0, W / 4.0, 0.0),))
    tr = p.MakeSketchTransform(sketchPlane=face[0], sketchUpEdge=edge_ref[0],
                               sketchPlaneSide=SIDE1, origin=(0.0, 0.0, 0.0))
    s2 = m.ConstrainedSketch(name='partition', sheetSize=2.0 * L, transform=tr)
    s2.Line(point1=(0.0, zy), point2=(zx, zy))
    s2.Line(point1=(zx, zy), point2=(zx, 0.0))
    p.PartitionFaceBySketch(sketchUpEdge=edge_ref[0], faces=face, sketch=s2)

    # --- Materiau et section ---
    m.Material(name='alu')
    m.materials['alu'].Elastic(table=((E, NU),))
    m.HomogeneousSolidSection(name='sec', material='alu', thickness=t)
    p.SectionAssignment(region=regionToolset.Region(faces=p.faces),
                        sectionName='sec')

    # --- Assemblage et step ---
    a = m.rootAssembly
    a.DatumCsysByDefault(CARTESIAN)
    inst = a.Instance(name='plaque-1', part=p, dependent=ON)
    m.StaticStep(name='Step-1', previous='Initial', nlgeom=OFF)

    # --- Conditions aux limites (aretes trouvees par position calculee) ---
    e_x0 = inst.edges.findAt(((0.0, (r + zy) / 2.0, 0.0),),
                             ((0.0, (zy + W / 2.0) / 2.0, 0.0),))
    e_y0 = inst.edges.findAt((((r + zx) / 2.0, 0.0, 0.0),),
                             (((zx + L / 2.0) / 2.0, 0.0, 0.0),))
    e_ld = inst.edges.findAt(((L / 2.0, W / 4.0, 0.0),))
    m.XsymmBC(name='BC-XSYM', createStepName='Step-1',
              region=regionToolset.Region(edges=e_x0))
    m.YsymmBC(name='BC-YSYM', createStepName='Step-1',
              region=regionToolset.Region(edges=e_y0))
    a.Set(edges=e_ld, name='SET_LOAD')
    m.DisplacementBC(name='BC-LOAD', createStepName='Step-1',
                     region=a.sets['SET_LOAD'], u1=delta)

    # --- Type d'element : quadrangles CPS8R, triangles CPS6 ---
    p.setElementType(regions=(p.faces,),
                     elemTypes=(mesh.ElemType(elemCode=CPS8R),
                                mesh.ElemType(elemCode=CPS6)))

    # --- Maillage : on reduit n_arc jusqu'a rester sous la limite ---
    arc = p.edges.findAt(((r * math.cos(math.pi / 4.0),
                           r * math.sin(math.pi / 4.0), 0.0),))
    b_v = p.edges.findAt(((zx, zy / 2.0, 0.0),))
    b_h = p.edges.findAt(((zx / 2.0, zy, 0.0),))
    n = n_arc
    while n >= 4:
        try:
            p.deleteMesh()
        except Exception:
            pass
        p.seedPart(size=H_GLOBAL, deviationFactor=0.1, minSizeFactor=0.1)
        p.seedEdgeByNumber(edges=arc, number=n, constraint=FIXED)
        p.seedEdgeByNumber(edges=b_v, number=n, constraint=FIXED)
        p.seedEdgeByNumber(edges=b_h, number=n, constraint=FIXED)
        p.generateMesh()
        nb = len(p.nodes)
        if nb <= NODES_MAX:
            return m, nom, nb, n
        n -= 2
    return None, nom, None, None


def lancer_et_lire(nom):
    j = mdb.Job(name=nom, model=nom)
    j.submit()
    j.waitForCompletion()
    odb = odbAccess.openOdb(path=nom + '.odb')
    fr = odb.steps['Step-1'].frames[-1]
    # S11 non moyenne aux noeuds des elements : on garde le max
    sub = fr.fieldOutputs['S'].getSubset(position=ELEMENT_NODAL)
    s11_max = max([v.data[0] for v in sub.values])
    # RF1 total sur le bord charge
    reg = odb.rootAssembly.nodeSets['SET_LOAD']
    rf = fr.fieldOutputs['RF'].getSubset(region=reg)
    if DEBUG:
        print('nb noeuds SET_LOAD dans ODB : %d' % len(rf.values))
    rf1 = sum([v.data[0] for v in rf.values])
    odb.close()
    return s11_max, rf1


# ============ 2. BALAYAGE ============
nom_csv = 'resultats_kt_%s_%s.csv' % (
    TAG, '_'.join(['%03d' % int(round(100 * r)) for r in RATIOS]))
entete = ('d/W;d;n_arc;noeuds;RF1;S11max;sigma_nom;Kt;'
          'Kt_howland;ecart_howland_%;Kt_plan;ecart_plan_%')

f = open(nom_csv, 'w')
f.write(entete + '\n')
f.close()

for dw in RATIOS:
    d = dw * W
    n_voulu = min(N_ARC_MAX, int(round((math.pi * d / 4.0) / H_ARC)))
    m, nom, nb, n_ok = construire(d, n_voulu)
    if m is None:
        print('d/W=%s : maillage impossible sous %d noeuds, cas saute'
              % (dw, NODES_MAX))
        continue
    s11, rf1 = lancer_et_lire(nom)
    s_nom = rf1 / ((W / 2.0 - d / 2.0) * t)      # section NETTE du quart
    kt = s11 / s_nom
    kh = kt_howland(dw)
    kp = kt_plan(dw)
    ligne = ('%.2f;%.1f;%d;%d;%.1f;%.2f;%.2f;%.3f;%.3f;%.2f;%.3f;%.2f'
             % (dw, d, n_ok, nb, rf1, s11, s_nom, kt,
                kh, 100.0 * (kt - kh) / kh, kp, 100.0 * (kt - kp) / kp))
    print(ligne)
    f = open(nom_csv, 'a')          # ecriture cas par cas
    f.write(ligne + '\n')
    f.close()

print('Termine : %s/%s' % (DOSSIER, nom_csv))