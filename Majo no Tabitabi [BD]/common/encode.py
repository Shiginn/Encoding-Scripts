from __future__ import annotations

__all__ = ["Encoder"]

import os
from fractions import Fraction
from pathlib import Path
from shutil import rmtree
from typing import Any, Dict, List, Sequence, Tuple, Type, Union

import vapoursynth as vs
from lvsfunc.misc import source
from vardautomation import (
    FileInfo, VPath,
    X265, X264, FFV1, NVEncCLossless,
    FFmpegAudioExtracter, MKVAudioExtracter, Eac3toAudioExtracter,
    EztrimCutter, SoxCutter, ScipyCutter, PassthroughCutter,
    FlacEncoder, OpusEncoder, QAACEncoder, PassthroughAudioEncoder,
    FlacCompressionLevel, BitrateMode,
    Chapter, MatroskaXMLChapters, OGMChapters,
    MatroskaFile, VideoTrack, AudioTrack, ChaptersTrack, Track,
    Lang, UNDEFINED,
    RunnerConfig, SelfRunner, logger,
    make_comps,
)


class Types:
    VIDEO_ENCODER = Union[X264, X265]
    VIDEO_LOSSLESS_ENCODER = Union[FFV1, NVEncCLossless]

    AUDIO_EXTRACTOR = Union[FFmpegAudioExtracter, MKVAudioExtracter, Eac3toAudioExtracter]
    AUDIO_CUTTER = Union[EztrimCutter, SoxCutter, ScipyCutter, PassthroughCutter]
    AUDIO_ENCODER = Union[FlacEncoder, OpusEncoder, QAACEncoder, PassthroughAudioEncoder]

    CHAPTER = Union[OGMChapters, MatroskaXMLChapters]

    PATH = Union[str, Path]


class Defaults:
    AAC: Dict[str, Any] = dict(bitrate=127, mode=BitrateMode.TVBR)
    OPUS: Dict[str, Any] = dict(bitrate=2 * 96, mode=BitrateMode.VBR, use_ffmpeg=True)
    FLAC: Dict[str, Any] = dict(level=FlacCompressionLevel.VARDOU, use_ffmpeg=True)

    # TODO: finish this
    VIDEO_ENCODER = [
        "-o {clip_output:s} --output-depth {bits:d} - --fps {fps_num:d}/{fps_den:d} --frames {frames:d}"
    ]

    X264 = VIDEO_ENCODER + [
        " --demuxer y4m"
    ]

    X265 = VIDEO_ENCODER + [
        " --y4m" +
        " --min-luma {min_luma:d} --max-luma {max_luma:d}" +
        " --videoformat ntsc --range limited --colormatrix bt709 --colorprim bt709 --transfer bt709 --sar 1"
    ]



class Encoder:
    """Encoder class"""

    file: FileInfo
    """FileInfo object"""
    clip: vs.VideoNode
    """Clip to encode"""
    ep_num: int | str
    """Episode number"""

    chapters: List[int] | List[Chapter] | None
    """Chapters to mux"""
    chapters_names: Sequence[str | None] | None
    """Names of the chapters"""

    v_encoder: Types.VIDEO_ENCODER | None
    """Video encoder"""
    v_lossless_encoder: Types.VIDEO_LOSSLESS_ENCODER | None
    """Lossless video encoder"""

    a_tracks: List[int]
    """Audio tracks"""
    a_extracter: Sequence[Types.AUDIO_EXTRACTOR] | None
    """Audio extractor"""
    a_cutter: Sequence[Types.AUDIO_CUTTER] | None
    """Audio cutter"""
    a_encoder: Sequence[Types.AUDIO_ENCODER] | None
    """Audio encoder"""

    mux: MatroskaFile | None
    """Configured muxer"""

    runner: SelfRunner
    """Vardautomation runner"""

    def __init__(
        self,
        file: FileInfo,
        clip: vs.VideoNode,
        ep_num: int | str,
        chapters: List[int] | List[Chapter] | None = None,
        chapters_names: Sequence[str | None] | None = None,
    ) -> None:

        self.clip = clip
        self.file = file

        self.ep_num = ep_num
        self.file.name_file_final = VPath(f"./premux/{self.ep_num}_premux.mkv")

        self.chapters = chapters
        self.chapters_names = chapters_names


        # defaults
        self.v_encoder = None
        self.v_lossless_encoder = None
        self.a_extracter = None
        self.a_cutter = None
        self.a_encoder = None
        self.a_tracks = []
        self.mux = None


    def video_encoder(
        self,
        encoder: Type[Types.VIDEO_ENCODER] = X265,
        settings: str | List[str] | None = None,
        zones: Dict[Tuple[int, int], Dict[str, Any]] | None = None,
        resumable: bool = False,
        **encoder_params: Any,
    ) -> None:
        logger.info(
            f"Video Encoder: {self._print_name(encoder)}" +
            f"\nZones: {str(zones) if zones is not None else 'None'}"
        )

        self.v_encoder = encoder(settings, zones=zones, **encoder_params)
        self.v_encoder.resumable = resumable



    def video_lossless_encoder(
        self,
        encoder: Type[Types.VIDEO_LOSSLESS_ENCODER] = FFV1,
        **encoder_params: Any
    ) -> None:
        # don't use lossless encoder very often so probably missing things
        self.v_lossless_encoder = encoder(**encoder_params)


    def audio_encoder(
        self,
        tracks: int | List[int] = 1,
        extracter: Type[Types.AUDIO_EXTRACTOR] | Sequence[Type[Types.AUDIO_EXTRACTOR]] = FFmpegAudioExtracter,
        cutter: Type[Types.AUDIO_CUTTER] | Sequence[Type[Types.AUDIO_CUTTER]] = EztrimCutter,
        encoder: Type[Types.AUDIO_ENCODER] | Sequence[Type[Types.AUDIO_ENCODER]] | None = QAACEncoder,
        extracter_settings: Dict[str, Any] = {},  # need support for per extracter/cutter/encoder settings
        cutter_settings: Dict[str, Any] = {},
        encoder_settings: Dict[str, Any] = {},
    ) -> None:
        if isinstance(tracks, int):
            tracks = [tracks]
        self.a_tracks = tracks
        track_number = len(self.a_tracks)

        if not isinstance(extracter, Sequence):
            extracter = [extracter] * track_number
        assert len(extracter) == track_number

        if not isinstance(cutter, Sequence):
            cutter = [cutter] * track_number
        assert len(cutter) == track_number

        if encoder is not None:
            if not isinstance(encoder, Sequence):
                encoder = [encoder] * track_number
            assert len(encoder) == track_number

        logger.info(
            f"Audio extractor: {self._print_sequence_name(extracter)}" +
            f"\nAudio cutter: {self._print_sequence_name(cutter)}" +
            f"\nAudio encoder: {self._print_sequence_name(encoder)}" +
            f"\nTrack(s): {self._print_sequence_name(tracks)}"
        )

        self.a_extracter = []
        self.a_cutter = []
        self.a_encoder = []

        output_tracks = range(1, track_number + 1)

        for in_idx, out_idx, extracter, cutter in zip(self.a_tracks, output_tracks, extracter, cutter):
            self.a_extracter.append(extracter(self.file, track_in=in_idx, track_out=out_idx), **extracter_settings)
            self.a_cutter.append(cutter(self.file, track=out_idx, **cutter_settings))

        if encoder is not None:
            for out_idx, encoder in zip(output_tracks, encoder):
                if encoder == QAACEncoder:
                    enc_args = Defaults.AAC
                    enc_args |= encoder_settings
                elif encoder == OpusEncoder:
                    enc_args = Defaults.OPUS
                    enc_args |= encoder_settings
                elif encoder == FlacEncoder:
                    enc_args = Defaults.FLAC
                    enc_args |= encoder_settings
                else:
                    enc_args = encoder_settings
                self.a_encoder.append(encoder(self.file, track=out_idx, **enc_args))
        else:
            self.a_encoder = None


    def muxer(
        self,
        v_title: str | None = None,
        a_title: str | List[str | None] | None = None,
        a_lang: Lang | List[Lang] = UNDEFINED,
        **muxer_options: Any
    ) -> None:
        assert self.file.a_enc_cut
        assert self.file.a_src_cut

        a_track_number = len(self.a_tracks)

        if(isinstance(a_title, str)):
            a_title = [a_title] * a_track_number
        if(isinstance(a_lang, Lang)):
            a_lang = [a_lang] * a_track_number

        if not a_title:
            a_title = [None] * a_track_number
        else:
            assert len(a_title) == a_track_number

        if not a_lang:
            a_lang = [UNDEFINED] * a_track_number
        else:
            assert len(a_lang) == a_track_number

        a_src = zip(range(1, a_track_number + 1), a_title, a_lang)

        tracks: List[Track] = [
            VideoTrack(self.file.name_clip_output, v_title),
        ]

        for idx, name, lang in a_src:
            if self.a_encoder is None:
                track = self.file.a_src_cut.set_track(idx)
            else:
                track = self.file.a_enc_cut.set_track(idx)
            tracks.append(AudioTrack(track, name, lang))

        if self.file.chapter:
            tracks.append(ChaptersTrack(self.file.chapter))

        self.mux = MatroskaFile(self.file.name_file_final, tracks, **muxer_options)


    def make_chapters(
        self,
        chapter_format: Type[Types.CHAPTER] = MatroskaXMLChapters,
        path: str | VPath | None = None
    ) -> None:
        assert self.chapters
        assert self.chapters_names
        assert len(self.chapters) == len(self.chapters_names)

        if not path:
            path = f"{self.ep_num}_chapters.xml"

        if isinstance(path, str):
            path = VPath(path)

        if(all(isinstance(chapter, int) for chapter in self.chapters)):
            chapters = [Chapter(f"Chapter {i}", f, None) for i, f in enumerate(self.chapters, 1)]  # type: ignore
        else:
            chapters = self.chapters  # type: ignore

        chapter_file = chapter_format(path)
        chapter_file.create(chapters, Fraction(self.clip.fps_num, self.clip.fps_den))

        chapter_offset = self.file.trims_or_dfs[0]  # type: ignore

        if isinstance(chapter_offset, int):
            chapter_offset = chapter_offset * -1
            chapter_file.shift_times(chapter_offset, self.file.clip.fps)
            chapter_file.set_names(self.chapters_names)

        self.file.chapter = path


    def run(
        self,
        order: RunnerConfig.Order = RunnerConfig.Order.VIDEO,
    ) -> None:
        config = RunnerConfig(
            v_encoder=self.v_encoder,  # type: ignore
            v_lossless_encoder=self.v_lossless_encoder,
            a_extracters=self.a_extracter,
            a_cutters=self.a_cutter,
            a_encoders=self.a_encoder,
            mkv=self.mux,
            order=order,
        )

        self.runner = SelfRunner(self.clip, self.file, config)
        self.runner.run()


    def generate_keyframes(self, delete_index: bool = True) -> None:
        import kagefunc as kgf

        if self.file.name_file_final.exists():
            clip = source(self.file.name_file_final.to_str(), force_lsmas=True)
            logger.info("Generating keyframes from encoded file")

            if delete_index:
                os.remove(f"{self.file.name_file_final.to_str()}.lwi")
        else:
            clip = self.clip
            logger.info("Generating keyframes from filtered clip")

        kgf.generate_keyframes(clip, f"{self.file.name_file_final.to_str()}_keyframes.txt")
        print("")


    def clean_up(
        self,
        add_file: Types.PATH | List[Types.PATH] | None = None,
        ignore_file: VPath | List[VPath] | None = None
    ) -> None:
        logger.info("Cleaning up extra files")

        if not hasattr(self, "runner"):
            logger.error("Runner not found", False)

        if isinstance(add_file, str) or isinstance(add_file, Path):
            add_file = [add_file]
        elif add_file is None:
            add_file = []

        if isinstance(ignore_file, VPath):
            ignore_file = [ignore_file]
        elif ignore_file is None:
            ignore_file = []

        for file in add_file:
            self.runner.work_files.add(file)
        for file in ignore_file:
            self.runner.work_files.remove(file)

        self.runner.work_files.clear()


    def make_comp(self, **comp_args: Any) -> None:
        logger.info("Making comp file")

        args: Dict[str, Any] = dict(num=100, force_bt709=True)
        args |= comp_args

        if os.path.isdir("comps"):
            rmtree("comps")
            logger.info("Removed old comps folder")

        def write_props(clip: vs.VideoNode, props: str | List[str] | None = None) -> vs.VideoNode:
            if props is None:
                props = ["_FrameNumber", "_PictType"]
            return clip.text.FrameProps(props, 7, 1)

        make_comps(
            {
                "source": write_props(self.file.clip_cut),
                "filtered": write_props(self.clip),
                "encode": write_props(source(self.file.name_file_final.to_str(), force_lsmas=True)),
            },
            **args
        )


    @staticmethod
    def _print_name(object: Any) -> str:
        if object is None:
            return "None"
        elif isinstance(object, str):                               # str
            return object
        elif hasattr(object, "__name__"):                           # class type
            return str(object.__name__)
        elif isinstance(object, int) or isinstance(object, float):  # numbers
            return str(object)
        elif hasattr(object, "__class__"):                          # class instance
            return str(object.__class__.__name__)
        else:                                                       # the rest
            return str(object)


    @staticmethod
    def _print_sequence_name(objects: Sequence[Any] | None) -> str:
        return "None" if objects is None else ", ".join([Encoder._print_name(obj) for obj in objects])
