import vapoursynth as vs
import lvsfunc as lvf
import vardefunc as vdf
import havsfunc as haf
import EoEfunc as eoe
from vsutil import depth, get_y
from debandshit import dumb3kdb
from vardautomation import FileInfo

from typing import List, Optional, Tuple

core = vs.core


class EightySixFiltering():

    def __init__(
        self,
        BD: FileInfo,
        NCOP: Optional[FileInfo] = None,
        NCED: Optional[FileInfo] = None,
        op_start: Optional[int] = None,
        op_offset: Optional[int] = None,
        ed_start: Optional[int] = None,
        ed_offset: Optional[int] = None,
        title_range: Optional[List[Tuple[int, int]]] = None
    ) -> None:

        self.JP_BD = BD
        self.NCED = NCED
        self.NCOP = NCOP

        self.op_offset = op_offset
        self.ed_offset = ed_offset

        self.title_range = title_range

        self.op_start = op_start
        self.ed_start = ed_start

        self.op_ranges = (self.op_start, self.op_start + self.NCOP.clip_cut.num_frames - self.op_offset) if self.op_start is not None else None
        self.ed_ranges = (self.ed_start, self.ed_start + self.NCED.clip_cut.num_frames - self.ed_offset) if self.ed_start else None


    def filter(self) -> vs.VideoNode:
        """Main filterchain"""
        src = depth(self.JP_BD.clip_cut, 16)

        denoise = eoe.denoise.BM3D(src, sigma=1, radius=1, chroma=True, CUDA=True)

        baa = lvf.aa.based_aa(denoise, "common/FSRCNNX_x2_56-16-4-1.glsl")
        sraa = lvf.aa.upscaled_sraa(denoise, rfactor=1.75)
        aa_clamped = lvf.aa.clamp_aa(denoise, baa, sraa, strength=1)

        lmask = get_y(denoise).std.Prewitt().std.Binarize(60<<8).std.Maximum().std.BoxBlur()
        masked_aa = core.std.MaskedMerge(denoise, aa_clamped, lmask)

        dehalo = haf.FineDehalo(masked_aa, rx=1.8, darkstr=0)

        deband = dumb3kdb(dehalo, radius=20, threshold=20, grain=[12, 6])

        detail_mask = lvf.mask.detail_mask(dehalo, brz_a=0.03, brz_b=0.045)
        masked_deband = core.std.MaskedMerge(deband, dehalo, detail_mask)

        scenefilter = self.scenefilter(masked_deband, denoise)

        if self.title_range:
            scenefilter = lvf.rfs(scenefilter, denoise, self.title_range)

        if self.op_ranges:
            scenefilter = self.filter_op(scenefilter, denoise, self.NCOP)

        if self.ed_ranges:
            scenefilter = self.filter_ed(scenefilter, denoise, self.NCED)

        seed = sum([ord(x) for x in "shigin"])
        grain = vdf.noise.Graigasm(
            thrs=[x << 8 for x in [32, 80, 128, 176]],
            strengths=[(0.20, 0), (0.15, 0), (0.10, 0), (0.10, 0)],
            sizes=[1.35, 1.30, 1.25, 1.20],
            sharps=[75, 65, 55, 55],
            grainers=[
                vdf.noise.AddGrain(constant=True, seed=seed),
                vdf.noise.AddGrain(constant=True, seed=seed),
                vdf.noise.AddGrain(constant=False, seed=seed),
                vdf.noise.AddGrain(constant=False, seed=seed),
            ]
        ).graining(scenefilter)

        self.filtersteps_clips = {
            "src": self.JP_BD.clip_cut,
            "denoise": denoise,
            "aa": masked_aa,
            "dehalo": dehalo,
            "deband": masked_deband,
            "scenefilter": scenefilter,
            "grain": grain
        }

        return grain


    def filtersteps(self, display_frame: int = 0, display_props: int = 0, font_scaling: int = 1):
        """Debug"""
        debug = vdf.misc.DebugOutput(props=display_props, num=display_frame, scale=font_scaling)

        for output_name, output in self.filtersteps_clips.items():
            debug <<= {output_name: output}


    def scenefilter(self, clip: vs.VideoNode, denoise: vs.VideoNode) -> vs.VideoNode:
        """Scenefilter"""
        return clip


    def filter_op(self, clip: vs.VideoNode, denoise: vs.VideoNode, NCOP: FileInfo) -> vs.VideoNode:
        """OP filterchain"""
        op_start, op_end = self.op_ranges
        op_filterchain_ranges = self._get_op_filter_ranges(op_start, op_end)

        dpir = lvf.deblock.vsdpir(
            depth(self.JP_BD.clip_cut, 16),
            strength=15, mode="deblock", matrix=1, cuda=False
        )

        merged = lvf.rfs(
            lvf.rfs(clip, dpir, self.op_ranges),  # too lazy to rewrite frame ranges
            clip,
            op_filterchain_ranges
        )

        if "NCOP" not in self.JP_BD.ep_num:
            credit_mask = vdf.mask.Difference().creditless(
                self.JP_BD.clip_cut,
                self.JP_BD.clip_cut[op_start:op_end+1],
                NCOP.clip_cut[:-self.op_offset],
                op_start,
                thr=150,
                prefilter=True
            )

            credit_merged = core.std.MaskedMerge(merged, denoise, depth(credit_mask, 16))

            merged = lvf.rfs(merged, credit_merged, op_filterchain_ranges)

        return merged


    def filter_ed(self, clip: vs.VideoNode, denoise: vs.VideoNode, NCED: FileInfo) -> vs.VideoNode:
        """ED filterchain"""
        return lvf.rfs(clip, denoise, self.ed_ranges)


    @staticmethod
    def _get_op_filter_ranges(start: int, end: int) -> List[Tuple[int, int]]:
        """Get filtering range for the OP"""
        return [
            (start + 33, start + 228),
            (start + 486, start + 773),
            (start + 816, start + 1189),
            (start + 1221, start + 1732),
            (start + 1792, end)
        ]
