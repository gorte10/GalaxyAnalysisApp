import sys
import traceback
import io


def handle_exception(exc_type, exc_value, exc_traceback):
    """Обработчик необработанных исключений"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    print("Произошла критическая ошибка:")
    traceback.print_exception(exc_type, exc_value, exc_traceback)

    # Запись в файл лога
    with open("error_log.txt", "w") as f:
        traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)

    input("Нажмите Enter для выхода...")


sys.excepthook = handle_exception

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D
import seaborn as sns
from scipy import stats
import warnings
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib
from matplotlib.patches import Rectangle
import re
import os
from matplotlib.colors import LogNorm, Normalize
import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageTk
import threading
import time
import urllib.parse

matplotlib.use('TkAgg')

warnings.filterwarnings('ignore')

# Настройка стиля для научных графиков
plt.style.use('default')
sns.set_palette("husl")
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 10
plt.rcParams['axes.titlesize'] = 12

class GalaxyImageDownloader:
    """Класс для загрузки изображений галактик с сайта HyperLeda"""

    @staticmethod
    def download_galaxy_image(pgc_number, image_folder="galaxy_images"):
        """Загружает изображение галактики через Aladin по PGC номеру"""
        try:
            # 1. Создаем папку и проверяем кэш (как в вашем коде)
            if not os.path.exists(image_folder):
                os.makedirs(image_folder)
            filename = os.path.join(image_folder, f"PGC{pgc_number}.jpg")
            if os.path.exists(filename):
                return filename

            # 2. Загружаем страницу HyperLeda для получения координат
            base_url = "http://atlas.obs-hp.fr/hyperleda/ledacat.cgi"
            url = f"{base_url}?o=PGC{pgc_number}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # 3. Парсим HTML для поиска координат (J2000) или target Aladin
            soup = BeautifulSoup(response.content, 'html.parser')

            # Способ 1: Ищем координаты в таблице "Celestial position" -> J2000
            coord_text = None
            for td in soup.find_all('td'):
                if td.text.strip() == 'J2000':
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        coord_text = next_td.text.strip()
                        break

            # Способ 2: Ищем координаты в JavaScript Aladin (более надежно)
            if not coord_text:
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string and 'target:' in script.string:
                        # Ищем строку типа target: 'J100705.35-055259.1' или target: 'J004244.33+411608.1'
                        import re
                        match = re.search(r"target:\s*'([^']+)'", script.string)
                        if match:
                            coord_text = match.group(1)
                            break

            if not coord_text:
                print(f"Не удалось найти координаты для PGC{pgc_number}")
                return None

            print(f"Найдены координаты: {coord_text}")

            # 4. Преобразуем координаты из строки в градусы
            # Формат: JHHMMSS.ss±DDMMSS.ss (например: J004244.33+411608.1 или J100705.35-055259.1)
            try:
                # Удаляем начальную 'J'
                clean_coord = coord_text.replace('J', '')

                # Разделяем RA и DEC по знаку +/- (сохраняя знак для DEC)
                import re
                match = re.match(r'([+-]?\d{6}\.\d+)([+-]\d{6}\.\d+)', clean_coord)
                if match:
                    ra_str = match.group(1)  # "004244.33" или "100705.35"
                    dec_str = match.group(2)  # "+411608.1" или "-055259.1"

                    # Конвертация RA из ЧЧММСС.сс в градусы
                    # RA: 1 час = 15 градусов, 1 минута = 0.25 градуса, 1 секунда = 15/3600 градуса
                    ra_h = int(ra_str[0:2])
                    ra_m = int(ra_str[2:4])
                    ra_s = float(ra_str[4:])
                    ra_deg = 15 * (ra_h + ra_m / 60 + ra_s / 3600)

                    # Конвертация DEC из ±ГГММСС.сс в градусы
                    # Определяем знак
                    dec_sign = -1 if dec_str[0] == '-' else 1
                    dec_abs = dec_str[1:]  # Убираем знак

                    dec_d = int(dec_abs[0:2])
                    dec_m = int(dec_abs[2:4])
                    dec_s = float(dec_abs[4:])
                    dec_deg = dec_sign * (dec_d + dec_m / 60 + dec_s / 3600)

                    print(f"Координаты в градусах: RA={ra_deg:.6f}, DEC={dec_deg:.6f}")

                else:
                    # Пробуем альтернативный формат, если стандартный не подошел
                    print(f"Не удалось распарсить координаты: {coord_text}")
                    return None

            except Exception as e:
                print(f"Ошибка конвертации координат {coord_text}: {e}")
                import traceback
                traceback.print_exc()
                return None

            # 5. Формируем URL для запроса изображения из Aladin
            # Используем обзор DSS2 (Digitized Sky Survey)
            survey = "DSS2"  # Можно использовать "P/DSS2/color" для цветного изображения
            width = 500
            height = 500
            fov = 0.1  # Поле зрения в градусах (можно регулировать)

            # Вариант через hips2fits сервис (рекомендуется)
            aladin_url = (
                f"http://alasky.u-strasbg.fr/hips-image-services/hips2fits"
                f"?hips=CDS/P/{survey}/color"
                f"&width={width}&height={height}"
                f"&ra={ra_deg}&dec={dec_deg}"
                f"&fov={fov}&format=jpg"
            )

            print(f"Загружаем изображение из Aladin: {aladin_url}")

            # 6. Загружаем изображение
            img_response = requests.get(aladin_url, headers=headers, timeout=30)
            img_response.raise_for_status()

            # Проверяем, что получен действительно изображение
            if 'image' not in img_response.headers.get('content-type', ''):
                print(f"Ошибка: сервер вернул не изображение. Content-Type: {img_response.headers.get('content-type')}")
                # Пробуем альтернативный URL
                aladin_url2 = f"http://alasky.u-strasbg.fr/P/{survey}/color?ra={ra_deg}&dec={dec_deg}&fov={fov}&width={width}&height={height}"
                print(f"Пробуем альтернативный URL: {aladin_url2}")
                img_response = requests.get(aladin_url2, headers=headers, timeout=30)
                img_response.raise_for_status()

            # 7. Сохраняем изображение
            with open(filename, 'wb') as f:
                f.write(img_response.content)

            print(f"Изображение сохранено: {filename}")
            return filename

        except requests.exceptions.RequestException as e:
            print(f"Ошибка сети при загрузке изображения PGC{pgc_number}: {e}")
            return None
        except Exception as e:
            print(f"Неизвестная ошибка при загрузке изображения PGC{pgc_number}: {e}")
            import traceback
            traceback.print_exc()
            return None

    @staticmethod
    def get_galaxy_image_from_cache(pgc_number, image_folder="galaxy_images"):
        """
        Получает изображение галактики из кэша (папки)

        Args:
            pgc_number: Номер PGC галактики
            image_folder: Папка с изображениями

        Returns:
            str: Путь к изображению или None
        """
        filename = os.path.join(image_folder, f"PGC{pgc_number}.jpg")
        if os.path.exists(filename):
            return filename

        # Также проверяем другие возможные расширения
        for ext in ['.jpeg', '.png', '.gif']:
            alt_filename = os.path.join(image_folder, f"PGC{pgc_number}{ext}")
            if os.path.exists(alt_filename):
                return alt_filename

        return None

    @staticmethod
    def download_images_for_dataframe(df, image_folder="galaxy_images", pgc_column='pgc'):
        """
        Загружает изображения для всех галактик в DataFrame

        Args:
            df: DataFrame с данными галактик
            image_folder: Папка для сохранения изображений
            pgc_column: Название колонки с PGC номерами

        Returns:
            dict: Словарь с информацией о загруженных изображениях
        """
        results = {
            'success': 0,
            'failed': 0,
            'cached': 0,
            'total': 0
        }

        if pgc_column not in df.columns:
            print(f"Колонка {pgc_column} не найдена в DataFrame")
            return results

        # Создаем папку для изображений
        if not os.path.exists(image_folder):
            os.makedirs(image_folder)

        # Обрабатываем каждую галактику
        for idx, row in df.iterrows():
            pgc_val = row[pgc_column]
            if pd.isna(pgc_val):
                continue

            try:
                pgc_num = int(float(pgc_val))
                results['total'] += 1

                # Проверяем, есть ли изображение в кэше
                cached_path = GalaxyImageDownloader.get_galaxy_image_from_cache(pgc_num, image_folder)
                if cached_path:
                    results['cached'] += 1
                    print(f"Изображение для PGC{pgc_num} уже в кэше")
                    continue

                # Загружаем изображение
                image_path = GalaxyImageDownloader.download_galaxy_image(pgc_num, image_folder)
                if image_path:
                    results['success'] += 1
                    print(f"Успешно загружено изображение для PGC{pgc_num}")
                else:
                    results['failed'] += 1
                    print(f"Не удалось загрузить изображение для PGC{pgc_num}")

                # Небольшая пауза, чтобы не перегружать сервер
                time.sleep(0.5)

            except Exception as e:
                print(f"Ошибка при обработке PGC значения {pgc_val}: {e}")
                results['failed'] += 1

        print(f"\nРезультаты загрузки изображений:")
        print(f"  Всего галактик: {results['total']}")
        print(f"  Успешно загружено: {results['success']}")
        print(f"  Уже в кэше: {results['cached']}")
        print(f"  Не удалось загрузить: {results['failed']}")

        return results


class GalaxyAnalyzer:
    def __init__(self, root):
        self.root = root
        self.root.title("Анализатор галактик с баром")
        self.root.geometry("1400x900")  # Увеличил размер окна для изображения

        self.df = None
        self.numeric_columns = []
        self.galaxy_names = []
        self.current_file_path = None
        self.current_canvas = None
        self.current_fig = None
        self.current_ax = None
        self.current_scatter = None
        self.current_x_data = None
        self.current_y_data = None
        self.current_x_param = None
        self.current_y_param = None
        self.current_plot_type = None
        self.click_annotation = None
        self.show_median = tk.BooleanVar(value=False)
        self.show_quartiles = tk.BooleanVar(value=False)
        self.show_mean = tk.BooleanVar(value=False)
        self.show_std = tk.BooleanVar(value=False)
        self.image_folder = "galaxy_images"
        if not os.path.exists(self.image_folder):
            os.makedirs(self.image_folder)
        self.current_img_ref = None  # Для хранения ссылки на PhotoImage
        self.current_image_label = None  # Для хранения ссылки на виджет с изображением
        self.current_pgc_number = None  # Текущий PGC номер для отображения изображения

        # Для отображения заглушки при отсутствии изображения
        self.no_image_img = self.create_no_image_placeholder()

        # Настройки графика
        self.plot_settings = {
            'xscale': 'linear',
            'yscale': 'linear',
            'grid': True,
            'grid_alpha': 0.3,
            'point_size': 30,
            'point_alpha': 0.7,
            'point_color': 'blue',
            'show_legend': True,
            'legend_position': 'best',
            'title_fontsize': 12,
            'label_fontsize': 10,
            'tick_fontsize': 9,
            'bivariate_bins': 20,  # Количество бинов для бивариантной гистограммы
            'bivariate_cmap': 'viridis',  # Цветовая карта
            'bivariate_logscale': True,  # Логарифмическая шкала для цвета
            'bivariate_3d_azimuth': 45,  # Азимут для 3D графика
            'bivariate_3d_elevation': 30,  # Элевация для 3D графика
            'bivariate_3d_xlim': None,  # Ограничение по оси X (None - автоматическое)
            'bivariate_3d_ylim': None,  # Ограничение по оси Y (None - автоматическое)
            'bivariate_3d_zlim': None,  # Ограничение по оси Z (None - автоматическое)
        }

        # Создание интерфейса
        self.create_interface()

        # Автоматическая попытка загрузки файла по умолчанию
        self.try_load_default_file()

    def create_no_image_placeholder(self):
        """Создает изображение-заглушку для случаев, когда нет изображения галактики"""
        try:
            # Создаем простое изображение с текстом
            img = Image.new('RGB', (300, 300), color='lightgray')
            # Для простоты возвращаем None, будем использовать текстовую метку
            return None
        except:
            return None

    def create_interface(self):
        """Создание графического интерфейса с изображением справа"""
        # Главный контейнер с разделением на левую и правую части
        main_container = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая панель - основной интерфейс с графиками
        left_panel = ttk.Frame(main_container)
        main_container.add(left_panel, weight=3)  # 3/4 ширины

        # Правая панель - изображение галактики
        right_panel = ttk.Frame(main_container)
        main_container.add(right_panel, weight=1)  # 1/4 ширины

        # ===== ЛЕВАЯ ПАНЕЛЬ =====
        main_frame = ttk.Frame(left_panel)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        file_frame = ttk.LabelFrame(top_frame, text="Управление файлами", padding=5)
        file_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Button(file_frame, text="Загрузить файл",
                   command=self.load_file_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Перезагрузить",
                   command=self.reload_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_frame, text="Загрузить все изображения",
                   command=self.download_all_images).pack(side=tk.LEFT, padx=5)

        status_frame = ttk.LabelFrame(top_frame, text="Статус", padding=5)
        status_frame.pack(side=tk.RIGHT, fill=tk.X)

        self.status_label = ttk.Label(status_frame,
                                      text="Файл не загружен | Объектов: 0 | Параметров: 0")
        self.status_label.pack()

        control_frame = ttk.LabelFrame(main_frame, text="Управление графиками", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(control_frame, text="Режим анализа:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.analysis_mode = tk.StringVar(value="all")
        analysis_modes = [("Все галактики", "all"),
                          ("Конкретная галактика", "single")]

        for i, (text, value) in enumerate(analysis_modes):
            ttk.Radiobutton(control_frame, text=text, variable=self.analysis_mode,
                            value=value, command=self.update_interface).grid(row=0, column=i + 1, padx=5)

        ttk.Label(control_frame, text="Тип графика:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.plot_type = tk.StringVar(value="scatter")
        plot_types = [("Точечная диаграмма", "scatter"),
                      ("Гистограмма", "histogram"),
                      ("Распределение с подсчетом", "distribution"),
                      ("Бивариантная гистограмма (2D)", "bivariate_histogram"),
                      ("3D Бивариантная гистограмма", "bivariate_3d_histogram")]  # Добавлен новый тип

        for i, (text, value) in enumerate(plot_types):
            ttk.Radiobutton(control_frame, text=text, variable=self.plot_type,
                            value=value, command=self.update_interface).grid(row=1, column=i + 1, padx=5)

        param_frame = ttk.Frame(control_frame)
        param_frame.grid(row=2, column=0, columnspan=6, sticky=tk.W, pady=10)

        ttk.Label(param_frame, text="Ось X:").grid(row=0, column=0, padx=(0, 10))
        self.x_var = tk.StringVar()
        self.x_entry = ttk.Entry(param_frame, textvariable=self.x_var, width=25)
        self.x_entry.grid(row=0, column=1, padx=(0, 20))
        ttk.Button(param_frame, text="📋", width=3,
                   command=self.show_parameter_list_x).grid(row=0, column=2, padx=(0, 20))

        ttk.Label(param_frame, text="Ось Y:").grid(row=0, column=3, padx=(0, 10))
        self.y_var = tk.StringVar()
        self.y_entry = ttk.Entry(param_frame, textvariable=self.y_var, width=25)
        self.y_entry.grid(row=0, column=4, padx=(0, 20))
        ttk.Button(param_frame, text="📋", width=3,
                   command=self.show_parameter_list_y).grid(row=0, column=5, padx=(0, 10))

        help_label = ttk.Label(param_frame,
                               text="Формат: имя_колонки или выражение (например: bt/vt, vt-bt)",
                               font=("Arial", 8), foreground="gray")
        help_label.grid(row=1, column=0, columnspan=6, sticky=tk.W, pady=(5, 0))

        galaxy_frame = ttk.Frame(control_frame)
        galaxy_frame.grid(row=3, column=0, columnspan=6, sticky=tk.W, pady=5)

        ttk.Label(galaxy_frame, text="Галактика:").grid(row=0, column=0, padx=(0, 10))
        self.galaxy_var = tk.StringVar()
        self.galaxy_combo = ttk.Combobox(galaxy_frame, textvariable=self.galaxy_var,
                                         values=self.galaxy_names, width=25, state="readonly")
        self.galaxy_combo.grid(row=0, column=1, padx=(0, 10))
        if self.galaxy_names:
            self.galaxy_combo.set(self.galaxy_names[0])

        ttk.Label(galaxy_frame, text="Поиск:").grid(row=0, column=2, padx=(20, 10))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(galaxy_frame, textvariable=self.search_var, width=20)
        self.search_entry.grid(row=0, column=3, padx=(0, 10))

        ttk.Button(galaxy_frame, text="Найти",
                   command=self.search_galaxy).grid(row=0, column=4, padx=5)

        options_frame = ttk.LabelFrame(control_frame, text="Статистические линии", padding=5)
        options_frame.grid(row=4, column=0, columnspan=6, sticky=tk.W, pady=10)

        ttk.Checkbutton(options_frame, text="Показать медиану",
                        variable=self.show_median).grid(row=0, column=0, padx=10)
        ttk.Checkbutton(options_frame, text="Показать среднее",
                        variable=self.show_mean).grid(row=0, column=1, padx=10)
        ttk.Checkbutton(options_frame, text="Показать квартили (25%/75%)",
                        variable=self.show_quartiles).grid(row=0, column=2, padx=10)
        ttk.Checkbutton(options_frame, text="Показать ±1σ",
                        variable=self.show_std).grid(row=0, column=3, padx=10)

        button_frame = ttk.Frame(control_frame)
        button_frame.grid(row=5, column=0, columnspan=6, pady=10)

        ttk.Button(button_frame, text="Построить график",
                   command=self.plot_data).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Расширенная статистика",
                   command=self.show_extended_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Информация о файле",
                   command=self.show_file_info).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Справочный материал",
                   command=self.show_reference_material).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Экспорт графика",
                   command=self.export_plot).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Настройки графика",
                   command=self.show_plot_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Настройки 2D графиков",
                   command=self.show_bivariate_2d_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Настройки 3D графиков",
                   command=self.show_bivariate_3d_settings).pack(side=tk.LEFT, padx=5)  # Новая кнопка
        ttk.Button(button_frame, text="Настройки распределения",
                   command=self.show_distribution_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Выход",
                   command=self.exit_app).pack(side=tk.LEFT, padx=5)

        self.figure_frame = ttk.LabelFrame(main_frame, text="График", padding=10)
        self.figure_frame.pack(fill=tk.BOTH, expand=True)

        self.update_interface()

        # ===== ПРАВАЯ ПАНЕЛЬ - ИЗОБРАЖЕНИЕ ГАЛАКТИКИ =====
        # Создаем фрейм для изображения
        image_frame = ttk.LabelFrame(right_panel, text="Изображение галактики", padding=10)
        image_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Добавляем кнопку для обновления изображения
        image_button_frame = ttk.Frame(image_frame)
        image_button_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(image_button_frame, text="Загрузить изображение",
                   command=self.download_current_galaxy_image).pack(side=tk.LEFT, padx=5)
        ttk.Button(image_button_frame, text="Обновить",
                   command=self.update_current_galaxy_image).pack(side=tk.LEFT, padx=5)

        # Создаем метку для отображения названия галактики
        self.image_title_label = ttk.Label(image_frame, text="Выберите галактику",
                                           font=('Arial', 10, 'bold'), wraplength=250)
        self.image_title_label.pack(pady=(0, 10))

        # Создаем фрейм для самого изображения
        self.image_display_frame = ttk.Frame(image_frame)
        self.image_display_frame.pack(fill=tk.BOTH, expand=True)

        # Инициализируем метку для изображения
        self.current_image_label = ttk.Label(self.image_display_frame,
                                             text="Изображение не загружено\n\nНажмите 'Загрузить изображение'",
                                             relief=tk.SUNKEN)
        self.current_image_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Создаем метку для статуса загрузки
        self.image_status_label = ttk.Label(image_frame, text="",
                                            font=('Arial', 8), foreground="gray")
        self.image_status_label.pack(pady=(10, 0))

    def download_all_images(self):
        """Загрузить изображения для всех галактик"""
        if self.df is None or self.df.empty:
            messagebox.showwarning("Предупреждение", "Сначала загрузите файл с данными")
            return

        if 'pgc' not in self.df.columns:
            messagebox.showwarning("Предупреждение", "В данных отсутствует колонка 'pgc'")
            return

        # Спрашиваем подтверждение
        confirm = messagebox.askyesno("Подтверждение",
                                      f"Вы собираетесь загрузить изображения для {len(self.df)} галактик.\n"
                                      "Это может занять длительное время.\n\n"
                                      "Продолжить?")
        if not confirm:
            return

        # Запускаем загрузку в отдельном потоке, чтобы не блокировать интерфейс
        def download_thread():
            self.image_status_label.config(text="Загрузка изображений...")
            self.root.update()

            results = GalaxyImageDownloader.download_images_for_dataframe(
                self.df, self.image_folder, 'pgc'
            )

            # Обновляем статус
            self.image_status_label.config(
                text=f"Загружено: {results['success']}, В кэше: {results['cached']}, Ошибок: {results['failed']}"
            )

            messagebox.showinfo("Завершено",
                                f"Загрузка изображений завершена:\n"
                                f"Успешно: {results['success']}\n"
                                f"В кэше: {results['cached']}\n"
                                f"Ошибок: {results['failed']}")

        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()

    def download_current_galaxy_image(self):
        """Загрузить изображение для текущей выбранной галактики"""
        if self.df is None or self.df.empty:
            messagebox.showwarning("Предупреждение", "Сначала загрузите файл с данными")
            return

        if 'pgc' not in self.df.columns:
            messagebox.showwarning("Предупреждение", "В данных отсутствует колонка 'pgc'")
            return

        # Определяем PGC номер текущей галактики
        galaxy_name = self.galaxy_var.get()
        if not galaxy_name:
            messagebox.showwarning("Предупреждение", "Сначала выберите галактику")
            return

        galaxy_data = self.get_galaxy_data(galaxy_name)
        if galaxy_data is None:
            messagebox.showwarning("Предупреждение", f"Не удалось найти данные для галактики: {galaxy_name}")
            return

        pgc_val = galaxy_data['pgc'] if 'pgc' in galaxy_data else None
        if pd.isna(pgc_val):
            messagebox.showwarning("Предупреждение", f"У галактики {galaxy_name} нет PGC номера")
            return

        try:
            pgc_num = int(float(pgc_val))
            self.current_pgc_number = pgc_num

            # Обновляем заголовок
            self.image_title_label.config(text=f"PGC{pgc_num} - {galaxy_name}")

            # Показываем сообщение о загрузке
            self.current_image_label.config(
                text=f"Загрузка изображения для PGC{pgc_num}...",
                image='', compound='top'
            )
            self.image_status_label.config(text="Загрузка...")
            self.root.update()

            # Загружаем изображение
            image_path = GalaxyImageDownloader.download_galaxy_image(pgc_num, self.image_folder)

            if image_path:
                self.update_image_display(image_path, pgc_num, galaxy_name)
                self.image_status_label.config(text="Изображение загружено")
            else:
                self.current_image_label.config(
                    text=f"Не удалось загрузить изображение\nдля PGC{pgc_num}",
                    image='', compound='top'
                )
                self.image_status_label.config(text="Ошибка загрузки")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке изображения: {e}")
            self.image_status_label.config(text="Ошибка")

    def update_current_galaxy_image(self):
        """Обновить отображение изображения для текущей галактики"""
        if self.current_pgc_number is None:
            messagebox.showwarning("Предупреждение", "Сначала загрузите изображение галактики")
            return

        # Ищем изображение в кэше
        image_path = GalaxyImageDownloader.get_galaxy_image_from_cache(self.current_pgc_number, self.image_folder)

        if image_path:
            # Определяем название галактики
            galaxy_name = self.galaxy_var.get() if self.galaxy_var.get() else f"PGC{self.current_pgc_number}"
            self.update_image_display(image_path, self.current_pgc_number, galaxy_name)
            self.image_status_label.config(text="Изображение загружено из кэша")
        else:
            self.current_image_label.config(
                text=f"Изображение для PGC{self.current_pgc_number}\nне найдено в кэше",
                image='', compound='top'
            )
            self.image_status_label.config(text="Изображение не найдено")

    def update_image_display(self, image_path, pgc_num, galaxy_name):
        """Обновить отображение изображения в интерфейсе"""
        try:
            # Загружаем изображение с помощью PIL
            img = Image.open(image_path)

            # Масштабируем изображение, чтобы оно поместилось в отведенное пространство
            max_width = 300
            max_height = 300

            # Вычисляем новые размеры с сохранением пропорций
            img_width, img_height = img.size
            ratio = min(max_width / img_width, max_height / img_height)
            new_width = int(img_width * ratio)
            new_height = int(img_height * ratio)

            # Изменяем размер
            img_resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Конвертируем в формат PhotoImage для Tkinter
            img_tk = ImageTk.PhotoImage(img_resized)

            # Обновляем метку с изображением
            self.current_image_label.config(
                image=img_tk,
                text=f"PGC{pgc_num}\n{galaxy_name}",
                compound='top'
            )

            # Сохраняем ссылку, чтобы изображение не удалилось сборщиком мусора
            self.current_img_ref = img_tk

            # Обновляем заголовок
            self.image_title_label.config(text=f"PGC{pgc_num} - {galaxy_name}")

        except Exception as e:
            print(f"Ошибка при отображении изображения: {e}")
            self.current_image_label.config(
                text=f"Ошибка загрузки изображения\nPGC{pgc_num}",
                image='', compound='top'
            )

    def on_plot_click(self, event):
        """Обработчик клика мыши на графике - обновлен для загрузки изображения"""
        if event.inaxes is None:
            return

        if self.current_plot_type != "scatter" or self.current_ax is None:
            return

        x = event.xdata
        y = event.ydata

        if x is None or y is None:
            return

        # Ищем ближайшую точку
        if self.current_scatter is not None and hasattr(self.current_scatter, 'get_offsets'):
            points = self.current_scatter.get_offsets()
            if len(points) == 0:
                return

            # Вычисляем расстояния до всех точек
            distances = np.sqrt((points[:, 0] - x) ** 2 + (points[:, 1] - y) ** 2)
            min_idx = np.argmin(distances)
            min_distance = distances[min_idx]

            # Пороговое расстояние для клика
            threshold = 0.05 * max(np.ptp(points[:, 0]), np.ptp(points[:, 1]))

            if min_distance < threshold:
                # Получаем индексы данных
                if self.current_x_data is not None and self.current_y_data is not None:
                    # Находим индекс галактики в исходных данных
                    x_vals = self.current_x_data.values
                    y_vals = self.current_y_data.values

                    # Ищем совпадение значений
                    x_match = np.where(np.abs(x_vals - points[min_idx, 0]) < 1e-10)[0]
                    y_match = np.where(np.abs(y_vals - points[min_idx, 1]) < 1e-10)[0]

                    common_indices = np.intersect1d(x_match, y_match)

                    if len(common_indices) > 0:
                        idx = common_indices[0]

                        # Получаем индекс в оригинальном DataFrame
                        if idx < len(self.current_x_data):
                            df_idx = self.current_x_data.index[idx]
                        elif idx < len(self.current_y_data):
                            df_idx = self.current_y_data.index[idx]
                        else:
                            df_idx = idx

                        # Получаем название галактики
                        galaxy_name = self.get_galaxy_name_by_index(df_idx)

                        # Получаем значения параметров
                        x_val = points[min_idx, 0]
                        y_val = points[min_idx, 1]

                        # Удаляем предыдущую аннотацию
                        if self.click_annotation:
                            self.click_annotation.remove()

                        # Создаем новую аннотацию
                        x_info = self.get_parameter_info(self.current_x_param)
                        y_info = self.get_parameter_info(self.current_y_param)

                        annotation_text = f"{galaxy_name}\n"
                        annotation_text += f"{x_info['ru_name']}: {x_val:.3f}\n"
                        annotation_text += f"{y_info['ru_name']}: {y_val:.3f}"

                        # Создаем аннотацию с фоном
                        bbox_props = dict(boxstyle="round,pad=0.3", facecolor="yellow", alpha=0.8, edgecolor="black")
                        self.click_annotation = self.current_ax.annotate(
                            annotation_text,
                            xy=(x_val, y_val),
                            xytext=(10, 10),
                            textcoords="offset points",
                            bbox=bbox_props,
                            fontsize=9,
                            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0.2")
                        )

                        # Выделяем точку
                        self.current_ax.plot(x_val, y_val, 'ro', markersize=10, markeredgecolor='red',
                                             markeredgewidth=2)

                        # Перерисовываем график
                        self.current_canvas.draw_idle()

                        # Обновляем выбранную галактику в комбобоксе
                        if galaxy_name in self.galaxy_names:
                            self.galaxy_var.set(galaxy_name)

                        # Пытаемся получить PGC номер и загрузить изображение
                        galaxy_data = self.get_galaxy_data(galaxy_name)
                        if galaxy_data is not None and 'pgc' in galaxy_data:
                            pgc_val = galaxy_data['pgc']
                            if pd.notna(pgc_val):
                                try:
                                    pgc_num = int(float(pgc_val))
                                    self.current_pgc_number = pgc_num

                                    # Обновляем заголовок
                                    self.image_title_label.config(text=f"PGC{pgc_num} - {galaxy_name}")

                                    # Проверяем, есть ли изображение в кэше
                                    image_path = GalaxyImageDownloader.get_galaxy_image_from_cache(pgc_num,
                                                                                                   self.image_folder)

                                    if image_path:
                                        self.update_image_display(image_path, pgc_num, galaxy_name)
                                        self.image_status_label.config(text="Изображение загружено из кэша")
                                    else:
                                        self.current_image_label.config(
                                            text=f"Нажмите 'Загрузить изображение'\nдля PGC{pgc_num}",
                                            image='', compound='top'
                                        )
                                        self.image_status_label.config(text="Изображение не загружено")
                                except:
                                    pass

    # ... (остальной код остается без изменений, начиная с метода try_load_default_file)
    # Все остальные методы класса GalaxyAnalyzer остаются без изменений
    # Я сохранил всю оригинальную функциональность

    def try_load_default_file(self):
        """Попытка автоматической загрузки файла по умолчанию"""
        default_files = ['Выборка с баром.csv', 'data.csv', 'galaxies.csv']

        for file_name in default_files:
            if os.path.exists(file_name):
                self.current_file_path = file_name
                self.load_data()
                messagebox.showinfo("Успех", f"Файл {file_name} загружен автоматически")
                return

        # Если файл не найден, показываем диалог выбора файла
        messagebox.showinfo("Выбор файла", "Файл данных не найден. Пожалуйста, выберите файл CSV.")
        self.load_file_dialog()

    def load_file_dialog(self):
        """Диалог выбора файла"""
        file_path = filedialog.askopenfilename(
            title="Выберите файл данных",
            filetypes=[
                ("CSV files", "*.csv"),
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )

        if file_path:
            self.current_file_path = file_path
            self.load_data()
        else:
            # Если пользователь отменил выбор, создаем пустой датафрейм
            self.df = pd.DataFrame()
            self.numeric_columns = []
            self.galaxy_names = []
            messagebox.showwarning("Предупреждение",
                                   "Файл не выбран. Программа будет работать в демонстрационном режиме.")

    def clean_numeric_value(self, value):
        """Очистка числовых значений от лишних пробелов и символов"""
        if pd.isna(value) or value == '':
            return np.nan

        # Преобразуем в строку и убираем лишние пробелы
        str_value = str(value).strip()

        # Заменяем запятые на точки для десятичных чисел
        str_value = str_value.replace(',', '.')

        # Убираем множественные пробелы
        str_value = re.sub(r'\s+', ' ', str_value)

        # Если значение состоит только из пробелов или пустое
        if not str_value or str_value.isspace():
            return np.nan

        try:
            return float(str_value)
        except (ValueError, TypeError):
            return np.nan

    def load_data(self):
        """Загрузка данных из файла"""
        if not self.current_file_path:
            messagebox.showerror("Ошибка", "Файл не выбран")
            return

        try:
            # Определяем кодировку файла
            encodings = ['utf-8', 'cp1251', 'latin-1', 'iso-8859-1']

            for encoding in encodings:
                try:
                    # Читаем файл с правильными параметрами
                    self.df = pd.read_csv(self.current_file_path,
                                          sep=';',
                                          skipinitialspace=True,
                                          decimal='.',
                                          na_values=['', ' ', 'NaN', 'nan', '        ', '        ', '...'],
                                          encoding=encoding,
                                          comment='#',
                                          dtype={'objname': str},
                                          quoting=3)
                    print(f"✓ Файл загружен с кодировкой {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                # Если ни одна кодировка не подошла, используем последнюю с ошибками
                self.df = pd.read_csv(self.current_file_path,
                                      sep=';',
                                      skipinitialspace=True,
                                      decimal='.',
                                      na_values=['', ' ', 'NaN', 'nan', '        ', '        ', '...'],
                                      encoding='utf-8',
                                      comment='#',
                                      dtype={'objname': str},
                                      quoting=3,
                                      errors='ignore')

            print(f"✓ Данные загружены успешно. Размер: {self.df.shape}")
            print(f"✓ Файл: {os.path.basename(self.current_file_path)}")

            # Очищаем числовые колонки
            self.clean_numeric_columns()

            # Покажем структуру данных для диагностики
            print("\nПервые 5 строк данных:")
            print(self.df.head())
            print("\nКолонки данных:")
            print(self.df.columns.tolist())
            print("\nТипы данных:")
            print(self.df.dtypes)

            # Находим числовые колонки
            self.find_numeric_columns()

            # Получаем список названий галактик из objname
            self.get_galaxy_names()

            # Обновляем интерфейс
            self.update_interface_after_load()

        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            # Попробуем альтернативный способ чтения
            try:
                self.load_data_alternative()
                self.update_interface_after_load()
            except Exception as e2:
                print(f"Альтернативный способ тоже не сработал: {e2}")
                messagebox.showerror("Ошибка", f"Не удалось загрузить данные: {e}")

    def load_data_alternative(self):
        """Альтернативный способ загрузки данных"""
        with open(self.current_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()

        # Парсим заголовок
        header = lines[0].strip().split(';')
        data = []

        for line in lines[1:]:
            if line.strip():
                values = line.strip().split(';')
                # Обеспечиваем одинаковую длину
                while len(values) < len(header):
                    values.append('')
                data.append(values[:len(header)])

        self.df = pd.DataFrame(data, columns=header)
        print(f"✓ Данные загружены альтернативным способом. Размер: {self.df.shape}")

        # Очищаем числовые колонки
        self.clean_numeric_columns()

        # Находим числовые колонки
        self.find_numeric_columns()

        # Получаем список названий галактик из objname
        self.get_galaxy_names()

    def update_interface_after_load(self):
        """Обновление интерфейса после загрузки данных"""
        # Обновляем комбобоксы
        if hasattr(self, 'x_entry'):
            if self.numeric_columns:
                self.x_entry.delete(0, tk.END)
                self.x_entry.insert(0, self.numeric_columns[0])

        if hasattr(self, 'y_entry'):
            if len(self.numeric_columns) > 1:
                self.y_entry.delete(0, tk.END)
                self.y_entry.insert(0, self.numeric_columns[1])

        if hasattr(self, 'galaxy_combo'):
            self.galaxy_combo['values'] = self.galaxy_names
            if self.galaxy_names:
                self.galaxy_combo.set(self.galaxy_names[0])

        # Обновляем статус
        if hasattr(self, 'status_label'):
            file_name = os.path.basename(self.current_file_path) if self.current_file_path else "Файл не загружен"
            self.status_label.config(
                text=f"Файл: {file_name} | Объектов: {len(self.df)} | Параметров: {len(self.numeric_columns)}"
            )

    def clean_numeric_columns(self):
        """Очистка числовых колонки от лишних пробелов"""
        for col in self.df.columns:
            if col.lower() not in ['objname', 'pgc', 'type', 'objtype']:
                # Применяем очистку к каждой ячейке
                self.df[col] = self.df[col].apply(self.clean_numeric_value)

    def get_galaxy_names(self):
        """Получаем правильные названия галактики"""
        if 'objname' in self.df.columns:
            # Извлекаем названия из колонки objname
            names = self.df['objname'].astype(str).str.strip()

            # Фильтруем и очищаем названия
            valid_names = []
            for name in names:
                clean_name = str(name).strip()
                # Пропускаем пустые и некорректные названия
                if (clean_name and
                        clean_name != 'nan' and
                        clean_name != 'G' and
                        not clean_name.isspace() and
                        len(clean_name) > 2):
                    valid_names.append(clean_name)
                else:
                    # Создаем имя из PGC, если objname некорректен
                    idx = names.tolist().index(name)
                    if 'pgc' in self.df.columns and pd.notna(self.df.iloc[idx]['pgc']):
                        pgc_val = self.df.iloc[idx]['pgc']
                        if pd.notna(pgc_val):
                            valid_names.append(f"PGC{int(float(pgc_val))}")
                        else:
                            valid_names.append(f"Галактика_{idx + 1}")
                    else:
                        valid_names.append(f"Галактика_{idx + 1}")

            self.galaxy_names = valid_names
            print(f"✓ Названия галактик загружены: {len(self.galaxy_names)} имен")
            print("Примеры названий:", self.galaxy_names[:10])

        else:
            # Создаем имена из PGC номеров или порядковых номеров
            if 'pgc' in self.df.columns:
                self.galaxy_names = [
                    f"PGC{int(float(pgc))}" if pd.notna(pgc) else f"Галактика_{i + 1}"
                    for i, pgc in enumerate(self.df['pgc'])
                ]
            else:
                self.galaxy_names = [f"Галактика_{i + 1}" for i in range(len(self.df))]

            print(f"✓ Созданы названия галактик: {len(self.galaxy_names)} имен")
            print("Примеры названий:", self.galaxy_names[:10])

    def find_numeric_columns(self):
        """Поиск числовых колонок"""
        self.numeric_columns = []
        excluded_cols = ['objname', 'pgc', 'type', 'objtype']

        for col in self.df.columns:
            col_lower = col.lower()
            if any(excluded in col_lower for excluded in excluded_cols):
                continue

            numeric_data = self.get_numeric_data(col)
            if len(numeric_data) > 5:  # Минимум 5 значений
                self.numeric_columns.append(col)

        print(f"✓ Найдено числовых колонок: {len(self.numeric_columns)}")
        print("Числовые колонки:", self.numeric_columns[:10])  # Покажем первые 10

    def get_numeric_data(self, column):
        """Безопасно извлекает числовые данные из колонки"""
        if column not in self.df.columns:
            return pd.Series([], dtype=float)

        # Уже очищенные данные, просто фильтруем NaN
        numeric_data = self.df[column].dropna()
        return numeric_data

    def get_galaxy_names_for_values(self, column, values):
        """Получает названия галактик для заданных значений параметра"""
        result = []
        for val in values:
            # Ищем галактики с близким значением параметра (из-за float точности)
            numeric_col = self.df[column]
            mask = numeric_col.notna()

            if mask.any():
                # Находим ближайшее значение
                differences = np.abs(numeric_col - val)
                min_diff_idx = differences.idxmin()

                if differences[min_diff_idx] < 0.001:  # Допустимая погрешность
                    galaxy_name = self.get_galaxy_name_by_index(min_diff_idx)
                    result.append(galaxy_name)
                else:
                    result.append("Не найдено")
            else:
                result.append("Не найдено")

        return result

    def get_galaxy_name_by_index(self, index):
        """Получает название галактики по индексу"""
        if index < len(self.galaxy_names):
            return self.galaxy_names[index]
        return f"Галактика_{index + 1}"

    def search_galaxies(self, search_term):
        """Поиск галактик по названию"""
        if not search_term:
            return self.galaxy_names

        search_term = search_term.lower().strip()
        results = []

        for name in self.galaxy_names:
            if search_term in name.lower():
                results.append(name)

        return results[:50]  # Ограничиваем результаты для производительности

    def get_galaxy_data(self, galaxy_name):
        """Получает все данные для конкретной галактики"""
        # Ищем по нашему списку названий
        if galaxy_name in self.galaxy_names:
            idx = self.galaxy_names.index(galaxy_name)
            return self.df.iloc[idx]

        # Пробуем найти по PGC номеру
        if galaxy_name.upper().startswith('PGC'):
            try:
                pgc_num = int(galaxy_name[3:])
                if 'pgc' in self.df.columns:
                    # Сравниваем как числа
                    pgc_series = pd.to_numeric(self.df['pgc'], errors='coerce')
                    mask = pgc_series == pgc_num
                    if mask.any():
                        return self.df[mask].iloc[0]
            except:
                pass

        # Пробуем найти по частичному совпадению в objname
        if 'objname' in self.df.columns:
            mask = self.df['objname'].astype(str).str.lower().str.contains(
                galaxy_name.lower(), na=False)
            if mask.any():
                return self.df[mask].iloc[0]

        return None

    def show_reference_material(self):
        """Показать справочный материал с описанием параметров"""
        ref_window = tk.Toplevel(self.root)
        ref_window.title("Справочный материал по параметрам галактик")
        ref_window.geometry("1000x700")

        # Создаем Notebook (вкладки)
        notebook = ttk.Notebook(ref_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка 1: Основные параметры
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Основные параметры")

        basic_text = tk.Text(basic_frame, wrap=tk.WORD, font=("Arial", 10))
        basic_scrollbar = ttk.Scrollbar(basic_frame, orient=tk.VERTICAL, command=basic_text.yview)
        basic_text.configure(yscrollcommand=basic_scrollbar.set)

        basic_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        basic_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Вкладка 2: Фотометрические параметры
        photometry_frame = ttk.Frame(notebook)
        notebook.add(photometry_frame, text="Фотометрия")

        photometry_text = tk.Text(photometry_frame, wrap=tk.WORD, font=("Arial", 10))
        photometry_scrollbar = ttk.Scrollbar(photometry_frame, orient=tk.VERTICAL, command=photometry_text.yview)
        photometry_text.configure(yscrollcommand=photometry_scrollbar.set)

        photometry_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        photometry_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Вкладка 3: Кинематические параметры
        kinematics_frame = ttk.Frame(notebook)
        notebook.add(kinematics_frame, text="Кинематика")

        kinematics_text = tk.Text(kinematics_frame, wrap=tk.WORD, font=("Arial", 10))
        kinematics_scrollbar = ttk.Scrollbar(kinematics_frame, orient=tk.VERTICAL, command=kinematics_text.yview)
        kinematics_text.configure(yscrollcommand=kinematics_scrollbar.set)

        kinematics_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        kinematics_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Вкладка 4: Морфологические параметры
        morphology_frame = ttk.Frame(notebook)
        notebook.add(morphology_frame, text="Морфология")

        morphology_text = tk.Text(morphology_frame, wrap=tk.WORD, font=("Arial", 10))
        morphology_scrollbar = ttk.Scrollbar(morphology_frame, orient=tk.VERTICAL, command=morphology_text.yview)
        morphology_text.configure(yscrollcommand=morphology_scrollbar.set)

        morphology_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        morphology_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Заполняем вкладки справочной информацией
        self.fill_basic_parameters(basic_text)
        self.fill_photometry_parameters(photometry_text)
        self.fill_kinematics_parameters(kinematics_text)
        self.fill_morphology_parameters(morphology_text)

    def fill_basic_parameters(self, text_widget):
        """Заполняет вкладку с основными параметрами"""
        content = """
ОСНОВНЫЕ ПАРАМЕТРЫ ГАЛАКТИК

1. КООРДИНАТЫ И ПОЛОЖЕНИЕ
────────────────────────

• al2000, de2000 - Прямое восхождение и склонение (эпоха J2000)
  Формула преобразования координат:
    α = al2000 (часы, минуты, секунды)
    δ = de2000 (градусы, минуты, секунды)
  Используется для точного позиционирования на небесной сфере.

• l2, b2 - Галактические координаты
  l₂ - галактическая долгота (0°-360°)
  b₂ - галактическая широта (-90° до +90°)
  Отсчитываются от центра Галактики в галактической плоскости.

• sgl, sgb - Сверхгалактические координаты
  Определяются относительно плоскости Местного сверхскопления галактик.

2. РАССТОЯНИЯ И МОДУЛИ РАССТОЯНИЙ
────────────────────────────────

• modz - Космологический модуль расстояния
  Формула: modz = 5·log₁₀(Dₗ) + 25
  где Dₗ - светимость расстояния в мегапарсеках
  Учитывает расширение Вселенной (ΛCDM модель).

• mod0 - Модуль расстояния от прямых измерений
  Основан на цефеидах, сверхновых и других индикаторов расстояния.

• modbest - Наилучшая оценка модуля расстояния
  Комбинация mod0 и modz с учетом точности измерений.

• mabs - Абсолютная звездная величина в фильтре B
  Формула: M = m - 5·log₁₀(d) + 5
  где m - видимая звездная величина, d - расстояние в парсеках

3. ОСНОВНЫЕ ИДЕНТИФИКАТОРЫ
────────────────────────

• pgc - Номер в каталоге Principal Galaxies Catalogue
  Уникальный идентификатор галактики.

• objname - Основное название объекта
  Может содержать различные обозначения (NGC, IC, UGC, etc.)

• objtype - Тип объекта
  G - галактика, S - звезда, Q - квазар, etc.
"""
        text_widget.insert(1.0, content)
        text_widget.configure(state='disabled')

    def fill_photometry_parameters(self, text_widget):
        """Заполняет вкладку с фотометрическими параметрами"""
        content = """
ФОТОМЕТРИЧЕСКИЕ ПАРАМЕТРЫ ГАЛАКТИК

1. ЗВЕЗДНЫЕ ВЕЛИЧИНЫ (MAGNITUDES)
────────────────────────────────

• bt, vt, ut, it, kt - Полные звездные величины
  Индексы: U (ультрафиолет), B (синий), V (визуальный), I (инфракрасный), K (ближний ИК)
  Шкала величин: m = -2.5·log₁₀(F/F₀)
  где F - поток излучения, F₀ - поток нулевой точки

• btc, itc - Скорректированные полные величины
  Учтены: поглощение в Млечном Пути, внутреннее поглощение, к-поправка

2. ЦВЕТОВЫЕ ИНДЕКСЫ
──────────────────

• ube, bve - Эффективные цвета
  ube = U - B, bve = B - V
  Показывают распределение энергии в спектре

• ubtc, bvtc - Скорректированные полные цвета
  Учтены все поправки, отражают истинные свойства галактики

3. ПОВЕРХНОСТНАЯ ЯРКОСТЬ
───────────────────────

• brief - Средняя эффективная поверхностная яркость
  Определяется внутри изофоты 25 mag/arcsec² в фильтре B

• bri25 - Средняя поверхностная яркость внутри изофоты 25

4. ФОРМУЛЫ И ПРЕОБРАЗОВАНИЯ
─────────────────────────

• Связь видимой и абсолютной величины:
  M = m - 5·log₁₀(d) + 5 - A
  где A - межзвездное поглощение

• Поток и звездная величина:
  F = F₀·10^(-0.4·m)

• Цвет и температура:
  Для звезд: B-V ≈ 0.65·(T - 7000)/1000 (приближенно)
  Для галактики сложнее из-за составного спектра

5. ПОГЛОЩЕНИЕ И ЭКСТИНКЦИЯ
─────────────────────────

• ag - Галактическое поглощение в полосе B
  Модель поглощения в Млечном Пути

• ai - Внутреннее поглощение из-за наклона галактики
  Зависит от морфологического типа и наклона
"""
        text_widget.insert(1.0, content)
        text_widget.configure(state='disabled')

    def fill_kinematics_parameters(self, text_widget):
        """Заполняет вкладку с кинематическими параметрами"""
        content = """
КИНЕМАТИЧЕСКИЕ ПАРАМЕТРЫ ГАЛАКТИК

1. ЛУЧЕВЫЕ СКОРОСТИ
──────────────────

• v - Средняя гелиоцентрическая лучевая скорость
  Определяется по оптическим спектрам

• vrad - Лучевая скорость по радионаблюдениям
  Чаще всего по линии HI 21 см

• vopt - Оптическая лучевая скорость
  Измерена по оптическим спектральным линиям

• vlg - Скорость относительно Местной группы
  vlg = v + 300·sin(l)·cos(b) [км/с]

• vgsr - Скорость относительно Galactic Standard of Rest
  Учитывает движение Солнца в Галактике

• vvir - Скорость, скорректированная на падение на скопление Девы

2. СКОРОСТИ ВРАЩЕНИЯ
───────────────────

• vmaxg - Максимальная скорость вращения газа
  Измеряется по кривой вращения HI или Hα

• vmaxs - Максимальная скорость вращения звезд
  По звездным дисперсиям скоростей

• vrot - Скорректированная максимальная скорость вращения
  vrot = vmax / sin(i), где i - угол наклона

3. ДИСПЕРСИИ СКОРОСТЕЙ
─────────────────────

• vdis - Центральная дисперсия скоростей
  σ - дисперсия скоростей в центральной области
  Важна для соотношения Фабер-Джексон (эллиптические галактики)

4. ФОРМУЛЫ И СООТНОШЕНИЯ
───────────────────────

• Закон Талли-Фишера (спиральные галактики):
  M = -a·log₁₀(vrot) + b
  где a ≈ 5-10, b - константа калибровки

• Соотношение Фабер-Джексон (эллиптические галактики):
  L ∝ σ⁴
  или в величинах: M = -10·log₁₀(σ) + const

• Кривая вращения:
  v(r) = √(GM(r)/r)
  Позволяет изучать распределение массы

5. КОСМОЛОГИЧЕСКИЕ ПРИЛОЖЕНИЯ
────────────────────────────

• Красное смещение: z = v/c (для v << c)
• Закон Хаббла: v = H₀·d
• Модуль расстояния из скоростей: modz = 5·log₁₀(v/H₀) + 25
"""
        text_widget.insert(1.0, content)
        text_widget.configure(state='disabled')

    def fill_morphology_parameters(self, text_widget):
        """Заполняет вкладку с морфологическими параметрами"""
        content = """
МОРФОЛОГИЧЕСКИЕ ПАРАМЕТРЫ ГАЛАКТИК

1. КЛАССИФИКАЦИЯ ПО ХАББЛУ
─────────────────────────

• t - Числовой код морфологического типа
  Шкала Хаббла: -5 → +10
  -5: cD (гигантские эллиптические)
  -3 до -1: Эллиптические (E0-E7)
  0: S0 (линзовидные)
  1-3: Обычные спиральные (Sa-Sc)
  6-9: Неправильные (Im)
  10: Карликовые неправильные

2. РАЗМЕРЫ И ФОРМА
─────────────────

• logd25 - Логарифм большого диаметра
  d25 - диаметр на изофоте 25 mag/arcsec² в B-фильтре
  В единицах 0.1 угловой минуты

• logr25 - Логарифм отношения осей
  r25 = a/b (большая/малая ось)
  Показывает сплюснутость галактики

• pa - Позиционный угол большой оси
  Отсчитывается от направления на север к востоку (0-360°)

• incl - Угол наклона
  cos(i) = b/a (для тонкого диска)
  i = 0° - плашмя, i = 90° - с ребра

3. СТРУКТУРНЫЕ ОСОБЕННОСТИ
─────────────────────────

• bar - Наличие бара
  B - галактика с баром

• ring - Наличие кольца
  R - галактика с кольцевой структуряой

• multiple - Кратная система
  M - взаимодействующая или кратная галактика

• compactness - Компактность
  C - компактная, D - диффузная

4. ФОРМУЛЫ И ЗАВИСИМОСТИ
───────────────────────

• Угловой размер в линейный:
  D [кпк] = d25 [угл. мин] · d [Мпк] / 3438

• Связь наклона и отношения осей:
  Для чисто дисковых галактики: cos(i) = (b/a)
  Для сфероидальных: более сложные зависимости

• Поверхностная яркость:
  μ [mag/arcsec²] = m + 2.5·log₁₀(π·a·b) - 36.57
  где a, b - полуоси в угловых секундах

5. ФИЗИЧЕСКАЯ ИНТЕРПРЕТАЦИЯ
──────────────────────────

• Диаметр D25 соответствует примерно 83% полного светового потока
• Отношение осей связано с морфологическим типом:
  - Эллиптические: более круглые
  - Спиральные: более вытянутые
• Бар указывает на динамическую эволюцию диска
• Кольца часто связаны с резонансами в диске
"""
        text_widget.insert(1.0, content)
        text_widget.configure(state='disabled')

    def get_param_info(self, col_name):
        """Возвращает русское описание параметра"""
        param_descriptions = {
            'pgc': 'Номер в каталоге PGC',
            'objname': 'Основное название объекта',
            'objtype': 'Тип объекта (G=галактика; S=звезда...)',
            'al1950': 'Прямое восхождение 1950 (часы)',
            'de1950': 'Склонение 1950 (градусы)',
            'al2000': 'Прямое восхождение 2000 (часы)',
            'de2000': 'Склонение 2000 (градусы)',
            'l2': 'Галактическая долгота (градусы)',
            'b2': 'Галактическая широта (градусы)',
            'sgl': 'Сверхгалактическая долгота (градусы)',
            'sgb': 'Сверхгалактическая широта (градусы)',
            'type': 'Морфологический тип',
            'bar': 'Галактика с баром (B)',
            'ring': 'Галактика с кольцом (R)',
            'multiple': 'Кратная галактика (M)',
            'compactness': 'Компактность (C) или диффузность (D)',
            't': 'Код морфологического типа',
            'e_t': 'Ошибка кода морфологического типа',
            'logd25': 'Логарифм видимого диаметра (d25 в 0.1 угл. мин)',
            'e_logd25': 'Ошибка логарифма видимого диаметра',
            'logr25': 'Логарифм отношения осей (большая/малая ось)',
            'e_logr25': 'Ошибка логарифма отношения осей',
            'pa': 'Позиционный угол большой оси (Север-Восток)',
            'brief': 'Средняя эффективная поверхностная яркость',
            'e_brief': 'Ошибка средней эффективной поверхностной яркости',
            'logdc': 'Логарифм скорректированного видимого диаметра (dc в 0.1 угл. мин)',
            'bt': 'Полная B-звездная величина',
            'e_bt': 'Ошибка полной B-звездная величина',
            'it': 'Полная I-звездная величина',
            'e_it': 'Ошибка полной I-звездная величина',
            'ut': 'Полная U-звездная величина',
            'e_ut': 'Ошибка полной U-звездной величины',
            'vt': 'Полная V-звездная величина',
            'e_vt': 'Ошибка полной V-звездной величины',
            'kt': 'Полная K-звездная величина',
            'e_kt': 'Ошибка полной K-звездной величины',
            'ube': 'Эффективный цвет U-B',
            'bve': 'Эффективный цвет B-V',
            'ubtc': 'Скорректированный полный цвет U-B',
            'bvtc': 'Скорректированный полный цвет B-V',
            'vmaxg': 'Видимая максимальная скорость вращения газа',
            'e_vmaxg': 'Ошибка видимой максимальной скорости вращения газа',
            'vmaxs': 'Видимая максимальная скорость вращения звезд',
            'e_vmaxs': 'Ошибка видимой максимальной скорости вращения звезд',
            'vdis': 'Центральная дисперсия скоростей',
            'e_vdis': 'Ошибка центральной дисперсии скоростей',
            'vrot': 'Максимальная скорость вращения, скорректированная на наклон',
            'e_vrot': 'Ошибка максимальной скорости вращения',
            'vrad': 'Гелиоцентрическая лучевая скорость (радио)',
            'e_vrad': 'Ошибка гелиоцентрической лучевой скорости (радио)',
            'vopt': 'Гелиоцентрическая лучевая скорость (оптическая)',
            'e_vopt': 'Ошибка гелиоцентрической лучевой скорости (оптическая)',
            'v': 'Средняя гелиоцентрическая лучевая скорость',
            'e_v': 'Ошибка средней гелиоцентрической лучевой скорости',
            'vlg': 'Лучевая скорость относительно Местной группы',
            'vgsr': 'Лучевая скорость относительно GSR',
            'vvir': 'Лучевая скорость, скорректированная на падение на Virgo',
            'v3k': 'Лучевая скорость относительно реликтового излучения',
            'm21': 'Поток линии 21 см в звездных величинах',
            'e_m21': 'Ошибка потока линии 21 см',
            'mfir': 'Звездная величина в дальнем ИК-диапазоне',
            'm21c': 'Скорректированный потока линии 21 см в звездных величинах',
            'hic': 'Индекс 21 см btc-m21c в звездных величинах',
            'ag': 'Галактическое поглощение в B-диапазоне',
            'ai': 'Внутреннее поглощение из-за наклона в B-диапазоне',
            'a21': 'Самопоглощение на линии 21 см',
            'incl': 'Наклон между лучом зрения и полярной осей галактики',
            'btc': 'Скорректированная полная B-звездная величина',
            'itc': 'Скорректированная полная I-звездная величина',
            'mg2': 'Центральный индекс Линка Mg2',
            'e_mg2': 'Ошибка центрального индекса Линка Mg2',
            'logavmm': 'Логарифм среднего значения',
            'e_logavmm': 'Ошибка логарифма среднего значения',
            'modz': 'Космологический модуль расстояния (от vvir с ΛCDM)',
            'e_modz': 'Ошибка космологического модуля расстояния',
            'mod0': 'Модуль расстояния от измерений расстояния',
            'e_mod0': 'Ошибка модуля расстояния от измерений расстояния',
            'mabs': 'Абсолютная B-звездная величина',
            'e_mabs': 'Ошибка абсолютной B-звездной величины',
            'modbest': 'Лучший модуль расстояния (комбинация mod0 и modz)',
            'e_modbest': 'Ошибка лучшего модуля расстояния',
            'bri25': 'Средняя поверхностная яркость внутри изофоты 25',
            'numtype': 'Числовой тип',
            'hptr': 'Указатель',
            'agnclass': 'Класс активности активного ядра',
            'f_astrom': 'Флаг точности астрометрии',
            'name': 'Название',
            'id': 'Идентификатор',
            'stage': 'Стадия Хаббла',
            'mtype': 'Морфологический тип',
            'b': 'Параметр бара',
        }

        col_lower = col_name.lower().strip()

        if col_lower in param_descriptions:
            ru_name = param_descriptions[col_lower]
        else:
            clean_col = re.sub(r'^e_', '', col_lower)
            if clean_col in param_descriptions:
                ru_name = f"Ошибка {param_descriptions[clean_col]}"
            else:
                ru_name = self.generate_param_description(col_name)

        return {'name': col_name, 'ru_name': ru_name, 'unit': ''}

    def generate_param_description(self, col_name):
        """Генерирует описание параметра на основе его имени"""
        col_lower = col_name.lower()

        if any(word in col_lower for word in ['mag', 'bt', 'vt', 'ut', 'it', 'jt', 'ht', 'kt', 'm21', 'mfir']):
            return f"Звездная величина ({col_name})"
        elif any(word in col_lower for word in ['flux', 'f_']):
            return f"Поток ({col_name})"
        elif any(word in col_lower for word in ['lum', 'l_']):
            return f"Светимость ({col_name})"
        elif any(word in col_lower for word in ['mass', 'm_']):
            return f"Масса ({col_name})"
        elif any(word in col_lower for word in ['vel', 'v_', 'w20', 'w50', 'vmax', 'vrot', 'vdis']):
            return f"Скорость ({col_name})"
        elif any(word in col_lower for word in ['rad', 'r_', 'd25', 'a25', 'b25', 'diameter']):
            return f"Радиус/размер ({col_name})"
        elif any(word in col_lower for word in ['e_', 'err', 'error']):
            clean_name = re.sub(r'^e_', '', col_lower)
            return f"Ошибка параметра {clean_name}"
        elif any(word in col_lower for word in ['pa', 'incl', 'ellip', 'angle']):
            return f"Геометрический параметр ({col_name})"
        elif any(word in col_lower for word in ['z', 'redshift', 'mod']):
            return f"Расстояние/красное смещение ({col_name})"
        elif any(word in col_lower for word in ['temp', 'teff']):
            return f"Температура ({col_name})"
        elif any(word in col_lower for word in ['metal', 'feh', 'oh', 'mg2']):
            return f"Металличность/спектральный индекс ({col_name})"
        elif any(word in col_lower for word in ['age', 'tau']):
            return f"Возраст ({col_name})"
        elif any(word in col_lower for word in ['sfr', 'sfr_']):
            return f"Скорость звездообразования ({col_name})"
        elif any(word in col_lower for word in ['dens', 'n_']):
            return f"Плотность ({col_name})"
        elif any(word in col_lower for word in ['log']):
            return f"Логарифмический параметр ({col_name})"
        elif any(word in col_lower for word in ['color', 'ube', 'bve', 'ubtc', 'bvtc']):
            return f"Цвет ({col_name})"
        elif any(word in col_lower for word in ['brightness', 'bri', 'sb']):
            return f"Поверхностная яркость ({col_name})"
        elif any(word in col_lower for word in ['extinction', 'ag', 'ai', 'a21']):
            return f"Поглощение/экстинкция ({col_name})"
        elif any(word in col_lower for word in ['coord', 'ra', 'dec', 'l2', 'b2', 'sgl', 'sgb']):
            return f"Координата ({col_name})"
        elif any(word in col_lower for word in ['type', 'bar', 'ring', 'multiple', 'compact']):
            return f"Морфологический параметр ({col_name})"
        elif any(word in col_lower for word in ['flag', 'f_']):
            return f"Флаг ({col_name})"
        elif any(word in col_lower for word in ['class', 'agn']):
            return f"Классификация ({col_name})"
        else:
            return f"Параметр {col_name}"

    def show_parameter_list_x(self):
        """Показать список параметров для выбора оси X"""
        self.show_parameter_list("x")

    def show_parameter_list_y(self):
        """Показать список параметров для выбора оси Y"""
        self.show_parameter_list("y")

    def show_parameter_list(self, axis):
        """Показать окно со списком параметров для выбора"""
        if not self.numeric_columns:
            messagebox.showinfo("Список параметров", "Нет доступных числовых параметров")
            return

        list_window = tk.Toplevel(self.root)
        list_window.title(f"Выбор параметра для оси {axis.upper()}")
        list_window.geometry("500x400")

        search_frame = ttk.Frame(list_window)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="Поиск:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.focus()

        list_frame = ttk.Frame(list_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        listbox = tk.Listbox(list_frame, font=("Arial", 10))
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)

        for col in self.numeric_columns:
            param_info = self.get_param_info(col)
            listbox.insert(tk.END, f"{col} - {param_info['ru_name']}")

        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        button_frame = ttk.Frame(list_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def select_parameter():
            selection = listbox.curselection()
            if selection:
                selected_text = listbox.get(selection[0])
                param_name = selected_text.split(' - ')[0]
                if axis == "x":
                    self.x_var.set(param_name)
                else:
                    self.y_var.set(param_name)
                list_window.destroy()

        def update_list(*args):
            search_term = search_var.get().lower()
            listbox.delete(0, tk.END)
            for col in self.numeric_columns:
                param_info = self.get_param_info(col)
                if search_term in col.lower() or search_term in param_info['ru_name'].lower():
                    listbox.insert(tk.END, f"{col} - {param_info['ru_name']}")

        ttk.Button(button_frame, text="Выбрать", command=select_parameter).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=list_window.destroy).pack(side=tk.LEFT, padx=5)

        search_var.trace('w', update_list)
        listbox.bind('<Double-Button-1>', lambda e: select_parameter())

    def reload_file(self):
        """Перезагрузка текущего файла"""
        if self.current_file_path:
            self.load_data()
            messagebox.showinfo("Успех", f"Файл {os.path.basename(self.current_file_path)} перезагружен")
        else:
            messagebox.showwarning("Предупреждение", "Нет загруженного файла для перезагрузки")

    def show_file_info(self):
        """Показать информацию о загруженном файле"""
        if self.df is None or self.df.empty:
            messagebox.showinfo("Информация о файле", "Файл не загружен")
            return

        info_window = tk.Toplevel(self.root)
        info_window.title("Информация о файле")
        info_window.geometry("600x400")

        text_widget = tk.Text(info_window, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(info_window, orient=tk.VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        info_text = "ИНФОРМАЦИЯ О ФАЙЛЕ\n"
        info_text += "=" * 50 + "\n\n"

        if self.current_file_path:
            info_text += f"Имя файла: {os.path.basename(self.current_file_path)}\n"
            info_text += f"Полный путь: {self.current_file_path}\n"
            info_text += f"Размер файла: {os.path.getsize(self.current_file_path) / 1024:.1f} KB\n\n"

        info_text += f"Размер данных: {self.df.shape[0]} строк × {self.df.shape[1]} столбцов\n"
        info_text += f"Числовых параметров: {len(self.numeric_columns)}\n"
        info_text += f"Названий галактик: {len(self.galaxy_names)}\n\n"

        info_text += "СТОЛБЦЫ ДАННЫХ:\n"
        info_text += "-" * 30 + "\n"
        for col in self.df.columns:
            non_null = self.df[col].notna().sum()
            param_info = self.get_param_info(col)
            info_text += f"{col}: {non_null} значений ({param_info['ru_name']})\n"

        info_text += f"\nПЕРВЫЕ 5 ГАЛАКТИК:\n"
        info_text += "-" * 30 + "\n"
        for i, name in enumerate(self.galaxy_names[:5]):
            info_text += f"{i + 1}. {name}\n"

        text_widget.insert(1.0, info_text)
        text_widget.configure(state='disabled')

    def search_galaxy(self):
        """Поиск галактики по названию"""
        search_term = self.search_var.get().strip()

        if not search_term:
            self.galaxy_combo['values'] = self.galaxy_names
            if self.galaxy_names:
                self.galaxy_combo.set(self.galaxy_names[0])
            messagebox.showinfo("Поиск", "Введите название галактики для поиска")
            return

        results = self.search_galaxies(search_term)

        if results:
            self.galaxy_combo['values'] = results
            self.galaxy_combo.set(results[0])
            messagebox.showinfo("Результаты поиска",
                                f"Найдено галактик: {len(results)}\nПервая: {results[0]}")
        else:
            messagebox.showinfo("Поиск", "Галактики не найдены")
            self.galaxy_combo['values'] = self.galaxy_names
            if self.galaxy_names:
                self.galaxy_combo.set(self.galaxy_names[0])

    def update_interface(self):
        """Обновление интерфейса в зависимости от типа графика и режима"""
        plot_type = self.plot_type.get()
        analysis_mode = self.analysis_mode.get()

        if plot_type == "histogram" or plot_type == "distribution":
            self.y_entry.configure(state='disabled')
            self.y_var.set('')
        elif plot_type in ["bivariate_histogram", "bivariate_3d_histogram"]:
            self.y_entry.configure(state='normal')
        else:
            self.y_entry.configure(state='normal')

        if analysis_mode == "single":
            self.galaxy_combo.configure(state='readonly')
            self.search_entry.configure(state='normal')
        else:
            self.galaxy_combo.configure(state='disabled')
            self.search_entry.configure(state='disabled')
            self.galaxy_var.set('')
            self.search_var.set('')

    def parse_parameter_expression(self, param_expr):
        """Парсит выражение параметра, может быть простым параметром или выражением"""
        if not param_expr or not param_expr.strip():
            return None

        expr = param_expr.strip()

        if expr in self.numeric_columns:
            return {
                'type': 'simple',
                'column': expr,
                'expression': expr
            }

        try:
            if any(op in expr for op in ['+', '-', '*', '/', '(', ')']):
                columns_in_expr = [col for col in self.numeric_columns if col in expr]

                if columns_in_expr:
                    return {
                        'type': 'expression',
                        'expression': expr,
                        'columns': columns_in_expr
                    }

            return {
                'type': 'unknown',
                'expression': expr,
                'columns': []
            }

        except:
            return {
                'type': 'unknown',
                'expression': expr,
                'columns': []
            }

    def get_parameter_data(self, param_expr):
        """Получает данные для параметра (простого или выражения)"""
        param_info = self.parse_parameter_expression(param_expr)

        if param_info is None:
            return pd.Series([], dtype=float)

        if param_info['type'] == 'simple':
            return self.get_numeric_data(param_info['column'])

        elif param_info['type'] == 'expression':
            results = []
            valid_indices = []

            safe_dict = {
                'abs': abs, 'min': min, 'max': max, 'sum': sum, 'len': len,
                'log': np.log, 'log10': np.log10, 'exp': np.exp, 'sqrt': np.sqrt,
                'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
                'pi': np.pi, 'e': np.e
            }

            for idx, row in self.df.iterrows():
                try:
                    row_data = {}
                    has_all_data = True

                    for col in param_info['columns']:
                        value = row[col]
                        if pd.isna(value):
                            has_all_data = False
                            break
                        row_data[col] = value

                    if not has_all_data:
                        continue

                    eval_dict = {**row_data, **safe_dict}
                    result = eval(param_info['expression'], {"__builtins__": {}}, eval_dict)

                    if pd.notna(result) and np.isfinite(result):
                        results.append(result)
                        valid_indices.append(idx)

                except (ZeroDivisionError, ValueError, TypeError, SyntaxError, NameError):
                    continue

            return pd.Series(results, index=valid_indices)

        return pd.Series([], dtype=float)

    def get_parameter_info(self, param_expr):
        """Возвращает информацию о параметре (простом или выражении)"""
        param_info = self.parse_parameter_expression(param_expr)

        if param_info is None:
            return {'name': param_expr, 'ru_name': f"Неизвестный параметр: {param_expr}", 'unit': ''}

        if param_info['type'] == 'simple':
            return self.get_param_info(param_info['column'])

        elif param_info['type'] == 'expression':
            col_descriptions = []
            for col in param_info['columns']:
                col_info = self.get_param_info(col)
                col_descriptions.append(col_info['ru_name'])

            return {
                'name': param_expr,
                'ru_name': f"Выражение: {param_expr}",
                'unit': 'расчетная величина'
            }

        else:
            return {
                'name': param_expr,
                'ru_name': f"Параметр: {param_expr}",
                'unit': ''
            }

    def get_galaxy_parameter_value(self, galaxy_data, param_expr):
        """Получает значение параметра (простого или выражения) для конкретной галактики"""
        param_info = self.parse_parameter_expression(param_expr)

        if param_info is None:
            return np.nan

        if param_info['type'] == 'simple':
            return galaxy_data[param_info['column']] if pd.notna(galaxy_data[param_info['column']]) else np.nan

        elif param_info['type'] == 'expression':
            try:
                row_data = {}
                for col in param_info['columns']:
                    value = galaxy_data[col]
                    if pd.isna(value):
                        return np.nan
                    row_data[col] = value

                safe_dict = {
                    'abs': abs, 'min': min, 'max': max, 'sum': sum, 'len': len,
                    'log': np.log, 'log10': np.log10, 'exp': np.exp, 'sqrt': np.sqrt,
                    'sin': np.sin, 'cos': np.cos, 'tan': np.tan,
                    'pi': np.pi, 'e': np.e
                }

                eval_dict = {**row_data, **safe_dict}
                result = eval(param_info['expression'], {"__builtins__": {}}, eval_dict)
                return result if pd.notna(result) and np.isfinite(result) else np.nan

            except (ZeroDivisionError, ValueError, TypeError, SyntaxError, NameError):
                return np.nan

        return np.nan

    def add_statistical_lines(self, ax, data, orientation='horizontal', color='red', alpha=0.7, linewidth=1.5):
        """Добавление статистических линий на график"""
        if len(data) < 2:
            return

        mean_val = np.mean(data)
        median_val = np.median(data)
        std_val = np.std(data)
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)

        legend_labels = []
        legend_lines = []

        if self.show_median.get():
            if orientation == 'horizontal':
                line = ax.axhline(y=median_val, color='red', linestyle='--', linewidth=linewidth, alpha=alpha)
            else:
                line = ax.axvline(x=median_val, color='red', linestyle='--', linewidth=linewidth, alpha=alpha)
            legend_labels.append(f'Медиана = {median_val:.3f}')
            legend_lines.append(line)

        if self.show_mean.get():
            if orientation == 'horizontal':
                line = ax.axhline(y=mean_val, color='green', linestyle=':', linewidth=linewidth, alpha=alpha)
            else:
                line = ax.axvline(x=mean_val, color='green', linestyle=':', linewidth=linewidth, alpha=alpha)
            legend_labels.append(f'Среднее = {mean_val:.3f}')
            legend_lines.append(line)

        if self.show_quartiles.get():
            if orientation == 'horizontal':
                line1 = ax.axhline(y=q1, color='orange', linestyle='-.', linewidth=linewidth, alpha=alpha)
                line2 = ax.axhline(y=q3, color='orange', linestyle='-.', linewidth=linewidth, alpha=alpha)
                ax.fill_between(ax.get_xlim(), q1, q3, color='orange', alpha=0.1)
            else:
                line1 = ax.axvline(x=q1, color='orange', linestyle='-.', linewidth=linewidth, alpha=alpha)
                line2 = ax.axvline(x=q3, color='orange', linestyle='-.', linewidth=linewidth, alpha=alpha)
                ax.fill_betweenx(ax.get_ylim(), q1, q3, color='orange', alpha=0.1)

            legend_labels.append(f'Q1 (25%) = {q1:.3f}')
            legend_labels.append(f'Q3 (75%) = {q3:.3f}')
            legend_lines.append(line1)
            legend_lines.append(line2)

        if self.show_std.get():
            if orientation == 'horizontal':
                line1 = ax.axhline(y=mean_val - std_val, color='purple', linestyle=':', linewidth=linewidth,
                                   alpha=alpha)
                line2 = ax.axhline(y=mean_val + std_val, color='purple', linestyle=':', linewidth=linewidth,
                                   alpha=alpha)
                ax.fill_between(ax.get_xlim(), mean_val - std_val, mean_val + std_val,
                                color='purple', alpha=0.1)
            else:
                line1 = ax.axvline(x=mean_val - std_val, color='purple', linestyle=':', linewidth=linewidth,
                                   alpha=alpha)
                line2 = ax.axvline(x=mean_val + std_val, color='purple', linestyle=':', linewidth=linewidth,
                                   alpha=alpha)
                ax.fill_betweenx(ax.get_ylim(), mean_val - std_val, mean_val + std_val,
                                 color='purple', alpha=0.1)

            legend_labels.append(f'Среднее ± σ = {mean_val:.3f} ± {std_val:.3f}')
            legend_lines.append(line1)

        if legend_labels:
            ax.legend(legend_lines, legend_labels, loc='best', fontsize=9)

    def show_bivariate_3d_settings(self):
        """Показать окно настроек 3D бивариантной гистограммы"""
        if self.plot_type.get() != "bivariate_3d_histogram":
            messagebox.showwarning("Предупреждение",
                                   "Для открытия этих настроек выберите тип графика '3D Бивариантная гистограмма'")
            return

        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки 3D бивариантной гистограммы")
        settings_window.geometry("500x750")
        settings_window.resizable(False, False)
        main_frame = ttk.Frame(settings_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Настройки 3D бивариантной гистограммы", font=('Arial', 12, 'bold')).pack(
            pady=(0, 20))

        # Валидатор для целых чисел
        validate_int_cmd = self.root.register(
            lambda P: P.isdigit() or P == "" or (P.startswith('-') and P[1:].isdigit()))

        # --- Настройки графика ---

        # Количество бинов
        bins_frame = ttk.Frame(main_frame)
        bins_frame.pack(fill=tk.X, pady=5)
        ttk.Label(bins_frame, text="Количество бинов по каждой оси (5-50):").pack(anchor=tk.W)
        bins_var = tk.StringVar(value=str(self.plot_settings.get('bivariate_bins', 20)))
        bins_spinbox = tk.Spinbox(bins_frame, from_=5, to=50, textvariable=bins_var, width=10, validate="key",
                                  validatecommand=(validate_int_cmd, "%P"))
        bins_spinbox.pack(anchor=tk.W, pady=5)

        # Цветовая карта
        cmap_frame = ttk.Frame(main_frame)
        cmap_frame.pack(fill=tk.X, pady=5)
        ttk.Label(cmap_frame, text="Цветовая карта:").pack(anchor=tk.W)
        cmap_var = tk.StringVar(value=self.plot_settings.get('bivariate_cmap', 'viridis'))
        cmaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis', 'hot', 'cool', 'spring', 'summer', 'autumn',
                 'winter', 'Blues', 'Greens', 'Reds', 'Purples', 'Oranges', 'YlOrBr', 'YlOrRd', 'OrRd', 'PuRd', 'RdPu',
                 'BuPu', 'GnBu', 'PuBu', 'YlGnBu', 'PuBuGn', 'BuGn', 'YlGn']
        cmap_combo = ttk.Combobox(cmap_frame, textvariable=cmap_var, values=cmaps, width=30, state='readonly')
        cmap_combo.pack(anchor=tk.W, pady=5)

        # Логарифмическая шкала для цвета
        logscale_frame = ttk.Frame(main_frame)
        logscale_frame.pack(fill=tk.X, pady=5)
        logscale_var = tk.BooleanVar(value=self.plot_settings.get('bivariate_logscale', True))
        ttk.Checkbutton(logscale_frame, text="Логарифмическая шкала для цвета (Z-ось)", variable=logscale_var).pack(
            anchor=tk.W)

        # Тип поверхности
        surface_frame = ttk.Frame(main_frame)
        surface_frame.pack(fill=tk.X, pady=5)
        ttk.Label(surface_frame, text="Тип поверхности:").pack(anchor=tk.W)
        surface_type_var = tk.StringVar(value=self.plot_settings.get('bivariate_3d_surface_type', 'bars'))
        surface_types = ['bars', 'surface', 'wireframe']
        surface_combo = ttk.Combobox(surface_frame, textvariable=surface_type_var, values=surface_types, width=15,
                                     state='readonly')
        surface_combo.pack(anchor=tk.W, pady=5)

        # Прозрачность поверхности
        alpha_frame = ttk.Frame(main_frame)
        alpha_frame.pack(fill=tk.X, pady=5)
        ttk.Label(alpha_frame, text="Прозрачность (0.0 - 1.0):").pack(anchor=tk.W)
        alpha_var = tk.StringVar(value=str(self.plot_settings.get('bivariate_3d_alpha', 0.8)))
        alpha_entry = ttk.Entry(alpha_frame, textvariable=alpha_var, width=10)
        alpha_entry.pack(anchor=tk.W, pady=5)

        # Азимут и Элевация (угол обзора)
        view_frame = ttk.LabelFrame(main_frame, text="Угол обзора 3D", padding=10)
        view_frame.pack(fill=tk.X, pady=10)

        azimuth_frame = ttk.Frame(view_frame)
        azimuth_frame.pack(fill=tk.X, pady=5)
        ttk.Label(azimuth_frame, text="Азимут (azim, -180..180):").pack(side=tk.LEFT, padx=(0, 10))
        azimuth_var = tk.StringVar(value=str(self.plot_settings.get('bivariate_3d_azimuth', 45)))
        azimuth_spinbox = tk.Spinbox(azimuth_frame, from_=-180, to=180, textvariable=azimuth_var, width=10,
                                     validate="key", validatecommand=(validate_int_cmd, "%P"))
        azimuth_spinbox.pack(side=tk.LEFT)

        elevation_frame = ttk.Frame(view_frame)
        elevation_frame.pack(fill=tk.X, pady=5)
        ttk.Label(elevation_frame, text="Элевация (elev, 0..90):").pack(side=tk.LEFT, padx=(0, 10))
        elevation_var = tk.StringVar(value=str(self.plot_settings.get('bivariate_3d_elevation', 30)))
        elevation_spinbox = tk.Spinbox(elevation_frame, from_=0, to=90, textvariable=elevation_var, width=10,
                                       validate="key", validatecommand=(validate_int_cmd, "%P"))
        elevation_spinbox.pack(side=tk.LEFT)

        # Ограничения по осям для 3D графика
        limits_frame = ttk.LabelFrame(main_frame, text="Ограничения осей для 3D (оставить пустым для автоматического)",
                                      padding=10)
        limits_frame.pack(fill=tk.X, pady=10)

        xlim_frame = ttk.Frame(limits_frame)
        xlim_frame.pack(fill=tk.X, pady=5)
        ttk.Label(xlim_frame, text="Ось X (мин, макс):").pack(side=tk.LEFT, padx=(0, 10))
        xlim_value = ""
        if self.plot_settings.get('bivariate_3d_xlim') is not None:
            xlim = self.plot_settings.get('bivariate_3d_xlim')
            xlim_value = f"{xlim[0]}, {xlim[1]}"
        xlim_var = tk.StringVar(value=xlim_value)
        xlim_entry = ttk.Entry(xlim_frame, textvariable=xlim_var, width=30)
        xlim_entry.pack(side=tk.LEFT)
        ttk.Label(xlim_frame, text="Пример: 0, 100", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT,
                                                                                                padx=(10, 0))

        ylim_frame = ttk.Frame(limits_frame)
        ylim_frame.pack(fill=tk.X, pady=5)
        ttk.Label(ylim_frame, text="Ось Y (мин, макс):").pack(side=tk.LEFT, padx=(0, 10))
        ylim_value = ""
        if self.plot_settings.get('bivariate_3d_ylim') is not None:
            ylim = self.plot_settings.get('bivariate_3d_ylim')
            ylim_value = f"{ylim[0]}, {ylim[1]}"
        ylim_var = tk.StringVar(value=ylim_value)
        ylim_entry = ttk.Entry(ylim_frame, textvariable=ylim_var, width=30)
        ylim_entry.pack(side=tk.LEFT)
        ttk.Label(ylim_frame, text="Пример: 0, 100", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT,
                                                                                                padx=(10, 0))

        zlim_frame = ttk.Frame(limits_frame)
        zlim_frame.pack(fill=tk.X, pady=5)
        ttk.Label(zlim_frame, text="Ось Z (мин, макс):").pack(side=tk.LEFT, padx=(0, 10))
        zlim_value = ""
        if self.plot_settings.get('bivariate_3d_zlim') is not None:
            zlim = self.plot_settings.get('bivariate_3d_zlim')
            zlim_value = f"{zlim[0]}, {zlim[1]}"
        zlim_var = tk.StringVar(value=zlim_value)
        zlim_entry = ttk.Entry(zlim_frame, textvariable=zlim_var, width=30)
        zlim_entry.pack(side=tk.LEFT)
        ttk.Label(zlim_frame, text="Пример: 0, 100", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT,
                                                                                                padx=(10, 0))

        # --- Определение функции Применить и добавление кнопки ---
        def apply_settings():
            """Применить настройки"""
            try:
                # Чтение значений из виджетов
                bins = int(bins_spinbox.get())
                cmap = cmap_var.get()
                logscale = logscale_var.get()
                azimuth = int(azimuth_spinbox.get())
                elevation = int(elevation_spinbox.get())
                surface_type = surface_type_var.get()
                alpha = float(alpha_var.get())

                # Парсирование ограничений осей
                xlim = None
                ylim = None
                zlim = None

                xlim_text = xlim_var.get().strip()
                if xlim_text:
                    parts = [x.strip() for x in xlim_text.split(',')]
                    if len(parts) == 2:
                        xlim = (float(parts[0]), float(parts[1]))
                    else:
                        messagebox.showerror("Ошибка", "Ограничение оси X должно быть в формате: мин, макс")
                        return

                ylim_text = ylim_var.get().strip()
                if ylim_text:
                    parts = [x.strip() for x in ylim_text.split(',')]
                    if len(parts) == 2:
                        ylim = (float(parts[0]), float(parts[1]))
                    else:
                        messagebox.showerror("Ошибка", "Ограничение оси Y должно быть в формате: мин, макс")
                        return

                zlim_text = zlim_var.get().strip()
                if zlim_text:
                    parts = [x.strip() for x in zlim_text.split(',')]
                    if len(parts) == 2:
                        zlim = (float(parts[0]), float(parts[1]))
                    else:
                        messagebox.showerror("Ошибка", "Ограничение оси Z должно быть в формате: мин, макс")
                        return

                # Проверки
                if not (5 <= bins <= 50):
                    messagebox.showerror("Ошибка", "Количество бинов должно быть от 5 до 50")
                    return
                if not (0.0 <= alpha <= 1.0):
                    messagebox.showerror("Ошибка", "Прозрачность должна быть от 0.0 до 1.0")
                    return

                # Обновление настроек
                self.plot_settings['bivariate_bins'] = bins
                self.plot_settings['bivariate_cmap'] = cmap
                self.plot_settings['bivariate_logscale'] = logscale
                self.plot_settings['bivariate_3d_azimuth'] = azimuth
                self.plot_settings['bivariate_3d_elevation'] = elevation
                self.plot_settings['bivariate_3d_surface_type'] = surface_type
                self.plot_settings['bivariate_3d_alpha'] = alpha
                self.plot_settings['bivariate_3d_xlim'] = xlim
                self.plot_settings['bivariate_3d_ylim'] = ylim
                self.plot_settings['bivariate_3d_zlim'] = zlim

                # Если график уже построен, перестраиваем его
                if self.current_plot_type == "bivariate_3d_histogram":
                    self.plot_data()  # Вызов перерисовки графика

                settings_window.destroy()
                messagebox.showinfo("Успех", "Настройки применены. График перестроен.")

            except ValueError:
                messagebox.showerror("Ошибка", "Некорректное значение. Убедитесь, что введены числа.")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Произошла ошибка при применении настроек: {e}")

        # --- Кнопки Применить/Отмена ---
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        # Добавлена кнопка "Применить"
        ttk.Button(button_frame, text="Применить", command=apply_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=settings_window.destroy).pack(side=tk.LEFT, padx=5)

        settings_window.mainloop()

    def show_bivariate_2d_settings(self):
        """Показать окно настроек 2D бивариантной гистограммы"""
        if self.plot_type.get() != "bivariate_histogram":
            messagebox.showwarning("Предупреждение",
                                   "Для открытия этих настроек выберите тип графика 'Бивариантная гистограмма'")
            return

        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки 2D бивариантной гистограммы")
        settings_window.geometry("480x380")
        settings_window.resizable(False, False)
        main_frame = ttk.Frame(settings_window, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Настройки 2D бивариантной гистограммы", font=('Arial', 12, 'bold')).pack(
            pady=(0, 10))

        # Валидатор для целых чисел
        validate_int_cmd = self.root.register(
            lambda P: P.isdigit() or P == "" or (P.startswith('-') and P[1:].isdigit()))

        # Количество бинов
        bins_frame = ttk.Frame(main_frame)
        bins_frame.pack(fill=tk.X, pady=5)
        ttk.Label(bins_frame, text="Количество бинов по каждой оси (5-200):").pack(anchor=tk.W)
        bins_default = self.plot_settings.get('bivariate_2d_bins', self.plot_settings.get('bivariate_bins', 20))
        bins_var = tk.StringVar(value=str(bins_default))
        bins_spinbox = tk.Spinbox(bins_frame, from_=5, to=200, textvariable=bins_var, width=10, validate="key",
                                  validatecommand=(validate_int_cmd, "%P"))
        bins_spinbox.pack(anchor=tk.W, pady=5)

        # Логарифмическая шкала для цвета (опционально)
        logscale_frame = ttk.Frame(main_frame)
        logscale_frame.pack(fill=tk.X, pady=5)
        logscale_var = tk.BooleanVar(value=self.plot_settings.get('bivariate_logscale', True))
        ttk.Checkbutton(logscale_frame, text="Логарифмическая шкала для цвета (Z-ось)", variable=logscale_var).pack(
            anchor=tk.W)

        # Ограничения по осям для 2D графика
        limits_frame = ttk.LabelFrame(main_frame, text="Ограничения осей (оставить пустым для автоматического)",
                                      padding=8)
        limits_frame.pack(fill=tk.X, pady=10)

        xlim_frame = ttk.Frame(limits_frame)
        xlim_frame.pack(fill=tk.X, pady=5)
        ttk.Label(xlim_frame, text="Ось X (мин, макс):").pack(side=tk.LEFT, padx=(0, 10))
        xlim_value = ""
        if self.plot_settings.get('bivariate_2d_xlim') is not None:
            xr = self.plot_settings.get('bivariate_2d_xlim')
            xlim_value = f"{xr[0]}, {xr[1]}"
        xlim_var = tk.StringVar(value=xlim_value)
        xlim_entry = ttk.Entry(xlim_frame, textvariable=xlim_var, width=30)
        xlim_entry.pack(side=tk.LEFT)
        ttk.Label(xlim_frame, text="Пример: 0, 100", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT,
                                                                                                padx=(10, 0))

        ylim_frame = ttk.Frame(limits_frame)
        ylim_frame.pack(fill=tk.X, pady=5)
        ttk.Label(ylim_frame, text="Ось Y (мин, макс):").pack(side=tk.LEFT, padx=(0, 10))
        ylim_value = ""
        if self.plot_settings.get('bivariate_2d_ylim') is not None:
            yr = self.plot_settings.get('bivariate_2d_ylim')
            ylim_value = f"{yr[0]}, {yr[1]}"
        ylim_var = tk.StringVar(value=ylim_value)
        ylim_entry = ttk.Entry(ylim_frame, textvariable=ylim_var, width=30)
        ylim_entry.pack(side=tk.LEFT)
        ttk.Label(ylim_frame, text="Пример: 0, 100", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT,
                                                                                                padx=(10, 0))

        # Применить
        def apply_2d_settings():
            try:
                bins = int(bins_spinbox.get())
                logscale = logscale_var.get()

                # Парсинг лимитов
                xlim = None
                ylim = None
                x_text = xlim_var.get().strip()
                if x_text:
                    parts = [p.strip() for p in x_text.split(',')]
                    if len(parts) == 2:
                        xlim = (float(parts[0]), float(parts[1]))
                    else:
                        messagebox.showerror("Ошибка", "Ограничение оси X должно быть в формате: мин, макс")
                        return

                y_text = ylim_var.get().strip()
                if y_text:
                    parts = [p.strip() for p in y_text.split(',')]
                    if len(parts) == 2:
                        ylim = (float(parts[0]), float(parts[1]))
                    else:
                        messagebox.showerror("Ошибка", "Ограничение оси Y должно быть в формате: мин, макс")
                        return

                if not (5 <= bins <= 200):
                    messagebox.showerror("Ошибка", "Количество бинов должно быть от 5 до 200")
                    return

                # Сохраняем
                self.plot_settings['bivariate_2d_bins'] = bins
                self.plot_settings['bivariate_logscale'] = logscale
                self.plot_settings['bivariate_2d_xlim'] = xlim
                self.plot_settings['bivariate_2d_ylim'] = ylim

                if self.plot_type.get() == 'bivariate_histogram':
                    self.plot_data()

                settings_window.destroy()
                messagebox.showinfo("Успех", "Настройки 2D применены")
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректное значение. Проверьте ввод")

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(btn_frame, text="Применить", command=apply_2d_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Отмена", command=settings_window.destroy).pack(side=tk.LEFT, padx=5)

        settings_window.mainloop()

    def show_plot_settings(self):
        """Показать окно настроек графика"""

    def show_distribution_settings(self):
        """Показать окно настроек для графика распределения (distribution)"""
        if self.plot_type.get() not in ("distribution", "histogram"):
            messagebox.showwarning("Предупреждение",
                                   "Для открытия этих настроек выберите тип графика 'Распределение' или 'Гистограмма'")
            return

        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки распределения")
        settings_window.geometry("420x220")
        settings_window.resizable(False, False)
        main_frame = ttk.Frame(settings_window, padding=12)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Настройки графика распределения", font=('Arial', 12, 'bold')).pack(pady=(0, 8))

        validate_int_cmd = self.root.register(lambda P: P.isdigit() or P == "")

        # Количество бинов
        bins_frame = ttk.Frame(main_frame)
        bins_frame.pack(fill=tk.X, pady=6)
        ttk.Label(bins_frame, text="Количество бинов:").pack(side=tk.LEFT)
        bins_default = self.plot_settings.get('distribution_bins', 20)
        bins_var = tk.StringVar(value=str(bins_default))
        bins_spin = tk.Spinbox(bins_frame, from_=5, to=200, textvariable=bins_var, width=8,
                               validate='key', validatecommand=(validate_int_cmd, '%P'))
        bins_spin.pack(side=tk.LEFT, padx=(8, 0))

        # Ограничения по оси X
        limits_frame = ttk.Frame(main_frame)
        limits_frame.pack(fill=tk.X, pady=6)
        ttk.Label(limits_frame, text="Ограничение по оси X (мин, макс):").pack(anchor=tk.W)
        xlim_value = ""
        if self.plot_settings.get('distribution_xlim') is not None:
            xr = self.plot_settings.get('distribution_xlim')
            xlim_value = f"{xr[0]}, {xr[1]}"
        xlim_var = tk.StringVar(value=xlim_value)
        xlim_entry = ttk.Entry(limits_frame, textvariable=xlim_var, width=30)
        xlim_entry.pack(anchor=tk.W, pady=(4, 0))
        ttk.Label(limits_frame, text="Оставьте пустым для автоматического диапазона", foreground='gray',
                  font=(None, 8)).pack(anchor=tk.W)

        def apply_dist_settings():
            try:
                bins = int(bins_spin.get())
                xlim_text = xlim_var.get().strip()
                xlim = None
                if xlim_text:
                    parts = [p.strip() for p in xlim_text.split(',')]
                    if len(parts) == 2:
                        xlim = (float(parts[0]), float(parts[1]))
                    else:
                        messagebox.showerror("Ошибка", "Ограничение оси X должно быть в формате: мин, макс")
                        return

                if bins < 5 or bins > 200:
                    messagebox.showerror("Ошибка", "Количество бинов должно быть от 5 до 200")
                    return

                self.plot_settings['distribution_bins'] = bins
                self.plot_settings['distribution_xlim'] = xlim

                # Перестраиваем график, если он сейчас выбран
                if self.plot_type.get() in ("distribution", "histogram"):
                    self.plot_data()

                settings_window.destroy()
                messagebox.showinfo("Успех", "Настройки распределения применены")
            except ValueError:
                messagebox.showerror("Ошибка", "Некорректные значения. Проверьте ввод")

        btns = ttk.Frame(main_frame)
        btns.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btns, text="Применить", command=apply_dist_settings).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Отмена", command=settings_window.destroy).pack(side=tk.LEFT, padx=6)

        settings_window.mainloop()

        settings_window = tk.Toplevel(self.root)
        settings_window.title("Настройки графика")
        settings_window.geometry("500x600")
        settings_window.resizable(False, False)

        # Создаем Notebook для вкладок
        notebook = ttk.Notebook(settings_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Вкладка 1: Масштабирование и оси
        scale_frame = ttk.Frame(notebook)
        notebook.add(scale_frame, text="Масштаб и оси")

        ttk.Label(scale_frame, text="Масштабирование осей:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        scale_frame_inner = ttk.Frame(scale_frame)
        scale_frame_inner.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(scale_frame_inner, text="Ось X:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        x_scale_var = tk.StringVar(value=self.plot_settings['xscale'])
        ttk.Combobox(scale_frame_inner, textvariable=x_scale_var, values=['linear', 'log', 'symlog'], width=15,
                     state='readonly').grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(scale_frame_inner, text="Ось Y:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        y_scale_var = tk.StringVar(value=self.plot_settings['yscale'])
        ttk.Combobox(scale_frame_inner, textvariable=y_scale_var, values=['linear', 'log', 'symlog'], width=15,
                     state='readonly').grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Separator(scale_frame).pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(scale_frame, text="Пределы осей:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        limits_frame = ttk.Frame(scale_frame)
        limits_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(limits_frame, text="X min:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        x_min_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=x_min_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(limits_frame, text="X max:").grid(row=0, column=2, sticky=tk.W, padx=(20, 5), pady=2)
        x_max_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=x_max_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=2)

        ttk.Label(limits_frame, text="Y min:").grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=2)
        y_min_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=y_min_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(limits_frame, text="Y max:").grid(row=1, column=2, sticky=tk.W, padx=(20, 5), pady=2)
        y_max_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=y_max_var, width=10).grid(row=1, column=3, sticky=tk.W, pady=2)

        auto_limits_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(scale_frame, text="Автоматические пределы осей", variable=auto_limits_var).pack(anchor=tk.W,
                                                                                                        padx=20, pady=5)

        # Вкладка 2: Легенда и подписи
        legend_frame = ttk.Frame(notebook)
        notebook.add(legend_frame, text="Легенда и подписи")

        ttk.Label(legend_frame, text="Настройки легенды:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        show_legend_var = tk.BooleanVar(value=self.plot_settings['show_legend'])
        ttk.Checkbutton(legend_frame, text="Показывать легенду", variable=show_legend_var).pack(anchor=tk.W, padx=20,
                                                                                                pady=5)

        legend_frame_inner = ttk.Frame(legend_frame)
        legend_frame_inner.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(legend_frame_inner, text="Позиция:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        legend_pos_var = tk.StringVar(value=self.plot_settings['legend_position'])
        ttk.Combobox(legend_frame_inner, textvariable=legend_pos_var,
                     values=['best', 'upper right', 'upper left', 'lower right', 'lower left', 'right', 'center left',
                             'center right', 'lower center', 'upper center', 'center'],
                     width=15, state='readonly').grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Separator(legend_frame).pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(legend_frame, text="Размеры шрифтов:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        # Функция для валидации числового ввода
        def validate_number_input(P):
            if P == "":
                return True
            try:
                value = float(P)
                if 0 <= value <= 100:  # Ограничиваем разумный диапазон
                    return True
                else:
                    return False
            except ValueError:
                return False

        validate_cmd = settings_window.register(validate_number_input)

        font_frame = ttk.Frame(legend_frame)
        font_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(font_frame, text="Заголовок:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        title_fontsize_var = tk.StringVar(value=str(self.plot_settings['title_fontsize']))
        ttk.Entry(font_frame, textvariable=title_fontsize_var, width=10,
                  validate="key", validatecommand=(validate_cmd, "%P")).grid(row=0, column=1, sticky=tk.W, pady=2)
        ttk.Label(font_frame, text="pt").grid(row=0, column=2, padx=(5, 0), sticky=tk.W)

        ttk.Label(font_frame, text="Подписи осей:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        label_fontsize_var = tk.StringVar(value=str(self.plot_settings['label_fontsize']))
        ttk.Entry(font_frame, textvariable=label_fontsize_var, width=10,
                  validate="key", validatecommand=(validate_cmd, "%P")).grid(row=1, column=1, sticky=tk.W, pady=2)
        ttk.Label(font_frame, text="pt").grid(row=1, column=2, padx=(5, 0), sticky=tk.W)

        ttk.Label(font_frame, text="Деления:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=2)
        tick_fontsize_var = tk.StringVar(value=str(self.plot_settings['tick_fontsize']))
        ttk.Entry(font_frame, textvariable=tick_fontsize_var, width=10,
                  validate="key", validatecommand=(validate_cmd, "%P")).grid(row=2, column=1, sticky=tk.W, pady=2)
        ttk.Label(font_frame, text="pt").grid(row=2, column=2, padx=(5, 0), sticky=tk.W)

        # Вкладка 3: Стиль и отображение
        style_frame = ttk.Frame(notebook)
        notebook.add(style_frame, text="Стиль и отображение")

        ttk.Label(style_frame, text="Настройки точек:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        points_frame = ttk.Frame(style_frame)
        points_frame.pack(fill=tk.X, padx=20, pady=5)

        ttk.Label(points_frame, text="Размер:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        point_size_var = tk.StringVar(value=str(self.plot_settings['point_size']))
        ttk.Entry(points_frame, textvariable=point_size_var, width=10,
                  validate="key", validatecommand=(validate_cmd, "%P")).grid(row=0, column=1, sticky=tk.W, pady=5)
        ttk.Label(points_frame, text="пикс.").grid(row=0, column=2, padx=(5, 0), sticky=tk.W)

        ttk.Label(points_frame, text="Прозрачность:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        point_alpha_var = tk.StringVar(value=str(self.plot_settings['point_alpha']))
        ttk.Entry(points_frame, textvariable=point_alpha_var, width=10,
                  validate="key", validatecommand=(validate_cmd, "%P")).grid(row=1, column=1, sticky=tk.W, pady=5)
        ttk.Label(points_frame, text="(0.0-1.0)").grid(row=1, column=2, padx=(5, 0), sticky=tk.W)

        ttk.Label(points_frame, text="Цвет:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        point_color_var = tk.StringVar(value=self.plot_settings['point_color'])
        color_combo = ttk.Combobox(points_frame, textvariable=point_color_var,
                                   values=['blue', 'red', 'green', 'purple', 'orange', 'brown', 'pink', 'gray', 'olive',
                                           'cyan', 'black', 'magenta', 'teal', 'navy', 'maroon', 'lime', 'aqua'],
                                   width=15, state='readonly')
        color_combo.grid(row=2, column=1, sticky=tk.W, pady=5)

        ttk.Separator(style_frame).pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(style_frame, text="Сетка:", font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))

        grid_frame = ttk.Frame(style_frame)
        grid_frame.pack(fill=tk.X, padx=20, pady=5)

        show_grid_var = tk.BooleanVar(value=self.plot_settings['grid'])
        ttk.Checkbutton(grid_frame, text="Показывать сетку", variable=show_grid_var).grid(row=0, column=0, sticky=tk.W,
                                                                                          pady=5)

        ttk.Label(grid_frame, text="Прозрачность:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=5)
        grid_alpha_var = tk.StringVar(value=str(self.plot_settings['grid_alpha']))
        ttk.Entry(grid_frame, textvariable=grid_alpha_var, width=10,
                  validate="key", validatecommand=(validate_cmd, "%P")).grid(row=1, column=1, sticky=tk.W, pady=5)
        ttk.Label(grid_frame, text="(0.0-1.0)").grid(row=1, column=2, padx=(5, 0), sticky=tk.W)

        # Кнопки сохранения/отмены
        button_frame = ttk.Frame(settings_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        def apply_settings():
            """Применить настройки"""
            try:
                # Проверяем и преобразуем все числовые значения
                title_fontsize = float(title_fontsize_var.get()) if title_fontsize_var.get() else 12
                label_fontsize = float(label_fontsize_var.get()) if label_fontsize_var.get() else 10
                tick_fontsize = float(tick_fontsize_var.get()) if tick_fontsize_var.get() else 9
                point_size = float(point_size_var.get()) if point_size_var.get() else 30
                point_alpha = float(point_alpha_var.get()) if point_alpha_var.get() else 0.7
                grid_alpha = float(grid_alpha_var.get()) if grid_alpha_var.get() else 0.3

                # Проверяем допустимые диапазоны
                if not (1 <= title_fontsize <= 50):
                    messagebox.showerror("Ошибка", "Размер шрифта заголовка должен быть от 1 до 50")
                    return
                if not (1 <= label_fontsize <= 30):
                    messagebox.showerror("Ошибка", "Размер шрифта подписей должен быть от 1 до 30")
                    return
                if not (1 <= tick_fontsize <= 20):
                    messagebox.showerror("Ошибка", "Размер шрифта делений должен быть от 1 до 20")
                    return
                if not (1 <= point_size <= 200):
                    messagebox.showerror("Ошибка", "Размер точек должен быть от 1 до 200")
                    return
                if not (0 <= point_alpha <= 1):
                    messagebox.showerror("Ошибка", "Прозрачность точек должна быть от 0.0 до 1.0")
                    return
                if not (0 <= grid_alpha <= 1):
                    messagebox.showerror("Ошибка", "Прозрачность сетки должна быть от 0.0 до 1.0")
                    return

                self.plot_settings.update({
                    'xscale': x_scale_var.get(),
                    'yscale': y_scale_var.get(),
                    'grid': show_grid_var.get(),
                    'grid_alpha': grid_alpha,
                    'point_size': int(point_size),
                    'point_alpha': point_alpha,
                    'point_color': point_color_var.get(),
                    'show_legend': show_legend_var.get(),
                    'legend_position': legend_pos_var.get(),
                    'title_fontsize': int(title_fontsize),
                    'label_fontsize': int(label_fontsize),
                    'tick_fontsize': int(tick_fontsize)
                })

                # Применяем настройки к текущему графику
                if self.current_canvas:
                    self.apply_plot_settings()

                settings_window.destroy()

            except ValueError as e:
                messagebox.showerror("Ошибка", f"Некорректное числовое значение: {e}")

        def reset_settings():
            """Сбросить настройки к значениям по умолчанию"""
            default_settings = {
                'xscale': 'linear',
                'yscale': 'linear',
                'grid': True,
                'grid_alpha': 0.3,
                'point_size': 30,
                'point_alpha': 0.7,
                'point_color': 'blue',
                'show_legend': True,
                'legend_position': 'best',
                'title_fontsize': 12,
                'label_fontsize': 10,
                'tick_fontsize': 9,
                'bivariate_bins': 20,
                'bivariate_cmap': 'viridis',
                'bivariate_logscale': True,
                'bivariate_3d_azimuth': 45,
                'bivariate_3d_elevation': 30,
                'bivariate_3d_surface_type': 'bars',
                'bivariate_3d_alpha': 0.8
            }

            self.plot_settings.update(default_settings)

            # Обновляем переменные в интерфейсе
            x_scale_var.set('linear')
            y_scale_var.set('linear')
            show_grid_var.set(True)
            grid_alpha_var.set('0.3')
            point_size_var.set('30')
            point_alpha_var.set('0.7')
            point_color_var.set('blue')
            show_legend_var.set(True)
            legend_pos_var.set('best')
            title_fontsize_var.set('12')
            label_fontsize_var.set('10')
            tick_fontsize_var.set('9')

        ttk.Button(button_frame, text="Применить", command=apply_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Сбросить", command=reset_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Отмена", command=settings_window.destroy).pack(side=tk.LEFT, padx=5)

    def apply_plot_settings(self):
        """Применить текущие настройки к графику"""
        if not self.current_canvas or not self.current_ax:
            return

        try:
            # Применяем масштабирование осей
            self.current_ax.set_xscale(self.plot_settings['xscale'])
            self.current_ax.set_yscale(self.plot_settings['yscale'])

            # Применяем настройки сетки
            if self.plot_settings['grid']:
                self.current_ax.grid(True, alpha=self.plot_settings['grid_alpha'])
            else:
                self.current_ax.grid(False)

            # Обновляем размеры шрифтов
            self.current_ax.title.set_fontsize(self.plot_settings['title_fontsize'])
            self.current_ax.xaxis.label.set_fontsize(self.plot_settings['label_fontsize'])
            self.current_ax.yaxis.label.set_fontsize(self.plot_settings['label_fontsize'])
            self.current_ax.tick_params(axis='both', labelsize=self.plot_settings['tick_fontsize'])

            # Обновляем настройки легенды
            if self.plot_settings['show_legend'] and self.current_ax.get_legend():
                self.current_ax.legend(loc=self.plot_settings['legend_position'])

            # Если есть scatter plot, обновляем его настройки
            if self.current_scatter:
                self.current_scatter.set_sizes([self.plot_settings['point_size']])
                self.current_scatter.set_alpha(self.plot_settings['point_alpha'])
                self.current_scatter.set_color(self.plot_settings['point_color'])

            self.current_canvas.draw_idle()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось применить настройки: {str(e)}")

    def plot_data(self):
        """Построение графика"""
        if self.df is None or self.df.empty:
            messagebox.showerror("Ошибка", "Нет загруженных данных. Пожалуйста, загрузите файл.")
            return

        x_col = self.x_var.get().strip()
        if not x_col:
            messagebox.showwarning("Предупреждение", "Введите параметр для оси X")
            return

        y_col = self.y_var.get().strip()
        plot_type = self.plot_type.get()
        analysis_mode = self.analysis_mode.get()

        if plot_type in ["scatter", "bivariate_histogram",
                         "bivariate_3d_histogram"] and analysis_mode == "all" and not y_col:
            messagebox.showwarning("Предупреждение", "Введите параметр для оси Y")
            return

        if analysis_mode == "single" and not self.galaxy_var.get():
            messagebox.showwarning("Предупреждение", "Выберите галактику для анализа")
            return

        # Очистка предыдущего графика
        for widget in self.figure_frame.winfo_children():
            widget.destroy()

        # Создание нового графика
        fig = plt.figure(figsize=(12, 6))

        success = False
        if analysis_mode == "all":
            if plot_type == "scatter":
                success = self.plot_scatter_all(x_col, y_col, fig)
            elif plot_type == "histogram":
                success = self.plot_histogram_all(x_col, fig)
            elif plot_type == "distribution":
                success = self.plot_distribution_all(x_col, fig)
            elif plot_type == "bivariate_histogram":  # Новый тип графика
                success = self.plot_bivariate_histogram_all(x_col, y_col, fig)
            elif plot_type == "bivariate_3d_histogram":  # Новый 3D тип графика
                success = self.plot_bivariate_3d_histogram_all(x_col, y_col, fig)
        else:  # Режим одной галактики
            if plot_type == "scatter":
                success = self.plot_single_galaxy_scatter(x_col, y_col, fig)
            elif plot_type == "histogram":
                success = self.plot_single_galaxy_histogram(x_col, fig)
            elif plot_type == "distribution":
                success = self.plot_single_galaxy_distribution(x_col, fig)
            elif plot_type in ["bivariate_histogram", "bivariate_3d_histogram"]:
                messagebox.showinfo("Информация", "Бивариантная гистограмма доступна только в режиме 'Все галактики'")
                return

        if success:
            # Сохраняем ссылки на текущий график
            self.current_fig = fig
            self.current_plot_type = plot_type

            # Встраивание графика в интерфейс
            self.current_canvas = FigureCanvasTkAgg(fig, self.figure_frame)
            self.current_canvas.draw()

            # Добавляем панель инструментов для масштабирования
            toolbar = NavigationToolbar2Tk(self.current_canvas, self.figure_frame)
            toolbar.update()
            self.current_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            # Применяем текущие настройки графика
            if plot_type != "bivariate_3d_histogram":  # Не применяем к 3D
                self.apply_plot_settings()

            # Добавляем обработчик кликов мыши для точечных графиков
            if plot_type == "scatter" and analysis_mode == "all":
                self.current_canvas.mpl_connect('button_press_event', self.on_plot_click)

            # Добавляем обработчик кликов для 2D гистограммы
            if plot_type == "bivariate_histogram" and analysis_mode == "all":
                if getattr(fig, 'setup_2d_histogram_handler', False):
                    ax = self.current_ax
                    self.current_canvas.mpl_connect('button_press_event',
                                                    lambda event: self.on_2d_histogram_click(event, ax))
        else:
            fig.clear()
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'Недостаточно данных для построения графика\nПроверьте правильность введенных параметров',
                    ha='center', va='center', transform=ax.transAxes, fontsize=12)
            ax.set_xticks([])
            ax.set_yticks([])

            self.current_canvas = FigureCanvasTkAgg(fig, self.figure_frame)
            self.current_canvas.draw()
            self.current_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def plot_bivariate_3d_histogram_all(self, x_col, y_col, fig):
        """Построение 3D бивариантной гистограммы для всех галактик"""
        x_data = self.get_parameter_data(x_col)
        y_data = self.get_parameter_data(y_col)

        common_idx = x_data.index.intersection(y_data.index)

        if len(common_idx) < 20:  # Для 3D гистограммы нужно больше точек
            messagebox.showwarning("Предупреждение",
                                   f"Недостаточно данных для построения 3D бивариантной гистограммы.\n"
                                   f"X: {len(x_data)} значений, Y: {len(y_data)} значений, "
                                   f"Общих: {len(common_idx)} (минимум 20)")
            return False

        x_vals = x_data.loc[common_idx]
        y_vals = y_data.loc[common_idx]

        # Сохраняем данные
        self.current_x_data = x_data.loc[common_idx]
        self.current_y_data = y_data.loc[common_idx]
        self.current_x_param = x_col
        self.current_y_param = y_col

        # Очищаем фигуру и создаем 3D axes
        fig.clear()
        ax = fig.add_subplot(111, projection='3d')
        self.current_ax = ax

        bins = self.plot_settings['bivariate_bins']
        cmap = plt.get_cmap(self.plot_settings['bivariate_cmap'])

        # Вычисляем 2D гистограмму
        hist, xedges, yedges = np.histogram2d(x_vals, y_vals, bins=bins)

        # Создаем координатную сетку
        xpos, ypos = np.meshgrid(xedges[:-1] + 0.25 * np.diff(xedges),
                                 yedges[:-1] + 0.25 * np.diff(yedges),
                                 indexing="ij")

        xpos = xpos.flatten()
        ypos = ypos.flatten()
        zpos = np.zeros_like(xpos)

        # Размеры столбцов
        dx = 0.5 * np.diff(xedges)[0]
        dy = 0.5 * np.diff(yedges)[0]
        dz = hist.flatten()

        # Применяем логарифмическую шкалу если нужно
        if self.plot_settings.get('bivariate_logscale', True):
            dz = np.log10(dz + 1)  # +1 чтобы избежать log(0)

        # Получаем тип поверхности из настроек
        surface_type = self.plot_settings.get('bivariate_3d_surface_type', 'bars')
        alpha = self.plot_settings.get('bivariate_3d_alpha', 0.8)

        # Сохраняем все данные для пересоздания при изменении лимитов
        ax.histogram_data = {
            'xpos': xpos.copy(),
            'ypos': ypos.copy(),
            'zpos': zpos.copy(),
            'dx': dx,
            'dy': dy,
            'dz': dz.copy(),
            'hist': hist.copy(),
            'xedges': xedges.copy(),
            'yedges': yedges.copy(),
            'dz_original': hist.flatten().copy(),
            'x_col': x_col,
            'y_col': y_col,
            'fig': fig,
            'bins': bins,
            'cmap': cmap,
            'alpha': alpha,
            'surface_type': surface_type,
            'log_scale': self.plot_settings.get('bivariate_logscale', True)
        }

        if surface_type == "bars":
            # 3D гистограмма в виде столбцов
            colors = cmap(dz / dz.max() if dz.max() > 0 else dz)

            # Получаем оригинальные значения гистограммы (до логарифмирования) для отображения на столбцах
            dz_original = hist.flatten()

            # Рисуем ВСЕ столбцы изначально
            ax.bar3d(xpos, ypos, zpos, dx, dy, dz, color=colors, alpha=alpha, edgecolor='black', linewidth=0.1)

            # Добавляем текстовые метки над столбцами с количеством объектов
            for i, (x, y, z, count) in enumerate(zip(xpos, ypos, dz, dz_original)):
                if count > 0:  # Показываем только для непустых столбцов
                    ax.text(x, y, z, f'{int(count)}', fontsize=7, ha='center', va='bottom')

        elif surface_type == "surface":
            # Поверхность
            X, Y = np.meshgrid(xedges[:-1] + 0.5 * np.diff(xedges),
                               yedges[:-1] + 0.5 * np.diff(yedges))
            Z = hist.T

            if self.plot_settings.get('bivariate_logscale', True):
                Z = np.log10(Z + 1)

            ax.plot_surface(X, Y, Z, cmap=cmap, alpha=alpha, linewidth=0, antialiased=True)

        elif surface_type == "wireframe":
            # Проволочная сетка
            X, Y = np.meshgrid(xedges[:-1] + 0.5 * np.diff(xedges),
                               yedges[:-1] + 0.5 * np.diff(yedges))
            Z = hist.T

            if self.plot_settings.get('bivariate_logscale', True):
                Z = np.log10(Z + 1)

            ax.plot_wireframe(X, Y, Z, color='blue', alpha=alpha, linewidth=0.5)

        # Устанавливаем угол обзора
        ax.view_init(elev=self.plot_settings['bivariate_3d_elevation'],
                     azim=self.plot_settings['bivariate_3d_azimuth'])

        # Получаем лимиты осей
        xlim = self.plot_settings.get('bivariate_3d_xlim')
        ylim = self.plot_settings.get('bivariate_3d_ylim')
        zlim = self.plot_settings.get('bivariate_3d_zlim')

        # Применяем ограничения по осям если они установлены
        if xlim is not None:
            ax.set_xlim(xlim)
        if ylim is not None:
            ax.set_ylim(ylim)
        if zlim is not None:
            ax.set_zlim(zlim)

        # Подписи осей
        x_info = self.get_parameter_info(x_col)
        y_info = self.get_parameter_info(y_col)

        ax.set_xlabel(f"{x_info['ru_name']}")
        ax.set_ylabel(f"{y_info['ru_name']}")

        if self.plot_settings.get('bivariate_logscale', True):
            ax.set_zlabel('log₁₀(Количество объектов + 1)')
        else:
            ax.set_zlabel('Количество объектов')

        title = f'3D Бивариантная гистограмма: {x_info["ru_name"]} vs {y_info["ru_name"]}\n'
        title += f'N={len(common_idx)}, бины={bins}×{bins}'
        ax.set_title(title)

        # Добавляем цветовую шкалу для поверхности
        if surface_type in ["surface", "wireframe"]:
            mappable = plt.cm.ScalarMappable(cmap=cmap)
            mappable.set_array(hist)
            cbar = fig.colorbar(mappable, ax=ax, shrink=0.5, aspect=5)
            if self.plot_settings.get('bivariate_logscale', True):
                cbar.set_label('log₁₀(Количество объектов + 1)')
            else:
                cbar.set_label('Количество объектов')

        return True

    def plot_bivariate_histogram_all(self, x_col, y_col, fig):
        """Построение двумерной (бивариантной) гистограммы для всех галактик"""
        x_data = self.get_parameter_data(x_col)
        y_data = self.get_parameter_data(y_col)

        common_idx = x_data.index.intersection(y_data.index)

        if len(common_idx) < 10:  # Для 2D гистограммы нужно больше точек
            messagebox.showwarning("Предупреждение",
                                   f"Недостаточно данных для построения бивариантной гистограммы.\n"
                                   f"X: {len(x_data)} значений, Y: {len(y_data)} значений, "
                                   f"Общих: {len(common_idx)} (минимум 10)")
            return False

        x_vals = x_data.loc[common_idx]
        y_vals = y_data.loc[common_idx]

        # Сохраняем данные
        self.current_x_data = x_data.loc[common_idx]
        self.current_y_data = y_data.loc[common_idx]
        self.current_x_param = x_col
        self.current_y_param = y_col

        # Очищаем фигуру и создаем новый axes
        fig.clear()
        ax = fig.add_subplot(111)
        self.current_ax = ax

        # Читаем настройки 2D (если заданы отдельно) — оставляем независимыми от 3D
        bins = self.plot_settings.get('bivariate_2d_bins', self.plot_settings.get('bivariate_bins', 20))
        cmap = plt.get_cmap(self.plot_settings.get('bivariate_cmap', 'viridis'))

        # Вычисляем диапазоны для бинов — используем заданные ограничения, если есть
        x_range = None
        y_range = None
        if self.plot_settings.get('bivariate_2d_xlim') is not None:
            x_range = tuple(self.plot_settings.get('bivariate_2d_xlim'))
        else:
            x_range = (float(x_vals.min()), float(x_vals.max()))

        if self.plot_settings.get('bivariate_2d_ylim') is not None:
            y_range = tuple(self.plot_settings.get('bivariate_2d_ylim'))
        else:
            y_range = (float(y_vals.min()), float(y_vals.max()))

        # Создаем бивариантную гистограмму
        if self.plot_settings.get('bivariate_logscale', True):
            norm = LogNorm()
        else:
            norm = Normalize()

        h = ax.hist2d(x_vals, y_vals, bins=bins, range=[x_range, y_range],
                      cmap=cmap, norm=norm, alpha=0.8)

        # Получаем данные гистограммы для добавления текста
        hist_data = h[0]  # матрица подсчётов
        xedges = h[1]  # границы по X
        yedges = h[2]  # границы по Y

        # Добавляем текстовые значения на каждый бин
        for i in range(len(xedges) - 1):
            for j in range(len(yedges) - 1):
                count = hist_data[i, j]
                if count > 0:  # Показываем только ненулевые значения
                    # Центр бина
                    x_center = (xedges[i] + xedges[i + 1]) / 2
                    y_center = (yedges[j] + yedges[j + 1]) / 2

                    # Цвет текста зависит от яркости фона
                    # Для светлого фона - тёмный текст, для тёмного - светлый
                    text_color = 'black' if count < (hist_data.max() / 2) else 'white'

                    ax.text(x_center, y_center, f'{int(count)}',
                            ha='center', va='center', fontsize=8,
                            color=text_color, weight='bold')

        # Добавляем цветовую шкалу (компактно) и подпись в зависимости от логшкалы
        cbar = fig.colorbar(h[3], ax=ax, shrink=0.8, pad=0.02)
        if self.plot_settings.get('bivariate_logscale', True):
            cbar.set_label('log₁₀(Количество объектов + 1)', fontsize=9)
        else:
            cbar.set_label('Количество объектов', fontsize=9)
        cbar.ax.tick_params(labelsize=8)

        # Подписи осей
        x_info = self.get_parameter_info(x_col)
        y_info = self.get_parameter_info(y_col)

        ax.set_xlabel(f"{x_info['ru_name']}")
        ax.set_ylabel(f"{y_info['ru_name']}")

        title = f'Бивариантная гистограмма: {x_info["ru_name"]} vs {y_info["ru_name"]}\n'
        title += f'N={len(common_idx)}, бины={bins}×{bins}'
        ax.set_title(title)
        ax.grid(True, alpha=self.plot_settings['grid_alpha'])

        # Добавляем статистику в заголовок
        try:
            corr = np.corrcoef(x_vals, y_vals)[0, 1]
            title += f', корреляция={corr:.3f}'
            ax.set_title(title)
        except:
            pass

        # Устанавливаем видимые лимиты осей (если заданы пользователем)
        try:
            ax.set_xlim(x_range)
            ax.set_ylim(y_range)
        except Exception:
            pass

        # Сохраняем данные гистограммы для обработки кликов
        # Составляем согласованный список имён галактик для common_idx
        galaxy_names_for_bin = []
        for idx in common_idx:
            try:
                # Попробуем интерпретовать индекс как позицию
                pos = int(idx)
                if 0 <= pos < len(self.galaxy_names):
                    galaxy_names_for_bin.append(self.galaxy_names[pos])
                else:
                    galaxy_names_for_bin.append(str(idx))
            except Exception:
                galaxy_names_for_bin.append(str(idx))

        ax.histogram_2d_data = {
            'x_vals': x_vals.values if hasattr(x_vals, 'values') else x_vals,
            'y_vals': y_vals.values if hasattr(y_vals, 'values') else y_vals,
            'x_range': x_range,
            'y_range': y_range,
            'bins': bins,
            'galaxy_names': galaxy_names_for_bin
        }

        # Устанавливаем флаг, что нужно подключить обработчик после создания canvas
        fig.setup_2d_histogram_handler = True

        return True

    def on_2d_histogram_click(self, event, ax):
        """Обработчик клика по 2D гистограмме - показывает галактики в бине"""
        if event.inaxes != ax or event.xdata is None or event.ydata is None:
            return

        hist_data = getattr(ax, 'histogram_2d_data', None)
        if hist_data is None:
            return

        x_vals = hist_data['x_vals']
        y_vals = hist_data['y_vals']
        x_range = hist_data['x_range']
        y_range = hist_data['y_range']
        bins = hist_data['bins']
        galaxy_names = hist_data['galaxy_names']

        # Определяем размер бина
        bin_width_x = (x_range[1] - x_range[0]) / bins
        bin_width_y = (y_range[1] - y_range[0]) / bins

        # Определяем, в какой бин упал клик
        clicked_bin_x = int((event.xdata - x_range[0]) / bin_width_x)
        clicked_bin_y = int((event.ydata - y_range[0]) / bin_width_y)

        # Проверяем границы
        if not (0 <= clicked_bin_x < bins and 0 <= clicked_bin_y < bins):
            return

        # Находим все галактики в этом бине
        bin_x_min = x_range[0] + clicked_bin_x * bin_width_x
        bin_x_max = x_range[0] + (clicked_bin_x + 1) * bin_width_x
        bin_y_min = y_range[0] + clicked_bin_y * bin_width_y
        bin_y_max = y_range[0] + (clicked_bin_y + 1) * bin_width_y

        # Создаём маску для значений в этом бине
        mask = (x_vals >= bin_x_min) & (x_vals < bin_x_max) & (y_vals >= bin_y_min) & (y_vals < bin_y_max)

        # Фильтруем галактики по маске
        galaxies_in_bin = [name for i, name in enumerate(galaxy_names) if i < len(mask) and mask[i]]

        if len(galaxies_in_bin) == 0:
            messagebox.showinfo("Информация", "В этом бине нет галактик")
            return

        # Создаём окно со списком галактик
        result_window = tk.Toplevel(self.root)
        result_window.title(f"Галактики в бине ({len(galaxies_in_bin)} объектов)")
        result_window.geometry("400x500")

        # Заголовок
        title_label = tk.Label(result_window,
                               text=f"Бин: X=[{bin_x_min:.3f}, {bin_x_max:.3f}], Y=[{bin_y_min:.3f}, {bin_y_max:.3f}]\n"
                                    f"Количество объектов: {len(galaxies_in_bin)}",
                               font=('Arial', 10, 'bold'), wraplength=380)
        title_label.pack(padx=10, pady=10)

        # Список с прокруткой
        frame = tk.Frame(result_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(frame, yscrollcommand=scrollbar.set, font=('Courier', 9))
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        # Добавляем галактики в список
        for i, galaxy_name in enumerate(galaxies_in_bin, 1):
            listbox.insert(tk.END, f"{i}. {galaxy_name}")

        # Кнопка копирования
        def copy_to_clipboard():
            text = '\n'.join(galaxies_in_bin)
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            messagebox.showinfo("Успех", f"Скопировано {len(galaxies_in_bin)} названий в буфер обмена")

        button_frame = tk.Frame(result_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Button(button_frame, text="Копировать в буфер", command=copy_to_clipboard).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Закрыть", command=result_window.destroy).pack(side=tk.LEFT, padx=5)

    def plot_scatter_all(self, x_col, y_col, fig):
        """Построение точечной диаграммы для всех галактик"""
        x_data = self.get_parameter_data(x_col)
        y_data = self.get_parameter_data(y_col)

        common_idx = x_data.index.intersection(y_data.index)

        if len(common_idx) < 5:
            messagebox.showwarning("Предупреждение",
                                   f"Недостаточно данных для построения графика.\n"
                                   f"X: {len(x_data)} значений, Y: {len(y_data)} значений, "
                                   f"Общих: {len(common_idx)}")
            return False

        x_vals = x_data.loc[common_idx]
        y_vals = y_data.loc[common_idx]

        # Сохраняем данные для обработки кликов
        self.current_x_data = x_data.loc[common_idx]
        self.current_y_data = y_data.loc[common_idx]
        self.current_x_param = x_col
        self.current_y_param = y_col

        # Очищаем фигуру и создаем новый axes
        fig.clear()
        ax = fig.add_subplot(111)
        self.current_ax = ax

        # Scatter plot с настройками из plot_settings
        self.current_scatter = ax.scatter(x_vals, y_vals,
                                          alpha=self.plot_settings['point_alpha'],
                                          s=self.plot_settings['point_size'],
                                          color=self.plot_settings['point_color'],
                                          edgecolors='white', linewidth=0.5, picker=True)

        # Линия тренда
        if len(common_idx) > 2:
            try:
                z = np.polyfit(x_vals, y_vals, 1)
                p = np.poly1d(z)
                corr_coef = np.corrcoef(x_vals, y_vals)[0, 1]
                ax.plot(x_vals, p(x_vals), "r--", alpha=0.8, linewidth=2,
                        label=f'Тренд (r={corr_coef:.2f})')
                ax.legend()
            except:
                pass

        # Добавляем статистические линии для оси Y
        if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
            self.add_statistical_lines(ax, y_vals, orientation='horizontal', alpha=0.7, linewidth=1.5)

        # Добавляем статистические линии для оси X (вертикальные)
        if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
            self.add_statistical_lines(ax, x_vals, orientation='vertical', alpha=0.5, linewidth=1.0)

        # Подписи осей
        x_info = self.get_parameter_info(x_col)
        y_info = self.get_parameter_info(y_col)

        ax.set_xlabel(f"{x_info['ru_name']}")
        ax.set_ylabel(f"{y_info['ru_name']}")

        # Добавляем подсказку о кликах
        title = f'{x_info["ru_name"]} vs {y_info["ru_name"]}\nN={len(common_idx)}'
        if len(common_idx) > 0:
            title += " (кликните на точку для информации о галактике)"

        ax.set_title(title)
        ax.grid(True, alpha=self.plot_settings['grid_alpha'])

        return True

    def plot_histogram_all(self, x_col, fig):
        """Построение гистограммы для всех галактик"""
        x_data = self.get_parameter_data(x_col)

        if len(x_data) < 5:
            messagebox.showwarning("Предупреждение",
                                   f"Недостаточно данных для построения гистограммы.\n"
                                   f"Найдено значений: {len(x_data)}")
            return False

        # Очищаем фигуру и создаем новый axes
        fig.clear()
        ax = fig.add_subplot(111)
        self.current_ax = ax

        # Гистограмма
        n, bins, patches = ax.hist(x_data, bins=15, alpha=0.7, color='skyblue',
                                   edgecolor='black', density=True)

        # Кривая плотности
        if len(x_data) > 5:
            try:
                from scipy.stats import gaussian_kde
                kde = gaussian_kde(x_data)
                x_range = np.linspace(x_data.min(), x_data.max(), 100)
                ax.plot(x_range, kde(x_range), 'r-', linewidth=2, alpha=0.8,
                        label='Плотность вероятности')
                ax.legend()
            except:
                pass

        # Добавляем статистические линии
        if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
            self.add_statistical_lines(ax, x_data, orientation='vertical', alpha=0.7, linewidth=1.5)

        x_info = self.get_parameter_info(x_col)
        ax.set_xlabel(f"{x_info['ru_name']}")
        ax.set_ylabel('Плотность вероятности')
        ax.set_title(f'Распределение {x_info["ru_name"]}\nN={len(x_data)}')
        ax.grid(True, alpha=self.plot_settings['grid_alpha'])

        return True

    def plot_distribution_all(self, x_col, fig):
        """Построение графика распределения с подсчетом галактик"""
        x_data = self.get_parameter_data(x_col)

        if len(x_data) < 5:
            messagebox.showwarning("Предупреждение",
                                   f"Недостаточно данных для построения распределения.\n"
                                   f"Найдено значений: {len(x_data)}")
            return False

        # Очищаем фигуру и создаем два подграфика
        fig.clear()
        ax1 = fig.add_subplot(121)
        ax2 = fig.add_subplot(122)
        self.current_ax = ax1  # Сохраняем ссылку на первый axes

        # Поддержка пользовательских настроек распределения: ограничение осей и авто-подбор бинов
        full_min = float(x_data.min())
        full_max = float(x_data.max())
        default_bins = self.plot_settings.get('distribution_bins', 20)

        # Если пользователь указал лимиты для распределения — используем их и фильтруем данные
        dist_xlim = self.plot_settings.get('distribution_xlim', None)
        if dist_xlim is not None:
            try:
                xmin, xmax = float(dist_xlim[0]), float(dist_xlim[1])
                # Фильтруем данные по заданным лимитам
                x_filtered = x_data[(x_data >= xmin) & (x_data <= xmax)]
                if len(x_filtered) < 5:
                    messagebox.showwarning("Предупреждение",
                                           "После применения ограничений данных недостаточно для построения распределения")
                    return False

                # Автоматически увеличиваем число бинов пропорционально сужению диапазона
                try:
                    ratio = (full_max - full_min) / (xmax - xmin)
                except Exception:
                    ratio = 1.0
                if ratio > 1.0:
                    bins_to_use = min(int(default_bins * ratio), 200)
                else:
                    bins_to_use = default_bins

                # Левый график: распределение значений (фильтрованные)
                n, bins, patches = ax1.hist(x_filtered, bins=bins_to_use, alpha=0.7, color='lightblue',
                                            edgecolor='black')
                # Применяем лимиты на оси
                try:
                    ax1.set_xlim((xmin, xmax))
                except Exception:
                    pass
            except Exception:
                # При ошибке парсинга — строим по всем данным
                n, bins, patches = ax1.hist(x_data, bins=default_bins, alpha=0.7, color='lightblue',
                                            edgecolor='black')
        else:
            # Левый график: распределение значений (весь диапазон)
            n, bins, patches = ax1.hist(x_data, bins=default_bins, alpha=0.7, color='lightblue',
                                        edgecolor='black')

        # Выбираем данные, которые отображаются (учитываем фильтр по диапазону)
        display_data = x_data
        if dist_xlim is not None and 'x_filtered' in locals():
            display_data = x_filtered

        # Добавляем статистические линии на гистограмму
        if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
            self.add_statistical_lines(ax1, display_data, orientation='vertical', alpha=0.7, linewidth=1.5)

        ax1.set_xlabel(f"{self.get_parameter_info(x_col)['ru_name']}")
        ax1.set_ylabel('Количество галактик')
        ax1.set_title(f'Распределение {self.get_parameter_info(x_col)["ru_name"]}\nN={len(display_data)}')
        ax1.grid(True, alpha=self.plot_settings['grid_alpha'])

        # Добавляем подписи количества над столбцами
        for i, (count, patch) in enumerate(zip(n, patches)):
            if count > 0:
                ax1.text(patch.get_x() + patch.get_width() / 2, count + 0.1,
                         f'{int(count)}', ha='center', va='bottom', fontsize=8)

        # Правый график: кумулятивное распределение
        sorted_data = np.sort(x_data)
        y_vals = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

        ax2.plot(sorted_data, y_vals, 'b-', linewidth=2, alpha=0.8)
        ax2.fill_between(sorted_data, y_vals, alpha=0.3, color='blue')

        # Правый график: кумулятивное распределение на отображаемых данных
        sorted_data = np.sort(display_data)
        y_vals = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

        ax2.plot(sorted_data, y_vals, 'b-', linewidth=2, alpha=0.8)
        ax2.fill_between(sorted_data, y_vals, alpha=0.3, color='blue')

        # Добавляем статистические линии на кумулятивное распределение
        if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
            self.add_statistical_lines(ax2, display_data, orientation='vertical', alpha=0.7, linewidth=1.5)

        ax2.set_xlabel(f"{self.get_parameter_info(x_col)['ru_name']}")
        ax2.set_ylabel('Кумулятивная доля галактик')
        ax2.set_title(f'Кумулятивное распределение\nN={len(display_data)}')
        ax2.grid(True, alpha=self.plot_settings['grid_alpha'])

        fig.tight_layout()
        return True

    def plot_single_galaxy_scatter(self, x_col, y_col, fig):
        """Построение точечного графика для конкретной галактики"""
        galaxy_name = self.galaxy_var.get()
        galaxy_data = self.get_galaxy_data(galaxy_name)

        if galaxy_data is None:
            messagebox.showerror("Ошибка", f"Не удалось найти данные для галактики: {galaxy_name}")
            return False

        try:
            x_data_all = self.get_parameter_data(x_col)
            y_data_all = self.get_parameter_data(y_col)

            x_val = self.get_galaxy_parameter_value(galaxy_data, x_col)
            y_val = self.get_galaxy_parameter_value(galaxy_data, y_col)

            if pd.isna(x_val) or pd.isna(y_val):
                messagebox.showwarning("Предупреждение",
                                       f"Отсутствуют данные для выбранных параметров у галактики {galaxy_name}")
                return False

            common_idx = x_data_all.index.intersection(y_data_all.index)

            fig.clear()
            ax = fig.add_subplot(111)
            self.current_ax = ax

            if len(common_idx) > 0:
                ax.scatter(x_data_all.loc[common_idx], y_data_all.loc[common_idx],
                           alpha=0.3, s=20, color='gray', label='Все галактики')

            ax.scatter(x_val, y_val, alpha=1.0, s=100, color='red',
                       edgecolors='black', linewidth=2, label=galaxy_name)

            if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
                self.add_statistical_lines(ax, y_data_all.loc[common_idx],
                                           orientation='horizontal', alpha=0.5, linewidth=1.0)
                self.add_statistical_lines(ax, x_data_all.loc[common_idx],
                                           orientation='vertical', alpha=0.5, linewidth=1.0)

            x_info = self.get_parameter_info(x_col)
            y_info = self.get_parameter_info(y_col)

            ax.set_xlabel(f"{x_info['ru_name']}")
            ax.set_ylabel(f"{y_info['ru_name']}")
            ax.set_title(f'{galaxy_name}\n{x_info["ru_name"]} vs {y_info["ru_name"]}')
            ax.grid(True, alpha=self.plot_settings['grid_alpha'])
            ax.legend()

            return True

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при построении графика: {e}")
            return False

    def plot_single_galaxy_histogram(self, x_col, fig):
        """Построение гистограммы для конкретной галактики"""
        galaxy_name = self.galaxy_var.get()
        galaxy_data = self.get_galaxy_data(galaxy_name)

        if galaxy_data is None:
            messagebox.showerror("Ошибка", f"Не удалось найти данные для галактики: {galaxy_name}")
            return False

        try:
            x_val = self.get_galaxy_parameter_value(galaxy_data, x_col)

            if pd.isna(x_val):
                messagebox.showwarning("Предупреждение",
                                       f"Отсутствуют данные для параметра {x_col} у галактики {galaxy_name}")
                return False

            x_all = self.get_parameter_data(x_col)

            if len(x_all) < 5:
                return False

            fig.clear()
            ax = fig.add_subplot(111)
            self.current_ax = ax

            # Применяем настройки распределения (лимиты и авто-подбор бинов) к гистограмме всех галактик
            default_bins = self.plot_settings.get('distribution_bins', 15)
            dist_xlim = self.plot_settings.get('distribution_xlim', None)
            if dist_xlim is not None:
                try:
                    xmin, xmax = float(dist_xlim[0]), float(dist_xlim[1])
                    x_all_filtered = x_all[(x_all >= xmin) & (x_all <= xmax)]
                    if len(x_all_filtered) < 5:
                        messagebox.showwarning("Предупреждение",
                                               "После применения ограничений данных недостаточно для построения гистограммы")
                        return False
                    # Рассчитываем увеличение числа бинов
                    full_min = float(x_all.min())
                    full_max = float(x_all.max())
                    try:
                        ratio = (full_max - full_min) / (xmax - xmin)
                    except Exception:
                        ratio = 1.0
                    bins_to_use = min(int(default_bins * ratio) if ratio > 1.0 else default_bins, 200)
                    n, bins, patches = ax.hist(x_all_filtered, bins=bins_to_use, alpha=0.3, color='gray',
                                               edgecolor='black', density=True, label='Все галактики')
                    try:
                        ax.set_xlim((xmin, xmax))
                    except Exception:
                        pass
                except Exception:
                    n, bins, patches = ax.hist(x_all, bins=default_bins, alpha=0.3, color='gray',
                                               edgecolor='black', density=True, label='Все галактики')
            else:
                n, bins, patches = ax.hist(x_all, bins=default_bins, alpha=0.3, color='gray',
                                           edgecolor='black', density=True, label='Все галактики')

            ax.axvline(x=x_val, color='red', linewidth=3, label=f'{galaxy_name} = {x_val:.3f}')

            # Статистические линии для отображаемых данных
            display_all = x_all
            if dist_xlim is not None and 'x_all_filtered' in locals():
                display_all = x_all_filtered
            if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
                self.add_statistical_lines(ax, display_all, orientation='vertical', alpha=0.7, linewidth=1.5)

            x_info = self.get_parameter_info(x_col)
            ax.set_xlabel(f"{x_info['ru_name']}")
            ax.set_ylabel('Плотность вероятности')
            ax.set_title(f'Распределение {x_info["ru_name"]}\nГалактика: {galaxy_name} | N={len(display_all)}')
            ax.grid(True, alpha=self.plot_settings['grid_alpha'])
            ax.legend()

            return True

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при построении гистограммы: {e}")
            return False

    def plot_single_galaxy_distribution(self, x_col, fig):
        """Построение графика распределения для конкретной галактики"""
        galaxy_name = self.galaxy_var.get()
        galaxy_data = self.get_galaxy_data(galaxy_name)

        if galaxy_data is None:
            messagebox.showerror("Ошибка", f"Не удалось найти данные для галактики: {galaxy_name}")
            return False

        try:
            x_val = self.get_galaxy_parameter_value(galaxy_data, x_col)

            if pd.isna(x_val):
                messagebox.showwarning("Предупреждение",
                                       f"Отсутствуют данные для параметра {x_col} у галактики {galaxy_name}")
                return False

            x_all = self.get_parameter_data(x_col)

            if len(x_all) < 5:
                return False

            fig.clear()
            ax1 = fig.add_subplot(121)
            ax2 = fig.add_subplot(122)
            self.current_ax = ax1

            # Применяем настройки распределения (лимиты и авто-подбор бинов) к гистограмме всех галактик
            default_bins = self.plot_settings.get('distribution_bins', 20)
            dist_xlim = self.plot_settings.get('distribution_xlim', None)
            if dist_xlim is not None:
                try:
                    xmin, xmax = float(dist_xlim[0]), float(dist_xlim[1])
                    x_all_filtered = x_all[(x_all >= xmin) & (x_all <= xmax)]
                    if len(x_all_filtered) < 5:
                        messagebox.showwarning("Предупреждение",
                                               "После применения ограничений данных недостаточно для построения гистограммы")
                        return False
                    full_min = float(x_all.min())
                    full_max = float(x_all.max())
                    try:
                        ratio = (full_max - full_min) / (xmax - xmin)
                    except Exception:
                        ratio = 1.0
                    bins_to_use = min(int(default_bins * ratio) if ratio > 1.0 else default_bins, 200)
                    n, bins, patches = ax1.hist(x_all_filtered, bins=bins_to_use, alpha=0.3, color='gray',
                                                edgecolor='black', label='Все галактики')
                    try:
                        ax1.set_xlim((xmin, xmax))
                    except Exception:
                        pass
                except Exception:
                    n, bins, patches = ax1.hist(x_all, bins=default_bins, alpha=0.3, color='gray',
                                                edgecolor='black', label='Все галактики')
            else:
                # Если не было фильтра — используем все данные
                display_all = x_all
                n, bins, patches = ax1.hist(x_all, bins=default_bins, alpha=0.3, color='gray',
                                            edgecolor='black', label='Все галактики')
                ax1.axvline(x=x_val, color='red', linewidth=3, label=f'{galaxy_name} = {x_val:.3f}')

                if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
                    self.add_statistical_lines(ax1, display_all, orientation='vertical', alpha=0.7, linewidth=1.5)

                ax1.set_xlabel(f"{self.get_parameter_info(x_col)['ru_name']}")
                ax1.set_ylabel('Количество галактик')
                ax1.set_title(
                    f'Распределение {self.get_parameter_info(x_col)["ru_name"]}\nГалактика: {galaxy_name} | N={len(display_all)}')
                ax1.grid(True, alpha=self.plot_settings['grid_alpha'])
                ax1.legend()

            for i, (count, patch) in enumerate(zip(n, patches)):
                if count > 0:
                    ax1.text(patch.get_x() + patch.get_width() / 2, count + 0.1,
                             f'{int(count)}', ha='center', va='bottom', fontsize=8)

            # Построение кумулятивного распределения на отображаемых данных
            if dist_xlim is not None and 'x_all_filtered' in locals():
                sorted_data = np.sort(x_all_filtered)
            else:
                sorted_data = np.sort(x_all)
            y_vals = np.arange(1, len(sorted_data) + 1) / len(sorted_data)

            ax2.plot(sorted_data, y_vals, 'b-', linewidth=2, alpha=0.8, label='Кумулятивное распределение')
            ax2.fill_between(sorted_data, y_vals, alpha=0.3, color='blue')

            idx = np.searchsorted(sorted_data, x_val)
            percentile = idx / len(sorted_data) if len(sorted_data) > 0 else 0.0

            ax2.axvline(x=x_val, color='red', linewidth=3, label=f'{galaxy_name}')
            ax2.axhline(y=percentile, color='red', linestyle='--', alpha=0.7)
            ax2.plot(x_val, percentile, 'ro', markersize=8)
            ax2.text(x_val, percentile, f'  {percentile * 100:.1f}%', va='center', color='red', fontweight='bold')

            if any([self.show_median.get(), self.show_mean.get(), self.show_quartiles.get(), self.show_std.get()]):
                self.add_statistical_lines(ax2, x_all, orientation='vertical', alpha=0.7, linewidth=1.5)

            ax2.set_xlabel(f"{self.get_parameter_info(x_col)['ru_name']}")
            ax2.set_ylabel('Кумулятивная доля галактик')
            ax2.set_title(f'Позиция {galaxy_name} в распределении\nПроцентиль: {percentile * 100:.1f}%')
            ax2.grid(True, alpha=self.plot_settings['grid_alpha'])
            ax2.legend()

            fig.tight_layout()
            return True

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при построении графика распределения: {e}")
            return False

    def show_extended_statistics(self):
        """Показать расширенную статистику в отдельном окне с вкладками"""
        if self.df is None or self.df.empty:
            messagebox.showinfo("Статистика", "Нет загруженных данных для анализа")
            return

        stats_window = tk.Toplevel(self.root)
        stats_window.title("Расширенная статистика данных")
        stats_window.geometry("900x700")

        notebook = ttk.Notebook(stats_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        general_frame = ttk.Frame(notebook)
        notebook.add(general_frame, text="Общая статистика")

        general_text = tk.Text(general_frame, wrap=tk.WORD)
        general_scrollbar = ttk.Scrollbar(general_frame, orient=tk.VERTICAL, command=general_text.yview)
        general_text.configure(yscrollcommand=general_scrollbar.set)

        general_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        general_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        current_frame = ttk.Frame(notebook)
        notebook.add(current_frame, text="Текущий график")

        current_text = tk.Text(current_frame, wrap=tk.WORD)
        current_scrollbar = ttk.Scrollbar(current_frame, orient=tk.VERTICAL, command=current_text.yview)
        current_text.configure(yscrollcommand=current_scrollbar.set)

        current_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        current_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        galaxy_frame = ttk.Frame(notebook)
        notebook.add(galaxy_frame, text="Выбранная галактика")

        galaxy_text = tk.Text(galaxy_frame, wrap=tk.WORD)
        galaxy_scrollbar = ttk.Scrollbar(galaxy_frame, orient=tk.VERTICAL, command=galaxy_text.yview)
        galaxy_text.configure(yscrollcommand=galaxy_scrollbar.set)

        galaxy_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        galaxy_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.fill_general_statistics(general_text)
        self.fill_current_graph_statistics(current_text)
        self.fill_galaxy_statistics(galaxy_text)

    def fill_general_statistics(self, text_widget):
        """Заполняет вкладку общей статистики"""
        stats_text = "ОБЩАЯ СТАТИСТИКА ДАННЫХ\n"
        stats_text += "=" * 80 + "\n"
        stats_text += f"Всего объектов: {len(self.df)}\n"
        stats_text += f"Числовых параметров: {len(self.numeric_columns)}\n"
        stats_text += f"Названий галактик: {len(self.galaxy_names)}\n\n"

        stats_text += "СТАТИСТИКА ПО БАЗОВЫМ ПАРАМЕТРАМ:\n"
        stats_text += "=" * 80 + "\n\n"

        for i, col in enumerate(self.numeric_columns[:10]):
            data = self.get_numeric_data(col)
            param_info = self.get_param_info(col)

            stats_text += f"{i + 1}. {param_info['ru_name']} ({col}):\n"
            stats_text += f"   Значений: {len(data)}\n"
            if len(data) > 0:
                stats_text += f"   Среднее: {data.mean():.6f} ± {data.std():.6f}\n"
                stats_text += f"   Медиана: {data.median():.6f}\n"
                stats_text += f"   Минимум: {data.min():.6f}\n"
                stats_text += f"   Максимум: {data.max():.6f}\n"
                stats_text += f"   Q1 (25%): {data.quantile(0.25):.6f}\n"
                stats_text += f"   Q3 (75%): {data.quantile(0.75):.6f}\n"
                stats_text += f"   IQR: {data.quantile(0.75) - data.quantile(0.25):.6f}\n"
                stats_text += f"   Коэф. вариации: {(data.std() / data.mean()) * 100 if data.mean() != 0 else np.inf:.2f}%\n"

            stats_text += "\n" + "-" * 60 + "\n\n"

        text_widget.insert(1.0, stats_text)
        text_widget.configure(state='disabled')

    def fill_current_graph_statistics(self, text_widget):
        """Заполняет вкладку статистики текущего графика"""
        x_col = self.x_var.get().strip()
        y_col = self.y_var.get().strip()
        plot_type = self.plot_type.get()

        stats_text = "СТАТИСТИКА ТЕКУЩЕГО ГРАФИКА\n"
        stats_text += "=" * 80 + "\n\n"

        if not x_col:
            stats_text += "График не построен. Введите параметры и постройте график.\n"
        else:
            x_data = self.get_parameter_data(x_col)
            x_info = self.get_parameter_info(x_col)

            stats_text += f"ОСЬ X: {x_info['ru_name']}\n"
            stats_text += "-" * 40 + "\n"
            stats_text += f"Выражение: {x_col}\n"
            stats_text += f"Количество значений: {len(x_data)}\n"
            if len(x_data) > 0:
                stats_text += f"Среднее: {x_data.mean():.6f} ± {x_data.std():.6f}\n"
                stats_text += f"Медиана: {x_data.median():.6f}\n"
                stats_text += f"Минимум: {x_data.min():.6f}\n"
                stats_text += f"Максимум: {x_data.max():.6f}\n"
                stats_text += f"Q1 (25%): {x_data.quantile(0.25):.6f}\n"
                stats_text += f"Q3 (75%): {x_data.quantile(0.75):.6f}\n\n"

            if (
                    plot_type == "scatter" or plot_type == "bivariate_histogram" or plot_type == "bivariate_3d_histogram") and y_col:
                y_data = self.get_parameter_data(y_col)
                common_idx = x_data.index.intersection(y_data.index)

                y_info = self.get_parameter_info(y_col)
                stats_text += f"ОСЬ Y: {y_info['ru_name']}\n"
                stats_text += "-" * 40 + "\n"
                stats_text += f"Выражение: {y_col}\n"
                stats_text += f"Количество значений: {len(y_data)}\n"
                if len(y_data) > 0:
                    stats_text += f"Среднее: {y_data.mean():.6f} ± {y_data.std():.6f}\n"
                    stats_text += f"Медиана: {y_data.median():.6f}\n"
                    stats_text += f"Минимум: {y_data.min():.6f}\n"
                    stats_text += f"Максимум: {y_data.max():.6f}\n"
                    stats_text += f"Q1 (25%): {y_data.quantile(0.25):.6f}\n"
                    stats_text += f"Q3 (75%): {y_data.quantile(0.75):.6f}\n\n"

                if len(common_idx) > 2:
                    x_common = x_data.loc[common_idx]
                    y_common = y_data.loc[common_idx]
                    corr = np.corrcoef(x_common, y_common)[0, 1]

                    stats_text += f"КОРРЕЛЯЦИОННЫЙ АНАЛИЗ\n"
                    stats_text += "-" * 40 + "\n"
                    stats_text += f"Коэффициент корреляции: {corr:.6f}\n"
                    stats_text += f"Количество пар: {len(common_idx)}\n"

                    try:
                        slope, intercept, r_value, p_value, std_err = stats.linregress(x_common, y_common)
                        stats_text += f"Наклон линии тренда: {slope:.6f}\n"
                        stats_text += f"Пересечение: {intercept:.6f}\n"
                        stats_text += f"R²: {r_value ** 2:.6f}\n"
                        stats_text += f"P-значение: {p_value:.6e}\n"
                    except:
                        stats_text += "Не удалось вычислить линейную регрессию\n"

        text_widget.insert(1.0, stats_text)
        text_widget.configure(state='disabled')

    def fill_galaxy_statistics(self, text_widget):
        """Заполняет вкладку статистики выбранной галактики"""
        galaxy_name = self.galaxy_var.get()
        galaxy_data = self.get_galaxy_data(galaxy_name)

        stats_text = f"ПОЛНАЯ СТАТИСТИКА ГАЛАКТИКИ: {galaxy_name}\n"
        stats_text += "=" * 80 + "\n\n"

        if galaxy_data is None:
            stats_text += f"Не удалось найти данные для галактики: {galaxy_name}\n"
        else:
            stats_text += "ОСНОВНЫЕ ПАРАМЕТРЫ:\n"
            stats_text += "=" * 80 + "\n\n"

            main_params = ['bt', 'vt', 'ut', 'it', 'v', 'vrad', 'vopt', 'logd25', 'logr25', 't']
            shown_count = 0

            for col in main_params:
                if col in self.df.columns:
                    value = galaxy_data[col]
                    if pd.notna(value):
                        param_info = self.get_param_info(col)
                        stats_text += f"{param_info['ru_name']} ({col}): {value:.6f}\n"

                        if col in self.numeric_columns:
                            all_data = self.get_numeric_data(col)
                            if len(all_data) > 0:
                                percentile = (all_data < value).mean() * 100
                                stats_text += f"  Процентиль среди всех галактик: {percentile:.1f}%\n"
                                stats_text += f"  Среднее по всем: {all_data.mean():.6f}\n"
                                stats_text += f"  Медиана по всем: {all_data.median():.6f}\n"
                                stats_text += f"  Отклонение от среднего: {(value - all_data.mean()) / all_data.std() if all_data.std() > 0 else 0:.2f}σ\n"

                        stats_text += "\n"
                        shown_count += 1

            if shown_count == 0:
                stats_text += "Нет данных по основным параметрам\n"

        text_widget.insert(1.0, stats_text)
        text_widget.configure(state='disabled')

    def export_plot(self):
        """Экспорт текущего графика"""
        try:
            if self.current_canvas is None:
                messagebox.showwarning("Предупреждение",
                                       "Нет активного графика для экспорта. Сначала постройте график.")
                return

            filename = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[
                    ("PNG files", "*.png"),
                    ("PDF files", "*.pdf"),
                    ("SVG files", "*.svg"),
                    ("JPEG files", "*.jpg"),
                    ("All files", "*.*")
                ],
                title="Сохранить график как"
            )

            if filename:
                figure = self.current_canvas.figure
                figure.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
                messagebox.showinfo("Успех", f"График сохранен как:\n{filename}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить график: {str(e)}")

    def exit_app(self):
        """Выход из приложения"""
        if messagebox.askokcancel("Выход", "Вы уверены, что хотите выйти?"):
            self.root.quit()
            self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = GalaxyAnalyzer(root)
    root.mainloop()