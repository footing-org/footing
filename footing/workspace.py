import dataclasses

import yaml

import footing.toolkit
import footing.util


def workspace_path():
    return footing.util.repo_cache_dir() / ".workspace.yml"


@dataclasses.dataclass
class Workspace:
    toolkit: footing.toolkit.Toolkit = None

    @classmethod
    def load(cls):
        try:
            with open(workspace_path()) as f:
                workspace = yaml.load(f, Loader=yaml.SafeLoader)
        except FileNotFoundError:
            workspace = {}

        if workspace.get("toolkit"):
            workspace["toolkit"] = footing.toolkit.get(workspace["toolkit"])

        if not workspace.get("toolkit"):
            workspace["toolkit"] = footing.toolkit.get()

        return cls(**workspace)

    def save(self):
        with open(workspace_path(), "w") as f:
            yaml.dump({"toolkit": self.toolkit.key if self.toolkit else None}, f)


def get():
    return Workspace.load()


def set(*, toolkit=None):
    workspace = get()
    if toolkit:
        workspace.toolkit = footing.toolkit.get(toolkit)

    workspace.save()


def unset(*, toolkit=None):
    workspace = get()
    if toolkit:
        workspace.toolkit = None

    workspace.save()
