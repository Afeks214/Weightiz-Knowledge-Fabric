from __future__ import annotations

import re
from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass(frozen=True)
class HarvestedPaper:
    source_key: str
    arxiv_id: str
    title: str
    abstract: str
    authors: list[str]
    categories: list[str]
    source_url: str
    pdf_url: str
    license_status: str


class ArxivAtomHarvester:
    def __init__(self, query_id: str):
        self.query_id = query_id

    def parse(self, atom_xml: str) -> list[HarvestedPaper]:
        root = ElementTree.fromstring(atom_xml)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        papers: list[HarvestedPaper] = []
        for entry in root.findall("atom:entry", ns):
            source_url = _text(entry.find("atom:id", ns))
            arxiv_id = _arxiv_id(source_url)
            papers.append(
                HarvestedPaper(
                    source_key=f"arxiv:{self.query_id}",
                    arxiv_id=arxiv_id,
                    title=_text(entry.find("atom:title", ns)),
                    abstract=_text(entry.find("atom:summary", ns)),
                    authors=[
                        _text(author.find("atom:name", ns))
                        for author in entry.findall("atom:author", ns)
                    ],
                    categories=[
                        category.attrib.get("term", "")
                        for category in entry.findall("atom:category", ns)
                    ],
                    source_url=source_url,
                    pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
                    license_status="open_metadata_pdf_allowed",
                )
            )
        return papers


def _text(element: ElementTree.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return " ".join(element.text.split())


def _arxiv_id(source_url: str) -> str:
    tail = source_url.rstrip("/").split("/")[-1]
    return re.sub(r"v\d+$", "", tail)
