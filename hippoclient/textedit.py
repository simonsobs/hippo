"""
The text editor flow for hippo. Uses textual to launch a TUI app and edit
the text associated with a collection or product.
"""

import ast
import json
from pathlib import Path

import xxhash
from beanie import PydanticObjectId
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Input,
    Label,
    RadioButton,
    RadioSet,
    Select,
    TabbedContent,
    TabPane,
    TextArea,
)

from hippometa import ALL_METADATA, ALL_METADATA_TYPE

from . import product
from .core import Client


class EditorApp(App):
    CSS_PATH = "textedit.tcss"
    _product_name = reactive("")
    _description = reactive("")
    _sources = reactive(None)
    _metadata = reactive(None)
    _selected_metadata_class: ALL_METADATA_TYPE | None
    _current_version: str
    _projected_version: str
    _version: int = 2
    _drop_sources = []
    _replace_sources = []
    _new_sources = []

    BINDINGS = [
        ("d", "show_tab('details-tab')", "Details"),
        ("s", "show_tab('sources-tab')", "Sources"),
        ("m", "show_tab('metadata-tab')", "Metadata"),
    ]

    def __init__(self, id: PydanticObjectId, client: Client):
        self._object_id = id
        self._client = client

        _product = product.read(client, id)

        self._current_version = _product.version
        self._projected_version = self.project_version()

        super().__init__()

        self._product_name = _product.name
        self._description = _product.description
        self._sources = _product.sources
        self._metadata = _product.metadata

    def compose(self) -> ComposeResult:
        """
        This function builds the Textual GUI components. The GUI contains a footer
        and a tabbed display. The footer contains keyboard shortcuts to help
        navigate the tabbed display. The available tabs and their descriptions are:
          Details: Enables edits to product title, product description, and version level
          Sources: Enables adding, replacing or deleting sources
          Metadata: Enables changing metadata type and/or editing metadata fields
        """
        yield Footer()

        with TabbedContent():
            # Construct the Details tab
            with TabPane("Details", id="details-tab"):
                with Vertical(classes="title"):
                    yield Label("Product Title:", variant="accent")
                    yield Input(
                        value=self._product_name,
                        placeholder="Product title...",
                        id="product-title",
                    )
                with Vertical(classes="description"):
                    yield Label("Product Description:", variant="accent")
                    yield TextArea(
                        classes="textarea",
                        text=self._description,
                        language="markdown",
                        id="product-description",
                    )
                with Vertical(classes="versioning"):
                    yield Label("Version Bump:", variant="accent")
                    yield RadioSet(
                        RadioButton("Major"),
                        RadioButton("Minor"),
                        RadioButton("Patch", value=True),
                        id="version",
                    )
                    yield Label(
                        f"{self._current_version} → {self._projected_version}",
                        id="versionproject",
                        variant="success",
                    )
                with Horizontal(classes="save-or-cancel"):
                    yield Button("Save", variant="success", id="save")
                    yield Button("Cancel", variant="error", id="cancel")

            # Construct the Sources tab
            with TabPane("Sources", id="sources-tab"):
                for source in self._sources:
                    with Horizontal(classes="sources existing-source"):
                        with Vertical():
                            yield Label("Filename:", variant="accent")
                            yield Input(
                                value=source.name,
                                placeholder="",
                                id=f"edit-source-name-{source.uuid}",
                                tooltip=(
                                    "Enter the absolute filepath to a file of the same name to "
                                    "update the file; leave this field as-is if only editing "
                                    "other fields (i.e., source description)"
                                ),
                            )
                        with Vertical():
                            yield Label("Source Description:", variant="accent")
                            yield Input(
                                value=source.description,
                                placeholder="Description...",
                                id=f"edit-source-desc-{source.uuid}",
                            )
                        with Vertical():
                            yield Label("Is Primary Source?", variant="accent")
                            yield Checkbox(
                                "Primary",
                                classes="primary-source-checkbox",
                                id=f"edit-primary-source-checkbox-{source.uuid}",
                            )
                        with Vertical():
                            yield Label("Delete Source?", variant="accent")
                            yield Checkbox(
                                "Yes",
                                classes="delete-source-checkbox",
                                id=f"delete_source_checkbox_{source.uuid}",
                            )
                with Horizontal(classes="sources new-source"):
                    with Vertical():
                        yield Label("Filepath:", variant="accent")
                        yield Input(
                            value=None,
                            placeholder="Path to new source file...",
                            id="new-source-file-path",
                        )
                    with Vertical():
                        yield Label("Source Description:", variant="accent")
                        yield Input(
                            value=None,
                            placeholder="Source description...",
                            id="new-source-file-desc",
                        )
                    with Vertical():
                        yield Label("Is Primary Source?", variant="accent")
                        yield Checkbox(
                            "Primary",
                            classes="primary-source-checkbox",
                            id="new-primary-source-checkbox",
                        )
                with Horizontal(classes="save-or-cancel"):
                    yield Button("Save", variant="success", id="save")
                    yield Button("Cancel", variant="error", id="cancel")

            # Construct the Metadata tab
            with TabPane("Metadata", id="metadata-tab"):
                class_schema = self._metadata.model_json_schema()
                class_title = class_schema["title"]
                yield Label("Metadata Type:", variant="primary")
                metadata_options = [
                    v.model_json_schema()["title"]
                    for v in ALL_METADATA.values()
                    if v is not None
                ]
                yield Select.from_values(
                    metadata_options, value=class_title, id="metadata-selector"
                )
                with Horizontal(classes="metadata-inputs-container"):
                    None
                with Horizontal(classes="save-or-cancel"):
                    yield Button("Save", variant="success", id="save")
                    yield Button("Cancel", variant="error", id="cancel")

    def action_show_tab(self, tab: str) -> None:
        """Switch to a new tab."""
        self.get_child_by_type(TabbedContent).active = tab

    def project_version(self):
        split = [int(x) for x in self._current_version.split(".")]
        split[self._version] = split[self._version] + 1
        for index in range(self._version + 1, len(split)):
            split[index] = 0
        return ".".join([f"{x}" for x in split])

    def update_projected_version(self):
        """Update the Textual GUI's "Version Bump" string (ie 1.0.0 -> 1.0.1)"""
        self._projected_version = self.project_version()
        version_label = self.query_one("#versionproject")
        version_label.update(f"{self._current_version} → {self._projected_version}")

    @on(RadioSet.Changed)
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle radio set changes."""
        if event.radio_set.id == "version":
            self._version = {"Major": 0, "Minor": 1, "Patch": 2}[
                event.pressed.label.plain
            ]
            self.update_projected_version()

    @on(Checkbox.Changed)
    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Handle checkbox changes; currently only 'Delete Source?' field has a checkbox"""
        if event.checkbox.has_class("delete-source-checkbox"):
            split_id = event.checkbox.id.split("_")
            uuid = split_id[len(split_id) - 1]
            toggled_source = [source for source in self._sources if source.uuid == uuid]
            if toggled_source[0].name in self._drop_sources:
                self._drop_sources.remove(toggled_source[0].name)
            else:
                self._drop_sources.append(toggled_source[0].name)
            return

    def generate_metadata_fields(self):
        original_class_schema = self._metadata.model_json_schema()
        original_class_json = self._metadata.model_dump(mode="json")
        original_class_schema = self._metadata.model_json_schema()
        original_class_title = original_class_schema["title"]
        is_original_selected = (
            original_class_title
            == self._selected_metadata_class.model_json_schema()["title"]
        )

        for field_key, field_data in self._selected_metadata_class.model_json_schema()[
            "properties"
        ].items():
            if field_key == "metadata_type":
                continue
            vertical = Vertical()
            self.query_one(".metadata-inputs-container").mount(vertical)
            vertical.mount(Label(field_data["title"], variant="accent"))
            if "enum" in field_data:
                vertical.mount(
                    Select.from_values(
                        field_data["enum"],
                        id=field_key,
                        value=str(original_class_json[field_key])
                        if is_original_selected
                        else Select.BLANK,
                    )
                )
            elif "additionalProperties" in field_data:
                vertical.add_class("metadata-textarea")
                vertical.mount(
                    TextArea.code_editor(
                        classes="textarea",
                        language="json",
                        text=json.dumps(original_class_json[field_key], indent=2)
                        if is_original_selected
                        else "",
                        id=field_key,
                    )
                )
            else:
                vertical.mount(
                    Input(
                        value=str(original_class_json[field_key])
                        if is_original_selected
                        else "",
                        id=field_key,
                        placeholder=f"Enter {field_data['title'].lower()}...",
                    )
                )

    @on(Select.Changed)
    def select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "metadata-selector":
            selected_class_title = event.select.value
            if selected_class_title is Select.BLANK:
                # if _selected_metadata_class is None, revert back to stored _metadata value
                if self._selected_metadata_class is None:
                    class_schema = self._metadata.model_json_schema()
                    class_title = class_schema["title"]
                    event.select.value = class_title
                # if _selected_metadata_class exists, revert back to stored value of _selected_metadata_class
                else:
                    saved_class_schema = (
                        self._selected_metadata_class.model_json_schema()
                    )
                    saved_class_schema_title = saved_class_schema["title"]
                    event.select.value = saved_class_schema_title
            else:
                metadata_class = next(
                    v
                    for v in ALL_METADATA.values()
                    if v.model_json_schema()["title"] == selected_class_title
                )
                self._selected_metadata_class = metadata_class
            self.query_one(".metadata-inputs-container").remove_children(Vertical)
            self.query_one(".metadata-inputs-container").remove_children(Label)
            self.query_one(".metadata-inputs-container").remove_children(Input)
            self.query_one(".metadata-inputs-container").remove_children(Select)
            self.generate_metadata_fields()

    def get_file_metadata(self, path, source_description):
        source = Path(path)
        with source.open("rb") as file:
            file_info = {
                "name": source.name,
                "size": source.stat().st_size,
                "checksum": f"xxh64:{xxhash.xxh64(file.read()).hexdigest()}",
                "description": source_description,
            }
            return file_info

    def get_new_source(self):
        file_path = self.query_one("#new-source-file-path").value
        source_desc = self.query_one("#new-source-file-desc").value
        if file_path:
            new_source_metadata = self.get_file_metadata(file_path, source_desc)
            return [new_source_metadata]
        else:
            return []

    def get_replace_sources(self):
        source_data = []
        for source in self._sources:
            source_name = self.query_one(f"#edit-source-name-{source.uuid}").value
            source_desc = self.query_one(f"#edit-source-desc-{source.uuid}").value
            is_set_to_delete = self.query_one(
                f"#delete_source_checkbox_{source.uuid}"
            ).value
            if source_name == source.name and is_set_to_delete is False:
                source_metadata = {
                    "name": source.name,
                    "size": source.size,
                    "checksum": source.checksum,
                    "description": source_desc,
                }
                source_data.append(source_metadata)
                continue
            if source_name != source.name and is_set_to_delete is False:
                source_metadata = self.get_file_metadata(source_name, source_desc)
                source_data.append(source_metadata)
        return source_data

    def get_metadata_type(self, field_data):
        if "anyOf" in field_data:
            options = [x for x in field_data["anyOf"]]
            true_type = [x for x in options if x["type"] != "null"][0]
            return {
                "true_type": true_type["type"],
                "is_optional": ({"type": "null"} in options),
            }
        elif "enum" in field_data:
            return {"true_type": "enum", "is_optional": False}
        elif "additionalProperties" in field_data:
            return {
                "true_type": field_data["type"],
                "is_optional": False,
                "empty_value": {},
            }
        return {"true_type": "string", "is_optional": False}

    def get_metadata_changes(self):
        metadata_schema = (
            self._metadata.model_json_schema()
            if self._selected_metadata_class is None
            else self._selected_metadata_class.model_json_schema()
        )
        metadata_properties = metadata_schema["properties"]
        metadata_key_name = metadata_properties["metadata_type"]["default"]
        new_metadata_values = (
            self._metadata.model_dump(mode="json")
            if type(self._metadata) is self._selected_metadata_class
            else {}
        )
        for field_key, field_data in metadata_properties.items():
            if field_key == "metadata_type":
                new_metadata_values[field_key] = metadata_key_name
                continue
            metadata_type = self.get_metadata_type(field_data)
            input_field = self.query_one(f"#{field_key}")
            input_field_value = (
                input_field.text
                if input_field.has_class("textarea")
                else input_field.value
            )
            if "additionalProperties" in field_data:
                new_metadata_values[field_key] = (
                    metadata_type["empty_value"]
                    if bool(input_field_value) is False
                    else ast.literal_eval(input_field_value)
                )
                continue
            if input_field_value == "None" and metadata_type["is_optional"] is True:
                new_metadata_values[field_key] = None
                continue
            if metadata_type["true_type"] == "array":
                new_metadata_values[field_key] = (
                    None
                    if bool(input_field_value) is False
                    and metadata_type["is_optional"] is True
                    else input_field_value.split(",")
                )
                continue
            if metadata_type["true_type"] == "number":
                new_metadata_values[field_key] = (
                    None
                    if bool(input_field_value) is False
                    and metadata_type["is_optional"] is True
                    else int(input_field_value)
                )
                continue
            new_metadata_values[field_key] = (
                None
                if bool(input_field_value) is False
                and metadata_type["is_optional"] is True
                else input_field_value
            )
        return ALL_METADATA[metadata_key_name](**new_metadata_values)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "save":
            product.update(
                self._client,
                self._object_id,
                self.query_one("#product-title").value,
                self.query_one("#product-description").text,
                self._version,
                self.get_metadata_changes().model_dump(),
                self.get_new_source(),
                self.get_replace_sources(),
                self._drop_sources,
            )
            exit(0)
        elif event.button.id == "cancel":
            exit(0)
        else:
            raise AttributeError(f"Unknown button pressed: {event.button.id}")


def edit_product(client: Client, id: PydanticObjectId):
    """
    Edit the text of a product. This downloads the metadata for the product,
    and then launches a text editor to edit the text. Once the text is saved,
    the updated metadata is uploaded (if changed).
    """

    app = EditorApp(id, client)
    app.run()
