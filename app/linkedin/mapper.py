"""Map tagged flagship RSC hops onto the public profile schema."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.connectors.base import Hop
from app.linkedin.rsc import date_ranges, image_urls, iter_dicts, leaf_texts

NOISE_PREFIXES = (
    "proto.",
    "com.linkedin",
    "urn:li:",
    "http://",
    "https://",
    "$Sreact",
    "MemoryNamespace",
    "ProfileComponentState",
    "d_flagship",
)

SECTION_HEADERS = {
    "about",
    "experience",
    "education",
    "skills",
    "languages",
    "licenses & certifications",
    "licenses and certifications",
    "volunteering",
    "publications",
    "patents",
    "courses",
    "honors & awards",
    "organizations",
    "featured",
    "activity",
}

ABOUT_STOP_HEADERS = SECTION_HEADERS - {"about"}

HTML_TAGS = {"div", "span", "p", "a", "button", "img", "ul", "li", "section", "header", "br"}
PROTO_WORDS = {
    "id",
    "intvalue",
    "booleanvalue",
    "stringvalue",
    "visible",
    "$undefined",
    "null",
    "true",
    "false",
}
EMPLOYMENT_TYPES = {
    "full-time",
    "part-time",
    "self-employed",
    "freelance",
    "contract",
    "internship",
    "seasonal",
    "apprenticeship",
}
CHROME_PHRASES = {
    "view settings",
    "send profile in a message",
    "save to pdf",
    "report / block",
    "about this member",
    "contact info",
    "talent solutions",
    "marketing solutions",
    "sales solutions",
    "small business",
    "safety center",
    "community guidelines",
    "privacy & terms",
    "ad choices",
    "privacy policy",
    "user agreement",
    "pages terms",
    "cookie policy",
    "copyright policy",
    "help center",
}
POST_OPENERS = (
    "excited to share",
    "i'm happy to",
    "i am happy to",
    "i’m happy to",
    "proud to",
    "thrilled to",
    "delighted to",
    "honored to",
    "honoured to",
)

CSS_CLASS_RE = re.compile(r"^(?:_?[0-9a-f]{5,10}\s*){3,}$", re.I)
RSC_REF_RE = re.compile(r"^\$L[0-9a-z]+(?:\$L[0-9a-z]+)*$", re.I)
DOT_SPLIT_RE = re.compile(r"\s+[·•⋅]\s+")
DURATION_LINE_RE = re.compile(
    r"^(?:Full-time|Part-time|Self-employed|Freelance|Contract|Internship|Seasonal)\s+[·•⋅]\s+\d+",
    re.I,
)
ENDORSEMENT_RE = re.compile(r"^(\d+)\s+endorsements?$", re.I)
LOCATION_WORK_RE = re.compile(r"^(on-site|remote|hybrid)$", re.I)
FOLLOWERS_RE = re.compile(r"\b(followers|connections)\b", re.I)
ROLE_RE = re.compile(
    r"\b(engineer|officer|trainer|founder|co-founder|developer|manager|intern|"
    r"director|architect|consultant|analyst|designer|specialist|scientist|"
    r"president|lead|head|cto|ceo|coo|cfo|vp|vice president)\b",
    re.I,
)
AT_JOB_RE = re.compile(r"\s+at\s+", re.I)
YEAR_SPAN_RE = re.compile(r"^(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}$")
INSTITUTION_RE = re.compile(
    r"\b(university|college|institute|school|academy|polytechnic)\b",
    re.I,
)
COURSE_RE = re.compile(r"\b(training|course|bootcamp|certification|certificate)\b", re.I)
COURSE_HEAD_RE = re.compile(
    r"\b(training|course|bootcamp|certification|certificate)s?\s*$",
    re.I,
)
DEGREE_RE = re.compile(
    r"\b(bachelor|master|b\.?\s*tech|m\.?\s*tech|mba|ph\.?d|diploma|associate)\b",
    re.I,
)
EDU_NOISE_RE = re.compile(
    r"^(issued|expired|associated with|technologies used|comments)\b",
    re.I,
)
SKILL_SUMMARY_RE = re.compile(r"\+\d+\s+skills?\b|\(programming language\)", re.I)
ENGAGEMENT_RE = re.compile(
    r"(?:^|\s)\d[\d,]*\s+(reactions?|comments?|reposts?|likes?)\b",
    re.I,
)
SKILL_CHIP_HINT_RE = re.compile(r"\(programming language\)|\b(mern|dsa)\b", re.I)
COUNTRY_HINTS = {
    "india",
    "united states",
    "usa",
    "uk",
    "united kingdom",
    "canada",
    "australia",
    "germany",
    "singapore",
    "uae",
    "united arab emirates",
}

CARD_TAGS = {
    "profileCardsAboveActivity": "about",
    "profileCardsExperienceOnly": "experience",
    "profileCardsBelowActivityPart1WithoutExp": "education",
    "profileCardsBelowActivityPart7": "skills",
    "profileCardsBelowActivityPart3": "certs",
    "profileCardsBelowActivityPart4": "languages",
}


def tag_from_component_id(component_id: str) -> str | None:
    name = component_id.rsplit(".", 1)[-1]
    return CARD_TAGS.get(name)


def _texts(tagged: list[tuple[str, str]], *tags: str) -> list[str]:
    wanted = set(tags)
    return [text for tag, text in tagged if tag in wanted]


def _looks_like_css_classes(value: str) -> bool:
    tokens = value.split()
    if len(tokens) < 3:
        return False
    hashed = sum(1 for token in tokens if re.fullmatch(r"_?[0-9a-f]{5,10}", token, re.I))
    return hashed / len(tokens) >= 0.7


def _is_noise(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) < 2:
        return True
    if stripped.startswith("$") or RSC_REF_RE.fullmatch(stripped.replace(" ", "")):
        return True
    if stripped.startswith(NOISE_PREFIXES):
        return True
    if stripped.lower() in HTML_TAGS or stripped.lower() in PROTO_WORDS:
        return True
    if _looks_like_css_classes(stripped) or CSS_CLASS_RE.fullmatch(stripped):
        return True
    if re.fullmatch(r"[A-Fa-f0-9]{8,}", stripped):
        return True
    if re.fullmatch(r"[\d.]+", stripped):
        return True
    if stripped.startswith(("experience-", "skills-", "profile-card", "entity-collection")):
        return True
    return False


def _is_chrome(value: str) -> bool:
    lowered = value.lower().strip()
    if lowered in CHROME_PHRASES or lowered in SECTION_HEADERS:
        return True
    if FOLLOWERS_RE.search(lowered):
        return True
    if "linkedin" in lowered:
        return True
    if lowered.startswith(
        (
            "unfollow ",
            "follow ",
            "message ",
            "connect ",
            "view ",
            "visit our",
            "go to your",
            "learn more",
            "verify ",
        )
    ):
        return True
    return False


def _is_post_opener(value: str) -> bool:
    lowered = value.lower().lstrip()
    return any(lowered.startswith(prefix) for prefix in POST_OPENERS)


def _is_year_span(value: str) -> bool:
    return bool(YEAR_SPAN_RE.fullmatch(value.strip()))


def _has_month_date(value: str | None) -> bool:
    return bool(value and re.search(r"[A-Za-z]", value))


def _looks_like_skill_chips(value: str) -> bool:
    seps = len(re.findall(r"[•·⋅]", value))
    if seps >= 2 and not re.search(r"[.!?]", value):
        return True
    if SKILL_CHIP_HINT_RE.search(value) and seps >= 1:
        return True
    return False


def _looks_like_engagement(value: str) -> bool:
    return bool(ENGAGEMENT_RE.search(value.strip()))


def _looks_like_featured_title(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) > 120:
        return False
    if re.search(r"[.?]", stripped):
        return False
    return " - " in stripped


def _is_about_prose(value: str, skill_names: set[str]) -> bool:
    if (
        _is_post_opener(value)
        or _looks_like_skill_chips(value)
        or _looks_like_engagement(value)
        or _looks_like_featured_title(value)
    ):
        return False
    parts = [part.strip() for part in DOT_SPLIT_RE.split(value) if part.strip()]
    if len(parts) >= 2 and skill_names:
        lowered_skills = {name.lower() for name in skill_names}
        hits = sum(1 for part in parts if part.lower() in lowered_skills)
        if hits >= 2:
            return False
    return True


def _acceptable_school(school: str | None, *, has_month_dates: bool) -> bool:
    if not school:
        return False
    if COURSE_HEAD_RE.search(school.strip()):
        return False
    if COURSE_RE.search(school) and not INSTITUTION_RE.search(school):
        return False
    if INSTITUTION_RE.search(school) or "growthx" in school.lower():
        return True
    return has_month_dates


def _looks_like_degree(value: str) -> bool:
    return bool(DEGREE_RE.search(value)) and not COURSE_HEAD_RE.search(value.strip())


def _split_degree_field(value: str) -> tuple[str, str | None]:
    if ", " in value:
        left, right = value.split(", ", 1)
        if any(token in left.lower() for token in ("degree", "bachelor", "master", "tech", "diploma")):
            return left, right
    return value, None


def _plausible_school(value: str, *, has_month_dates: bool, paired_with_degree: bool) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) > 100 or "\n" in stripped:
        return False
    if COURSE_HEAD_RE.search(stripped) or _looks_like_degree(stripped):
        return False
    if EDU_NOISE_RE.search(stripped) or SKILL_SUMMARY_RE.search(stripped):
        return False
    if stripped.startswith(("#", "•")):
        return False
    if _acceptable_school(stripped, has_month_dates=has_month_dates):
        return True
    return paired_with_degree and 3 <= len(stripped) <= 80


def _education_from_buffer(
    buffer: list[str],
    start: str | None,
    end: str | None,
) -> dict[str, Any] | None:
    cleaned = [
        value
        for value in buffer
        if not _is_year_span(value) and not _is_work_location(value) and not DURATION_LINE_RE.match(value)
    ]
    has_month_dates = _has_month_date(start) or _has_month_date(end)
    degree = field = None
    school = None
    pending_degree = any(_looks_like_degree(value) for value in cleaned)
    for value in reversed(cleaned):
        if COURSE_HEAD_RE.search(value.strip()) or EDU_NOISE_RE.search(value.strip()):
            continue
        if _looks_like_degree(value):
            if degree is None:
                degree, field = _split_degree_field(value)
            continue
        if school is None and _plausible_school(
            value, has_month_dates=has_month_dates, paired_with_degree=pending_degree
        ):
            school = value
            break
    if not school:
        return None
    return {
        "school": school,
        "degree": degree,
        "field": field,
        "start_date": start,
        "end_date": end,
        "description": None,
    }


def _leaf_human(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in leaf_texts(text):
        value = raw.replace("\\n", "\n").strip()
        if _is_noise(value) or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _is_date_line(value: str) -> bool:
    return bool(date_ranges(value))


def _is_geo_location(value: str) -> bool:
    stripped = value.strip()
    if not stripped or len(stripped) > 80:
        return False
    if any(char in stripped for char in "!?"):
        return False
    head = DOT_SPLIT_RE.split(stripped)[0].strip()
    parts = [part.strip() for part in head.split(",") if part.strip()]
    if any(len(part) > 40 for part in parts):
        return False
    if len(parts) >= 3 and all(any(char.isalpha() for char in part) for part in parts[:2]):
        return True
    if len(parts) == 2:
        return parts[-1].lower() in COUNTRY_HINTS
    return False


def _is_work_location(value: str) -> bool:
    stripped = value.strip()
    if LOCATION_WORK_RE.fullmatch(stripped):
        return True
    lowered = stripped.lower()
    if DOT_SPLIT_RE.search(stripped) and any(token in lowered for token in ("on-site", "remote", "hybrid")):
        return True
    return _is_geo_location(stripped)


def _split_company_line(value: str) -> tuple[str, str] | None:
    parts = DOT_SPLIT_RE.split(value, maxsplit=1)
    if len(parts) != 2:
        return None
    left, right = parts[0].strip(), parts[1].strip()
    first = right.split()[0].lower().replace(",", "") if right else ""
    if first in EMPLOYMENT_TYPES or right.lower() in EMPLOYMENT_TYPES:
        return left, right
    return None


def _looks_like_role(value: str) -> bool:
    return bool(ROLE_RE.search(value))


def _identity(tagged: list[tuple[str, str]], vanity: str, warnings: list[str]) -> dict[str, str | None]:
    first = last = headline = location = None
    shells = _texts(tagged, "shell")
    scan = shells or [text for _, text in tagged]
    for body in scan:
        for node in iter_dicts(body):
            if node.get("vanityName") == vanity and node.get("firstName"):
                first = str(node.get("firstName") or first)
                last = str(node.get("lastName") or last)
            raw_headline = node.get("headline")
            if (
                isinstance(raw_headline, str)
                and "invitationType" not in node
                and 3 < len(raw_headline) <= 220
                and not _is_noise(raw_headline)
                and not _looks_like_css_classes(raw_headline)
                and not _is_post_opener(raw_headline)
            ):
                headline = headline or raw_headline
            geo = node.get("geoLocationName") or node.get("locationName")
            if isinstance(geo, str) and _is_geo_location(geo):
                location = location or geo
    full = " ".join(part for part in (first, last) if part).strip() or None

    header_leaves: list[str] = []
    for body in scan:
        header_leaves.extend(_leaf_human(body))
    if full:
        for index, value in enumerate(header_leaves):
            if value != full:
                continue
            for follow in header_leaves[index + 1 : index + 12]:
                if _is_chrome(follow) or _is_date_line(follow) or _is_post_opener(follow):
                    continue
                if _is_geo_location(follow):
                    location = location or DOT_SPLIT_RE.split(follow)[0].strip()
                    continue
                if headline is None and 3 <= len(follow) <= 220:
                    headline = follow
                if headline and location:
                    break
            break
    if location is None:
        for value in header_leaves:
            if _is_geo_location(value) and not _is_chrome(value):
                location = DOT_SPLIT_RE.split(value)[0].strip()
                break
        else:
            for body in _texts(tagged, "about"):
                for value in _leaf_human(body):
                    if _is_geo_location(value):
                        continue
                    if _is_post_opener(value) or (len(value) > 80 and "," in value):
                        warnings.append("location_rejected_non_geo")
                        break
    return {
        "first_name": first,
        "last_name": last,
        "full_name": full,
        "headline": headline,
        "location": location,
    }


def _photo_size(url: str) -> int:
    match = re.search(r"shrink_(\d+)_(\d+)", url)
    if not match:
        return 0
    return int(match.group(1))


def _pick_image(urls: list[str], *needles: str) -> str | None:
    matches = [url for url in urls if any(needle in url.lower() for needle in needles)]
    if not matches:
        return None
    matches.sort(
        key=lambda url: (
            url.count("profile-displayphoto-shrink_") <= 1,
            "/0/" in url,
            _photo_size(url),
            not url.endswith("shrink_"),
            len(url),
        ),
        reverse=True,
    )
    return matches[0]


def _about(
    tagged: list[tuple[str, str]],
    warnings: list[str],
    skill_names: set[str] | None = None,
) -> str | None:
    skills = skill_names or set()
    rich_blocks: list[str] = []
    for body in _texts(tagged, "about"):
        for value in _leaf_human(body):
            if "\n" not in value or len(value) < 80:
                continue
            if _is_post_opener(value) or not _is_about_prose(value, skills):
                continue
            if 80 <= len(value) <= 12000:
                rich_blocks.append(value)
    if rich_blocks:
        return max(rich_blocks, key=len)

    candidates: list[str] = []
    saw_opener = False
    saw_non_prose = False
    for body in _texts(tagged, "about"):
        seen_header = False
        for value in _leaf_human(body):
            if value.lower() == "about":
                seen_header = True
                continue
            if not seen_header:
                continue
            if value.lower() in ABOUT_STOP_HEADERS:
                if not candidates:
                    saw_non_prose = True
                break
            if "\n" in value:
                continue
            if _is_chrome(value) or _looks_like_css_classes(value) or _is_geo_location(value):
                continue
            if _is_post_opener(value):
                saw_opener = True
                continue
            if 20 <= len(value) <= 2000 and " " in value:
                if not _is_about_prose(value, skills):
                    saw_non_prose = True
                    continue
                candidates.append(value)
    if candidates:
        return candidates[0]
    if saw_opener:
        warnings.append("about_empty_after_filter")
    elif saw_non_prose:
        warnings.append("about_rejected_not_prose")
    return None


def _split_date_range(span: str) -> tuple[str | None, str | None, bool | None]:
    parts = re.split(r"\s*[-–—·•]\s*", span, maxsplit=1)
    if len(parts) != 2:
        return span, None, None
    start, end = parts[0].strip(), parts[1].strip()
    return start, end, end.lower() == "present"


def _title_company_from_buffer(buffer: list[str]) -> tuple[str | None, str | None]:
    buf = [
        value
        for value in buffer
        if not _is_work_location(value) and not DURATION_LINE_RE.match(value) and not SKILL_SUMMARY_RE.search(value)
    ]
    if not buf:
        return None, None
    company = None
    titles: list[str] = []
    for value in buf:
        split = _split_company_line(value)
        if split:
            company = split[0]
        else:
            titles.append(value)
    if company:
        if not titles:
            return None, company
        role = next((item for item in reversed(titles) if _looks_like_role(item)), titles[-1])
        return role, company
    if len(titles) == 1:
        return titles[0], None
    if len(titles) >= 2:
        roles = [item for item in titles if _looks_like_role(item)]
        other = [item for item in titles if not _looks_like_role(item)]
        if roles and other:
            return roles[-1], other[0]
        return titles[-1], titles[0]
    return None, None


def _items_from_dated_card(text: str, *, kind: str) -> tuple[list[dict[str, Any]], bool]:
    leaves = [value for value in _leaf_human(text) if value.lower() not in SECTION_HEADERS]
    items: list[dict[str, Any]] = []
    buffer: list[str] = []
    leftover_rejected = False
    index = 0
    while index < len(leaves):
        value = leaves[index]
        if _is_date_line(value) or (kind == "education" and _is_year_span(value)):
            if _is_year_span(value):
                start, end, current = _split_date_range(value)
            else:
                span = date_ranges(value)[0]
                start, end, current = _split_date_range(span)
            title, org = _title_company_from_buffer(buffer)
            location = None
            if index + 1 < len(leaves) and _is_work_location(leaves[index + 1]):
                next_leaf = leaves[index + 1]
                if _is_geo_location(DOT_SPLIT_RE.split(next_leaf)[0].strip()):
                    location = DOT_SPLIT_RE.split(next_leaf)[0].strip()
                index += 1
            if kind == "education":
                item = _education_from_buffer(buffer, start, end)
                if item:
                    items.append(item)
            elif title or org:
                items.append(
                    {
                        "title": title,
                        "org": org,
                        "location": location,
                        "start_date": start,
                        "end_date": end,
                        "is_current": current,
                        "description": None,
                    }
                )
            buffer = []
        else:
            buffer.append(value)
        index += 1
    if kind == "education" and buffer:
        item = _education_from_buffer(buffer, None, None)
        if item:
            items.append(item)
        elif any(value for value in buffer if not _is_work_location(value) and not DURATION_LINE_RE.match(value)):
            leftover_rejected = True
    return items, leftover_rejected


SKILL_DENY = {
    "skills",
    "show all",
    "see more",
    "show more",
    "follow",
    "message",
    "connect",
    "more",
    "activity",
    "about",
    "experience",
    "education",
    "licenses & certifications",
    "languages",
}


def _skills(text: str, *, deny_names: set[str]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    seen: set[str] = set()
    leaves = _leaf_human(text)
    index = 0
    while index < len(leaves):
        value = leaves[index]
        lowered = value.lower().strip()
        if lowered in SKILL_DENY or _is_chrome(value) or _is_date_line(value):
            index += 1
            continue
        count = None
        if index + 1 < len(leaves):
            match = ENDORSEMENT_RE.fullmatch(leaves[index + 1].strip())
            if match:
                count = int(match.group(1))
                index += 1
        if AT_JOB_RE.search(value) or value in deny_names:
            index += 1
            continue
        if not (2 <= len(value) <= 60) or "\n" in value:
            index += 1
            continue
        if value in seen:
            index += 1
            continue
        seen.add(value)
        skills.append({"name": value, "endorsement_count": count})
        index += 1
    return skills[:30]


def _languages(text: str) -> list[dict[str, Any]]:
    languages: list[dict[str, Any]] = []
    proficiency_words = {
        "native or bilingual proficiency",
        "full professional proficiency",
        "professional working proficiency",
        "limited working proficiency",
        "elementary proficiency",
    }
    pending_name: str | None = None
    for value in _leaf_human(text):
        lowered = value.lower()
        if lowered in SECTION_HEADERS or _is_chrome(value):
            continue
        if lowered in proficiency_words and pending_name:
            languages.append({"name": pending_name, "proficiency": value})
            pending_name = None
            continue
        if 2 <= len(value) <= 40 and not _is_date_line(value) and not _is_noise(value):
            pending_name = value
    if pending_name and all(item["name"] != pending_name for item in languages):
        if pending_name.lower() not in SECTION_HEADERS:
            languages.append({"name": pending_name, "proficiency": None})
    return languages[:20]


def _location_from_experience(experience: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for item in experience:
        loc = item.get("location")
        if not loc or LOCATION_WORK_RE.fullmatch(str(loc).strip()):
            continue
        if _is_geo_location(str(loc)):
            counts[str(loc)] = counts.get(str(loc), 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda loc: (counts[loc], len(loc)))


def map_profile(
    *,
    vanity: str,
    input_value: str,
    tagged: list[tuple[str, str]],
    hops: list[Hop] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    combined = "\n".join(text for _, text in tagged)
    identity = _identity(tagged, vanity, warnings)
    urls = image_urls(combined)

    experience: list[dict[str, Any]] = []
    education: list[dict[str, Any]] = []
    skills: list[dict[str, Any]] = []
    certifications: list[dict[str, Any]] = []
    languages: list[dict[str, Any]] = []

    leftover_education = False
    for body in _texts(tagged, "experience"):
        items, _ = _items_from_dated_card(body, kind="experience")
        for item in items:
            experience.append(
                {
                    "title": item["title"],
                    "company": item["org"],
                    "company_url": None,
                    "location": item["location"],
                    "start_date": item["start_date"],
                    "end_date": item["end_date"],
                    "is_current": item["is_current"],
                    "description": item["description"],
                }
            )
    if not identity["location"]:
        from_jobs = _location_from_experience(experience)
        if from_jobs:
            identity["location"] = from_jobs
            warnings[:] = [item for item in warnings if item != "location_rejected_non_geo"]

    for body in _texts(tagged, "education"):
        items, rejected = _items_from_dated_card(body, kind="education")
        education.extend(items)
        leftover_education = leftover_education or rejected
    if not education and leftover_education:
        warnings.append("education_empty_after_filter")

    deny_names = {item["title"] for item in experience if item.get("title")}
    deny_names.update(
        f"{item['title']} at {item['company']}" for item in experience if item.get("title") and item.get("company")
    )
    for body in _texts(tagged, "skills"):
        skills.extend(_skills(body, deny_names=deny_names))
    about = _about(tagged, warnings, skill_names={item["name"] for item in skills if item.get("name")})
    for body in _texts(tagged, "languages"):
        languages.extend(_languages(body))
    for body in _texts(tagged, "certs"):
        items, _ = _items_from_dated_card(body, kind="experience")
        for item in items:
            if not item["title"] and not item["org"]:
                continue
            certifications.append(
                {
                    "name": item["title"],
                    "issuer": item["org"],
                    "issued_on": item["start_date"],
                    "expires_on": item["end_date"],
                    "credential_id": None,
                    "url": None,
                }
            )

    profile_image = _pick_image(urls, "profile-displayphoto", "/profile-framedphoto/")
    background = _pick_image(urls, "profile-displaybackground", "profile-cover")
    unique_warnings = list(dict.fromkeys(warnings))

    sections = {
        "profile": bool(identity["full_name"] or identity["headline"]),
        "images": bool(profile_image or background),
        "experience": bool(experience),
        "education": bool(education),
        "skills": bool(skills),
        "certifications": bool(certifications),
        "languages": bool(languages),
        "about": bool(about),
    }

    return {
        "schema_version": "1.0",
        "input": input_value,
        "vanity_name": vanity,
        "linkedin_url": f"https://www.linkedin.com/in/{vanity}/",
        "fetched_at": datetime.now(UTC),
        "profile": {
            "first_name": identity["first_name"],
            "last_name": identity["last_name"],
            "full_name": identity["full_name"],
            "headline": identity["headline"],
            "location": identity["location"],
            "about": about,
            "connection_degree": None,
        },
        "images": {
            "profile_url": profile_image,
            "background_url": background,
        },
        "experience": experience,
        "education": education,
        "skills": skills,
        "certifications": certifications,
        "languages": languages,
        "sections_available": sections,
        "warnings": unique_warnings,
        "meta": {"hops": [hop.as_dict() for hop in hops or []]},
    }


def vanity_from_input(input_value: str) -> str | None:
    parsed = urlparse(input_value if "://" in input_value else f"https://{input_value}")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] == "in":
        return parts[1]
    return None
