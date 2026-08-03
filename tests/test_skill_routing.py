"""Tests for gating new skills until their configured routing is approved."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.config import Config
from lib.routing import approve_skill, discover_unapproved_skills, seed_routing_index
from lib.sync import sync_harness


class SkillRoutingTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.source = self.root / "shared-skills" / "category" / "example"
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
        self.write_config("")
        self.config = Config(self.root)
        self.source_id = "shared-skills/category/example"

    def tearDown(self):
        self.tempdir.cleanup()

    def write_config(self, extra: str, source_type: str = "local"):
        (self.root / "config.yaml").write_text(
            f"""sources:
  shared-skills:
    type: {source_type}
    root: .
    harness: agents
"""
            + extra
        )

    def test_unapproved_skill_is_withheld_until_its_configured_route_is_approved(self):
        self.write_config("", source_type="submodule")
        (self.root / "state").mkdir()
        (self.root / "state" / "skill-routing-index.json").write_text(
            '{"version": 1, "skills": {}}\n'
        )

        candidates = discover_unapproved_skills(self.config)

        self.assertEqual(
            [candidate.source for candidate in candidates], [self.source_id]
        )
        self.assertEqual(candidates[0].harness, "agents")
        self.assertEqual(list(self.config.list_configured_skills()), [])

        approve_skill(
            self.config, self.source_id, "agents", reason="general-use workflow"
        )

        self.assertEqual(
            [
                (harness, relative_path)
                for harness, relative_path, _ in self.config.list_configured_skills()
            ],
            [("agents", "example")],
        )
        index = json.loads(
            (self.root / "state" / "skill-routing-index.json").read_text()
        )
        self.assertEqual(
            index["skills"][self.source_id],
            {
                "harness": "agents",
                "path": "category/example",
                "reason": "general-use workflow",
            },
        )

    def test_source_specific_config_route_is_the_route_that_must_be_approved(self):
        self.write_config(
            """routes:
  shared-skills/category/example: claude
""",
            source_type="submodule",
        )
        (self.root / "state").mkdir()
        (self.root / "state" / "skill-routing-index.json").write_text(
            '{"version": 1, "skills": {}}\n'
        )

        candidate = discover_unapproved_skills(self.config)[0]

        self.assertEqual(candidate.harness, "claude")
        with self.assertRaises(SystemExit):
            approve_skill(self.config, self.source_id, "agents")
        approve_skill(self.config, self.source_id, "claude")
        self.assertEqual(
            [
                (harness, relative_path)
                for harness, relative_path, _ in self.config.list_configured_skills()
            ],
            [("claude", "example")],
        )

    def test_seed_indexes_existing_effective_routes(self):
        self.write_config("", source_type="submodule")
        seeded = seed_routing_index(self.config)

        self.assertEqual(seeded, 1)
        self.assertEqual(len(discover_unapproved_skills(self.config)), 0)
        self.assertEqual(
            [
                (harness, relative_path)
                for harness, relative_path, _ in self.config.list_configured_skills()
            ],
            [("agents", "example")],
        )

    def test_local_skill_is_not_approval_gated(self):
        (self.root / "state").mkdir()
        (self.root / "state" / "skill-routing-index.json").write_text(
            '{"version": 1, "skills": {}}\n'
        )

        local_source = (
            self.root / "harness" / "agents" / "skills" / "category" / "local-example"
        )
        local_source.mkdir(parents=True)
        (local_source / "SKILL.md").write_text("---\nname: local-example\n---\n")
        non_skill = self.root / "harness" / "agents" / "skills" / "not-a-skill"
        non_skill.mkdir(parents=True)
        (non_skill / "README.md").write_text("not a skill")
        (self.root / "config.yaml").write_text("sources: {}\n")

        self.assertEqual(discover_unapproved_skills(self.config), [])
        self.assertEqual(
            [
                (harness, relative_path)
                for harness, relative_path, _ in self.config.list_configured_skills()
            ],
            [("agents", "local-example")],
        )
        sync_harness(self.config, "agents")
        target = self.root / "home" / ".agents" / "skills" / "local-example"
        self.assertEqual(target.resolve(), local_source.resolve())
        self.assertFalse((target.parent / "category").exists())
        self.assertFalse((target.parent / "not-a-skill").exists())

        with self.assertRaisesRegex(SystemExit, "does not require approval"):
            approve_skill(
                self.config, "harness/agents/skills/category/local-example", "agents"
            )

    def test_artifacts_install_explicit_files_and_directories(self):
        source_root = self.root / "graphify" / "graphify"
        (source_root / "skills" / "opencode" / "references").mkdir(parents=True)
        (source_root / "skill-opencode.md").write_text("---\nname: graphify\n---\n")
        self.write_config(
            """  graphify:
    type: local
    artifacts:
      - from: graphify/skill-opencode.md
        harness: agents
        to: skills/graphify/SKILL.md
      - from: graphify/skills/opencode/references
        harness: agents
        to: skills/graphify/references
"""
        )

        self.assertEqual(
            [item[:3] for item in self.config.list_discovered_skills()],
            [
                (self.source_id, "agents", "category/example"),
                ("graphify/graphify/skill-opencode.md", "agents", "graphify/SKILL.md"),
                (
                    "graphify/graphify/skills/opencode/references",
                    "agents",
                    "graphify/references",
                ),
            ],
        )
        self.assertEqual(seed_routing_index(self.config), 0)
        self.assertEqual(
            [
                (harness, path)
                for harness, path, _ in self.config.list_configured_skills()
            ],
            [
                ("agents", "example"),
                ("agents", "graphify/SKILL.md"),
                ("agents", "graphify/references"),
            ],
        )

    def test_source_install_commands_run_from_source_directory(self):
        source_root = self.root / "graphify"
        source_root.mkdir()
        self.write_config(
            """  graphify:
    type: local
    install:
      - tool setup --editable .
"""
        )

        self.assertEqual(
            list(self.config.source_install_commands()),
            [(source_root.resolve(), ["tool", "setup", "--editable", "."])],
        )

    def test_source_path_preserves_logical_routing_ids(self):
        moved_source = (
            self.root
            / "submodules"
            / "shared-skills"
            / "skills"
            / "category"
            / "example"
        )
        moved_source.parent.mkdir(parents=True)
        self.source.rename(moved_source)
        (self.root / "config.yaml").write_text(
            """sources:
  shared-skills:
    type: submodule
    path: submodules/shared-skills
    root: skills
    harness: agents
"""
        )

        self.assertEqual(
            [item[:3] for item in self.config.list_discovered_skills()],
            [("shared-skills/skills/category/example", "agents", "category/example")],
        )
        self.assertEqual(
            self.config.configured_submodule_names(), ["submodules/shared-skills"]
        )

    def test_nested_skills_are_flattened_for_every_target(self):
        sync_harness(self.config, "agents")
        target = self.root / "home" / ".agents" / "skills" / "example"
        self.assertEqual(target.resolve(), self.source.resolve())
        self.assertFalse((target.parent / "category").exists())

    def test_harness_local_skill_wins_a_flattened_name_collision(self):
        local_source = self.root / "harness" / "agents" / "skills" / "local" / "example"
        local_source.mkdir(parents=True)
        (local_source / "SKILL.md").write_text("---\nname: example\n---\nlocal\n")

        sync_harness(self.config, "agents")

        target = self.root / "home" / ".agents" / "skills" / "example"
        self.assertEqual(target.resolve(), local_source.resolve())

    def test_claude_mirror_uses_the_flattened_agent_skill_path(self):
        self.write_config(
            """skill_mirrors:
  claude:
    from: agents
"""
        )

        self.assertEqual(
            [(harness, path) for harness, path, _ in self.config.list_skill_targets()],
            [("agents", "example"), ("claude", "example")],
        )

        sync_harness(self.config, "claude")
        self.assertEqual(
            (self.root / "home" / ".claude" / "skills" / "example").resolve(),
            self.source.resolve(),
        )


if __name__ == "__main__":
    unittest.main()
