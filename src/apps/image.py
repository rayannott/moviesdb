import threading
from collections.abc import Callable
from pathlib import Path
from time import perf_counter as pc
from typing import TYPE_CHECKING

from rich.console import Console
from rich.prompt import Prompt

from src.apps.base import BaseApp
from src.mongo import Mongo
from src.obj.image import ImageManager, S3Image
from src.parser import Flags, KeywordArgs, PositionalArgs
from src.utils.rich_utils import format_entry, get_pretty_progress

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
            self.image_manager = ImageManager(app.entries)
            t1 = pc()
            self._num_images = len(self.image_manager._get_s3_images_bare())
            t2 = pc()
        self._connected_in = t1 - t0
        self._images_loaded_in = t2 - t1
        self._tags_loaded_in = 0.0

        # S3 key -> Tags; keep in memory; reload on demand
        self._ids_to_tags: dict[str, dict[str, str]] = {}

        self._lock = threading.Lock()

        self.register_aliases({"tags": "tag"})

        # check for duplicates
        self._check_resolve_duplicate_images(verbose_if_no_dups=False)

    def _reload_ids_to_tags_thread(self):
        # this starts a thread that loads image tags
        def _load_tags():
            _t0 = pc()
            _ids_to_tags = self.image_manager._get_ids_to_tags()
            with self._lock:
                self._ids_to_tags = _ids_to_tags
            self._tags_loaded_in = pc() - _t0

        self.image_manager._get_ids_to_tags.cache_clear()
        # TODO use a thread pool executor
        load_tags_thread = threading.Thread(target=_load_tags)
        load_tags_thread.start()

    def _check_resolve_duplicate_images(self, *, verbose_if_no_dups: bool):
        hash_to_img_ids = self.image_manager._group_by_etag_hash()
        dups = {h: ids for h, ids in hash_to_img_ids.items() if len(ids) > 1}
        if not dups:
            if verbose_if_no_dups:
                self.cns.print("[green]No duplicate images found.")
            return
        self.cns.print(f"[bold yellow]Found {len(dups)} duplicate groups:")
        for i, ids in enumerate(dups.values()):
            self.cns.print(f"Group {i + 1}:")
            for s3_id in ids:
                self.cns.print(f"  - {S3Image(s3_id)}")
        prompt = Prompt.ask(
            "[yellow]Delete all but the first added image in each group? (this will ask for confirmation again)",
            choices=["y", "n"],
            default="n",
            console=self.cns,
        )
        if prompt != "y":
            self.cns.print("[yellow]No images were deleted.")
            return
        to_delete = []
        for ids in dups.values():
            s3_img_objs = sorted(map(S3Image, ids), key=lambda img: img.dt)
            to_delete.extend(s3_img_objs[1:])
        self.cns.print(f"Selected {', '.join(map(str, to_delete))} for deletion.")
        prompt = Prompt.ask(
            "Delete them?",
            choices=["y", "n"],
            default="n",
            console=self.cns,
        )
        if prompt != "y":
            self.cns.print("[yellow]No images were deleted.")
            return
        for img in to_delete:
            self.image_manager.delete_image(img)
            self.cns.print(f"[red]Deleted {img}")
        self.cns.print(f"[green]Deleted {len(to_delete)} images.")

    def load_tags_pretty(self) -> dict[str, dict[str, str]]:
        res = {}
        _t0 = pc()

        progress = get_pretty_progress()
        with progress:
            task = progress.add_task("Loading image tags...", total=self._num_images)
            for s3_id, tags in self.image_manager._iterate_ids_tagsets():
                res[s3_id] = tags
                progress.update(task, advance=1)
        self._tags_loaded_in = pc() - _t0
        self.cns.print(f"[dim]Tags loaded in {self._tags_loaded_in:.3f} sec.")
        return res

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

    def get_images(self, filter: str = "*") -> list[S3Image]:
        return self.image_manager.get_images(filter, with_tags=self._ids_to_tags)

    def update_in_memory_tags(self, images: list[S3Image]):
        with self._lock:
            for img in images:
                self._ids_to_tags[img.s3_id] = img.tags

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """list [<filter>] [--n <n>]
        Show images. Apply filter if specified.
        filter: sha1 prefix (#...), 'attached', '*', tag ('tag=avatar'); prepend '!' for negation
        n: number of images to list (default: 5, only applies without filter)
        """
        if pos:
            # list with filter
            filter = pos[0]
            some_images = self.get_images(filter)
            if not some_images:
                self.warning(f"No images found matching {filter!r}.")
                return
            self.cns.print(f"{len(some_images)} images matching {filter!r}:")
            for img in some_images:
                self.cns.print(str(img))
            return
        if (n := self.app.try_int(kwargs.get("n", "5"))) is None:
            return
        _images = self.get_images()
        if not _images:
            return
        self.cns.print(f"Last {n} images:")
        for img in _images[-n:]:
            self.cns.print(str(img))

    def cmd_app(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """app <cmd> *<args> **<kwargs>
        Run command for the main app.
        E.g. 'app find avatar'
        """
        if not pos:
            self.error("No main app command specified; try 'app help'")
            return
        root, *rest = pos
        if root == "images":
            self.cns.print("[bold black]Inception?..")
        self.app.process_command(root, rest, kwargs, flags)

    def cmd_dups(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """dups
        Check for and optionally resolve duplicate images.
        """
        self._check_resolve_duplicate_images(verbose_if_no_dups=True)

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
        imgs = self.get_images(image_filter)
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
        """tag|tags [<filter> **<tags>]
        Manage image tags.
        Reload tags if no arguments given.
        Set the specified tags on all images matching the filter.
        If a tag value is empty, the tag is removed.
        E.g., 'tag *' would clear tags on all images, `tag !what= --what avatar`
        would set 'what' tag to 'avatar' on all images that don't have it.
        """
        if not pos:
            if not self._ids_to_tags:
                self._ids_to_tags = self.load_tags_pretty()
            # TODO add tags stats here
            return
        image_filter = pos[0]
        imgs = self.get_images(image_filter)
        if not imgs:
            self.warning(f"No image found matching {image_filter!r}")
            return
        if not self._confirm(imgs, f"Set tags to {kwargs!r} in", ask_if_len_ge=1):
            return
        new_imgs = []
        # TODO change behavior
        for img in imgs:
            new_img = self.image_manager.set_s3_tags_for(img, kwargs)
            self.cns.print(f"Updated: {new_img}")
            new_imgs.append(new_img)
        self.update_in_memory_tags(new_imgs)

    def cmd_upload(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """upload [<path>] [--to <entry_id|title>] [**<tags>]
        Upload image from clipboard and optionally attach it to an entry.
        Any additional kwargs are passed as tags to the image's metadata.
        If (global) path is given, upload from path instead of clipboard.
        E.g., an image uploaded with
            upload --to -1 --what avatar --who me|john --misc something
        would match all of the following tag-filters:
            '=', 'what=', '=me', '=john'
        """
        attach_to_entry_id = kwargs.pop("to", None)
        with self.cns.status("Uploading image..."):
            if not pos:
                image = self.image_manager.upload_from_clipboard(kwargs)
                if not image:
                    self.warning("No image found in clipboard.")
                    return
            else:
                path = Path(pos[0])
                if not path.exists():
                    self.error(f"File not found: {path}")
                    return
                image = self.image_manager.upload_from_path(path, kwargs)
                if not image:
                    self.error(f"Failed to upload image from path: {path}")
                    return
        entry_ = None
        if attach_to_entry_id:
            entry_ = self.app.entry_by_idx_or_title(attach_to_entry_id)
            if not entry_:
                self.warning(
                    f"No entry found with ID: {attach_to_entry_id}; not attaching."
                )
        if image:
            self.cns.print(f"Uploaded {image}")
            self.update_in_memory_tags([image])
            if entry_:
                entry_.attach_image(image.s3_id)
                Mongo.update_entry(entry_)
                self.cns.print(f"Attached to {format_entry(entry_)}")
        else:
            self.error(f"Failed to upload {image} from clipboard.")

    def cmd_attach(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """attach <filter> <entry_id|title>
        Attach filtered image(s) to entry.
        """
        if len(pos) < 2:
            self.error("Usage: attach <filter> <entry_id|title>")
            return
        image_filter, entry_id_str = pos
        entry = self.app.entry_by_idx_or_title(entry_id_str)
        if not entry:
            self.error("Entry not found.")
            return
        images = self.get_images(image_filter)
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
        """detach <filter> <entry_id|title>
        Detach filtered image(s) from entry.
        """
        # TODO remove detach; add argument to prev command?
        if len(pos) < 2:
            self.error("Usage: detach <filter> <entry_id|title>")
            return
        image_filter, entry_id_str = pos
        entry = self.app.entry_by_idx_or_title(entry_id_str)
        if not entry:
            self.error("Entry not found.")
            return
        images = self.get_images(image_filter)
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
        """delete <filter>
        Delete image from S3 and detach from all associated entries.
        """
        if not pos:
            self.error("Usage: delete <filter>")
            return
        image_filter = pos[0]
        imgs = self.get_images(image_filter)
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

    def cmd_reload(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """reload
        Reload image tags from S3.
        """
        self._ids_to_tags = self.load_tags_pretty()

    def cmd_stats(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """stats
        Show total and attached image statistics.
        """
        num_attached_images = sum(1 for img in self.get_images() if img.entries)
        total_size_mb = sum(
            img.size_bytes * 2**-20 for img in self.get_images() if img.size_bytes
        )
        self.cns.print(f"""Total images: {self._num_images}
Attached images: {num_attached_images}
Total size: {total_size_mb:.2f} MB""")
        self.cns.print(f"[dim]Tags loaded in {self._tags_loaded_in:.3f} sec.")

    def cmd_clearcache(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """clearcache
        Clear local image cache.
        """
        n_removed = self.image_manager.clear_cache()
        self.cns.print(f"Removed {n_removed} cached images.")
