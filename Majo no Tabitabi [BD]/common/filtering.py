__all__ = ["ElainaFiltering"]

from typing import Optional, Tuple

import havsfunc as haf
import lvsfunc as lvf
import vapoursynth as vs
import vardefunc as vdf
from adptvgrnMod import adptvgrnMod
from debandshit import dumb3kdb
from jvsfunc.expr import ccdmod
from rekt import rektlvls
from stgfunc.tweaking import bbmod_fast
from stgfunc.misc import set_output
from vsmask.edge import FDoG
from vardautomation import FileInfo, PresetBD
from vsutil import get_y, depth

from common import BDMV


core = vs.core


class ElainaFiltering:
    OP_RANGES: Optional[Tuple[int, int]] = None
    ED_RANGES: Optional[Tuple[int, int]] = None

    NCOP = FileInfo(
        BDMV.bdmv_folder / "Wandering Witch - The Journey of Elaina Volume 1/BDMV/STREAM/00007.m2ts",
        trims_or_dfs=(24, -24), preset=[PresetBD]
    )

    NCED = FileInfo(
        BDMV.bdmv_folder / "Wandering Witch - The Journey of Elaina Volume 1/BDMV/STREAM/00016.m2ts",
        trims_or_dfs=(24, -24), preset=[PresetBD]
    )

    def __init__(
        self,
        bd: FileInfo,
    ) -> None:
        self.JPBD = bd


    def filterchain(self) -> vs.VideoNode:
        src = vdf.initialise_clip(self.JPBD.clip_cut, bits=8)

        # BD fixes (taken from LightArrowsEXE)
        fixed = self.prefilter(src)

        # DIRTY EDGES
        rekt = rektlvls(
            fixed,
            rownum=[0, fixed.height - 1],
            rowval=[5, 5],
            colnum=[0, fixed.width - 1],
            colval=[5, 5]
        )

        # most scenes have 1px dirty edge but some have 2px dirty edge
        bb = bbmod_fast(rekt, 2, 2, 2, 2)


        # DENOISE
        smd = haf.SMDegrain(depth(bb, 16), tr=2, thSAD=350, RefineMotion=True, prefilter=2)

        s = [0.95, 0.8]
        bb = depth(bb, 32)
        bm3d = core.bm3dcuda.BM3D(bb, ref=depth(smd, 32), sigma=s, radius=2).bm3d.VAggregate(radius=2)
        bm3d = core.bm3dcuda.BM3D(bb, ref=depth(bm3d, 32), sigma=s, radius=2).bm3d.VAggregate(radius=2)

        mask_thr = 75 << 8
        lmask = FDoG().edgemask(get_y(bm3d), lthr=mask_thr, hthr=mask_thr).std.Convolution([1] * 9)

        ccd = ccdmod(bm3d, threshold=4, matrix=1)
        stab: vs.VideoNode = haf.GSMC(ccd, thSAD=200, planes=[0])

        denoise = core.std.MaskedMerge(stab, bm3d, lmask)

        # AA
        nnedi_aa = lvf.aa.taa(denoise, lvf.aa.nnedi3())
        eedi_aa = lvf.aa.taa(denoise, lvf.aa.eedi3(opencl=True))
        clamp_aa = lvf.aa.clamp_aa(denoise, nnedi_aa, eedi_aa, strength=1.25)

        masked_aa = core.std.MaskedMerge(denoise, clamp_aa, lmask)


        # DEHALO
        dehalo = haf.FineDehalo(masked_aa, rx=1.8, darkstr=0)


        # DEBAND
        deband = dumb3kdb(dehalo, threshold=35, grain=[15, 10])

        details = lvf.mask.detail_mask_neo(dehalo)
        detail_mask = core.std.Expr([details, lmask], "x y +", vs.GRAY)
        masked_deband = core.std.MaskedMerge(deband, dehalo, detail_mask)


        # CREDIT MASKS
        credit_mask = core.std.BlankClip(src, format=vs.GRAY8)

        if self.OP_RANGES:
            op_start, op_end = self.OP_RANGES
            op_mask = vdf.diff_creditless_mask(
                src,
                src[op_start:op_end + 1],
                self.NCOP.clip_cut[:op_end + 1 - op_start],
                start_frame=op_start,
                prefilter=True,
                thr=130,
            )
            credit_mask = core.std.Expr([credit_mask, op_mask], "x y +", vs.YUV)

        if self.ED_RANGES:
            ed_start, ed_end = self.ED_RANGES
            ed_mask = vdf.diff_creditless_mask(
                src,
                src[ed_start:ed_end + 1],
                self.NCED.clip_cut[:ed_end + 1 - ed_start],
                start_frame=ed_start,
                prefilter=True,
                thr=130,
            )
            credit_mask = core.std.Expr([credit_mask, ed_mask], "x y +", vs.YUV)

        credit_mask = depth(credit_mask, 16)
        merge_credits = core.std.MaskedMerge(
            masked_deband, haf.EdgeCleaner(denoise, smode=1), credit_mask
        )


        # GRAIN
        seed = sum([ord(x) for x in "shigin"])
        grain = adptvgrnMod(
            merge_credits, strength=0.25, size=1.15, sharp=80,
            luma_scaling=6, static=True, grain_chroma=False, seed=seed
        )


        # DEBUG
        self.filtersteps_clips = {
            "src": self.JPBD.clip_cut,
            "fixed": fixed,
            "bb": bb,
            "bm3d": bm3d,
            "stab": stab,
            "denoise": denoise,
            "aa": masked_aa,
            "dering": dehalo,
            "deband": masked_deband,
            "grain": grain,
        }


        return vdf.finalise_clip(grain)


    def filtersteps(self, name_pos: int = 8, display_props: Optional[int] = None, font_scaling: int = 1) -> None:
        if not hasattr(self, "filtersteps_clips"):
            self.filterchain()

        for output_name, output in self.filtersteps_clips.items():
            if display_props:
                output = output.text.FrameProps(alignment=display_props)
            set_output(output, (name_pos, font_scaling, output_name))



    def prefilter(self, bd: vs.VideoNode) -> vs.VideoNode:
        return bd
