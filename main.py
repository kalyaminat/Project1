import logging as logger
import requests

from datetime import datetime
from json import dump as jdump
from sys import exit as exit_runtime
from tqdm import tqdm

logger.basicConfig(level=logger.INFO)

VK_ACCESS_TOKEN = ...
VK_ID = '590836872'
VK_URL = 'https://api.vk.com/method/photos.get'

YA_POLYGON_TOKEN = ...
YA_URL = 'https://cloud-api.yandex.net/v1/disk/resources/upload'
YA_FOLDER_NAME = 'test_folder'

RESULT_JSON_FILENAME = 'result.json'


class PhotosTransport:
    def __init__(self, client_id: int, access_token: str, ya_token: str = None) -> None:
        self.client_id = client_id
        self.access_token = access_token
        self.ya_token = ya_token
        self.vk_list = []

    def name_photo(self, photo_list: list) -> list:
        final_list = []

        # Выполняем поиск максимального количества лайков
        likes_list = []
        for el in photo_list:
            likes_list.append(el.get('likes_count'))
        r = max(likes_list)

        # Итерируем в диапазоне количества лайков
        for i in range(r + 1):
            sup_list = []

            # Каждый раз итерируем по списку фото и находим фото с количеством лайков, равным номеру итерации
            for el in photo_list:
                if i == int(el.get('likes_count')):
                    sup_list.append(el)
            # Если количество фотографий с одинаковым количеством лайков в итерации больше одной- меняем их названия
            if len(sup_list) > 1:
                for s_el in sup_list:
                    ts = s_el.get('date')
                    date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H_%M_%S")
                    s_el["name"] = f"{s_el.get('likes_count')}  {date}.jpg"
            else:
                sup_list[0]["name"] = f"{sup_list[0].get('likes_count')}.jpg"
            final_list += sup_list

        return sorted(final_list, key=self.photo_sorter, reverse=True)

    def photo_sorter(self, photo_dict: dict)-> int:
        return int(photo_dict.get('likes_count'))

    def get_vk_photos(self) -> dict:
        """Возвращает полный список ФОТО от VK API"""

        params = dict(access_token={self.access_token},
                      user_id={self.client_id},
                      album_id='wall',
                      v='5.131', extended=1)
        response = requests.get(url=VK_URL, params=params)
        response_dict = response.json()
        if response_dict.get("error"):
            logger.warning(f"Во время обращения к VK API возникла ошибка: "
                           f" {response_dict.get('error').get('error_msg')}")
            # raise RuntimeError
            exit_runtime(400)
        else:
            return response_dict


    def get_photo_list(self, response_dict: dict) -> None:
        """Переделывает полный список фото от ВК в нужный нам с сортировкой"""

        raw_list = []
        for item in response_dict.get('response').get('items'):
            raw_list.append(item)
        prepared_list = []
        for i in raw_list:
            p_el = dict(likes_count=i.get('likes').get('count'),
                                     date=i.get('date'),
                                     url=i.get('sizes')[-1].get('url'),
                                     size=i.get('sizes')[-1].get("type"),
                                     name='')
            prepared_list.append(p_el)

        self.vk_list = self.name_photo(prepared_list)

    def ya_create_folder(self) -> bool:
        """Создает папку на яндекс диске и возвращает Екгу если все хорошо иначе возвращает описание ошибки"""

        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': self.ya_token,
        }

        params = {
            'path': YA_FOLDER_NAME
        }
        response = requests.put('https://cloud-api.yandex.net/v1/disk/resources', params=params, headers=headers)
        cond_ok = response.status_code == 201
        cond_folder_exist = \
            response.status_code == 409 and response.json().get("error") == 'DiskPathPointsToExistentDirectoryError'
        if cond_ok or cond_folder_exist:
            logger.info(msg=f"Папка {YA_FOLDER_NAME} создана или существует")
            return True
        else:
            logger.warning(msg=f"Папка {YA_FOLDER_NAME} не создана.\nОшибка: {response.json().get('error')}")
            return False

    def file_load_params(self, ya_token: str, filename: str, url_name: str) -> tuple:
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'OAuth {ya_token}',
        }

        params = {
            'path': f'{YA_FOLDER_NAME}/{filename}',
            'url': url_name
        }
        return headers, params

    def ya_loader(self, photos_list: list, photos_quantity: int = 5) -> list:
        """Загружает на яндекс диск все фото через их URL"""

        loaded_list = []
        for el in tqdm(photos_list):
            headers, params = self.file_load_params(ya_token=YA_POLYGON_TOKEN,
                                                               filename=el.get("name"),
                                                               url_name=el.get("url"))
            response = requests.post(url=YA_URL, params=params, headers=headers)
            response_dict = response.json()
            if response.status_code == 202:
                loaded_list.append(dict(filename=el.get('name'), size=el.get('size')))
            else:
                logger.warning(msg=f"Файл {el.get('name')} не загружен.\nОтвет сервера: {response_dict}")

        return loaded_list

    def main(self):
        """Производит все необходимые процедуры"""

        p_list = self.get_vk_photos()
        self.get_photo_list(response_dict=p_list)

        if self.ya_create_folder():
            data_list = self.ya_loader(photos_list=self.vk_list)
            # print(*data_list, sep='\n')
            with open(file=RESULT_JSON_FILENAME, mode='w') as f:
                jdump(data_list, f)


if __name__ == '__main__':
    pt = PhotosTransport(client_id=VK_ID, access_token=VK_ACCESS_TOKEN, ya_token=YA_POLYGON_TOKEN)
    pt.main()

