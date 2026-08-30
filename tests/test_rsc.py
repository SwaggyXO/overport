from app.linkedin.rsc import image_urls


def test_image_urls_stitch_split_displayphoto() -> None:
    text = (
        '1:{"a":"https://media.licdn.com/dms/image/v2/C5603AQFxxx/profile-displayphoto-shrink_"}\n'
        '2:{"b":"800_800/profile-displayphoto-shrink_800_800/0/1648198196352"}\n'
    )
    urls = image_urls(text)
    assert any(url.endswith("profile-displayphoto-shrink_800_800/0/1648198196352") for url in urls)
