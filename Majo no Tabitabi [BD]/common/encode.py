from __future__ import annotations

__all__ = ["Encoder"]

import os
from fractions import Fraction
from shutil import rmtree
from typing import Any, Dict, List, Literal, Sequence, Tuple, Type, Union

import vapoursynth as vs
from lvsfunc import source, find_scene_changes
from lvsfunc.types import SceneChangeMode
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


# Types
VIDEO_ENCODER = Union[X264, X265]
VIDEO_LOSSLESS_ENCODER = Union[FFV1, NVEncCLossless]

AUDIO_EXTRACTER = Union[FFmpegAudioExtracter, MKVAudioExtracter, Eac3toAudioExtracter]
AUDIO_CUTTER = Union[EztrimCutter, SoxCutter, ScipyCutter, PassthroughCutter]
AUDIO_ENCODER = Union[FlacEncoder, OpusEncoder, QAACEncoder, PassthroughAudioEncoder]

# these exist so that func signature is readable in vscode
AUDIO_EXTRACTER_TYPE = Union[Type[AUDIO_EXTRACTER], None]
AUDIO_CUTTER_TYPE = Union[Type[AUDIO_CUTTER], None]
AUDIO_ENCODER_TYPE = Union[Type[AUDIO_ENCODER], Sequence[Type[AUDIO_ENCODER]], None]

AUDIO_ENCODER_NAMES = Literal["flac", "opus", "aac", "passthrough"]

CHAPTER = Union[OGMChapters, MatroskaXMLChapters]


class Defaults:
    AAC: Dict[str, Any] = dict(bitrate=127, mode=BitrateMode.TVBR)
    OPUS: Dict[str, Any] = dict(bitrate=2 * 96, mode=BitrateMode.VBR, use_ffmpeg=True)
    FLAC: Dict[str, Any] = dict(level=FlacCompressionLevel.VARDOU, use_ffmpeg=True)


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

    v_encoder: VIDEO_ENCODER | None
    """Video encoder"""
    v_lossless_encoder: VIDEO_LOSSLESS_ENCODER | None
    """Lossless video encoder"""

    a_tracks: List[int]
    """Audio tracks"""
    # a_extracter: Sequence[Types.AUDIO_EXTRACTOR] | None
    a_extracter: AUDIO_EXTRACTER | None
    """Audio extractor"""
    a_cutter: List[AUDIO_CUTTER] | None
    """Audio cutter"""
    a_encoder: List[AUDIO_ENCODER] | None
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
        encoder: Type[VIDEO_ENCODER],
        settings: str | List[str] | Dict[str, Any],
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
        encoder: Type[VIDEO_LOSSLESS_ENCODER] = FFV1,
        **encoder_params: Any
    ) -> None:
        # don't use lossless encoder very often so probably missing things
        self.v_lossless_encoder = encoder(**encoder_params)


    def audio_encoder(
        self,
        tracks: int | List[int],
        extracter: AUDIO_EXTRACTER_TYPE = FFmpegAudioExtracter,
        cutter: AUDIO_CUTTER_TYPE = EztrimCutter,
        encoder: AUDIO_ENCODER_TYPE = QAACEncoder,
        extracter_settings: Dict[str, Any] = {},
        cutter_settings: Dict[str, Any] = {},
        encoder_settings: Dict[AUDIO_ENCODER_NAMES, Dict[str, Any]] = {},
    ) -> None:
        if isinstance(tracks, int):
            tracks = [tracks]
        self.a_tracks = tracks
        track_number = len(self.a_tracks)

        if encoder is not None:
            if not isinstance(encoder, Sequence):
                encoder = [encoder] * track_number
            else:
                assert len(encoder) == track_number

        logger.info(
            f"Audio extractor: {self._print_name(extracter)}" +
            f"\nAudio cutter: {self._print_name(cutter)}" +
            f"\nAudio encoder: {self._print_sequence_name(encoder)}" +
            f"\nTrack(s): {self._print_sequence_name(tracks)}"
        )

        output_tracks = range(1, track_number + 1)

        if extracter is not None:
            self.a_extracter = extracter(
                self.file, track_in=self.a_tracks, track_out=output_tracks, **extracter_settings
            )

        if cutter is not None:
            self.a_cutter = []
            for out_idx in output_tracks:
                self.a_cutter.append(cutter(self.file, track=out_idx, **cutter_settings))

        if encoder is not None:
            self.a_encoder = []
            for out_idx, encoder in zip(output_tracks, encoder):
                if encoder == QAACEncoder:
                    enc_args = Defaults.AAC | (encoder_settings.get("aac") or {})
                elif encoder == OpusEncoder:
                    enc_args = Defaults.OPUS | (encoder_settings.get("opus") or {})
                elif encoder == FlacEncoder:
                    enc_args = Defaults.FLAC | (encoder_settings.get("flac") or {})
                elif encoder == PassthroughAudioEncoder:
                    enc_args = {}
                else:
                    raise ValueError("Invalid audio encoder")

                self.a_encoder.append(encoder(self.file, track=out_idx, **enc_args))


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
        chapter_format: Type[CHAPTER] = MatroskaXMLChapters,
        path: str | VPath | None = None
    ) -> None:
        assert self.chapters
        assert self.chapters_names
        assert len(self.chapters) == len(self.chapters_names)

        if not path:
            path = f"{self.ep_num}_chapters.xml"

        if isinstance(path, str):
            path = VPath(path)

        # mypy is so fucking dumb
        if(all(isinstance(chapter, int) for chapter in self.chapters)):
            chapters = [Chapter(f"Chapter {i}", f, None) for i, f in enumerate(self.chapters, 1)]  # type: ignore
        elif(all(isinstance(chapter, Chapter) for chapter in self.chapters)):
            chapters = self.chapters  # type: ignore
        else:
            raise ValueError("Invalid chapter type, should be all int or all Chapter instance")

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


    def generate_keyframes(self, mode: SceneChangeMode = SceneChangeMode.WWXD, delete_index: bool = True) -> None:
        if self.file.name_file_final.exists():
            logger.info("Generating keyframes from encoded file")
            clip = source(self.file.name_file_final.to_str(), force_lsmas=True)
        else:
            logger.info("Generating keyframes from filtered clip")
            clip = self.clip

        kf = find_scene_changes(clip, mode)

        with open(f"{self.file.name_file_final.to_str()}_keyframes.txt", "w") as f:
            f.write("# WWXD log file, using qpfile format\n\n")
            f.writelines([f"{frame} I -1\n" for frame in kf[1:]])

        if delete_index:
            os.remove(f"{self.file.name_file_final.to_str()}.lwi")


    def clean_up(
        self,
        add_file: str | Sequence[str] | None = None,
        ignore_file: VPath | Sequence[VPath] | None = None
    ) -> None:
        logger.info("Cleaning up extra files")

        if not hasattr(self, "runner"):
            logger.error("Runner not found", False)

        if add_file is None:
            add_file = []
        elif isinstance(add_file, str):
            add_file = [add_file]

        if ignore_file is None:
            ignore_file = []
        elif isinstance(ignore_file, VPath):
            ignore_file = [ignore_file]

        for add in add_file:
            self.runner.work_files.add(add)
        for ignore in ignore_file:
            self.runner.work_files.remove(ignore)

        self.runner.work_files.clear()


    def make_comp(self, **comp_args: Any) -> None:
        logger.info("Making comp file")

        args: Dict[str, Any] = dict(num=100, force_bt709=True)
        args |= comp_args

        if os.path.isdir("comps"):
            rmtree("comps")
            logger.info("Removed old comps folder")

        def _write_props(clip: vs.VideoNode, props: str | List[str] | None = None) -> vs.VideoNode:
            if props is None:
                props = ["_FrameNumber", "_PictType"]
            return clip.text.FrameProps(props, 7, 1)

        lossless = self.file.name_clip_output.append_stem("_lossless.mkv")
        filtered = source(lossless.resolve().to_str(), force_lsmas=True) if lossless.exists() else self.clip
        make_comps(
            {
                "source": _write_props(self.file.clip_cut),
                "filtered": _write_props(filtered),
                "encode": _write_props(source(self.file.name_file_final.to_str(), force_lsmas=True)),
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
