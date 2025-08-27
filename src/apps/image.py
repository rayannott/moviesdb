from collections.abc import Callable
from time import perf_counter as pc
from typing import TYPE_CHECKING
import threading

from rich.console import Console
from rich.prompt import Prompt

from src.apps.base import BaseApp
from src.mongo import Mongo
from src.obj.images_manager import ImagesStore, S3Image
from src.parser import Flags, KeywordArgs, PositionalArgs
from src.utils.rich_utils import format_entry

if TYPE_CHECKING:
    from src.apps import App


class ImagesApp(BaseApp):
    def __init__(
        self,
        app: "App",
        cns: Console,
        input_fn: Callable[[str], str],
    ):
        super().__init__(cns, input_fn, prompt_str="IMAGES>")
        self.app = app

        with self.cns.status("Connecting..."):
            t0 = pc()
            self.image_manager = ImagesStore(app.entries)
            t1 = pc()
            self._num_images = len(self.image_manager._get_s3_images())
            t2 = pc()
        self._connected_in = t1 - t0
        self._images_loaded_in = t2 - t1
        self._tags_loaded_in = 0.0

        self.register_aliases({"tags": "tag"})
        self._load_tags()

    def _load_tags(self):
        # this starts a thread that loads image tags
        def _load_tags():
            _t0 = pc()
            self.image_manager._get_ids_to_tags()
            self._tags_loaded_in = pc() - _t0

        self.image_manager._get_ids_to_tags.cache_clear()
        # TODO use a thread pool executor
        load_tags_thread = threading.Thread(target=_load_tags)
        load_tags_thread.start()

    def header(self):
        self.cns.rule(
            f"Images App ({self._num_images} images)",
            style="bold yellow",
        )

    def pre_run(self):
        super().pre_run()
        self.cns.print(
            f"[dim]Connected to S3 in {self._connected_in:.3f} sec; "
            f"{self._num_images} images loaded in {self._images_loaded_in:.3f} sec."
        )

    def _confirm(
        self, imgs: list[S3Image], prompt: str, *, ask_if_len_ge: int = 5
    ) -> bool:
        if len(imgs) >= ask_if_len_ge and "y" != (
            Prompt.ask(
                f"[underline bold]{prompt}[/] [green]{len(imgs)}[/] selected images"
                + (f"\n({'\n'.join(map(str, imgs))})?" if len(imgs) <= 5 else " (...)"),
                choices=["y", "n"],
                default="n",
                console=self.cns,
            )
        ):
            return False
        return True

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """list [<filter>] [--n <n>]
        Show images. Apply filter if specified.
        filter: sha1 prefix (#...), 'attached', '*', tag ('tag=avatar'); prepend '!' for negation
        n: number of images to list (default: 5, only applies without filter)
        """
        if pos:
            # list with filter
            filter = pos[0]
            some_images = self.image_manager.get_images(filter)
            if not some_images:
                self.warning(f"No images found matching {filter!r}.")
                return
            self.cns.print(f"{len(some_images)} images matching {filter!r}:")
            for img in some_images:
                self.cns.print(str(img))
            return
        if (n := self.app.try_int(kwargs.get("n", "5"))) is None:
            return
        self._images = self.image_manager.get_images()
        if not self._images:
            return
        self.cns.print(f"Last {n} images:")
        for img in self._images[-n:]:
            self.cns.print(str(img))

    def cmd_show(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """show [<filter>] [--no-browser]
        Show image(s).
        If no filter given: show image from clipboard.
        If filter given: show images matching the filter.
        --no-browser: open locally instead of in browser
        """
        if not pos:
            image = self.image_manager.grab_clipboard_image()
            if image:
                self.cns.print(f"Showing image: {image}")
                image.show()
            else:
                self.warning("No image found in clipboard.")
            return
        image_filter = pos[0]
        imgs = self.image_manager.get_images(image_filter)
        if not imgs:
            self.warning(f"No image found matching {image_filter!r}")
            return
        if not self._confirm(imgs, "Show", ask_if_len_ge=3):
            return
        for msg in self.image_manager.show_images(
            imgs, in_browser="no-browser" not in flags
        ):
            self.cns.print(msg)

    def cmd_tag(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """tag|tags [<filter> **<tags>] [--no-reload]
        Manage image tags.
        If a filter is given, set the specified tags on all images matching the filter.
        Unless --no-reload is specified, recompute the tags (runs in background).
        E.g., 'tag *' would clear tags on all images, `tag !what= --what avatar` 
        would set 'what' tag to 'avatar' on all images that don't have it.
        """
        if not pos or len(pos) > 2:
            self.error("Specify filter.")
            return
        image_filter = pos[0]
        imgs = self.image_manager.get_images(image_filter)
        if not imgs:
            self.warning(f"No image found matching {image_filter!r}")
            return
        if not self._confirm(imgs, f"Set tags to {kwargs!r} in", ask_if_len_ge=1):
            return
        for img in imgs:
            new_img = self.image_manager.set_s3_tags_for(img, kwargs)
            self.cns.print(f"Updated: {new_img}")
        if "no-reload" not in flags:
            self._load_tags()

    def cmd_upload(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """upload [--attach <entry_id|title>] [**<tags>]
        Upload image from clipboard and optionally attach it to an entry.
        Any additional kwargs are passed as tags to the image's metadata.
        E.g., an image uploaded with
            upload --attach -1 --what avatar --who me|john --misc something
        would match all of the following tag-filters:
            '=', 'what=', '=me', '=john'
        """
        attach_to_entry_id = kwargs.pop("attach", None)
        with self.cns.status("Uploading image from clipboard..."):
            img_cb = self.image_manager.upload_from_clipboard(kwargs)
        if not img_cb:
            self.warning("No image found in clipboard.")
            return
        entry_ = None
        if attach_to_entry_id:
            entry_ = self.app.entry_by_idx_or_title(attach_to_entry_id)
            if not entry_:
                self.warning(
                    f"No entry found with ID: {attach_to_entry_id}; not attaching."
                )
        if img_cb:
            self.cns.print(f"Uploaded {img_cb}")
            if entry_:
                entry_.attach_image(img_cb.s3_id)
                Mongo.update_entry(entry_)
                self.cns.print(f"Attached to {format_entry(entry_)}")
        else:
            self.error(f"Failed to upload {img_cb} from clipboard.")

    def cmd_attach(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """attach <image> <entry_id|title>
        Attach image to entry.
        """
        if len(pos) < 2:
            self.error("Usage: attach <image> <entry_id|title>")
            return
        image_filter, entry_id_str = pos
        entry = self.app.entry_by_idx_or_title(entry_id_str)
        if not entry:
            self.error("Entry not found.")
            return
        images = self.image_manager.get_images(image_filter)
        if not images:
            self.warning(f"No image found matching {image_filter!r}")
            return
        if not self._confirm(images, "Attach", ask_if_len_ge=2):
            return
        for img in images:
            entry.attach_image(img.s3_id)
            Mongo.update_entry(entry)
            self.cns.print(f"Attached {img} to {format_entry(entry)}")

    def cmd_detach(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """detach <image> <entry_id|title>
        Detach image from entry.
        """
        # TODO remove detach; add argument to prev command?
        if len(pos) < 2:
            self.error("Usage: detach <image> <entry_id|title>")
            return
        image_filter, entry_id_str = pos
        entry = self.app.entry_by_idx_or_title(entry_id_str)
        if not entry:
            self.error("Entry not found.")
            return
        images = self.image_manager.get_images(image_filter)
        if not images:
            self.warning(f"No image found matching {image_filter!r}")
            return
        if not self._confirm(images, "Detach", ask_if_len_ge=2):
            return
        for img in images:
            entry.detach_image(img.s3_id)
            Mongo.update_entry(entry)
            self.cns.print(f"Detached {img} from {format_entry(entry)}")

    def cmd_delete(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """delete <image>
        Delete image from S3 and detach from all associated entries.
        """
        if not pos:
            self.error("Usage: delete <image>")
            return
        image_filter = pos[0]
        imgs = self.image_manager.get_images(image_filter)
        if not imgs:
            self.warning(f"No image found matching {image_filter!r}")
            return
        if not self._confirm(imgs, "Delete", ask_if_len_ge=1):
            return
        for img_to_delete in imgs:
            self.image_manager.delete_image(img_to_delete)
            self.cns.print(f"Deleted {img_to_delete}")
            if not img_to_delete.entries:
                continue
            for entry in img_to_delete.entries:
                ok = entry.detach_image(img_to_delete.s3_id)
                if not ok:
                    self.error(f"Failed to detach {img_to_delete} from {entry}")
                Mongo.update_entry(entry)
                self.cns.print(f"  detached from {format_entry(entry)}")

    def cmd_entry(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """entry <entry_id|title> [--no-browser]
        Show all images for an entry.
        """
        if not pos:
            self.error("Usage: entry <entry_id|title>")
            return
        entry_id_str = pos[0]
        entry = self.app.entry_by_idx_or_title(entry_id_str)
        if not entry:
            self.error("Entry not found.")
            return
        if not entry.image_ids:
            self.warning("No images found for this entry.")
            return
        for msg in self.image_manager.show_images(
            list(map(S3Image, entry.image_ids)),
            in_browser="no-browser" not in flags,
        ):
            self.cns.print(msg)

    def cmd_stats(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """stats
        Show total and attached image statistics.
        """
        num_total_images, num_attached_images = self.image_manager.get_image_stats()
        self.cns.print(
            f"Total images: {num_total_images}\nAttached images: {num_attached_images}"
        )
        self.cns.print(f"[dim]Tags loaded in {self._tags_loaded_in:.3f} sec.")

    def cmd_clearcache(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """clearcache
        Clear local image cache.
        """
        n_removed = self.image_manager.clear_cache()
        self.cns.print(f"Removed {n_removed} cached images.")
