import os
import sys
import ctypes
import logging
import io
import re
import webbrowser
import json
import threading
import subprocess
from dataclasses import dataclass
from glob import glob
from subprocess import check_output

import wx
import wx.adv
from mutagen.mp4 import MP4, MP4Cover, MP4StreamInfoError, MP4FreeForm, AtomDataType
from PIL import Image

from kinopoisk import get_film_info, common_genres

ctypes.windll.shcore.SetProcessDpiAwareness(2)

VER = "0.2.4 Beta 1"

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]%(levelname)s:%(name)s:%(message)s', datefmt='%d.%m.%Y %H:%M:%S')
log = logging.getLogger("KL_Tag")

wildcard_pics = "Изображения (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp|"\
            "Все файлы (*.*)|*.*"
wildcard_png = "Изображения (*.png)|*.png|Все файлы (*.*)|*.*"


def convert_bytes(num, is_rate=False):
    for x in ['б', 'Кб', 'Мб', 'Гб', 'Тб']:
        if num < 1024.0:
            if is_rate:
                return f'{num:3.1f} {x}ит/с'
            else:
                return f'{num:3.1f} {x}'
        num /= 1024.0


def get_meta(file):
    ffprobe = get_resource_path("ffprobe.exe")
    if not os.path.isfile(ffprobe):
        log.error(f'Не наден файл: "{ffprobe}"!')
        return
    command = '{ffprobe} -v quiet -print_format json -show_format -show_streams "{file}"'
    output = check_output(command.format(ffprobe=ffprobe, file=file), shell=True).decode()
    out_json = json.loads(output)
    audio_streams = 0
    for strem in out_json['streams']:
        if strem['codec_type'] == 'audio':
            audio_streams += 1

    result = {}
    result['width'] = out_json['streams'][0]['width']
    result['height'] = out_json['streams'][0]['height']
    result['size'] = convert_bytes(int(out_json['format']['size']))
    result['bit_rate'] = convert_bytes(int(out_json['format']['bit_rate']), is_rate=True)
    result['audio_streams'] = audio_streams
    return result


@dataclass
class Mp4TagsClass:
    title: str = ""
    kpid: str = ""
    year: str = ""
    country: list | str = ""
    rating: str = ""
    directors: list | str = ""
    actors: list | str = ""
    description: str = ""
    long_descriplion: str = ""
    has_cover: bool = False
    genres: list | str = ""
    main_genre: str = ""


def read_from_buffer():
    text_data = wx.TextDataObject()
    if wx.TheClipboard.Open():
        success = wx.TheClipboard.GetData(text_data)
        wx.TheClipboard.Close()
    if success:
        return text_data.GetText()


def get_from_buffer():
    try:
        result = {}
        text: str = read_from_buffer()
        list = text.split('\n')
        result['title'] = re.findall(r"(.*)\s\(\d{4}\)", text)[0]
        result['year'] = list[list.index("Год производства") + 1]
        result['country'] = list[list.index("Страна") + 1].split(', ')
        result['director'] = list[list.index("Режиссер") + 1].split(', ')
        actors_start = list.index("В главных ролях") + 1
        for i in range(actors_start, len(list)):
            if list[i][0].isdigit():  # ищем следующую строку типа `15 актеров`
                actors_stop = i
                break
        # actors_stop = list.fi("В главных ролях") + 11
        result['actors'] = list[actors_start:actors_stop]
        if re.findall(r"Рейтинг Кинопоиска\s(\d+\.\d+)", text):
            result['rating'] = re.findall(r"Рейтинг Кинопоиска\s(\d+\.\d+)", text)[0]
            result['is_rating_kp'] = True
        elif re.findall(r"IMDb:\s(\d\.\d{2})", text):
            result['rating'] = re.findall(r"IMDb:\s(\d\.\d{2})", text)[0]
            result['is_rating_kp'] = False
        else:
            result['rating'] = ""
            result['is_rating_kp'] = True

        try:
            desc_start = list.index("Видно только вам") + 1
        except Exception as e:
            desc_start = list.index("Сиквелы, приквелы и ремейки") + 1

        desc_stop = list.index("Рейтинг фильма")
        result['description'] = "\n".join(list[desc_start:desc_stop]).strip("\n")
        return result
    except Exception as e:
        print(e)
        return


def image_to_file(image):
    """Return `image` as PNG file-like object."""
    image_file = io.BytesIO()
    image.save(image_file, format="PNG")
    return image_file


def get_resource_path(relative_path):
    '''
    Определение пути для запуска из автономного exe файла.
    Pyinstaller cоздает временную папку, путь в _MEIPASS.
    '''
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class CharValidator(wx.Validator):
    ''' Validates data as it is entered into the text controls. '''

    def __init__(self, flag):
        wx.Validator.__init__(self)
        self.flag = flag
        self.Bind(wx.EVT_CHAR, self.OnChar)

    def Clone(self):
        '''Required Validator method'''
        return CharValidator(self.flag)

    def Validate(self, win):
        return True

    def TransferToWindow(self):
        return True

    def TransferFromWindow(self):
        return True

    def OnChar(self, event):
        keycode = int(event.GetKeyCode())
        if keycode < 256:
            #print keycode
            key = chr(keycode)
            #print key
            if self.flag == 'no-alpha' and key.isalpha():
                return
            if self.flag == 'no-digit' and key.isdigit():
                return
        event.Skip()


class MyFrame(wx.Frame):

    def __init__(self, parent, title):
        super().__init__(parent, title=title, style=(wx.DEFAULT_FRAME_STYLE | wx.WANTS_CHARS) & ~(wx.MAXIMIZE_BOX))

        self.panel = wx.Panel(self)
        self.list_files = wx.ListBox(self.panel, size=self.FromDIP(wx.Size(350, 30)))
        self.Bind(wx.EVT_LISTBOX, self.onListClick, id=self.list_files.GetId())
        self.Bind(wx.EVT_LISTBOX_DCLICK, self.onListDoubleClick, id=self.list_files.GetId())
        self.tag_box_sizer = wx.StaticBoxSizer(wx.VERTICAL, self.panel)

        # title + year
        self.l_title = wx.StaticText(self.panel, label="Название:")
        self.t_title = wx.TextCtrl(self.panel, value="")
        self.l_year = wx.StaticText(self.panel, label="Год:")
        self.t_year = wx.TextCtrl(self.panel, value="", size=(70, 28))

        self.tag_box_title = wx.BoxSizer(orient=wx.HORIZONTAL)
        self.tag_box_title.Add(self.l_title, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_title.Add(self.t_title, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        self.tag_box_title.Add(self.l_year, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_title.Add(self.t_year, proportion=0, flag=wx.EXPAND)
        self.tag_box_sizer.Add(self.tag_box_title, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # country + rating
        self.l_country = wx.StaticText(self.panel, label="Страна:", size=self.l_title.Size)
        self.t_country = wx.TextCtrl(self.panel, value="")

        self.l_rating = wx.StaticText(self.panel, label="Рейтинг:")
        self.t_rating = wx.TextCtrl(self.panel, value="", size=(50, 28))
        self.choice = wx.Choice(self.panel, choices=["Кинопоиск", "IMDb"])
        self.choice.SetSelection(0)

        self.tag_box_country = wx.BoxSizer(orient=wx.HORIZONTAL)
        self.tag_box_country.Add(self.l_country, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.t_country, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.l_rating, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.t_rating, flag=wx.EXPAND | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.choice, flag=wx.ALIGN_CENTER)
        self.tag_box_sizer.Add(self.tag_box_country, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # genres
        self.l_genres = wx.StaticText(self.panel, label="Жанры:", size=self.l_title.Size)
        self.t_genres = wx.TextCtrl(self.panel, value="", size=self.t_country.Size)
        self.l_main_genre = wx.StaticText(self.panel, label="Основной жанр:")
        self.c_main_genre = wx.ComboBox(self.panel, value="", choices=[], size=(140, 28), style=wx.CB_DROPDOWN)
        self.tag_box_genres = wx.BoxSizer(orient=wx.HORIZONTAL)

        self.tag_box_genres.Add(self.l_genres, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_genres.Add(self.t_genres, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10)
        self.tag_box_genres.Add(self.l_main_genre, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_genres.Add(self.c_main_genre, proportion=0, flag=wx.EXPAND)
        self.tag_box_sizer.Add(self.tag_box_genres, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # director & kpid
        self.l_director = wx.StaticText(self.panel, label="Режиссер:", size=self.l_title.Size)
        self.t_director = wx.TextCtrl(self.panel, value="", size=self.t_country.Size)
        self.l_kpid = wx.StaticText(self.panel, label="Kinopoisk ID:")
        self.t_kpid = wx.TextCtrl(self.panel, value="", size=(140, 28), validator=CharValidator('no-alpha'))
        self.t_kpid.Bind(wx.EVT_TEXT, self.onKPIDChange)
        self.t_kpid.Bind(wx.EVT_TEXT_PASTE, self.onKPIDPaste)
        self.tag_box_director = wx.BoxSizer(orient=wx.HORIZONTAL)

        self.tag_box_director.Add(self.l_director, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.t_director, proportion=1, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.l_kpid, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.t_kpid, flag=wx.EXPAND)
        self.tag_box_sizer.Add(self.tag_box_director, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # actors
        self.l_actors = wx.StaticText(self.panel, label="Актеры:")
        self.t_actors = wx.TextCtrl(self.panel, wx.ID_ANY, style=wx.ALIGN_TOP | wx.TE_MULTILINE | wx.TE_WORDWRAP)
        self.t_actors.Bind(wx.EVT_TEXT_PASTE, self.TextPaste)

        # description
        self.l_description = wx.StaticText(self.panel, label="Описание:")
        self.t_description = wx.TextCtrl(self.panel, value="", style=wx.ALIGN_TOP | wx.TE_MULTILINE)

        self.tag_box_sizer.Add(self.l_actors, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.t_actors, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.l_description, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.t_description, proportion=1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # poster
        self.placeholder = Image.open(get_resource_path(R".\images\placeholder.png"))
        self.image = wx.StaticBitmap(self.panel, wx.ID_ANY, self.scale_picture(self.placeholder), size=self.FromDIP((200, 300)))
        self.image.Bind(wx.EVT_CONTEXT_MENU, self.OnPosterContextMenu)
        self.l_image_size = wx.StaticText(self.panel, label="Нет постера")
        self.b_paste = wx.Button(self.panel, wx.ID_ANY, label="Вставить из буфера", size=self.FromDIP((100, 25)))
        self.Bind(wx.EVT_BUTTON, self.onPaste, id=self.b_paste.GetId())
        self.b_openkp = wx.Button(self.panel, wx.ID_ANY, label="Открыть на Кинопоиске", size=self.FromDIP((100, 25)))
        self.Bind(wx.EVT_BUTTON, self.OpenOnKPClick, id=self.b_openkp.GetId())
        self.b_loadkp = wx.Button(self.panel, wx.ID_ANY, label="Загрузить из Кинопоиска", size=self.FromDIP((100, 25)))
        self.Bind(wx.EVT_BUTTON, self.onLoadKP, id=self.b_loadkp.GetId())
        self.b_opendir = wx.Button(self.panel, wx.ID_ANY, label="Открыть расположение", size=self.FromDIP((100, 25)))
        self.Bind(wx.EVT_BUTTON, self.onOpenDir, id=self.b_opendir.GetId())
        self.b_save = wx.Button(self.panel, wx.ID_ANY, label="Записать в файл", size=self.FromDIP((100, 25)))
        self.Bind(wx.EVT_BUTTON, self.onSaveTags, id=self.b_save.GetId())

        self.box1_h = wx.BoxSizer(orient=wx.HORIZONTAL)
        self.box2_v = wx.BoxSizer(orient=wx.VERTICAL)
        self.box1_h.Add(self.list_files, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.box2_v.Add(self.image, proportion=0, flag=wx.EXPAND, border=10)
        self.box2_v.Add(self.l_image_size, proportion=0, flag=wx.ALIGN_CENTER)
        self.box2_v.Add(self.b_paste, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box2_v.Add(self.b_loadkp, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box2_v.Add(self.b_openkp, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box2_v.Add(self.b_opendir, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box2_v.AddStretchSpacer(prop=1)
        self.box2_v.Add(self.b_save, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)

        self.box1_h.Add(self.tag_box_sizer, proportion=1, flag=wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box1_h.Add(self.box2_v, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.panel.SetSizer(self.box1_h)

        self.statusbar = self.CreateStatusBar(2, style=(wx.BORDER_DEFAULT) & ~(wx.STB_SHOW_TIPS))
        self.statusbar.SetStatusWidths([self.FromDIP(350), -1])
        self.statusbar.SetStatusText("")

        self.list_paths = []
        self.tags = Mp4TagsClass()
        self.OpenFiles()

    def onPaste(self, event):
        film_info = get_from_buffer()
        if not film_info:
            return
        self.tags.title = film_info['title']
        self.tags.year = film_info['year']
        self.tags.country = film_info['country']
        if film_info['rating'] and film_info['is_rating_kp']:
            self.tags.rating = film_info['rating']
        elif not film_info['is_rating_kp'] and film_info['rating']:
            self.tags.rating = "i" + film_info['rating']
        else:
            self.tags.rating = film_info['rating']
        self.tags.directors = film_info['director']
        self.tags.actors = film_info['actors']
        self.tags.description = film_info['description']
        self.ShowTags()

    def ReadTags(self, file_path) -> Mp4TagsClass | None:
        result = Mp4TagsClass()
        try:
            video = MP4(file_path)
        except Exception as error:
            log.error(f"Ошибка! Не удалось открыть файл ({error}): {os.path.basename(file_path)}")
            return result

        if "\xa9nam" in video:
            result.title = video["\xa9nam"][0]
        else:
            result.title = ""

        if "\xa9day" in video:
            result.year = video["\xa9day"][0]
        else:
            result.year = ""

        if "----:com.apple.iTunes:kpra" in video:
            result.rating = video["----:com.apple.iTunes:kpra"][0].decode()
        else:
            result.rating = ""

        if "----:com.apple.iTunes:countr" in video:
            result.country = video["----:com.apple.iTunes:countr"][0].decode().split(";")
        else:
            result.country = ""

        if "desc" in video:
            result.description = video["desc"][0]
        else:
            result.description = ""

        if "----:com.apple.iTunes:DIRECTOR" in video:
            result.directors = video["----:com.apple.iTunes:DIRECTOR"][0].decode().split(";")
        else:
            result.directors = ""

        if "----:com.apple.iTunes:Actors" in video:
            result.actors = video["----:com.apple.iTunes:Actors"][0].decode().split("\r\n")[1::2]
        else:
            result.actors = ""

        try:
            if Image.open(io.BytesIO(video["covr"][0])):
                result.cover = Image.open(io.BytesIO(video["covr"][0]))
                result.has_cover = True
            else:
                result.cover = self.placeholder
                result.has_cover = False
        except:
            result.cover = self.placeholder
            result.has_cover = False

        if "----:com.apple.iTunes:kpid" in video:
            result.kpid = video["----:com.apple.iTunes:kpid"][0].decode()
        else:
            result.kpid = ""

        if "----:com.apple.iTunes:genre" in video:
            result.genres = video["----:com.apple.iTunes:genre"][0].decode().split(";")
        else:
            result.genres = ""

        if "\xa9gen" in video:
            result.main_genre = video["\xa9gen"][0]
        else:
            result.main_genre = ""

        result.is_ok = True
        return result

    def ShowTags(self):
        self.t_title.ChangeValue(self.tags.title)
        self.t_year.ChangeValue(self.tags.year)
        self.t_country.ChangeValue(", ".join(self.tags.country))
        if self.tags.rating:
            if self.tags.rating[0] == "i":
                self.t_rating.ChangeValue(self.tags.rating[1:])
                self.choice.SetSelection(1)
            else:
                self.t_rating.ChangeValue(self.tags.rating)
                self.choice.SetSelection(0)
        else:
            self.t_rating.ChangeValue(self.tags.rating)
            self.choice.SetSelection(0)
        self.t_director.ChangeValue(", ".join(self.tags.directors))
        self.t_kpid.ChangeValue(self.tags.kpid)
        self.check_kpid()
        self.t_actors.ChangeValue(", ".join(self.tags.actors))  # doesn't generate wx.EVT_TEXT
        self.t_description.ChangeValue(self.tags.description)
        self.t_genres.ChangeValue(", ".join(self.tags.genres))
        self.c_main_genre.SetItems(self.tags.genres or common_genres)
        self.c_main_genre.SetValue(self.tags.main_genre)
        threading.Thread(target=self.ShowStatusbar).start()
        self.ShowPoster()

    def ShowPoster(self):
        if self.tags.has_cover:
            self.image.Bitmap = self.scale_picture(self.tags.cover)
            self.l_image_size.Label = f"{self.tags.cover.size[0]}×{self.tags.cover.size[1]}"
            self.panel.Layout()
        else:
            self.image.Bitmap = self.scale_picture(self.placeholder)
            self.l_image_size.Label = "Нет постера"
            self.panel.Layout()

    def ShowStatusbar(self):
        self.statusbar.SetStatusText(" Файлов: " + str(len(self.list_paths)), 0)
        fileinfo = get_meta(self.list_paths[self.list_files.GetSelection()])
        if fileinfo:
            self.statusbar.SetStatusText(
                " Размер: " + fileinfo['size'] + ", битрейт: " + fileinfo['bit_rate'] + ", разрешение: " + str(fileinfo['width']) + "×" +
                str(fileinfo['height']) + ", аудиотреков: " + str(fileinfo['audio_streams']), 1)

    def GetTags(self):
        self.tags.title = self.t_title.Value
        self.tags.year = self.t_year.Value
        self.tags.country = self.t_country.Value.split(", ")
        if self.choice.GetSelection() == 0:
            self.tags.rating = self.t_rating.Value
        elif self.choice.GetSelection() == 1 and self.t_rating.Value:
            self.tags.rating = "i" + self.t_rating.Value
        else:
            self.tags.rating = self.t_rating.Value
        self.tags.directors = self.t_director.Value.split(", ")
        self.tags.kpid = self.t_kpid.Value
        self.tags.actors = self.t_actors.Value.split(", ")
        self.tags.description = self.t_description.Value
        self.tags.genres = self.t_genres.Value.split(", ")
        self.tags.main_genre = self.c_main_genre.GetValue()

    def OpenFiles(self):
        if len(sys.argv) != 2:
            self.DisableInterface()
            return

        if os.path.isfile(sys.argv[1]):
            self.list_paths.append(sys.argv[1])
            self.list_files.AppendItems(os.path.basename(self.list_paths[0]))

        if os.path.isdir(sys.argv[1]):
            self.list_paths = glob(os.path.join(sys.argv[1], "*.mp4"))
            if not self.list_paths:
                self.DisableInterface()
                return
            for path in self.list_paths:
                self.list_files.AppendItems(os.path.basename(path))

        self.list_files.Select(0)
        self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
        if not self.tags.is_ok:
            self.ClearTags()
            self.DisableInterface()
            return
        self.EnableInterface()
        self.ShowTags()

    def onSaveTags(self, event):
        self.GetTags()
        file_path = self.list_paths[self.list_files.GetSelection()]
        try:
            video = MP4(file_path)
        except MP4StreamInfoError as error:
            wx.MessageDialog(None, "Ошибка! Не удалось открыть файл!\n({error})", "Ошибка!", wx.OK | wx.ICON_ERROR).ShowModal()
            log.error(f"Ошибка! Не удалось открыть файл ({error}): {os.path.basename(file_path)}")
            return False
        video["\xa9nam"] = self.tags.title  # title
        if self.tags.description:
            video["desc"] = self.tags.description  # description
            video["ldes"] = self.tags.description  # long description
        else:
            video["desc"] = " "  # description
            video["ldes"] = " "  # long description
        if self.tags.year:
            video["\xa9day"] = self.tags.year  # year

        if self.tags.has_cover:
            video["covr"] = [MP4Cover(image_to_file(self.tags.cover).getvalue(), imageformat=MP4Cover.FORMAT_PNG)]
        else:
            video["covr"] = b""

        video["----:com.apple.iTunes:DIRECTOR"] = MP4FreeForm((";".join(self.tags.directors)).encode(), AtomDataType.UTF8)
        bufferlist = []
        for item in self.tags.actors:
            bufferlist.append('')
            bufferlist.append(item)
        video["----:com.apple.iTunes:Actors"] = MP4FreeForm(("\r\n".join(bufferlist)).encode(), AtomDataType.UTF8)
        if self.tags.rating:
            video["----:com.apple.iTunes:kpra"] = MP4FreeForm(self.tags.rating.encode(), AtomDataType.UTF8)
        else:
            video["----:com.apple.iTunes:kpra"] = MP4FreeForm(("").encode(), AtomDataType.UTF8)
        if self.tags.country:
            video["----:com.apple.iTunes:countr"] = MP4FreeForm((";".join(self.tags.country)).encode(), AtomDataType.UTF8)
        if self.tags.kpid:
            video["----:com.apple.iTunes:kpid"] = MP4FreeForm((self.tags.kpid).encode(), AtomDataType.UTF8)
        if self.tags.genres:
            video["----:com.apple.iTunes:genre"] = MP4FreeForm((";".join(self.tags.genres)).encode(), AtomDataType.UTF8)
        if self.tags.main_genre:
            video["\xa9gen"] = self.tags.main_genre
        try:
            video.save()
        except Exception as error:
            wx.MessageDialog(None, f"Ошибка при сохранении тегов в файл!\n{error}", "Ошибка!", wx.OK | wx.ICON_ERROR).ShowModal()
            log.error(f"Ошибка при сохранении тегов в файл! ({error})!")
            return False
        return True

    def onListClick(self, event):
        self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
        if not self.tags.is_ok:
            self.ClearTags()
            self.DisableInterface()
            return
        self.EnableInterface()
        self.ShowTags()

    def TextPaste(self, event):
        text = read_from_buffer().strip(" \n")
        text = re.sub(r"\ \ +", "", text).replace("\n", ", ")
        self.t_actors.ChangeValue(text)

    def OnPosterContextMenu(self, event):
        menu = wx.Menu()
        item1 = wx.MenuItem(menu, wx.ID_ANY, "Добавить постер")
        self.Bind(wx.EVT_MENU, self.onAddPoster, id=item1.GetId())
        item2 = wx.MenuItem(menu, wx.ID_ANY, "Сохранить постер")
        self.Bind(wx.EVT_MENU, self.onSavePoster, id=item2.GetId())
        item3 = wx.MenuItem(menu, wx.ID_ANY, "Удалить постер")
        self.Bind(wx.EVT_MENU, self.onDelPoster, id=item3.GetId())

        menu.Append(item1)
        try:
            if self.tags.has_cover:
                menu.Append(item2)
                menu.AppendSeparator()
                menu.Append(item3)
            self.PopupMenu(menu)
            menu.Destroy()
        except AttributeError as e:
            return

    def scale_picture(self, picture: Image.Image):

        def PIL2wx(image):
            width, height = image.size
            return wx.Bitmap.FromBuffer(width, height, image.tobytes())

        bmp_source = PIL2wx(picture)
        bmp_source.SetScaleFactor(self.GetDPIScaleFactor())
        image = bmp_source.ConvertToImage()
        new_width, new_height = self.FromDIP((200, 300))
        image = image.Scale(new_width, new_height, quality=wx.IMAGE_QUALITY_HIGH)
        return image

    @staticmethod
    def image_cut(image: Image.Image):
        width, height = image.size
        # обрезка до соотношения сторон 1x1.5
        if width > (height / 1.5):
            image = image.crop((((width - height / 1.5) / 2), 0, ((width - height / 1.5) / 2) + height / 1.5, height))
        elif height > (1.5 * width):
            image = image.crop((0, ((height - width * 1.5) / 2), width, ((height + width * 1.5) / 2)))
        image.thumbnail((360, 540))
        return image

    def onAddPoster(self, event):
        with wx.FileDialog(self, "Открыть файл...", "", "", wildcard_pics, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            image_path = fileDialog.GetPath()
        cover = Image.open(image_path)
        cover = self.image_cut(cover)
        cover = cover.convert("RGB")
        self.tags.cover = cover
        self.tags.has_cover = True
        self.ShowPoster()

    def onSavePoster(self, event):
        with wx.FileDialog(self, "Сохранить файл...", "", "", wildcard_png, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            image_path = fileDialog.GetPath()
        if self.tags.has_cover:
            self.tags.cover.save(image_path)

    def onDelPoster(self, event):
        self.tags.cover = ""
        self.tags.has_cover = False
        self.ShowPoster()

    def ClearTags(self):
        self.tags.actors = ""
        self.tags.country = ""
        self.tags.description = ""
        self.tags.directors = ""
        self.tags.kpid = ""
        self.tags.title = ""
        self.tags.year = ""
        self.tags.long_descriplion = ""
        self.tags.rating = ""
        self.tags.has_cover = False
        self.ShowTags()

    def DisableInterface(self):
        self.t_title.Disable()
        self.t_actors.Disable()
        self.t_country.Disable()
        self.t_description.Disable()
        self.t_director.Disable()
        self.t_kpid.Disable()
        self.t_rating.Disable()
        self.t_year.Disable()
        self.b_save.Disable()
        self.b_paste.Disable()
        self.b_loadkp.Disable()
        self.b_openkp.Disable()
        self.b_opendir.Disable()
        self.choice.Disable()
        self.c_main_genre.Disable()
        self.t_genres.Disable()

    def EnableInterface(self):
        self.t_title.Enable()
        self.t_actors.Enable()
        self.t_country.Enable()
        self.t_description.Enable()
        self.t_director.Enable()
        self.t_kpid.Enable()
        self.t_rating.Enable()
        self.t_year.Enable()
        self.b_save.Enable()
        self.b_paste.Enable()
        self.b_loadkp.Enable()
        self.b_openkp.Enable()
        self.b_opendir.Enable()
        self.choice.Enable()
        self.c_main_genre.Enable()
        self.t_genres.Enable()

    def OpenOnKPClick(self, event):
        if self.t_kpid.GetValue():
            webbrowser.open(f'https://www.kinopoisk.ru/film/{self.t_kpid.GetValue()}/')

    def onKPIDChange(self, event):
        self.check_kpid()

    def check_kpid(self):
        if not self.t_kpid.GetValue():
            self.b_openkp.Disable()
            self.b_loadkp.Disable()
        else:
            self.b_openkp.Enable()
            self.b_loadkp.Enable()

    def onLoadKP(self, event):
        try:
            film_id = int(self.t_kpid.GetValue())
        except Exception as e:
            print(e)
            return
        self.tags.kpid = self.t_kpid.GetValue()

        film_info = get_film_info(film_id)
        if not film_info:
            return

        self.tags.title = film_info['title']
        self.tags.year = film_info['year']
        self.tags.country = film_info['country']
        if film_info['rating'] and film_info['is_rating_kp']:
            self.tags.rating = film_info['rating']
        elif not film_info['is_rating_kp'] and film_info['rating']:
            self.tags.rating = "i" + film_info['rating']
        else:
            self.tags.rating = film_info['rating']
        self.tags.directors = film_info['director']
        self.tags.actors = film_info['actors']
        self.tags.description = film_info['description']
        self.tags.genres = film_info['genres']
        self.tags.main_genre = film_info['main_genre']
        if film_info['cover']:
            cover = film_info['cover']
            cover = self.image_cut(cover)
            cover = cover.convert("RGB")
            self.tags.cover = cover
            self.tags.has_cover = True
        else:
            self.tags.cover = ""
            self.tags.has_cover = False
        self.ShowTags()
        self.ShowPoster()

    def onKPIDPaste(self, event):
        text = read_from_buffer().strip(" \n")
        id = re.search(r"KP~(\d+)", text)
        if id:
            self.t_kpid.ChangeValue(id.group(1))
            self.check_kpid()
            return
        self.t_kpid.ChangeValue(text)
        self.check_kpid()

    def onListDoubleClick(self, event):
        if self.list_files.GetSelection() != wx.NOT_FOUND:
            path = self.list_paths[self.list_files.GetSelection()]
            if os.path.isfile(path):
                subprocess.Popen(f'"{path}"', shell=True)

    def onOpenDir(self, event):
        path = self.list_paths[self.list_files.GetSelection()]
        if os.path.isfile(path):
            subprocess.Popen(f'explorer /select,"{path}"', shell=True)


def main():
    app = wx.App()
    top = MyFrame(None, title=f"Kinolist Tag Editor {VER}")
    top.SetIcon(wx.Icon(get_resource_path("./images/favicon.ico")))
    top.SetClientSize(top.FromDIP(wx.Size(1150, 600)))
    top.Centre()
    top.SetMinSize(top.Size)
    top.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
