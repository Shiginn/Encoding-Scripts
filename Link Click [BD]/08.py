import vapoursynth as vs
from vardautomation import FileInfo2, PresetBDWAV64, PresetOpus

from common import BDMV

core = vs.core

EP_NUM = __file__[-5:-3]

JPBD = FileInfo2(
    BDMV.episodes[int(EP_NUM) - 1], trims_or_dfs=(24, -24), preset=[PresetBDWAV64, PresetOpus]
)

JPBD.clip_cut.set_output()
