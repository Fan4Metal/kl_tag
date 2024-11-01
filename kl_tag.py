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

wildcard_pics = "Изображения (*.png;*.jpg;*.jpeg;*.webp)|*.png;*.jpg;*.jpeg;*.webp|"\
            "Все файлы (*.*)|*.*"


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
    cover: Image.Image | str
    has_cover: bool
    is_ok: bool


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
        self.t_country = wx.TextCtrl(self.panel, value="")

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
        self.t_director = wx.TextCtrl(self.panel, value="", size=self.t_country.Size)
        self.l_kpid = wx.StaticText(self.panel, label="Kinopoisk ID:")
        self.t_kpid = wx.TextCtrl(self.panel, value="", size=(140, 28))
        self.tag_box_director = wx.BoxSizer(orient=wx.HORIZONTAL)

        self.tag_box_director.Add(self.l_director, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.t_director, proportion=1, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.l_kpid, flag=wx.ALIGN_CENTER | wx.RIGHT, border=10)
        self.tag_box_director.Add(self.t_kpid, flag=wx.ALIGN_CENTER)
        self.tag_box_sizer.Add(self.tag_box_director, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # actors
        self.l_actors = wx.StaticText(self.panel, label="Актеры:")
        self.t_actors = wx.TextCtrl(self.panel, wx.ID_ANY, style=wx.ALIGN_TOP | wx.TE_MULTILINE | wx.TE_WORDWRAP)
        self.Bind(wx.EVT_TEXT, self.TextChange, id=self.t_actors.GetId())

        # description
        self.l_description = wx.StaticText(self.panel, label="Описание:")
        self.t_description = wx.TextCtrl(self.panel, value="", style=wx.ALIGN_TOP | wx.TE_MULTILINE)

        self.tag_box_sizer.Add(self.l_actors, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.t_actors, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.l_description, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.tag_box_sizer.Add(self.t_description, proportion=1, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)

        # poster
        self.placeholder = Image.open(".\images\placeholder.png")
        self.image = wx.StaticBitmap(self.panel, wx.ID_ANY, self.scale_picture(self.placeholder), size=self.FromDIP((200, 300)))
        self.image.Bind(wx.EVT_CONTEXT_MENU, self.OnPosterContextMenu)
        self.l_image_size = wx.StaticText(self.panel, label="Нет постера")
        self.b_save = wx.Button(self.panel, wx.ID_OK, label="Записать в файл", size=self.FromDIP((100, 25)))
        self.Bind(wx.EVT_BUTTON, self.onSaveTags, id=self.b_save.GetId())

        self.box1_h = wx.BoxSizer(orient=wx.HORIZONTAL)
        self.box2_v = wx.BoxSizer(orient=wx.VERTICAL)
        self.box1_h.Add(self.list_files, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT, border=10)
        self.box2_v.Add(self.image, proportion=0, flag=wx.EXPAND, border=10)
        self.box2_v.Add(self.l_image_size, proportion=0, flag=wx.ALIGN_CENTER)
        self.box2_v.AddStretchSpacer(prop=1)
        self.box2_v.Add(self.b_save, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)

        self.box1_h.Add(self.tag_box_sizer, proportion=1, flag=wx.EXPAND | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.box1_h.Add(self.box2_v, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM | wx.LEFT | wx.RIGHT, border=10)
        self.panel.SetSizer(self.box1_h)

        self.list_paths = []
        self.tags: Mp4TagsClass
        self.OpenFiles()

    def ReadTags(self, file_path) -> Mp4TagsClass | None:
        result = Mp4TagsClass("", "", "", "", "", "", "", "", "", "", False, False)
        try:
            video = MP4(file_path)
        except Exception as error:
            log.error(f"Ошибка! Не удалось открыть файл ({error}): {os.path.basename(file_path)}")
            return result

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
                result.has_cover = True
            else:
                result.cover = self.placeholder
                result.has_cover = False
        except:
            result.cover = self.placeholder
            result.has_cover = False

        try:
            if video["----:com.apple.iTunes:kpid"][0].decode():
                result.kpid = video["----:com.apple.iTunes:kpid"][0].decode()
            else:
                result.kpid = ""
        except:
            result.kpid = ""

        result.is_ok = True
        return result

    def ShowTags(self):
        self.t_title.Value = self.tags.title
        self.t_year.Value = self.tags.year
        self.t_country.Value = ", ".join(self.tags.country)
        if self.tags.rating:
            if self.tags.rating[0] == "i":
                self.t_rating.Value = self.tags.rating[1:]
                self.choice.SetSelection(1)
            else:
                self.t_rating.Value = self.tags.rating
                self.choice.SetSelection(0)
        else:
            self.t_rating.Value = self.tags.rating
            self.choice.SetSelection(0)
        self.t_director.Value = ", ".join(self.tags.directors)
        self.t_kpid.Value = self.tags.kpid
        self.t_actors.Value = ", ".join(self.tags.actors)
        self.t_description.Value = self.tags.description
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
        # self.tags.cover = self.placeholder

    def OpenFiles(self):
        if len(sys.argv) != 2:
            return
        if os.path.isfile(sys.argv[1]):
            self.list_paths.append(sys.argv[1])
            self.list_files.AppendItems(os.path.basename(self.list_paths[0]))
            self.list_files.Select(0)
            self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
            if not self.tags.is_ok:
                self.DisableInterface()
                return
            self.EnableInterface()
            self.ShowTags()

        if os.path.isdir(sys.argv[1]):
            self.list_paths = glob(os.path.join(sys.argv[1], "*.mp4"))
            for path in self.list_paths:
                self.list_files.AppendItems(os.path.basename(path))
            self.list_files.Select(0)
            self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
            if not self.tags.is_ok:
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
        # try:
        #     video.delete()  # удаление всех тегов
        # except Exception as error:
        #     log.error(f"Ошибка при сохранении тегов в файл ({error}): {os.path.basename(file_path)}")
        #     return False
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
        try:
            video.save()
        except Exception as error:
            wx.MessageDialog(None, f"Ошибка при сохранении тегов в файл!\n{error}", "Ошибка!", wx.OK | wx.ICON_ERROR).ShowModal()
            log.error(f"Ошибка при сохранении тегов в файл! ({error})!")
            return False
        return True

    def ListClick(self, event):
        self.tags = self.ReadTags(self.list_paths[self.list_files.GetSelection()])
        if not self.tags.is_ok:
            self.DisableInterface()
            return
        self.EnableInterface()
        self.ShowTags()

    def TextChange(self, event):
        self.t_actors.Value = self.t_actors.Value.replace("\n", ", ")
        self.t_actors.SetInsertionPointEnd()

    def OnPosterContextMenu(self, event):
        menu = wx.Menu()
        item1 = wx.MenuItem(menu, wx.ID_ANY, "Добавить постер")
        self.Bind(wx.EVT_MENU, self.OnAddPoster, id=item1.GetId())
        item2 = wx.MenuItem(menu, wx.ID_ANY, "Удалить постер")
        self.Bind(wx.EVT_MENU, self.OnDelPoster, id=item2.GetId())

        menu.Append(item1)
        if self.tags.has_cover:
            menu.Append(item2)
        self.PopupMenu(menu)
        menu.Destroy()

    def scale_picture(self, picture: Image.Image):

        def PIL2wx(image):
            width, height = image.size
            return wx.Bitmap.FromBuffer(width, height, image.tobytes())

        bmp_source = wx.Bitmap(PIL2wx(picture))
        image = bmp_source.ConvertToImage()
        return wx.Bitmap(image.Scale(self.FromDIP(200), self.FromDIP(300)))

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

    def OnAddPoster(self, event):
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

    def OnDelPoster(self, event):
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

        self.ClearTags()
        self.t_title.Disable()
        self.t_actors.Disable()
        self.t_country.Disable()
        self.t_description.Disable()
        self.t_director.Disable()
        self.t_kpid.Disable()
        self.t_rating.Disable()
        self.t_year.Disable()
        self.b_save.Disable()

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


def main():
    app = wx.App()
    top = MyFrame(None, title=f"Kinolist Tag Editor {VER}")
    top.SetIcon(wx.Icon(get_resource_path("./images/favicon.ico")))
    top.SetClientSize(top.FromDIP(wx.Size(1000, 500)))
    top.Centre()
    top.SetMinSize(top.Size)
    top.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
