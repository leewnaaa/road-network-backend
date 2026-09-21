import math

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return round(R * c, 2)

COST_PER_KM = 150

cities_db = [
    {
        "id": 1,
        "name": "Москва",
        "lat": 55.7558, "lon": 37.6173,
        "route": "Кутузовский проспект",
        "parent": None,
        "description": "Столица и корневой узел всей дорожной сети — сюда сходятся ключевые федеральные трассы.",
        "details": "Отсюда стартуют трассы М-4, М-11 и М-12. Средняя нагрузка на сеть — более 300 тыс. автомобилей в сутки.",
        "likes": ["user_101", "user_102", "user_103"],  # Массив ID пользователей
        "image_url": "http://localhost:9000/media/moscow.jpg",
        "video_url": "http://localhost:9000/media/moscow.mp4"
    },
    {
        "id": 2,
        "name": "Владимир",
        "lat": 56.1290, "lon": 40.3564,
        "route": "М-7 «Волга»",
        "parent": "Москва",
        "description": "Историческое ядро Золотого кольца и промежуточный узел на трассе М-7 между Москвой и Нижним.",
        "details": "Через город проходит около 40 тыс. транзитных машин в сутки, участок требует расширения до 4 полос.",
        "likes": ["user_201"],  # 1 лайк
        "image_url": "http://localhost:9000/media/vladimir.webp",
        "video_url": "http://localhost:9000/media/vladimir.MP4"
    },
    {
        "id": 3,
        "name": "Нижний Новгород",
        "lat": 56.2965, "lon": 43.9361,
        "route": "М-12 «Восток»",
        "parent": "Владимир",
        "description": "Крупный транспортный узел Приволжья, точка ветвления сети в сторону Казани по трассе М-12.",
        "details": "Мостовой переход через Волгу — одна из самых загруженных точек региона, свыше 90 тыс. проездов в сутки.",
        "likes": ["user_301", "user_302", "user_303", "user_304", "user_305"],  # 5 лайков
        "image_url": "http://localhost:9000/media/nn.jpg",
        "video_url": "http://localhost:9000/media/nn.MP4"
    }
]

def get_construction_cost(city):
    if not city["parent"]:
        return 0
    parent_city = next((c for c in cities_db if c["name"] == city["parent"]), None)
    if parent_city:
        dist = calculate_distance(city["lat"], city["lon"], parent_city["lat"], parent_city["lon"])
        return round(dist * COST_PER_KM)
    return 0
