"""Source normalization: what must be stripped, and what must survive."""

from __future__ import annotations

from tauri_assistant.ingest.pipeline import dedupe_document_ids
from tauri_assistant.ingest.types import Document
from tauri_assistant.sources.tauri_docs import (
    CONTENT_ROOT,
    TauriDocsSource,
    page_url,
    parse_frontmatter,
    strip_mdx,
)
from tauri_assistant.sources.tauri_js_api import clean_jsdoc, iter_symbols


class TestMdx:
    def test_frontmatter_is_parsed_and_removed(self):
        fields, body = parse_frontmatter("---\ntitle: Hello\ni18nReady: true\n---\nbody\n")
        assert fields["title"] == "Hello"
        assert body.strip() == "body"

    def test_imports_are_dropped(self):
        assert "import" not in strip_mdx("import X from 'y';\n\ntext")

    def test_directives_become_blockquotes(self):
        out = strip_mdx(":::note[Use std::fs]\ncontent\n:::")
        assert ":::" not in out
        assert "> **Use std::fs**" in out
        assert "content" in out

    def test_xml_inside_a_code_fence_survives(self):
        """`windows-installer.mdx` embeds WiX XML that looks exactly like JSX.

        A regex sweep over the whole page would gut the example, which is the
        entire content of that section.
        """
        source = 'text\n\n```xml\n<Wix xmlns="http://x">\n  <Fragment>\n  </Fragment>\n</Wix>\n```'
        out = strip_mdx(source)
        assert "<Wix" in out
        assert "<Fragment>" in out

    def test_jsx_outside_a_fence_is_removed(self):
        assert "<PluginLinks" not in strip_mdx("<PluginLinks plugin={x} />\n\ntext")

    def test_component_wrapped_prose_is_kept(self):
        out = strip_mdx("<Tabs>\n<TabItem label='npm'>\nrun npm install\n</TabItem>\n</Tabs>")
        assert "run npm install" in out
        assert "<Tabs>" not in out

    def test_command_tabs_install_commands_are_extracted(self):
        """The install command lives only in the attributes."""
        out = strip_mdx('<CommandTabs npm="npm run tauri add sql"\n  cargo="cargo tauri add sql" />')
        assert "npm run tauri add sql" in out
        assert "cargo tauri add sql" in out

    def test_url_is_derived_from_the_path(self):
        assert page_url("develop/calling-rust.mdx") == "https://v2.tauri.app/develop/calling-rust/"
        assert page_url("plugin/index.mdx") == "https://v2.tauri.app/plugin/"


class TestDocumentTransform:
    """`TauriDocsSource.iter_documents`: a page on disk becomes one `Document`."""

    def test_a_page_is_transformed_into_its_document_fields(self, tmp_path, monkeypatch):
        monkeypatch.setattr(TauriDocsSource, "path", tmp_path)
        page_dir = tmp_path / CONTENT_ROOT / "develop"
        page_dir.mkdir(parents=True)
        (page_dir / "calling-rust.mdx").write_text(
            "---\n"
            "title: Calling Rust\n"
            "description: Invoke commands from the frontend.\n"
            "---\n"
            "import X from 'y';\n"
            "\n"
            "<PluginLinks plugin={x} />\n"
            "\n"
            "Call `invoke` from JavaScript.\n"
        )

        (doc,) = TauriDocsSource().iter_documents()

        assert doc.id == "tauri-docs:develop/calling-rust.mdx"
        assert doc.text == "Invoke commands from the frontend.\n\nCall `invoke` from JavaScript."
        assert doc.breadcrumb == ("Tauri Docs", "Develop", "Calling Rust")
        assert doc.metadata == {
            "source": "tauri-docs",
            "repo": "tauri-docs",
            "path": "src/content/docs/develop/calling-rust.mdx",
            "url": "https://v2.tauri.app/develop/calling-rust/",
            "kind": "guide",
        }

    def test_a_page_without_a_title_falls_back_to_its_filename(self, tmp_path, monkeypatch):
        monkeypatch.setattr(TauriDocsSource, "path", tmp_path)
        page_dir = tmp_path / CONTENT_ROOT / "plugin"
        page_dir.mkdir(parents=True)
        (page_dir / "file-system.mdx").write_text("no frontmatter here\n")

        (doc,) = TauriDocsSource().iter_documents()

        assert doc.breadcrumb == ("Tauri Docs", "Plugin", "File System")


class TestJsApi:
    def test_jsdoc_gutter_is_stripped(self):
        assert clean_jsdoc("\n * Line one\n * Line two\n ") == "Line one\nLine two"

    def test_trailing_export_block_is_understood(self):
        """9 of 14 modules export at the bottom rather than inline."""
        text = "/** Listens for an event. */\nfunction listen() {}\n\nexport { listen }\n"
        assert [s.qualified for s in iter_symbols(text)] == ["listen"]

    def test_inline_exports_are_understood(self):
        text = "/** Listens for an event. */\nexport async function listen<T>() {}\n"
        assert [s.qualified for s in iter_symbols(text)] == ["listen"]

    def test_renamed_exports_are_matched_by_their_local_name(self):
        """`export { internal as publicName }` documents `internal` in this file.

        The public alias is what call sites import, but it is never a name
        that appears in this module's own AST -- matching against it instead
        of the local declaration would drop every renamed export's docs.
        """
        text = "/** Does the thing. */\nfunction internal() {}\n\nexport { internal as publicName }\n"
        assert [s.qualified for s in iter_symbols(text)] == ["internal"]

    def test_non_exported_symbol_without_english_doc_is_dropped(self):
        text = "/** does the thing */\nfunction helper() {}\n"
        assert list(iter_symbols(text)) == []

    def test_non_exported_symbol_with_english_doc_is_kept(self):
        text = "/** The internal retry budget. */\nconst RETRY_BUDGET = 3\n"
        assert [s.qualified for s in iter_symbols(text)] == ["RETRY_BUDGET"]

    def test_wrapped_signatures_are_joined(self):
        text = (
            "/** Listens for an event. */\n"
            "export async function listen<T>(\n"
            "  event: EventName,\n"
            "): Promise<void> {\n"
            "  return invoke('listen', { event })\n"
            "}\n"
        )
        (symbol,) = iter_symbols(text)
        assert "event: EventName" in symbol.signature

    def test_class_members_are_qualified_with_their_class(self):
        text = (
            "/** A window handle. */\n"
            "export class Window {\n"
            "  /** Sets the window title. */\n"
            "  async setTitle(title: string): Promise<void> {\n"
            "    return invoke('set_title', { title })\n"
            "  }\n"
            "}\n"
        )
        assert [s.qualified for s in iter_symbols(text)] == ["Window", "Window.setTitle"]

    def test_enclosing_class_does_not_leak_past_its_closing_brace(self):
        """A stale "last class seen" would wrongly qualify `listen` as `Window.listen`."""
        text = (
            "/** A window handle. */\n"
            "export class Window {\n"
            "  /** Sets the window title. */\n"
            "  async setTitle(title: string): Promise<void> {}\n"
            "}\n"
            "\n"
            "/** Listens for an event. */\n"
            "export async function listen(): Promise<void> {}\n"
        )
        assert [s.qualified for s in iter_symbols(text)] == ["Window", "Window.setTitle", "listen"]


class TestDedupe:
    def test_colliding_ids_are_disambiguated(self):
        docs = [Document(id="a", text="1", breadcrumb=()), Document(id="a", text="2", breadcrumb=())]
        out = dedupe_document_ids(docs)
        assert len({d.id for d in out}) == 2

    def test_unique_ids_are_untouched(self):
        docs = [Document(id="a", text="1", breadcrumb=()), Document(id="b", text="2", breadcrumb=())]
        assert [d.id for d in dedupe_document_ids(docs)] == ["a", "b"]

    def test_dedupe_is_deterministic(self):
        docs = [Document(id="a", text=str(i), breadcrumb=()) for i in range(3)]
        assert [d.id for d in dedupe_document_ids(docs)] == [d.id for d in dedupe_document_ids(docs)]

    def test_byte_identical_collision_is_dropped_not_suffixed(self):
        """A cfg-gated re-declaration with the same doc comment and signature.

        Suffixing its id would still leave two chunks with the same
        content-addressed id (breadcrumb + text), which Chroma's upsert
        rejects as a duplicate within one call.
        """
        docs = [Document(id="a", text="same", breadcrumb=()), Document(id="a", text="same", breadcrumb=())]
        out = dedupe_document_ids(docs)
        assert [d.id for d in out] == ["a"]

    def test_identical_text_recognized_regardless_of_position(self):
        """The third occurrence matches the first, not the intervening variant."""
        docs = [
            Document(id="a", text="x", breadcrumb=()),
            Document(id="a", text="y", breadcrumb=()),
            Document(id="a", text="x", breadcrumb=()),
        ]
        out = dedupe_document_ids(docs)
        assert [(d.id, d.text) for d in out] == [("a", "x"), ("a#2", "y")]
