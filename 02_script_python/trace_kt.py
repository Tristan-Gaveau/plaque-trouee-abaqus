import numpy as np
import matplotlib.pyplot as plt

DOSSIER = 'C:/Users/trist/plaque_resultats/'
V1 = DOSSIER + 'resultats_kt_v1.csv'
V2 = DOSSIER + 'resultats_kt_v2_010_020_030_040_050.csv'
SORTIE = DOSSIER + 'kt_vs_dw_howland.png'


def howland(x):
    # Peterson's Stress Concentration Factors, Chart 4.1 : Ktn
    a = 1.0 - x
    return 2.0 + 0.284 * a - 0.600 * a**2 + 1.32 * a**3


def lire(f):
    a = np.loadtxt(f, delimiter=';', skiprows=1, ndmin=2)
    dw, kt = a[:, 0], a[:, 7]               # d/W, Kt Abaqus
    ecart = 100.0 * (kt - howland(dw)) / howland(dw)
    return dw, kt, ecart


dw1, kt1, e1 = lire(V1)
dw2, kt2, e2 = lire(V2)
x = np.linspace(0.05, 0.55, 200)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 7.5), sharex=True,
                               gridspec_kw={'height_ratios': [3, 1.5]})
ax1.plot(x, howland(x), '-', label='Chart 4.1 (Howland), Ktn')
ax1.plot(dw1, kt1, 's', mfc='none', label="Abaqus v1 (8 elem. sur l'arc a d/W=0,1)")
ax1.plot(dw2, kt2, 'o', label='Abaqus v2 (maille adaptee)')
ax1.set_ylabel('Kt = S11max / sigma_nette')
ax1.set_title('Plaque trouee en traction : Kt en fonction de d/W')
ax1.grid(True, alpha=0.3)
ax1.legend()

w = 0.02
ax2.axhline(0.0, color='black', linewidth=0.8)
b1 = ax2.bar(dw1 - w / 2, e1, width=w, label='v1')
b2 = ax2.bar(dw2 + w / 2, e2, width=w, label='v2')
ax2.bar_label(b1, fmt='%.2f', fontsize=6)
ax2.bar_label(b2, fmt='%.2f', fontsize=6)
ax2.set_xlabel('d/W')
ax2.set_ylabel('Ecart a la Chart 4.1 (%)')
ax2.grid(True, alpha=0.3)
ax2.legend()

fig.tight_layout()
fig.savefig(SORTIE, dpi=200)
print('Figure enregistree :', SORTIE)
plt.show()