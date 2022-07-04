__all__ = ["ParseBD"]

from pathlib import Path
from typing import Any, Dict, List, Sequence, cast

import vapoursynth as vs
from vardautomation import Chapter, FileInfo, MplsChapters, MplsReader, PresetBD, PresetOpus, VPath

core = vs.core


class ParseBD:
    bdmv_folder: Path
    episodes: List[VPath]
    chapters: List[MplsChapters]
    episode_number: int

    def __init__(
        self, bdmv_folder: str | Path,
        bd_volumes: Sequence[str | Path] | None = None,
        ep_playlist: int | Sequence[int] = 1
    ) -> None:
        """
        Parse a Blu-Ray (BD) by reading the playlist files in order to get the list of episodes

        :param bdmv_folder:     Path to the BDMV folder that contains every volume
        :param bd_volumes:      Path to every volume of the BD (relative to the BDMV folder). Will try to automatically
                                find them if None.
        :param ep_playlist:     Playlist file for the episodes (defaults to 1, can be set for each volume)
        """
        self.bdmv_folder = Path(bdmv_folder).resolve()
        if not self.bdmv_folder.exists():
            raise ValueError("Invalid BDMV path")

        if bd_volumes:
            vols = [Path(self.bdmv_folder / bd_vol).resolve() for bd_vol in bd_volumes]
        else:
            subdirs = [x for x in self.bdmv_folder.iterdir() if x.is_dir()]
            vols = [self._find_vol_path(vol) for vol in subdirs]  # type: ignore

        if any(path is None or not path.exists() for path in vols):
            raise ValueError("Invalid volume path or could not find BD volume")
        vols = cast(List[Path], vols)  # type: ignore  # mypy is so fucking dumb


        vol_num = len(vols)
        if not isinstance(ep_playlist, Sequence):
            ep_playlist = [ep_playlist] * vol_num
        elif len(ep_playlist) < vol_num:
            ep_playlist = list(ep_playlist) + ([ep_playlist[-1]] * (vol_num - len(ep_playlist)))
        elif len(ep_playlist) > vol_num:
            raise ValueError(f"Too many playlist values, expected {vol_num} max")

        self.episodes = []
        self.chapters = []
        for bd_vol, p in zip(vols, ep_playlist):
            chaps = MplsReader(bd_vol).get_playlist()[p].mpls_chapters
            self.episodes += [chap.m2ts for chap in chaps]
            self.chapters += chaps

        self.episode_number = len(self.episodes)


    def _find_vol_path(self, root_dir: Path) -> Path | None:
        subdirs = [x.name for x in root_dir.iterdir() if x.is_dir()]

        if "BDMV" in subdirs and "CERTIFICATE" in subdirs:
            return root_dir

        elif len(subdirs):
            for dir in subdirs:
                path = self._find_vol_path(root_dir / dir)

                if path is not None:
                    return path

        return None  # mypy why ?


    def get_episode(self, ep_num: int | str, **fileinfo_args: Any) -> FileInfo:
        """
        Get FileInfo object of an episode

        :param ep_num:          Episode to get (not zero-based)
        :param fileinfo_args:   Additional parameters to be passed to FileInfo

        :return:                FileInfo object
        """
        if isinstance(ep_num, str):
            ep_num = int(ep_num)

        args: Dict[str, Any] = dict(trims_or_dfs=(24, -24), preset=[PresetBD, PresetOpus], idx=core.lsmas.LWLibavSource)
        args |= fileinfo_args

        return FileInfo(self.episodes[ep_num - 1], **args)


    def get_chapter(
        self,
        ep_num: int | str
    ) -> List[Chapter]:
        """Get a list of chapters of an episode

        :param ep_num:      Episode to get (not zero-based)

        :return:            List of chapters
        """
        if isinstance(ep_num, str):
            ep_num = int(ep_num)

        return self.chapters[ep_num - 1].to_chapters()
