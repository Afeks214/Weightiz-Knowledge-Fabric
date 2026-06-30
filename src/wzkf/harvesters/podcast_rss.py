from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree


class PodcastRssPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class HarvestedPodcastEpisode:
    source_key: str
    title: str
    source_url: str
    transcript_url: str | None
    audio_url: str | None
    selected_artifact_url: str
    selected_artifact_type: str
    used_transcription: bool


class PodcastRssHarvester:
    def harvest_first_episode(self, rss_xml: str, source_key: str) -> HarvestedPodcastEpisode:
        root = ElementTree.fromstring(rss_xml)
        item = root.find("./channel/item")
        if item is None:
            raise PodcastRssPolicyError("RSS feed has no episode item")
        title = _child_text(item, "title")
        source_url = _child_text(item, "link")
        transcript_url = _transcript_url(item)
        audio_url = _enclosure_url(item)

        if _is_youtube(source_url) and transcript_url is None:
            raise PodcastRssPolicyError("YouTube-only source lacks authorized transcript metadata")

        if transcript_url is not None:
            return HarvestedPodcastEpisode(
                source_key=source_key,
                title=title,
                source_url=source_url,
                transcript_url=transcript_url,
                audio_url=audio_url,
                selected_artifact_url=transcript_url,
                selected_artifact_type="transcript",
                used_transcription=False,
            )

        if audio_url is None:
            raise PodcastRssPolicyError("RSS episode has neither transcript metadata nor audio enclosure")

        return HarvestedPodcastEpisode(
            source_key=source_key,
            title=title,
            source_url=source_url,
            transcript_url=None,
            audio_url=audio_url,
            selected_artifact_url=audio_url,
            selected_artifact_type="audio",
            used_transcription=True,
        )


def _child_text(item: ElementTree.Element, child_name: str) -> str:
    child = item.find(child_name)
    if child is None or child.text is None:
        return ""
    return " ".join(child.text.split())


def _transcript_url(item: ElementTree.Element) -> str | None:
    for child in list(item):
        if child.tag.endswith("transcript"):
            return child.attrib.get("url")
    return None


def _enclosure_url(item: ElementTree.Element) -> str | None:
    enclosure = item.find("enclosure")
    if enclosure is None:
        return None
    return enclosure.attrib.get("url")


def _is_youtube(url: str) -> bool:
    lowered = url.casefold()
    return "youtube.com" in lowered or "youtu.be" in lowered
