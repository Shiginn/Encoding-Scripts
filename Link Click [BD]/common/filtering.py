__all__ = ["LinkClickFiltering"]

from fractions import Fraction
from functools import partial
from typing import Any, Dict, List, Optional, Tuple, cast

import lvsfunc as lvf
import vapoursynth as vs
from adptvgrnMod import sizedgrn, adptvgrnMod
from debandshit import placebo_deband, dumb3kdb
from lvsfunc.types import Range
from jvsfunc import ccdmod
from pytimeconv import Convert
from stgfunc import bbmod_fast, set_output, adg_mask
from vardautomation import FFV1, FileInfo, FileInfo2, PresetBD, VPath
from vskernels import Catrom
from vsdehalo import contrasharpening, edge_cleaner
from vardefunc import initialise_clip, finalise_clip
from vsmask.edge import FDoG
from vsutil import depth, get_peak_value, get_y, insert_clip

from .utils import BDMV, ED_RANGES, OP_RANGES

core = vs.core


class LinkClickFiltering:
    JPBD: FileInfo2
    op_prefilter: vs.VideoNode | None = None
    OP_RANGE: Tuple[int, int] | None = None
    ED_RANGE: Tuple[int, int] | None = None

    filtersteps_clips: Dict[str, vs.VideoNode] | None = None

    def __init__(
        self, bd: FileInfo2, ep_num: int | str,
        preview_op: Tuple[bool, bool] = (False, False)
    ) -> None:
        self.JPBD = bd

        self.OP_RANGE = OP_RANGES[int(ep_num) - 1]
        self.ED_RANGE = ED_RANGES[int(ep_num) - 1]
        self.change_ops_audio()

        if self.OP_RANGE:
            self.op_prefilter = self.prefilter_op(*preview_op)


    def filter(self) -> vs.VideoNode:
        src = initialise_clip(self.JPBD.clip_cut, bits=8)
        crop = src.std.Crop(0, 0, 140, 140)
        self.set_output(crop, "src")


        # DIRTY EDGES
        bb = bbmod_fast(crop, top=2, bottom=2)
        bb = depth(bb, 16)
        self.set_output(bb, "bb")


        # CHROMA
        catrom = Catrom()

        rgbs = catrom.resample(bb, format=vs.RGBS, matrix_in=vs.MATRIX_BT709)
        w2x = catrom.resample(
            rgbs.w2xncnnvk.Waifu2x(noise=0, scale=1, model=2, tile_h=rgbs.height, tile_w=int(rgbs.width / 2)),
            format=vs.YUV420P16, matrix=vs.MATRIX_BT709
        )
        self.set_output(core.std.ShufflePlanes([bb, w2x], [0, 1, 2], vs.YUV), "chroma recon")


        # DENOISE
        s = 0.7
        bm3d = core.bm3dcpu.BM3D(depth(bb, 32), sigma=s, radius=2).bm3d.VAggregate(radius=2)
        bm3d = core.bm3dcpu.BM3D(depth(bb, 32), ref=depth(bm3d, 32), sigma=s, radius=2).bm3d.VAggregate(radius=2)
        bm3d = core.std.ShufflePlanes([bm3d, w2x], [0, 1, 2], vs.YUV)
        self.set_output(bm3d, "denoise")

        ccd = ccdmod(bm3d, threshold=5, matrix=1)
        self.set_output(ccd, "ccd")

        merge = ccd


        # OP
        if self.OP_RANGE:
            op_start, op_end = self.OP_RANGE
            op_pref = cast(vs.VideoNode, self.op_prefilter)  # why is mypy so fucking dumb?

            if op_pref.num_frames > (op_length := op_end - op_start + 1):
                op_pref = op_pref[:op_length]
            elif op_pref.num_frames < op_length:
                op_pref = op_pref + op_pref[-1] * (op_length - op_pref.num_frames)

            merge = insert_clip(merge, op_pref, op_start)
            self.set_output(merge, "op merge")


        # ED
        if self.ED_RANGE:
            ed_start, ed_end = self.ED_RANGE

            ed_prefilter = self.prefilter_ed(src[ed_start:ed_end + 1])
            merge = insert_clip(merge, ed_prefilter, ed_start)
            self.set_output(merge, "ed merge")


        # AA
        mask_thr = 35 << 8
        lmask = FDoG().edgemask(get_y(merge), lthr=mask_thr, hthr=mask_thr).std.Convolution([1] * 9)

        masked_aa = lvf.aa.nneedi3_clamp(merge, mask=lmask, opencl=False)
        self.set_output(masked_aa, "aa")


        # DERING
        dering = edge_cleaner(masked_aa, strength=15, smode=True)
        self.set_output(dering, "dering")


        # DEBAND
        deband = core.average.Mean([
            dumb3kdb(dering, threshold=30, grain=[20, 10]),
            dumb3kdb(dering, threshold=40, grain=[30, 15]),
            placebo_deband(dering, threshold=5, iterations=2, grain=[4, 2, 2])
        ])

        detail_mask = lvf.mask.detail_mask_neo(dering)
        detail_mask = core.std.Expr([detail_mask, lmask], "x y +", vs.YUV)

        masked_deband = core.std.MaskedMerge(deband, dering, detail_mask)
        self.set_output(masked_deband, "deband")


        # GRAIN
        seed = sum(ord(x) for x in "shigin")

        # Episode
        grain = adptvgrnMod(
            masked_deband, strength=[0.25, 0], size=1.15, sharp=65, luma_scaling=8, static=True, seed=seed
        )

        # OP
        if self.OP_RANGE:
            op_grain_medium = adptvgrnMod(
                masked_deband, strength=[0.40, 0], size=1.25, sharp=80, luma_scaling=6, static=True, seed=seed
            )
            op_grain_heavy = sizedgrn(
                masked_deband, strength=[1, 0], size=1.15, sharp=150,
                static=False, temporal_average=25, seed=seed
            )
            op_grain_mask = adg_mask(masked_deband, luma_scaling=22.5).std.Invert()
            op_grain_merge = core.std.MaskedMerge(op_grain_medium, op_grain_heavy, op_grain_mask)

            s, _ = self.OP_RANGE
            op_grain = lvf.rfs(
                op_grain_medium, op_grain_merge,
                [(s + 459, s + 834), (s + 1012, s + 1023), (s + 1103, s + 1236), (s + 1308, s + 1404)]
            )

            grain = lvf.rfs(grain, op_grain, self.OP_RANGE)

        # ED
        if self.ED_RANGE:
            ed_grain_medium = adptvgrnMod(
                masked_deband, luma_scaling=8, temporal_average=25,
                strength=[0.45, 0], sharp=80, size=1.5, static=False, seed=seed
            )
            ed_grain_heavy = adptvgrnMod(
                masked_deband, luma_scaling=8, temporal_average=25, grainer=partial(
                    core.noise.Add, var=6.25, xsize=3.85, ysize=3.85, constant=False, type=3, seed=seed
                )
            )

            s, _ = self.ED_RANGE
            ed_grain = lvf.rfs(
                ed_grain_medium, ed_grain_heavy,
                [(s, s + 211), (s + 581, s + 921), (s + 935, s + 1267), (s + 1285, s + 1749)]
            )

            grain = lvf.rfs(grain, ed_grain, self.ED_RANGE)

        self.set_output(grain, "grain")

        return finalise_clip(grain)


    def change_ops_audio(self) -> None:
        from .utils import CN_ED, CN_OP

        f2s = partial(Convert.f2samples, fps=Fraction(24000, 1001), sample_rate=self.JPBD.audios_cut[1].sample_rate)

        if self.OP_RANGE:
            op_start, _ = self.OP_RANGE

            start_sample = f2s(op_start)
            offset = f2s(20)
            self.JPBD.audios_cut[1] = core.std.AudioSplice([
                self.JPBD.audios_cut[1][0:start_sample + offset],
                CN_OP.audios_cut[0][offset:],
                self.JPBD.audios_cut[1][start_sample + CN_OP.audios_cut[0].num_samples:]
            ])

        if self.ED_RANGE:
            ed_start, _ = self.ED_RANGE
            ed_trim = CN_ED.trims_or_dfs[0]  # type: ignore

            start_sample = f2s(ed_start)
            offset = f2s(ed_trim) - Convert.seconds2samples(0.025, self.JPBD.audios_cut[1].sample_rate)
            ed_end_sample = start_sample + CN_ED.audios[0].num_samples - offset

            a_clips = [self.JPBD.audios_cut[1][:start_sample], CN_ED.audios[0][offset:]]
            if ed_end_sample < self.JPBD.audios_cut[1].num_samples:
                a_clips.append(self.JPBD.audios_cut[1][ed_end_sample:])

            self.JPBD.audios_cut[1] = core.std.AudioSplice(a_clips)


    @staticmethod
    def prefilter_op(fast: bool = False, preview: bool = False) -> vs.VideoNode:
        import gc

        output_path = VPath("common/op_prefilter_lossless.mkv").resolve()

        def encode(clip: vs.VideoNode) -> None:
            file = FileInfo(
                BDMV.bdmv_folder / "Disc - 02/BDMV/STREAM/00005.m2ts", preset=[PresetBD]
            )
            file.clip = clip
            file.name_clip_output = VPath("common/op_prefilter")

            FFV1().run_enc(clip, file)

        def filter() -> vs.VideoNode:
            srcs = [BDMV.get_episode(i).clip_cut[start:end + 1] for i, (start, end) in enumerate(OP_RANGES, 1)]
            srcs.pop(5)  # need odd number for median + shortest clip

            min_len = min([clip.num_frames for clip in srcs])

            clips = []
            for clip in srcs:
                clips.append(depth(clip[:min_len].std.Crop(0, 0, 140, 140), 16))

            avg = core.median.Median(clips)

            if fast:
                return avg

            crf_51 = (194, 455)
            dpir = lvf.deblock.dpir(avg, strength=15, matrix=1, cuda="trt", zones=[(crf_51, 40)])

            contra = contrasharpening(dpir, avg)
            ccd = ccdmod(contra, threshold=10, matrix=1)

            merge = lvf.rfs(dpir, ccd, crf_51)

            return merge

        if preview:
            return filter()

        if not output_path.exists():
            flt = filter()
            encode(flt)

            del flt  # tfw can't run 2x dpir + w2x on a gtx 1060
            gc.collect()  # doesn't free memory unless explicitly calling garbage collector

        return depth(core.lsmas.LWLibavSource(output_path.to_str()), 16)


    @staticmethod
    def prefilter_ed(clip: vs.VideoNode) -> vs.VideoNode:
        crop = clip.resize.Spline36(format=vs.YUV444P16).std.Crop(0, 0, 145, 140)

        bb = bbmod_fast(crop, top=2, bottom=2).resize.Spline36(1920, 796, format=vs.YUV420P16)

        knl_settings: Dict[str, Any] = dict(d=1, a=2, h=0.35, device_type="gpu")
        denoise = core.knlm.KNLMeansCL(bb, channels="Y", **knl_settings)
        denoise = core.knlm.KNLMeansCL(denoise, channels="UV", **knl_settings)

        dpir_zone_1: List[Range] = [(212, 289), (1268, 1284)]
        dpir_zone_2: List[Range] = [(290, 362), (507, 580)]
        dpir = lvf.deblock.dpir(denoise, strength=10, matrix=1, cuda=True, tiles=2, zones=[
            (dpir_zone_1, 25),
            (dpir_zone_2, 30)  # what the hell happened here?
        ])
        contra = contrasharpening(dpir, denoise)
        contra = lvf.rfs(dpir, contra, dpir_zone_1 + dpir_zone_2)

        # nuking the blocking in the dark areas (and the 3 details that survived the quantization)
        contra_y = get_y(contra)

        lmask_thr = 15 << 8
        lmask = FDoG().edgemask(contra_y, lthr=lmask_thr, hthr=lmask_thr).std.Maximum()

        peak = get_peak_value(contra)
        lthr, hthr = 4750, 5000
        deblock_mask = core.akarin.Expr(
            [contra_y, lmask],
            f"x {lthr} < {peak} x {hthr} > 0 1 x {lthr} - {hthr - lthr} / - {peak} * ? ? y -"
        ).std.Convolution([1] * 9)

        deblock = core.deblock.Deblock(contra, quant=35),
        masked_deblock = core.std.MaskedMerge(contra, deblock, deblock_mask)

        deblock_ranges = [(920, 934), (1006, 1033), (1055, 1170)] + dpir_zone_1 + dpir_zone_2
        deblock_merge = lvf.rfs(contra, masked_deblock, deblock_ranges)

        return deblock_merge.std.AddBorders(0, 0, 2, 2)


    def set_output(self, clip: vs.VideoNode, name: str) -> None:
        input = {name: clip}
        self.filtersteps_clips = input if self.filtersteps_clips is None else self.filtersteps_clips | input


    def preview(self, name_pos: int = 8, display_props: Optional[int] = None, font_scaling: int = 1) -> None:
        if self.filtersteps_clips is None:
            raise ValueError("Filtering : you need to run the filter() method before previewing.")

        for output_name, output in self.filtersteps_clips.items():
            if display_props:
                output = output.text.FrameProps(alignment=display_props, scale=font_scaling)
            set_output(output, (name_pos, font_scaling, output_name))
