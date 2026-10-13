from app import normalize, parse

assert normalize("https://letterboxd.com/dave/list/top-250/page/3/") == "/dave/list/top-250/"
assert normalize("letterboxd.com/dave/watchlist") == "/dave/watchlist/"
assert normalize("https://www.letterboxd.com/dave/films/") == "/dave/films/"
assert normalize("https://evil.com/dave/list/x/") is None
assert normalize("https://letterboxd.com/film/alien/") is None

page = ('<div data-item-name="Alien (1979)" data-item-slug="alien" >'
        '<div data-item-name="Tom &amp; Jerry" data-item-slug="tom-and-jerry" >')
assert parse(page) == [("alien", "Alien", "1979"), ("tom-and-jerry", "Tom & Jerry", "")]
print("ok")
