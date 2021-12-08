import vapoursynth as vs
import lvsfunc as lvf
import vardefunc as vdf
import havsfunc as haf
from vsutil import depth, get_y
from debandshit.debanders import dumb3kdb
from vardautomation import FileInfo

from typing import List, Optional, Tuple

core = vs.core

class EightySixFiltering():

    def __init__(self, 
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

        self.op_ranges = (self.op_start, self.op_start + self.NCOP.clip_cut.num_frames - self.op_offset) if self.op_start else None
        self.ed_ranges = (self.ed_start, self.ed_start + self.NCED.clip_cut.num_frames - self.ed_offset) if self.ed_start else None


    def filter(self) -> vs.VideoNode:
        """Filterchain"""
        self.prefilter()

        self.denoise_clip = self.denoise(self.JP_BD.clip_cut)

        self.aa_clip = self.aa(self.denoise_clip)

        self.dehalo_clip = self.dehalo(self.aa_clip)

        self.deband_clip = self.deband(self.dehalo_clip)

        self.scenfilter_clip = self.scenefilter(self.deband_clip)

        if self.title_range:
            self.scenfilter_clip = lvf.rfs(self.scenfilter_clip, self.denoise_clip, self.title_range)

        if self.op_ranges:
            self.scenfilter_clip = self.filter_op(self.scenfilter_clip)

        if self.ed_ranges:
            self.scenfilter_clip = self.filter_ed(self.scenfilter_clip, self.NCED)

        self.grain_clip = self.grain(self.scenfilter_clip)

        return self.grain_clip


    def filtersteps(self, display_frame: int = 0, display_props: int = 0, font_scaling: int = 1) -> List[vs.VideoNode]:
        """Debug output of each filter step"""
        outputs = {
            "src": self.JP_BD.clip_cut,
            "denoise": self.denoise_clip,
            "aa": self.aa_clip,
            "dehalo": self.dehalo_clip,
            "deband": self.deband_clip,
            "scenefilter": self.scenfilter_clip,
            "grain": self.grain_clip
        }

        debug = vdf.misc.DebugOutput(props=display_props, num=display_frame, scale=font_scaling)

        for output_name, output in outputs.items():
            debug <<= {output_name: output}


    def prefilter(self):
        """Prefilter JP_BD -> convert from YUV420P8 to YUV420P16"""
        self.JP_BD.clip_cut = depth(self.JP_BD.clip_cut, 16)


    def denoise(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Weak denoise with KNLMeansCL"""
        denoise_y = core.knlm.KNLMeansCL(clip, h=0.6, device_type="gpu", device_id=0, channels="Y")
        denoise_uv = core.knlm.KNLMeansCL(clip, h=0.85, device_type="gpu", device_id=0, channels="UV")

        denoise = core.std.ShufflePlanes([denoise_y, denoise_uv], [0, 1, 2], vs.YUV)

        return denoise


    def aa(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Strong AA with clamped based_aa and sraa"""
        baa = lvf.aa.based_aa(clip, "common/FSRCNNX_x2_56-16-4-1.glsl")
        sraa = lvf.aa.upscaled_sraa(clip, rfactor=1.5)
        aa_clamped = lvf.aa.clamp_aa(clip, baa, sraa, strength=1.35)

        lmask = self.line_mask(clip)
        aa_masked = core.std.MaskedMerge(clip, aa_clamped, lmask)

        return aa_masked

    
    def dehalo(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Dehalo + edge cleaning with FineDehalo and EdgeCleaner"""
        dehalo = haf.FineDehalo(clip, rx=1.5, darkstr=0)
        edge_clean = haf.EdgeCleaner(dehalo)

        return edge_clean


    def deband(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Deband with masked_f3kdb"""
        detail_mask = lvf.mask.detail_mask(clip, brz_a=0.03, brz_b=0.045)
        detail_mask = core.std.BoxBlur(detail_mask)

        deband = dumb3kdb(clip, radius=24, threshold=20, grain=0, use_neo=True)

        return core.std.MaskedMerge(deband, clip, detail_mask)

    
    def grain(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Adaptive granning -> static + no chroma"""

        seed = sum([ord(x) for x in "shigin"])
        grain = vdf.noise.Graigasm(
            thrs=[x << 8 for x in [32, 80, 128, 176]],
            strengths=[(0.25, 0), (0.20, 0), (0.15, 0), (0.10, 0)],
            sizes=[1.25, 1.20, 1.15, 1.10],
            sharps=[90, 80, 70, 60],
            grainers=[
                vdf.noise.AddGrain(constant=True, seed=seed),
                vdf.noise.AddGrain(constant=True, seed=seed),
                vdf.noise.AddGrain(constant=False, seed=seed),
                vdf.noise.AddGrain(constant=False, seed=seed),
            ]
        ).graining(clip)

        return grain


    def scenefilter(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Custom scenefiltering"""
        return clip


    def filter_op(self, clip: vs.VideoNode) -> vs.VideoNode:
        """Filters OP with specific ranges to avoid detail loss"""

        src = depth(self.JP_BD.clip_cut, 8)
        op_start, op_end = self.op_ranges

        credit_mask = vdf.mask.Difference().creditless(
            src,
            src[op_start:op_end+1],
            self.NCOP.clip_cut[:-self.op_offset],
            op_start,
            thr=150,
            prefilter=True
        )

        op_filter_ranges = [
            (op_start + 33, op_start + 228),
            (op_start + 486, op_start + 773),
            (op_start + 816, op_start + 1189),
            (op_start + 1221, op_start + 1732),
            (op_start + 1792, op_end)
        ]

        denoise = self.denoise(self.JP_BD.clip_cut)
        merged = lvf.rfs(denoise, clip, op_filter_ranges)

        credit_merged = core.std.MaskedMerge(merged, denoise, depth(credit_mask, 16))

        return lvf.rfs(clip, credit_merged, self.op_ranges)


    def filter_ed(self, clip: vs.VideoNode, NCED: FileInfo) -> vs.VideoNode:
        """Filters ED with much lighter filtering"""
        ec = haf.EdgeCleaner(self.denoise_clip, strength=15)        
        return lvf.rfs(clip, ec, self.ed_ranges)


    def line_mask(self, clip: vs.VideoNode) -> vs.VideoNode:
        y = get_y(clip)
        lmask = y.std.Prewitt().std.Binarize(60<<8).std.Maximum().std.BoxBlur()

        return lmask