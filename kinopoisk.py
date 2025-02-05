from requests import get
from PIL import Image

from config import KINOPOISK_API_TOKEN as api

__all__ = ["get_film_info", "get_main_genre", "genres_hierarchy", "common_genres"]

genres_hierarchy = [
    "мультфильм",
    "мюзикл",
    "ужасы",
    "фантастика",
    "фэнтези",
    "военный",
    "история",
    "приключения",
    "боевик",
    "триллер",
    "детектив",
    "комедия",
    "мелодрама",
    "драма",
]

common_genres = [
    "драма",
    "мелодрама",
    "боевик",
    "триллер",
    "детектив",
    "фантастика",
    "фэнтези",
    "комедия",
    "ужасы",
    "история",
    "военный",
    "приключения",
    "мультфильм",
    "мюзикл",
]


def get_film_info(film_id: int):
    result = {}
    payload = {'filmId': film_id}
    headers = {'X-API-KEY': api, 'Content-Type': 'application/json'}
    try:
        r = get('https://kinopoiskapiunofficial.tech/api/v1/staff', headers=headers, params=payload)
        if r.status_code == 200:
            resp_json = r.json()
    except Exception as e:
        print(e)
        return

    actors = []
    director = []
    num = 0
    for i in resp_json:
        if i['professionText'] == 'Актеры' and num < 10:
            num += 1
            if i['nameRu']:
                actors.append(i['nameRu'])
            else:
                actors.append(i['nameEn'])
        if i['professionText'] == 'Режиссеры':
            if i['nameRu']:
                director.append(i['nameRu'])
            else:
                director.append(i['nameEn'])
    result['actors'] = actors
    result['director'] = director

    headers = {'X-API-KEY': api, 'Content-Type': 'application/json'}
    try:
        r = get(f'https://kinopoiskapiunofficial.tech/api/v2.2/films/{film_id}', headers=headers)
        if r.status_code == 200:
            resp_json = r.json()
    except Exception as e:
        print(e)
        return

    if resp_json['nameRu']:
        result['title'] = resp_json['nameRu']
    else:
        result['title'] = resp_json['nameOriginal']

    result['year'] = str(resp_json['year'])

    result['country'] = [x.get('country') for x in resp_json['countries']]

    if resp_json['ratingKinopoisk']:
        result['rating'] = str(resp_json['ratingKinopoisk'])
        result['is_rating_kp'] = True
    elif resp_json['ratingImdb']:
        result['rating'] = str(resp_json['ratingImdb'])
        result['is_rating_kp'] = False
    else:
        result['rating'] = ""
        result['is_rating_kp'] = True

    if resp_json['description']:
        result['description'] = resp_json['description'].replace("\n\n", " ")
    else:
        result['description'] = ""

    if resp_json['genres']:
        result['genres'] = [x.get('genre') for x in resp_json['genres']]

    result['main_genre'] = get_main_genre(result['genres'], genres_hierarchy)

    cover = get(resp_json['posterUrl'], stream=True)
    if cover.status_code == 200:
        cover.raw.decode_content = True
        result['cover'] = Image.open(cover.raw)
    else:
        result['cover'] = ""

    return result


def get_main_genre(genres: list, genres_hierarchy: list) -> str:
    """Опреде """
    if not genres:
        raise ValueError("Список жанров не может быть пустым.")

    # Преобразуем genres в set для быстрого поиска
    genres_set = set(genres)

    # Ищем первый жанр из иерархии, который есть в genres
    for genre in genres_hierarchy:
        if genre in genres_set:
            return genre

    # Если ничего не найдено, возвращаем первый жанр из списка genres
    return genres[0]


if __name__ == '__main__':
    print(get_film_info(5067984))
