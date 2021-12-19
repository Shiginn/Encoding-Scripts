import vapoursynth as vs
import lvsfunc as lvf
import havsfunc as haf
import vardefunc as vdf
import EoEfunc as eoe
from ccd import ccd as CCD
from debandshit import dumb3kdb
from vsutil import depth, get_y
from vardautomation import FileInfo, PresetAAC, PresetBD

from common import Encoder

core = vs.core

EP_NUM = __file__[-5:-3]

JP_BD = FileInfo(
    "./BD/[FsnGuild]Fate Grand Order Shinsei Entaku Ryouiki Camelot 1 - Wandering; Agateram + Extra's (lossless BD)/BDROM Movie 0.mkv", # bdmv pls
    preset=[PresetBD, PresetAAC],
    idx=lambda x: lvf.misc.source(x)
)
JP_BD.ep_num = EP_NUM

src = depth(JP_BD.clip_cut, 16)

denoise = eoe.denoise.BM3D(src, sigma=1.4, CUDA=True)

ccd = CCD(denoise, threshold=5, matrix="709")

baa = lvf.aa.based_aa(ccd, "common/FSRCNNX_x2_56-16-4-1.glsl")
sraa = lvf.aa.upscaled_sraa(ccd, rfactor=1.65)
aa = lvf.aa.clamp_aa(ccd, baa, sraa, strength=1.65)

lmask = get_y(ccd).std.Prewitt().std.Binarize(60<<8).std.Maximum().std.BoxBlur()
masked_aa = core.std.MaskedMerge(ccd, aa, lmask)

dehalo = haf.FineDehalo(masked_aa, rx=1, darkstr=0)

details = lvf.mask.detail_mask(dehalo, brz_a=0.017, brz_b=0.035)
deband = dumb3kdb(dehalo, radius=24, threshold=26, grain=[24, 12])
masked_deband = core.std.MaskedMerge(deband, dehalo, details)

merged = lvf.rfs(masked_deband, src, [(0, 353), (120982, 127800), (128952, 129187)])

seed = sum([ord(x) for x in "shigin"])
grain = vdf.noise.Graigasm(
    thrs=[x<<8 for x in (32, 80, 128, 176)],
    strengths=[(0.35, 0), (0.30, 0), (0.25, 0), (0.20, 0)],
    sizes=[1.25, 1.20, 1.15, 1.10],
    sharps=[85, 80, 75, 70],
    grainers=[
        vdf.noise.AddGrain(seed=seed, constant=True),
        vdf.noise.AddGrain(seed=seed, constant=True),
        vdf.noise.AddGrain(seed=seed, constant=False),
        vdf.noise.AddGrain(seed=seed, constant=False),
    ]
).graining(merged)

if __name__ == "__main__":
    Encoder(JP_BD, grain).run()

elif __name__ == "__vapoursynth__":
    grain.set_output()

else:
    from typing import Dict

    debug = vdf.misc.DebugOutput(props=7)

    outputs: Dict[str, vs.VideoNode] = {
        "src" : JP_BD.clip_cut,
        "denoise" : denoise,
        "ccd" : ccd,
        "aa" : masked_aa,
        "dehalo" : dehalo,
        "deband" : masked_deband,
        "grain" : grain
    }

    for output_name, output in outputs.items():
        debug <<= {output_name: output}