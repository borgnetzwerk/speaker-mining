from __future__ import annotations

import json
import re
from urllib.parse import urljoin


_EPISODENGUIDE_HREF_RE = re.compile(
    r'href=["\'](?P<href>[^"\']*/episodenguide[^"\']*)["\']',
    re.IGNORECASE,
)

_EPISODE_HREF_RE = re.compile(
    r'href=["\'](?P<href>[^"\']*/folgen/[^"\']+)["\']',
    re.IGNORECASE,
)

_H1_RE = re.compile(r"<h1[^>]*>(?P<text>.*?)</h1>", re.IGNORECASE | re.DOTALL)
_H2_RE = re.compile(r"<h2[^>]*>(?P<text>.*?)</h2>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_EPISODE_TITLE_RE = re.compile(
    r'<h3[^>]*class=["\']episode-output-titel["\'][^>]*>.*?<span[^>]*itemprop=["\']name["\'][^>]*>(?P<text>.*?)</span>',
    re.IGNORECASE | re.DOTALL,
)
_DURATION_RE = re.compile(
    r'<div[^>]*class=["\']episoden-zeile-1000["\'][^>]*>\s*<div[^>]*>(?P<text>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_DESCRIPTION_INNER_RE = re.compile(
    r'<div[^>]*class=["\']episode-output-inhalt-inner["\'][^>]*>(?P<text>.*?)</div>',
    re.IGNORECASE | re.DOTALL,
)
_DESCRIPTION_SOURCE_RE = re.compile(
    r'<span[^>]*class=["\']text-quelle["\'][^>]*>\s*\((?P<text>.*?)\)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)
_PREMIERE_DATE_RE = re.compile(r"<ea-angabe-datum>(?P<text>.*?)</ea-angabe-datum>", re.IGNORECASE | re.DOTALL)
_PREMIERE_SENDER_RE = re.compile(r"<ea-angabe-sender>(?P<text>.*?)</ea-angabe-sender>", re.IGNORECASE | re.DOTALL)
_CAST_SECTION_RE = re.compile(
    r'<h2[^>]*id=["\']?Cast-Crew["\']?[^>]*>.*?</h2>.*?<ul[^>]*class=["\']cast-crew[^"\']*["\'][^>]*>(?P<section>.*?)</ul>',
    re.IGNORECASE | re.DOTALL,
)
_CAST_ANCHOR_RE = re.compile(
    r'<a[^>]*data-event-category=["\']liste-cast-crew["\'][^>]*>(?P<block>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TITLE_ATTR_RE = re.compile(r'title=["\'](?P<text>[^"\']+)', re.IGNORECASE)
_HREF_ATTR_RE = re.compile(r'href=["\'](?P<text>[^"\']+)', re.IGNORECASE)
_META_IMAGE_RE = re.compile(r'<meta[^>]*itemprop=["\']image["\'][^>]*content=["\'](?P<url>[^"\']+)', re.IGNORECASE)
_LAZY_IMAGE_RE = re.compile(r'data-src=["\'](?P<url>[^"\']+)', re.IGNORECASE)
_DT_NAME_RE = re.compile(r'<dt[^>]*itemprop=["\']name["\'][^>]*>(?P<text>.*?)</dt>', re.IGNORECASE | re.DOTALL)
_DD_RE = re.compile(r'<dd[^>]*>\s*<p>(?P<text>.*?)</p>\s*</dd>', re.IGNORECASE | re.DOTALL)
_SENDETERMINE_SECTION_RE = re.compile(
    r'<h2[^>]*id=["\']?Sendetermine["\']?[^>]*>.*?</h2>(?P<section>.*?)</section>',
    re.IGNORECASE | re.DOTALL,
)
_START_DATE_RE = re.compile(
    r'<time[^>]*itemprop=["\']startDate["\'][^>]*datetime=["\'](?P<dt>[^"\']+)["\']',
    re.IGNORECASE,
)
_END_DATE_RE = re.compile(
    r'<time[^>]*itemprop=["\']endDate["\'][^>]*datetime=["\'](?P<dt>[^"\']+)["\']',
    re.IGNORECASE,
)
_BROADCASTER_RE = re.compile(
    r'itemprop=["\']name["\'][^>]*content=["\'](?P<name>[^"\']+)["\']',
    re.IGNORECASE,
)
_CANONICAL_EPISODE_URL_RE = re.compile(
    r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\'](?P<url>[^"\']*/folgen/[^"\']+)["\']',
    re.IGNORECASE,
)
_OG_URL_RE = re.compile(
    r'<meta[^>]*property=["\']og:url["\'][^>]*content=["\'](?P<url>[^"\']*/folgen/[^"\']+)["\']',
    re.IGNORECASE,
)
_FALLBACK_EPISODE_HREF_RE = re.compile(
    r'href=["\'](?P<href>[^"\']*/folgen/[^"\']+)["\']',
    re.IGNORECASE,
)
_NAV_EPISODE_LINK_RE = re.compile(
    r'<a[^>]*href=["\'](?P<href>[^"\']*/folgen/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)


def _clean_html_text(raw_html: str) -> str:
    plain = _TAG_RE.sub(" ", str(raw_html or ""))
    return " ".join(plain.split()).strip()


def _line_parts_from_html(raw_html: str) -> list[str]:
    raw = str(raw_html or "")
    parts = re.split(r"<br\s*/?>", raw, flags=re.IGNORECASE)
    clean_parts = [_clean_html_text(part) for part in parts]
    return [part for part in clean_parts if part]


def extract_first_episodenguide_url(*, html_text: str, root_url: str) -> str | None:
    """Return first episodenguide URL discovered in root page HTML."""
    if not html_text.strip():
        return None
    match = _EPISODENGUIDE_HREF_RE.search(html_text)
    if not match:
        return None
    return urljoin(root_url, match.group("href").strip())


def extract_episodenguide_urls(*, html_text: str, base_url: str) -> list[str]:
    """Extract unique episodenguide URLs from HTML in deterministic order."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _EPISODENGUIDE_HREF_RE.finditer(html_text or ""):
        absolute_url = urljoin(base_url, match.group("href").strip())
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        out.append(absolute_url)
    return out


def extract_episode_urls(*, html_text: str, base_url: str) -> list[str]:
    """Extract episode leaf URLs from episodenguide HTML."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _EPISODE_HREF_RE.finditer(html_text or ""):
        absolute_url = urljoin(base_url, match.group("href").strip())
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        out.append(absolute_url)
    return out


def extract_neighbor_episode_urls(*, html_text: str, base_url: str) -> list[str]:
    """Extract neighboring episode links from leaf-page navigation anchors."""
    seen: set[str] = set()
    out: list[str] = []
    for match in _NAV_EPISODE_LINK_RE.finditer(html_text or ""):
        label = _clean_html_text(match.group("label")).lower()
        if "weiter" not in label and "zur" not in label:
            continue
        absolute_url = urljoin(base_url, match.group("href").strip())
        if absolute_url in seen:
            continue
        seen.add(absolute_url)
        out.append(absolute_url)
    return out


def infer_episode_url_from_leaf_html(*, html_text: str, base_url: str = "https://www.fernsehserien.de/") -> str | None:
    """Infer leaf URL from canonical or og:url markers for legacy cache import."""
    html = html_text or ""
    canonical = _CANONICAL_EPISODE_URL_RE.search(html)
    if canonical:
        return urljoin(base_url, canonical.group("url").strip())
    og_url = _OG_URL_RE.search(html)
    if og_url:
        return urljoin(base_url, og_url.group("url").strip())
    fallback = _FALLBACK_EPISODE_HREF_RE.search(html)
    if fallback:
        return urljoin(base_url, fallback.group("href").strip())
    return None


def parse_episode_leaf_fields(*, html_text: str) -> dict:
    """Parse raw structured episode fields without semantic normalization."""
    html = html_text or ""

    title_match = _EPISODE_TITLE_RE.search(html)
    duration_match = _DURATION_RE.search(html)
    description_match = _DESCRIPTION_INNER_RE.search(html)
    source_match = _DESCRIPTION_SOURCE_RE.search(html)
    premiere_date_match = _PREMIERE_DATE_RE.search(html)
    premiere_sender_match = _PREMIERE_SENDER_RE.search(html)

    guests_raw: list[dict] = []
    cast_match = _CAST_SECTION_RE.search(html)
    if cast_match:
        for idx, anchor_match in enumerate(_CAST_ANCHOR_RE.finditer(cast_match.group("section"))):
            block = anchor_match.group("block")
            anchor_open = anchor_match.group(0).split(">", 1)[0]
            title_attr = _TITLE_ATTR_RE.search(anchor_open)
            href_attr = _HREF_ATTR_RE.search(anchor_open)
            name_match = _DT_NAME_RE.search(block)
            dd_match = _DD_RE.search(block)
            meta_img = _META_IMAGE_RE.search(block)
            lazy_img = _LAZY_IMAGE_RE.search(block)

            lines = _line_parts_from_html(dd_match.group("text")) if dd_match else []
            guest_role = lines[0] if lines else ""
            guest_description = " ".join(lines[1:]).strip() if len(lines) > 1 else ""

            guest_name = _clean_html_text(name_match.group("text")) if name_match else ""
            if not guest_name and title_attr:
                guest_name = _clean_html_text(title_attr.group("text"))

            guest_url_raw = href_attr.group("text").strip() if href_attr else ""
            image_url = ""
            if meta_img:
                image_url = meta_img.group("url").strip()
            elif lazy_img:
                image_url = lazy_img.group("url").strip()

            confidence = 0.55
            if guest_name:
                confidence += 0.25
            if guest_role:
                confidence += 0.1
            if guest_url_raw:
                confidence += 0.08

            guests_raw.append(
                {
                    "guest_name_raw": guest_name,
                    "guest_role_raw": guest_role,
                    "guest_description_raw": guest_description,
                    "guest_url_raw": guest_url_raw,
                    "guest_image_url_raw": image_url,
                    "guest_order": idx,
                    "confidence": round(min(confidence, 0.98), 3),
                }
            )

    broadcasts_raw: list[dict] = []
    sendetermine_match = _SENDETERMINE_SECTION_RE.search(html)
    if sendetermine_match:
        section = sendetermine_match.group("section")
        start_matches = list(_START_DATE_RE.finditer(section))
        for idx, start_match in enumerate(start_matches):
            start_pos = start_match.start()
            end_pos = start_matches[idx + 1].start() if idx + 1 < len(start_matches) else len(section)
            row_block = section[start_pos:end_pos]
            end_match = _END_DATE_RE.search(row_block)
            broadcaster_match = _BROADCASTER_RE.search(row_block)
            confidence = 0.5
            if start_match.group("dt").strip():
                confidence += 0.28
            if end_match and end_match.group("dt").strip():
                confidence += 0.12
            if broadcaster_match and broadcaster_match.group("name").strip():
                confidence += 0.08

            broadcasts_raw.append(
                {
                    "broadcast_start_datetime_raw": start_match.group("dt").strip(),
                    "broadcast_end_datetime_raw": end_match.group("dt").strip() if end_match else "",
                    "broadcast_broadcaster_raw": broadcaster_match.group("name").strip() if broadcaster_match else "",
                    "broadcast_is_premiere_raw": "TV-Premiere" if "TV-Premiere" in row_block or "NEU" in row_block else "",
                    "broadcast_order": idx,
                    "confidence": round(min(confidence, 0.98), 3),
                }
            )

    h1_match = _H1_RE.search(html)
    h2_match = _H2_RE.search(html)
    fallback_label = _clean_html_text(h1_match.group("text")) if h1_match else ""
    fallback_description = _clean_html_text(h2_match.group("text")) if h2_match else ""

    raw_extra = {
        "guests_count": len(guests_raw),
        "broadcasts_count": len(broadcasts_raw),
    }

    metadata_confidence = 0.5
    if title_match:
        metadata_confidence += 0.2
    if description_match:
        metadata_confidence += 0.2
    if premiere_date_match or premiere_sender_match:
        metadata_confidence += 0.08

    return {
        "episode_label": _clean_html_text(title_match.group("text")) if title_match else fallback_label,
        "description_text": _clean_html_text(description_match.group("text")) if description_match else fallback_description,
        "publication_text": _clean_html_text(premiere_date_match.group("text")) if premiere_date_match else "",
        "cast_crew_text": "; ".join([str(g.get("guest_name_raw", "")).strip() for g in guests_raw if g.get("guest_name_raw")]),
        "sendetermine_text": "; ".join([str(b.get("broadcast_start_datetime_raw", "")).strip() for b in broadcasts_raw if b.get("broadcast_start_datetime_raw")]),
        "episode_title_raw": _clean_html_text(title_match.group("text")) if title_match else fallback_label,
        "duration_raw": _clean_html_text(duration_match.group("text")) if duration_match else "",
        "description_raw_text": _clean_html_text(description_match.group("text")) if description_match else fallback_description,
        "description_source_raw": _clean_html_text(source_match.group("text")) if source_match else "",
        "premiere_date_raw": _clean_html_text(premiere_date_match.group("text")) if premiere_date_match else "",
        "premiere_broadcaster_raw": _clean_html_text(premiere_sender_match.group("text")) if premiere_sender_match else "",
        "guests_raw": guests_raw,
        "broadcasts_raw": broadcasts_raw,
        "raw_extra_json": json.dumps(raw_extra, ensure_ascii=False),
        "parser_rule": "leaf_v1_raw_structured",
        "confidence": round(min(metadata_confidence, 0.98), 3),
    }
