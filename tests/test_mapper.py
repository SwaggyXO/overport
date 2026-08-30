import json
import re

from app.linkedin.mapper import map_profile
from app.linkedin.rsc import leaf_texts


def _rsc(*chunks: dict | list) -> str:
    lines = []
    for index, chunk in enumerate(chunks, start=1):
        lines.append(f"{index}:{json.dumps(chunk)}")
    return "\n".join(lines)


def test_leaf_texts_reads_children_and_text_props() -> None:
    text = _rsc(
        {"className": "eb4cf114 ff70163b _4d19b25e", "children": ["Co-Founder"]},
        {"textProps": {"fontSize": "small", "children": ["Nov 2023 - Present"]}},
        {"children": ["$L1"]},
    )
    leaves = leaf_texts(text)
    assert "Co-Founder" in leaves
    assert "Nov 2023 - Present" in leaves
    assert "$L1" in leaves


def test_leaf_texts_joins_nested_react_about_tree() -> None:
    paragraph = (
        "I work across frontend, backend, APIs, databases, architecture, and deployment "
        "with a focus on building systems that are scalable, maintainable, and aligned "
        "with real business requirements."
    )
    text = _rsc(
        {
            "textProps": {
                "lineClamp": 3,
                "hasShowMore": False,
                "children": [
                    [
                        [
                            "$",
                            "$42",
                            "0",
                            {"children": [None, "I'm a Software Engineer and Career Mentor."]},
                        ],
                        ["$", "$42", "1", {"children": [["$", "br", None, {}], paragraph]}],
                    ]
                ],
            }
        }
    )
    leaves = leaf_texts(text)
    joined = "\n".join(leaves)
    assert "I'm a Software Engineer and Career Mentor." in joined
    assert "I work across frontend" in joined
    assert "$42" not in joined
    assert "br" not in joined.split()


def test_mapper_uses_visible_copy_not_rsc_chrome() -> None:
    vanity = "alex-rivera"
    identity = _rsc(
        {
            "vanityName": vanity,
            "firstName": "Alex",
            "lastName": "Rivera",
        },
        {"children": ["Alex Rivera"]},
        {"children": ["Co-Founder, Northshore"]},
        {"children": ["Austin, Texas, United States"]},
        {"className": "eb4cf114 ff70163b _4d19b25e _91bf0d9c _770d9e50"},
    )
    about = _rsc(
        {
            "data-sdui-component": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsAboveActivity",
            "textProps": {
                "fontSize": "xlarge",
                "children": ["About"],
            },
        },
        {
            "textProps": {
                "fontSize": "small",
                "children": ["Building Northshore - India's first bio-fermented protein brand."],
            },
        },
    )
    experience = _rsc(
        {"data-sdui-component": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsExperienceOnly"},
        {"textProps": {"children": ["Experience"]}},
        {"children": ["div"]},
        {"children": ["$L1"]},
        {"children": ["Co-Founder"]},
        {"children": ["Northshore · Full-time"]},
        {"textProps": {"children": ["Nov 2023 - Present · 2 yrs 10 mos"]}},
        {"children": ["Business Head - Foods"]},
        {"children": ["FUTURE CONSUMER LIMITED · Full-time"]},
        {"textProps": {"children": ["Apr 2014 - Dec 2022 · 8 yrs 9 mos"]}},
    )
    education = _rsc(
        {
            "data-sdui-component": (
                "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart1WithoutExp"
            )
        },
        {"textProps": {"children": ["Education"]}},
        {"children": ["King's College London"]},
        {"children": ["Bachelor's degree, Entrepreneurship/Entrepreneurial Studies"]},
        {"textProps": {"children": ["Jul 2010 · Jul 2013"]}},
        {"children": ["GrowthX"]},
        {"textProps": {"children": ["Apr 2022 - May 2022"]}},
    )
    skills = _rsc(
        {"data-sdui-component": "com.linkedin.sdui.generated.profile.dsl.impl.profileCardsBelowActivityPart7"},
        {"textProps": {"children": ["Microsoft Word"]}},
        {"children": ["8 endorsements"]},
        {"children": ["id"]},
        {"children": ["booleanValue"]},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[
            ("shell", identity),
            ("about", about),
            ("experience", experience),
            ("education", education),
            ("skills", skills),
        ],
    )
    assert mapped["linkedin_url"] == f"https://www.linkedin.com/in/{vanity}/"
    assert mapped["profile"]["full_name"] == "Alex Rivera"
    assert mapped["profile"]["headline"] == "Co-Founder, Northshore"
    assert mapped["profile"]["location"] == "Austin, Texas, United States"
    assert "Northshore" in (mapped["profile"]["about"] or "")
    assert mapped["profile"]["about"] is not None
    assert "eb4cf114" not in (mapped["profile"]["about"] or "")
    assert mapped["experience"][0]["title"] == "Co-Founder"
    assert mapped["experience"][0]["company"] == "Northshore"
    assert mapped["experience"][0]["is_current"] is True
    assert mapped["experience"][1]["title"] == "Business Head - Foods"
    assert mapped["experience"][1]["company"] == "FUTURE CONSUMER LIMITED"
    assert mapped["education"][0]["school"] == "King's College London"
    assert mapped["education"][0]["degree"] == "Bachelor's degree"
    assert any(item["school"] == "GrowthX" for item in mapped["education"])
    assert mapped["skills"][0]["name"] == "Microsoft Word"
    assert mapped["skills"][0]["endorsement_count"] == 8
    assert all(skill["name"] not in {"div", "$L1", "id", "booleanValue"} for skill in mapped["skills"])


def test_mapper_rejects_featured_post_as_location_and_about() -> None:
    vanity = "jordan-hale"
    post = (
        "Excited to share my submission for the Frontend Challenge - December Edition! "
        "Built an interactive educational app showcasing the Winter Solstice using "
        "React, TypeScript, and Tailwind CSS. Proud to bring science and culture to life!"
    )
    shell = _rsc(
        {"vanityName": vanity, "firstName": "Jordan", "lastName": "Hale"},
        {"children": ["Jordan Hale"]},
        {"children": ["Software Engineer @ Helix Systems | Full-Stack & SaaS Builder | AI • Python • Java"]},
        {"children": [post]},
    )
    about = _rsc(
        {"textProps": {"children": ["About"]}},
        {"textProps": {"children": [post]}},
    )
    experience = _rsc(
        {"textProps": {"children": ["Experience"]}},
        {"children": ["Chief Technology Officer"]},
        {"children": ["Brightfield"]},
        {"textProps": {"children": ["Aug 2024 - Apr 2025 · 9 mos"]}},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
        {"children": ["Software Engineer"]},
        {"children": ["Helix Systems"]},
        {"textProps": {"children": ["Oct 2025 - Present · 11 mos"]}},
    )
    education = _rsc(
        {"textProps": {"children": ["Education"]}},
        {"children": ["State University"]},
    )
    skills = _rsc(
        {"textProps": {"children": ["Artificial Intelligence (AI)"]}},
        {"children": ["Technical Trainer at Freelance"]},
        {"children": ["C (Programming Language)"]},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[
            ("shell", shell),
            ("about", about),
            ("experience", experience),
            ("education", education),
            ("skills", skills),
        ],
    )
    assert mapped["profile"]["full_name"] == "Jordan Hale"
    assert mapped["profile"]["location"] != post
    assert mapped["profile"]["location"] is None or "React" not in (mapped["profile"]["location"] or "")
    assert mapped["profile"]["about"] is None
    assert mapped["sections_available"]["about"] is False
    assert "about_empty_after_filter" in mapped["warnings"]
    titles = {item["title"] for item in mapped["experience"]}
    companies = {item["company"] for item in mapped["experience"]}
    assert "Chief Technology Officer" in titles
    assert "Brightfield" in companies
    assert mapped["experience"][0]["title"] != "Brightfield"
    assert any(item["school"] == "State University" for item in mapped["education"])
    skill_names = [item["name"] for item in mapped["skills"]]
    assert "Technical Trainer at Freelance" not in skill_names
    assert "Artificial Intelligence (AI)" in skill_names
    assert "•" in (mapped["profile"]["headline"] or "")


def test_mapper_rejects_chip_about_and_course_education() -> None:
    vanity = "jordan-hale"
    chip_about = "Python (Programming Language) • MERN Stack • Artificial Intelligence (AI) • Java • dsa"
    shell = _rsc(
        {"vanityName": vanity, "firstName": "Jordan", "lastName": "Hale"},
        {"children": ["Jordan Hale"]},
        {"children": ["Software Engineer @ Helix Systems | Full-Stack & SaaS Builder | AI • Python • Java"]},
    )
    about = _rsc(
        {"textProps": {"children": ["About"]}},
        {"textProps": {"children": [chip_about]}},
    )
    experience = _rsc(
        {"textProps": {"children": ["Experience"]}},
        {"children": ["Chief Technology Officer"]},
        {"children": ["Brightfield"]},
        {"textProps": {"children": ["Aug 2024 - Apr 2025 · 9 mos"]}},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
        {"children": ["On-site"]},
        {"children": ["Software Engineer"]},
        {"children": ["Helix Systems"]},
        {"textProps": {"children": ["Oct 2025 - Present · 11 mos"]}},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
    )
    education = _rsc(
        {"textProps": {"children": ["Education"]}},
        {"children": ["State University"]},
        {"children": ["XO Platform Developers Advanced Training"]},
        {"children": ["2015 – 2017"]},
    )
    skills = _rsc(
        {"textProps": {"children": ["Python (Programming Language)"]}},
        {"children": ["MERN Stack"]},
        {"children": ["Artificial Intelligence (AI)"]},
        {"children": ["Java"]},
        {"children": ["dsa"]},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[
            ("shell", shell),
            ("about", about),
            ("experience", experience),
            ("education", education),
            ("skills", skills),
        ],
    )
    assert mapped["profile"]["about"] is None
    assert mapped["sections_available"]["about"] is False
    assert "about_rejected_not_prose" in mapped["warnings"]
    assert mapped["profile"]["location"] == "Austin, Texas, United States"
    assert "location_rejected_non_geo" not in mapped["warnings"]
    schools = [item["school"] for item in mapped["education"]]
    degrees = [item["degree"] for item in mapped["education"]]
    assert "State University" in schools
    assert not any(school and "XO Platform" in school for school in schools)
    assert not any(
        degree and re.fullmatch(r"(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}", degree) for degree in degrees if degree
    )


def test_mapper_rejects_engagement_about_and_pre_university_course() -> None:
    vanity = "jordan-hale"
    engagement = "26 reactions · 2 comments"
    shell = _rsc(
        {"vanityName": vanity, "firstName": "Jordan", "lastName": "Hale"},
        {"children": ["Jordan Hale"]},
        {"children": ["Software Engineer @ Helix Systems | Full-Stack & SaaS Builder | AI • Python • Java"]},
    )
    about = _rsc(
        {"textProps": {"children": ["About"]}},
        {"textProps": {"children": [engagement]}},
    )
    experience = _rsc(
        {"textProps": {"children": ["Experience"]}},
        {"children": ["Technical Trainer"]},
        {"children": ["Freelance"]},
        {"textProps": {"children": ["Jan 2024 - Present · 2 yrs 8 mos"]}},
        {"children": ["On-site"]},
        {"children": ["Chief Technology Officer"]},
        {"children": ["Brightfield"]},
        {"textProps": {"children": ["Aug 2024 - Apr 2025 · 9 mos"]}},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
        {"children": ["Software Engineer"]},
        {"children": ["Helix Systems"]},
        {"textProps": {"children": ["Oct 2025 - Present · 11 mos"]}},
    )
    education = _rsc(
        {"textProps": {"children": ["Education"]}},
        {"children": ["State University"]},
        {"children": ["Pre-University Course"]},
        {"children": ["XO Platform Developers Advanced Training"]},
        {"children": ["2015 – 2017"]},
    )
    skills = _rsc(
        {"textProps": {"children": ["Artificial Intelligence (AI)"]}},
        {"children": ["C (Programming Language)"]},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[
            ("shell", shell),
            ("about", about),
            ("experience", experience),
            ("education", education),
            ("skills", skills),
        ],
    )
    assert mapped["profile"]["about"] is None
    assert mapped["sections_available"]["about"] is False
    assert "about_rejected_not_prose" in mapped["warnings"]
    assert mapped["profile"]["location"] == "Austin, Texas, United States"
    schools = [item["school"] for item in mapped["education"]]
    assert "State University" in schools
    assert "Pre-University Course" not in schools
    trainer = next(item for item in mapped["experience"] if item["title"] == "Technical Trainer")
    assert trainer["company"] == "Freelance"
    assert trainer["is_current"] is True
    assert trainer["location"] != "On-site"
    assert trainer["location"] is None
    cto = next(item for item in mapped["experience"] if item["title"] == "Chief Technology Officer")
    assert cto["location"] == "Austin, Texas, United States"


def test_mapper_rejects_featured_winter_solstice_title_as_about() -> None:
    vanity = "jordan-hale"
    featured_title = "Winter Solstice Celebrations - Interactive Educational Experience"
    shell = _rsc(
        {"vanityName": vanity, "firstName": "Jordan", "lastName": "Hale"},
        {"children": ["Jordan Hale"]},
        {"children": ["Software Engineer @ Helix Systems | Full-Stack & SaaS Builder | AI • Python • Java"]},
    )
    about = _rsc(
        {"textProps": {"children": ["About"]}},
        {"textProps": {"children": ["26 reactions · 2 comments"]}},
        {"textProps": {"children": ["Featured"]}},
        {"textProps": {"children": [featured_title]}},
    )
    experience = _rsc(
        {"textProps": {"children": ["Experience"]}},
        {"children": ["Chief Technology Officer"]},
        {"children": ["Brightfield"]},
        {"textProps": {"children": ["Aug 2024 - Apr 2025 · 9 mos"]}},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
    )
    education = _rsc(
        {"textProps": {"children": ["Education"]}},
        {"children": ["Pre-University Course"]},
        {"children": ["XO Platform Developers Advanced Training"]},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[
            ("shell", shell),
            ("about", about),
            ("experience", experience),
            ("education", education),
        ],
    )
    assert mapped["profile"]["about"] is None
    assert mapped["sections_available"]["about"] is False
    assert "about_rejected_not_prose" in mapped["warnings"]
    assert featured_title not in (mapped["profile"]["about"] or "")
    assert mapped["education"] == []
    assert mapped["sections_available"]["education"] is False
    assert "education_empty_after_filter" in mapped["warnings"]
    assert mapped["profile"]["location"] == "Austin, Texas, United States"


def test_mapper_extracts_nested_react_about_bio() -> None:
    vanity = "jordan-hale"
    opener = (
        "I'm a Software Engineer, Full-Stack and SaaS Builder, and Career Mentor focused on production-ready software."
    )
    paragraph = (
        "I work across frontend, backend, APIs, databases, architecture, and deployment "
        "with a focus on building systems that are scalable, maintainable, and aligned "
        "with real business requirements."
    )
    featured_title = "Winter Solstice Celebrations - Interactive Educational Experience"
    shell = _rsc(
        {"vanityName": vanity, "firstName": "Jordan", "lastName": "Hale"},
        {"children": ["Jordan Hale"]},
        {"children": ["Software Engineer @ Helix Systems"]},
        {"children": ["Austin, Texas, United States"]},
    )
    about = _rsc(
        {"textProps": {"children": ["About"]}},
        {
            "textProps": {
                "lineClamp": 3,
                "hasShowMore": False,
                "children": [
                    [
                        ["$", "$42", "0", {"children": [None, opener]}],
                        ["$", "$42", "1", {"children": [["$", "br", None, {}], paragraph]}],
                    ]
                ],
            }
        },
        {"textProps": {"children": ["Featured"]}},
        {"textProps": {"children": [featured_title]}},
    )
    experience = _rsc(
        {"textProps": {"children": ["Experience"]}},
        {"children": ["Software Engineer"]},
        {"children": ["Helix Systems"]},
        {"textProps": {"children": ["Oct 2025 - Present · 11 mos"]}},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[("shell", shell), ("about", about), ("experience", experience)],
    )
    about_text = mapped["profile"]["about"] or ""
    assert "I work across frontend" in about_text
    assert "Career Mentor" in about_text
    assert featured_title not in about_text
    assert mapped["sections_available"]["about"] is True


def test_mapper_extracts_year_span_education() -> None:
    vanity = "jordan-hale"
    shell = _rsc(
        {"vanityName": vanity, "firstName": "Jordan", "lastName": "Hale"},
        {"children": ["Jordan Hale"]},
        {"children": ["Austin, Texas, United States"]},
    )
    experience = _rsc(
        {"textProps": {"children": ["Experience"]}},
        {"children": ["Software Engineer"]},
        {"children": ["Helix Systems"]},
        {"textProps": {"children": ["Oct 2025 - Present · 11 mos"]}},
        {"children": ["C (Programming Language), Java and +7 skills"]},
        {"textProps": {"children": ["Austin, Texas, United States"]}},
    )
    education = _rsc(
        {"textProps": {"children": ["Education"]}},
        {"children": ["XO Platform Developers Advanced Training"]},
        {"children": ["Kore.ai"]},
        {"children": ["Issued Dec 2023 · Expired Dec 2025"]},
        {"children": ["Hillcrest Institute"]},
        {"children": ["Bachelor of Technology, Electrical, Electronics and Communications Engineering"]},
        {"children": ["2017 – 2021"]},
        {"children": ["Pre-University Course"]},
        {"children": ["2015 – 2017"]},
        {"children": ["Technologies used - HTML, CSS, React"]},
    )

    mapped = map_profile(
        vanity=vanity,
        input_value=vanity,
        tagged=[("shell", shell), ("experience", experience), ("education", education)],
    )
    schools = [item["school"] for item in mapped["education"]]
    assert "Hillcrest Institute" in schools
    school = next(item for item in mapped["education"] if item["school"] == "Hillcrest Institute")
    assert school["degree"] == "Bachelor of Technology"
    assert school["field"] and "Electrical" in school["field"]
    assert school["start_date"] == "2017"
    assert school["end_date"] == "2021"
    assert not any(school and "Pre-University" in school for school in schools)
    assert not any(school and "XO Platform" in school for school in schools)
    assert mapped["sections_available"]["education"] is True
    companies = [item["company"] for item in mapped["experience"]]
    assert "Helix Systems" in companies
    assert not any(company and "+7 skills" in company for company in companies if company)
