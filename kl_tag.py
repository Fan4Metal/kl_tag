import os
import sys
import ctypes
import logging
import io
from dataclasses import dataclass
from glob import glob

import wx
import wx.adv
from mutagen.mp4 import MP4, MP4Cover, MP4StreamInfoError, MP4FreeForm, AtomDataType
from PIL import Image

ctypes.windll.shcore.SetProcessDpiAwareness(2)

VER = "0.1.0"

logging.basicConfig(level=logging.INFO, format='[%(asctime)s]%(levelname)s:%(name)s:%(message)s', datefmt='%d.%m.%Y %H:%M:%S')
log = logging.getLogger("KL Tag")


@dataclass
class Mp4TagsClass:
    title: str
    kpid: str
    year: str
    country: list
    rating: str
    directors: list
    actors: list
    description: str
    long_descriplion: str
    cover: Image.Image


def PIL2wx(image):
    width, height = image.size
    return wx.Bitmap.FromBuffer(width, height, image.tobytes())


class MyFrame(wx.Frame):

    def __init__(self, parent, title):
        super().__init__(parent, title=title, style=(wx.DEFAULT_FRAME_STYLE | wx.WANTS_CHARS) & ~(wx.MAXIMIZE_BOX))

        self.panel = wx.Panel(self)
        self.list_files = wx.ListBox(self.panel, size=self.FromDIP(wx.Size(200, 30)))
        self.Bind(wx.EVT_LISTBOX, self.ListClick, id=self.list_files.GetId())
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
        self.t_country = wx.TextCtrl(self.panel, value="", size=(250, 28))
        self.l_rating = wx.StaticText(self.panel, label="Рейтинг:")
        self.t_rating = wx.TextCtrl(self.panel, value="", size=(50, 28))
        self.choice = wx.Choice(self.panel, choices=["Кинопоиск", "IMDB"])
        self.choice.SetSelection(0)

        self.tag_box_country = wx.BoxSizer(orient=wx.HORIZONTAL)
        self.tag_box_country.Add(self.l_country, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.t_country, proportion=1, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.l_rating, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.t_rating, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_country.Add(self.choice, flag=wx.ALIGN_CENTER)
        self.tag_box_sizer.Add(self.tag_box_country, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # director
        self.l_director = wx.StaticText(self.panel, label="Режиссер:", size=self.l_title.Size)
        self.t_director = wx.TextCtrl(self.panel, value="", size=(250, 28))
        self.tag_box_director = wx.BoxSizer(orient=wx.HORIZONTAL)

        self.tag_box_director.Add(self.l_director, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.t_director, proportion=1, flag=wx.ALIGN_CENTER)
        self.tag_box_sizer.Add(self.tag_box_director, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # actors
        self.l_actors = wx.StaticText(self.panel, label="Актеры:")
        self.t_actors = wx.TextCtrl(self.panel, wx.ID_ANY, style=wx.ALIGN_TOP | wx.TE_MULTILINE | wx.TE_WORDWRAP)

        # description
        self.l_description = wx.StaticText(self.panel, label="Описание:")
        self.t_description = wx.TextCtrl(self.panel, value="", style=wx.ALIGN_TOP | wx.TE_MULTILINE)

        self.tag_box_sizer.Add(self.l_actors, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.t_actors, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.l_description, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.t_description, proportion=1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # poster
        bmp_source = wx.Bitmap("./images/placeholder.png", wx.BITMAP_TYPE_PNG)
        image = bmp_source.ConvertToImage()
        bmp_converted = wx.Bitmap(image.Scale(self.FromDIP(200), self.FromDIP(300)))
        self.image = wx.StaticBitmap(self.panel, wx.ID_ANY, bmp_converted, size=self.FromDIP((200, 300)))
        self.l_image_size = wx.StaticText(self.panel, label=f"{bmp_source.Size[0]}×{bmp_source.Size[1]}")
        self.b_save = wx.Button(self.panel, wx.ID_OK, label="Сохранить", size=self.FromDIP((100, 25)))

        self.box1_h = wx.BoxSizer(orient=wx.HORIZONTAL)
        self.box2_v = wx.BoxSizer(orient=wx.VERTICAL)
        self.box1_h.Add(self.list_files, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.box2_v.Add(self.image, proportion=0, flag=wx.EXPAND, border=10)
        self.box2_v.Add(self.l_image_size, proportion=0, flag=wx.ALIGN_CENTER, border=10)
        self.box2_v.AddStretchSpacer(prop=1)
        self.box2_v.Add(self.b_save, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)

        self.box1_h.Add(self.tag_box_sizer, proportion=1, flag=wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box1_h.Add(self.box2_v, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.panel.SetSizer(self.box1_h)

        self.list_paths = []
        self.OpenFiles()

    def ReadTags(self, file_path) -> Mp4TagsClass | None:
        try:
            video = MP4(file_path)
        except Exception as error:
            log.error(f"Ошибка! Не удалось открыть файл ({error}): {os.path.basename(file_path)}")
            return None
        result = Mp4TagsClass
        # try:

        try:
            if video["\xa9nam"][0]:
                result.title = video["\xa9nam"][0]
            else:
                result.title = ""
        except:
            result.title = ""

        try:
            if video["\xa9day"][0]:
                result.year = video["\xa9day"][0]
            else:
                result.year = ""
        except:
            result.year = ""

        try:
            if video["----:com.apple.iTunes:kpra"][0].decode():
                result.rating = video["----:com.apple.iTunes:kpra"][0].decode()
            else:
                result.rating = ""
        except:
            result.rating = ""

        try:
            if video["----:com.apple.iTunes:countr"][0].decode().split(";"):
                result.country = video["----:com.apple.iTunes:countr"][0].decode().split(";")
            else:
                result.country = ""
        except:
            result.country = ""

        try:
            if video["desc"][0]:
                result.description = video["desc"][0]
            else:
                result.description = ""
        except:
            result.description = ""

        try:
            if video["----:com.apple.iTunes:DIRECTOR"][0].decode().split(";"):
                result.directors = video["----:com.apple.iTunes:DIRECTOR"][0].decode().split(";")
            else:
                result.directors = ""
        except:
            result.directors = ""

        try:
            if video["----:com.apple.iTunes:Actors"][0].decode().split("\r\n")[1::2]:
                result.actors = video["----:com.apple.iTunes:Actors"][0].decode().split("\r\n")[1::2]
            else:
                result.actors = ""
        except:
            result.actors = ""

        try:
            if Image.open(io.BytesIO(video["covr"][0])):
                result.cover = Image.open(io.BytesIO(video["covr"][0]))
            else:
                result.cover = Image.open(".\images\placeholder.png")
        except:
            result.cover = Image.open(".\images\placeholder.png")

        try:
            if video["----:com.apple.iTunes:kpid"][0].decode():
                result.kpid = video["----:com.apple.iTunes:kpid"][0].decode()
            else:
                result.kpid = ""
        except:
            result.kpid = ""

        # except Exception as e:
        #     return None
        return result

    def ShowTags(self, tags: Mp4TagsClass):
        self.t_title.Value = tags.title
        self.t_year.Value = tags.year
        self.t_country.Value = ", ".join(tags.country)
        self.t_rating.Value = tags.rating
        self.t_director.Value = ", ".join(tags.directors)
        self.t_actors.Value = ", ".join(tags.actors)
        self.t_description.Value = tags.description
        self.image.Bitmap = self.scale_picture(tags.cover)
        self.l_image_size.Label = f"{tags.cover.size[0]}×{tags.cover.size[1]}"

    def scale_picture(self, picture: Image.Image):
        bmp_source = wx.Bitmap(PIL2wx(picture))
        image = bmp_source.ConvertToImage()
        return wx.Bitmap(image.Scale(self.FromDIP(200), self.FromDIP(300)))

    def OpenFiles(self):
        if len(sys.argv) != 2:
            return
        if os.path.isfile(sys.argv[1]):
            self.list_paths.append(sys.argv[1])
            self.list_files.AppendItems(os.path.basename(self.list_paths[0]))
            self.list_files.Select(0)
            self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
            self.ShowTags(self.tags)

        if os.path.isdir(sys.argv[1]):
            self.list_paths = glob(os.path.join(sys.argv[1], "*.mp4"))
            for path in self.list_paths:
                self.list_files.AppendItems(os.path.basename(path))
            self.list_files.Select(0)
            self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
            self.ShowTags(self.tags)

    def ListClick(self, event):
        self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
        self.ShowTags(self.tags)


def main():
    app = wx.App()
    top = MyFrame(None, title=f"KL Tag {VER}")
    # top.SetIcon(wx.Icon(kl.get_resource_path("favicon.ico")))
    top.SetClientSize(top.FromDIP(wx.Size(1000, 500)))
    top.Centre()
    top.SetMinSize(top.Size)
    top.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
