import vapoursynth as vs
import kagefunc as kgf
import lvsfunc as lvf
from vsutil import depth, get_depth
from vardautomation import (
    FileInfo, VPath,
    X265Encoder, FFmpegAudioExtracter, QAACEncoder,
    Chapter, MatroskaXMLChapters,
    Mux, AudioStream, VideoStream, JAPANESE,
    RunnerConfig, SelfRunner
)
from vardautomation.status import Status

import os
from typing import Optional, List

core = vs.core

class Encoder:
    """Encoder class"""
    
    def __init__(
        self, 
        file: FileInfo, 
        clip: vs.VideoNode, 
        chapters: Optional[List[Chapter]] = None,
        chapter_names: Optional[List[str]] = None
    ) -> None:

        self.file = file
        self.clip = clip
        self.chapters = chapters
        self.chapters_names = chapter_names


    def run(self, generate_keyframes: bool=True, clean_up: bool=True) -> None:
        """Run the encoder with specified settings. 

        FGO Camelot specific settings: \\
        -x265 Encoder \\
        -FFmpegAudioExtracter (tracks 1 & 2) \\
        -QAACEncoder (2x, one for each track) \\
        -Muxer

        Args:
        -generate_keyframe: generate keyframes for timing
        -clean_up: clean temporary files after encoding (e.g. raw audio)
        """

        if get_depth(self.clip) != 10:
            self.clip = depth(self.clip, 10)

        v_encoder = X265Encoder("common/x265_settings")

        self.file.a_src_cut = self.file.a_src # QAACEncoder always takes a_src_cut

        a_tracks = [1, 2]
        a_extract = FFmpegAudioExtracter(self.file, track_in=a_tracks, track_out=a_tracks)
        a_encoders = [QAACEncoder(self.file, track=a_track, qaac_args=["-N"]) for a_track in a_tracks]

        audio_streams = [
            AudioStream(self.file.a_enc_cut.set_track(2), "AAC 2.0", JAPANESE),
            AudioStream(self.file.a_enc_cut.set_track(1), "AAC 5.1", JAPANESE),
        ]

        # bdmv pls
        if self.chapters:
            self.file.chapter = VPath(f"{self.file.ep_num}_chapters.xml")
            chapterXML = MatroskaXMLChapters(self.file.chapter)
            chapterXML.create(self.chapters, self.file.clip.fps)
            chapterXML.set_names(self.chapters_names)

            self.chapter_offset = self.file.trims_or_dfs[0]

            if isinstance(self.chapter_offset, int):
                self.chapter_offset = self.chapter_offset * -1
                chapterXML.shift_times(self.chapter_offset, self.file.clip.fps)

        self.file.name_file_final = VPath(f"./{self.file.ep_num}_premux.mkv")
        muxer = Mux(
            self.file,
            streams=(
                VideoStream(self.file.name_clip_output, "x265 BD"),
                audio_streams,
                None
            )
        )

        config = RunnerConfig(v_encoder, None, a_extract, None, a_encoders, muxer)

        runner = SelfRunner(self.clip, self.file, config)
        runner.run()

        if generate_keyframes:
            self.generate_keyframes()

        if clean_up:
            self.clean_up(runner)


    def generate_keyframes(self):
        if os.path.isfile(self.file.name_file_final):
            clip = lvf.misc.source(self.file.name_file_final)
            Status.info(f"Generating keyframes from encoded file")
        else:
            clip = self.clip
            Status.info(f"Generating keyframes from filtered clip")

        kgf.generate_keyframes(clip, f"{self.file.name_file_final.to_str()}_keyframes.txt")
    

    def clean_up(self, runner: SelfRunner):
        Status.info("Cleaning up extra files")
        runner.do_cleanup()

        #remove ffindex of final file if used to generate keyframe
        ffindex = f"{self.file.name_file_final.to_str()}.ffindex"
        if os.path.isfile(ffindex):
            os.remove(ffindex)