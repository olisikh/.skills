"""Tests for convention-based submodule exports."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import Config
from lib.sync import sync_harness, uninstall_harness


class SubmoduleExportTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source_root = self.root / "submodules" / "shared-skills"
        self.source = self.source_root / "skills" / "category" / "example"
        self.source.mkdir(parents=True)
        (self.source / "SKILL.md").write_text("---\nname: example\n---\n")
        for harness in ("agents", "claude", "hermes"):
            (self.root / "home" / f".{harness}").mkdir(parents=True)
        (self.root / "harness-paths.yaml").write_text(
            "harness:\n"
            f"  agents: {self.root / 'home' / '.agents'}\n"
            f"  claude: {self.root / 'home' / '.claude'}\n"
            f"  hermes: {self.root / 'home' / '.hermes'}\n"
        )
        (self.root / ".gitmodules").write_text(
            '[submodule "shared-skills"]\n'
            "\tpath = submodules/shared-skills\n"
            "\turl = https://example.test/shared-skills.git\n"
        )
        self.write_config("    exports:\n      - harness: agents\n")
        self.config = Config(self.root)

    def tearDown(self):
        self.tempdir.cleanup()

    def write_config(self, body: str, prefix: str = ""):
        (self.root / "config.yaml").write_text(
            "version: 2\n" + prefix + "submodules:\n" + "  shared-skills:\n" + body
        )

    def test_new_submodule_skills_install_without_approval_state(self):
        self.assertEqual(
            [
                (harness, target)
                for harness, target, _ in self.config.list_harness_targets()
            ],
            [("agents", "skills/example")],
        )

        sync_harness(self.config, "agents")

        target = self.root / "home" / ".agents" / "skills" / "example"
        self.assertEqual(target.resolve(), self.source.resolve())
        self.assertFalse((target.parent / "category").exists())

    def test_include_and_exclude_filter_discovered_skill_paths(self):
        other = self.source_root / "skills" / "other"
        other.mkdir()
        (other / "SKILL.md").write_text("---\nname: other\n---\n")
        self.write_config(
            """    exports:
      - harness: claude
        include:
          - category/example
          - other
        exclude:
          - other
"""
        )

        self.assertEqual(
            [
                (harness, target)
                for harness, target, _ in self.config.list_harness_targets()
            ],
            [("claude", "skills/example")],
        )

    def test_exact_file_and_directory_exports_use_harness_relative_targets(self):
        references = self.source_root / "references"
        references.mkdir()
        skill_file = self.source_root / "skill.md"
        skill_file.write_text("skill")
        self.write_config(
            """    exports:
      - from: skill.md
        harness: agents
        to: commands/example.md
      - from: references
        harness: agents
        to: shared/example/references
"""
        )

        sync_harness(self.config, "agents")

        home = self.root / "home" / ".agents"
        self.assertEqual(
            (home / "commands" / "example.md").resolve(), skill_file.resolve()
        )
        self.assertEqual(
            (home / "shared" / "example" / "references").resolve(),
            references.resolve(),
        )

    def test_setup_commands_are_exposed_but_not_run_by_sync(self):
        self.write_config(
            """    setup:
      - tool setup --editable .
    exports:
      - harness: agents
"""
        )

        self.assertEqual(
            list(self.config.submodule_setup_commands()),
            [
                (
                    "shared-skills",
                    self.source_root.resolve(),
                    ["tool", "setup", "--editable", "."],
                )
            ],
        )

    def test_physical_path_can_override_submodules_name_convention(self):
        moved = self.root / "vendor" / "shared"
        moved.parent.mkdir()
        self.source_root.rename(moved)
        (self.root / ".gitmodules").write_text(
            '[submodule "shared-skills"]\n'
            "\tpath = vendor/shared\n"
            "\turl = https://example.test/shared-skills.git\n"
        )
        self.write_config(
            """    path: vendor/shared
    exports:
      - harness: agents
"""
        )

        self.config.validate()
        self.assertEqual(self.config.configured_submodule_names(), ["vendor/shared"])

    def test_harness_local_skills_need_no_configuration(self):
        local = self.root / "harness" / "agents" / "skills" / "category" / "local"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: local\n---\n")
        (self.root / "config.yaml").write_text("version: 2\nsubmodules: {}\n")

        self.assertEqual(
            [
                (harness, target)
                for harness, target, _ in self.config.list_harness_targets()
            ],
            [("agents", "skills/local")],
        )

    def test_duplicate_flattened_targets_are_errors(self):
        local = self.root / "harness" / "agents" / "skills" / "local" / "example"
        local.mkdir(parents=True)
        (local / "SKILL.md").write_text("---\nname: example\n---\n")

        with self.assertRaisesRegex(
            SystemExit, "Duplicate target agents:skills/example"
        ):
            self.config.list_harness_targets()

    def test_mirror_uses_flattened_agent_skill_target(self):
        self.write_config(
            "    exports:\n      - harness: agents\n",
            prefix="skill_mirrors:\n  claude:\n    from: agents\n",
        )

        self.assertEqual(
            [
                (harness, target)
                for harness, target, _ in self.config.list_harness_targets()
            ],
            [("agents", "skills/example"), ("claude", "skills/example")],
        )

    def test_parent_path_escape_is_rejected(self):
        self.write_config(
            """    exports:
      - from: ../outside
        harness: agents
"""
        )
        with self.assertRaisesRegex(SystemExit, "must stay inside"):
            self.config.list_harness_targets()

    def test_configured_path_must_be_declared_in_gitmodules(self):
        (self.root / ".gitmodules").write_text("")
        with self.assertRaisesRegex(SystemExit, "absent from .gitmodules"):
            self.config.validate()

    def test_ancestor_and_descendant_targets_are_errors(self):
        child = self.source_root / "child.md"
        child.write_text("child")
        self.write_config(
            """    exports:
      - from: skills
        harness: agents
        to: shared/example
      - from: child.md
        harness: agents
        to: shared/example/child.md
"""
        )

        with self.assertRaisesRegex(SystemExit, "Overlapping targets"):
            self.config.list_harness_targets()

    def test_symlinked_target_parent_cannot_escape_harness_home(self):
        outside = self.root / "outside"
        outside.mkdir()
        commands = self.root / "home" / ".agents" / "commands"
        commands.symlink_to(outside)
        skill_file = self.source_root / "skill.md"
        skill_file.write_text("skill")
        self.write_config(
            """    exports:
      - from: skill.md
        harness: agents
        to: commands/example.md
"""
        )

        sync_harness(self.config, "agents")

        self.assertFalse((outside / "example.md").exists())

    def test_untracked_repo_symlink_outside_skills_is_preserved(self):
        sync_harness(self.config, "agents")
        manual = self.root / "home" / ".agents" / "manual"
        manual.symlink_to(self.source)

        sync_harness(self.config, "agents")

        self.assertTrue(manual.is_symlink())

    def test_export_source_symlink_cannot_escape_submodule(self):
        outside = self.root / "outside.md"
        outside.write_text("outside")
        (self.source_root / "outside-link.md").symlink_to(outside)
        self.write_config(
            """    exports:
      - from: outside-link.md
        harness: agents
        to: commands/outside.md
"""
        )

        with self.assertRaisesRegex(SystemExit, "resolves outside submodule"):
            self.config.list_harness_targets()

    def test_cleanup_cannot_escape_through_replaced_parent_symlink(self):
        skill_file = self.source_root / "skill.md"
        skill_file.write_text("skill")
        self.write_config(
            """    exports:
      - from: skill.md
        harness: agents
        to: commands/example.md
"""
        )
        sync_harness(self.config, "agents")

        commands = self.root / "home" / ".agents" / "commands"
        (commands / "example.md").unlink()
        commands.rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        external_target = outside / "example.md"
        external_target.symlink_to(skill_file)
        commands.symlink_to(outside)
        self.write_config("    exports: []\n")

        sync_harness(self.config, "agents")
        self.assertTrue(external_target.is_symlink())

        # Recreate prior manifest entry and confirm uninstall has same guard.
        manifest = self.root / "home" / ".agents" / ".llm-harness-managed-targets.json"
        manifest.write_text('{"version": 1, "targets": ["commands/example.md"]}\n')
        uninstall_harness(self.config, "agents")
        self.assertTrue(external_target.is_symlink())


if __name__ == "__main__":
    unittest.main()
