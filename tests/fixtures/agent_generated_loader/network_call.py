from urllib.request import urlopen


def build():
    return urlopen("https://example.invalid")
