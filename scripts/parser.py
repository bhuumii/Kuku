import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Beat:
    kind: str
    speaker: Optional[str]
    tone: Optional[str]
    content: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Scene:
    number: int
    heading: str
    start: float
    end: float
    beats: list[Beat] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def dialogue_beats(self) -> list[Beat]:
        return [b for b in self.beats if b.kind == "dialogue"]


@dataclass
class Episode:
    number: int
    logline: str
    continuity_notes: str
    scenes: list[Scene]
    source_path: Path

    @property
    def total_duration(self) -> float:
        return self.scenes[-1].end if self.scenes else 0.0

    def all_beats(self) -> list[tuple[Scene, Beat]]:
        return [(s, b) for s in self.scenes for b in s.beats]


_TIMESTAMP = r"(\d{1,3}):(\d{2})\.(\d{1,2})"
_SCENE_HEADER = re.compile(r"^SCENE\s+(\d+)", re.IGNORECASE)
_SCENE_HEADING = re.compile(r"^Scene heading:\s*(.+)", re.IGNORECASE)
_SCENE_START = re.compile(rf"^Scene start:\s*{_TIMESTAMP}", re.IGNORECASE)
_SCENE_END = re.compile(rf"^Scene end:\s*{_TIMESTAMP}", re.IGNORECASE)
_BEAT_HEADER = re.compile(r"^\*\*([^*:]+?)(?:\s*\(([^)]+)\))?:\*\*\s*$")
_BEAT_RANGE = re.compile(rf"^Start:\s*\({_TIMESTAMP}\)\s*\|\s*End:\s*\({_TIMESTAMP}\)")
_EPISODE_NUMBER = re.compile(r"EPISODE NUMBER:\s*Episode\s*(\d+)", re.IGNORECASE)
_EPISODE_LOGLINE = re.compile(r"EPISODE LOGLINE:\s*(.+)", re.IGNORECASE)
_CONTINUITY = re.compile(r"CONTINUITY NOTES:\s*(.+)", re.IGNORECASE)

_META_KINDS = {"CAMERA", "ACTION", "SFX", "MUSIC", "VFX", "TRANSITION"}


def _ts_to_seconds(minutes: str, seconds: str, hundredths: str) -> float:
    h = hundredths.ljust(2, "0")[:2]
    return int(minutes) * 60 + int(seconds) + int(h) / 100.0


def _classify_header(header: str) -> tuple[str, Optional[str]]:
    clean = header.strip().upper()
    if clean in _META_KINDS:
        return clean.lower(), None
    return "dialogue", header.strip()


def parse_episode(path: Path | str) -> Episode:
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()

    ep_num = 0
    logline = ""
    continuity = ""
    scenes: list[Scene] = []
    current_scene: Optional[Scene] = None
    pending_header: Optional[tuple[str, Optional[str]]] = None

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if m := _EPISODE_NUMBER.search(line):
            ep_num = int(m.group(1))
        elif m := _EPISODE_LOGLINE.search(line):
            logline = m.group(1).strip()
        elif m := _CONTINUITY.search(line):
            continuity = m.group(1).strip()

        if m := _SCENE_HEADER.match(line.strip()):
            current_scene = Scene(number=int(m.group(1)), heading="", start=0.0, end=0.0)
            scenes.append(current_scene)
            pending_header = None

        elif current_scene is not None and (m := _SCENE_HEADING.match(line.strip())):
            current_scene.heading = m.group(1).strip()

        elif current_scene is not None and (m := _SCENE_START.match(line.strip())):
            current_scene.start = _ts_to_seconds(m.group(1), m.group(2), m.group(3))

        elif current_scene is not None and (m := _SCENE_END.match(line.strip())):
            current_scene.end = _ts_to_seconds(m.group(1), m.group(2), m.group(3))

        elif current_scene is not None and (m := _BEAT_HEADER.match(line.strip())):
            header, tone = m.group(1), m.group(2)
            pending_header = (header, tone)

        elif current_scene is not None and pending_header and (m := _BEAT_RANGE.match(line.strip())):
            start = _ts_to_seconds(m.group(1), m.group(2), m.group(3))
            end = _ts_to_seconds(m.group(4), m.group(5), m.group(6))

            content_lines: list[str] = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j].rstrip()
                if (
                    not nxt
                    or _BEAT_HEADER.match(nxt.strip())
                    or _SCENE_HEADER.match(nxt.strip())
                    or _SCENE_HEADING.match(nxt.strip())
                    or _SCENE_START.match(nxt.strip())
                    or _SCENE_END.match(nxt.strip())
                ):
                    break
                content_lines.append(nxt.strip().strip('"'))
                j += 1

            header_text, tone = pending_header
            kind, speaker = _classify_header(header_text)
            content = " ".join(content_lines).strip()
            if content:
                current_scene.beats.append(
                    Beat(kind=kind, speaker=speaker, tone=tone, content=content,
                         start=start, end=end)
                )
            pending_header = None
            i = j - 1

        i += 1

    scenes = [s for s in scenes if s.beats or s.end > s.start]
    return Episode(
        number=ep_num,
        logline=logline,
        continuity_notes=continuity,
        scenes=scenes,
        source_path=path,
    )


def parse_all_episodes(folder: Path | str) -> list[Episode]:
    folder = Path(folder)
    files = sorted(folder.glob("episode-*.txt"))
    episodes = [parse_episode(f) for f in files]
    episodes.sort(key=lambda e: e.number)
    return episodes

def episodes_to_dict(episodes: list[Episode]) -> list[dict]:
    return [
        {
            "number": e.number,
            "logline": e.logline,
            "continuity_notes": e.continuity_notes,
            "source_path": str(e.source_path),
            "scenes": [
                {
                    "number": s.number,
                    "heading": s.heading,
                    "start": s.start,
                    "end": s.end,
                    "beats": [
                        {
                            "kind": b.kind,
                            "speaker": b.speaker,
                            "tone": b.tone,
                            "content": b.content,
                            "start": b.start,
                            "end": b.end,
                        }
                        for b in s.beats
                    ],
                }
                for s in e.scenes
            ],
        }
        for e in episodes
    ]


def episodes_from_dict(data: list[dict]) -> list[Episode]:
    episodes = []
    for e in data:
        scenes = []
        for s in e["scenes"]:
            beats = [Beat(**b) for b in s["beats"]]
            scenes.append(Scene(
                number=s["number"], heading=s["heading"],
                start=s["start"], end=s["end"], beats=beats,
            ))
        episodes.append(Episode(
            number=e["number"], logline=e["logline"],
            continuity_notes=e["continuity_notes"],
            scenes=scenes, source_path=Path(e["source_path"]),
        ))
    return episodes