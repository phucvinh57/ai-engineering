"""Parse Wayland protocol XML files into one record per interface.

Each <protocol> file contains one or more <interface> elements, each with a
<description> and nested <request>/<event>/<enum> children that each carry
their own description text. This walks that structure directly -- there is
no HTML to scrape, the documentation is already structured data.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

from lxml import etree

from wayland_assistant.config import Settings
from wayland_assistant.sources.repos import ProtocolFile, blob_url


def _clean(text: str | None) -> str:
    if not text:
        return ""
    return textwrap.dedent(text).strip()


def _description(elem: etree._Element) -> str:
    desc = elem.find("description")
    if desc is not None:
        return _clean(desc.text)
    return _clean(elem.get("summary"))


@dataclass
class EnumEntry:
    name: str
    summary: str
    value: str


@dataclass
class Enum:
    name: str
    summary: str
    description: str
    entries: list[EnumEntry] = field(default_factory=list)


@dataclass
class Member:
    kind: str  # "request" | "event"
    name: str
    summary: str
    description: str
    args: list[str] = field(default_factory=list)


@dataclass
class InterfaceDoc:
    protocol_name: str
    interface_name: str
    version: str
    maturity: str
    repo: str
    source_path: str
    url: str
    summary: str
    description: str
    requests: list[Member] = field(default_factory=list)
    events: list[Member] = field(default_factory=list)
    enums: list[Enum] = field(default_factory=list)

    def render_text(self) -> str:
        """Flatten the interface + all its members into one text blob."""
        parts = [f"Interface: {self.interface_name} (version {self.version})"]
        if self.description:
            parts.append(self.description)

        for req in self.requests:
            parts.append(_render_member(req))
        for ev in self.events:
            parts.append(_render_member(ev))
        for enum in self.enums:
            parts.append(_render_enum(enum))

        return "\n\n".join(p for p in parts if p)


def _render_member(member: Member) -> str:
    header = f"{member.kind.capitalize()}: {member.name}"
    if member.args:
        header += f" ({', '.join(member.args)})"
    body = member.description or member.summary
    return f"{header}\n{body}" if body else header


def _render_enum(enum: Enum) -> str:
    parts = [f"Enum: {enum.name}"]
    if enum.description:
        parts.append(enum.description)
    parts.extend(f"- {entry.name} ({entry.value}): {entry.summary}" for entry in enum.entries)
    return "\n\n".join(parts)


def _parse_member(elem: etree._Element, kind: str) -> Member:
    args = [
        f"{arg.get('name')}: {arg.get('type')}"
        for arg in elem.findall("arg")
    ]
    return Member(
        kind=kind,
        name=elem.get("name", ""),
        summary=elem.get("summary", ""),
        description=_description(elem),
        args=args,
    )


def _parse_enum(elem: etree._Element) -> Enum:
    entries = [
        EnumEntry(
            name=entry.get("name", ""),
            summary=entry.get("summary", ""),
            value=entry.get("value", ""),
        )
        for entry in elem.findall("entry")
    ]
    return Enum(
        name=elem.get("name", ""),
        summary=elem.get("summary", ""),
        description=_description(elem),
        entries=entries,
    )


def parse_protocol_file(pf: ProtocolFile, settings: Settings) -> list[InterfaceDoc]:
    """Parse a single protocol XML file into one InterfaceDoc per interface."""
    tree = etree.parse(str(pf.path))
    root = tree.getroot()
    protocol_name = root.get("name", pf.path.stem)
    url = blob_url(settings, pf)
    repo_root = settings.repos_dir / pf.repo

    docs: list[InterfaceDoc] = []
    for iface in root.findall("interface"):
        requests = [_parse_member(r, "request") for r in iface.findall("request")]
        events = [_parse_member(e, "event") for e in iface.findall("event")]
        enums = [_parse_enum(e) for e in iface.findall("enum")]
        desc_elem = iface.find("description")

        docs.append(
            InterfaceDoc(
                protocol_name=protocol_name,
                interface_name=iface.get("name", ""),
                version=iface.get("version", "1"),
                maturity=pf.maturity,
                repo=pf.repo,
                source_path=str(pf.path.relative_to(repo_root)),
                url=url,
                summary=desc_elem.get("summary", "") if desc_elem is not None else "",
                description=_description(iface),
                requests=requests,
                events=events,
                enums=enums,
            )
        )
    return docs
