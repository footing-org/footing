import contextlib
import dataclasses
import os
import subprocess
import unittest.mock

import cookiecutter.config as cc_config
from cookiecutter.exceptions import NonTemplatedInputDirException
from cookiecutter.find import logger as find_logger
import cookiecutter.generate as cc_generate
import cookiecutter.hooks as cc_hooks
import cookiecutter.prompt as cc_prompt
import cookiecutter.repository as cc_repository
import formaldict
import yaml

import footing.check
import footing.constants
import footing.util
import footing.utils


def _patched_find_template(repo_dir):
    """Used to patch cookiecutter's ``find_template`` function."""
    find_logger.debug("Searching %s for the project template.", repo_dir)

    repo_dir_contents = os.listdir(repo_dir)

    project_template = None
    for item in repo_dir_contents:
        if ("cookiecutter" in item or "footing" in item) and "{{" in item and "}}" in item:
            project_template = item
            break

    if project_template:
        project_template = os.path.join(repo_dir, project_template)
        find_logger.debug("The project template appears to be %s", project_template)
        return project_template
    else:
        raise NonTemplatedInputDirException


def _write_footing_config(parameters, cast):
    """Writes the footing YAML configuration"""
    config = footing.util.local_config(create=True)
    config["casts"] = config.get("casts", [])
    config["casts"].append(dataclasses.asdict(cast))

    with open(footing.util.local_config_path(), "w") as config_file:

        def yaml_represent_str(self, data):
            return yaml.representer.SafeRepresenter.represent_str(
                self,
                str(data),
            )

        yaml.SafeDumper.yaml_representers[None] = lambda self, data: yaml_represent_str(self, data)
        yaml.dump(config, config_file, Dumper=yaml.SafeDumper)


def _patched_run_hook(hook_name, project_dir, context):
    """Used to patch cookiecutter's ``run_hook`` function.

    This patched version ensures that the .footing/config.yml file is created before
    any cookiecutter hooks are executed
    """
    if hook_name == "post_gen_project":
        with footing.util.cd(project_dir):
            _write_footing_config(parameters=context["footing"], cast=context["cast"])
    return cc_hooks.run_hook(hook_name, project_dir, context)


def _get_cast_repo_dir(url, version=None):
    cc_config_dict = cc_config.get_user_config()
    repo_dir, _ = cc_repository.determine_repo_dir(
        template=url.authenticated(),
        abbreviations=cc_config_dict["abbreviations"],
        clone_to_dir=cc_config_dict["cookiecutters_dir"],
        checkout=version,
        no_input=True,
    )
    return repo_dir, cc_config_dict


def _get_parameters(
    url: footing.util.RepoURL,
    default_parameters=None,
    version=None,
    supplied_parameters=None,
):
    """Obtains the configuration used for cookiecutter templating

    Args:
        url: Path to the template
        default_parameters (dict, optional): The default configuration
        version (str, optional): The git SHA or branch to use when
            checking out template. Defaults to latest version
        parameters (dict, optional): Parameters to use for setup. Will avoid
            prompting if supplied.

    Returns:
        tuple: The cookiecutter repo directory and the config dict
    """
    default_parameters = default_parameters or {}
    supplied_parameters = supplied_parameters or {}
    repo_dir, cc_config_dict = _get_cast_repo_dir(url, version=version)
    cc_context_file = os.path.join(repo_dir, "cookiecutter.json")
    config_file = os.path.join(repo_dir, footing.constants.FOOTING_CONFIG_FILE)

    if os.path.exists(config_file):
        with open(config_file) as f:
            config = yaml.load(f, Loader=yaml.SafeLoader)

        # Get the parameters and format the keys so that formaldict can parse them
        param_schema = config["molds"][0]["parameters"]
        for p in param_schema:
            p["name"] = p["label"]
            p["label"] = p["key"]

        param_schema = formaldict.Schema(param_schema)

        if supplied_parameters:
            parameters = param_schema.parse({**default_parameters, **supplied_parameters}).data
        else:
            parameters = param_schema.prompt(defaults=default_parameters).data
    elif os.path.exists(cc_context_file):
        context = cc_generate.generate_context(
            context_file=cc_context_file,
            default_context={**cc_config_dict["default_context"], **default_parameters},
        )
        parameters = cc_prompt.prompt_for_config(context, no_input=bool(supplied_parameters))
    else:
        raise RuntimeError("No footing.yaml found")

    if supplied_parameters:
        for key, val in supplied_parameters.items():
            parameters[key] = val

    return parameters, repo_dir


def _get_latest_sha(repo_dir):
    with footing.util.cd(repo_dir):
        try:
            ret = footing.util.git(
                "rev-parse HEAD", stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            return ret.stdout.decode("utf-8").strip()
        except subprocess.CalledProcessError:
            return None


@dataclasses.dataclass
class Cast:
    key: str
    url: footing.util.RepoPath
    version: str = None
    parameters: dict = dataclasses.field(default_factory=dict)

    @classmethod
    def from_url(cls, url: footing.util.RepoPath, version=None):
        """Create a cast from a URL, allowing a user to dynamically enter parameters"""
        repo_dir, _ = _get_cast_repo_dir(url)

        config_file = os.path.join(repo_dir, footing.constants.FOOTING_CONFIG_FILE)
        if os.path.exists(config_file):
            with open(config_file) as f:
                config = yaml.load(f, Loader=yaml.SafeLoader)
                config = config["molds"][0]
                cast = cls(
                    key=config["key"],
                    url=url,
                    version=version or config.get("version"),
                    parameters=config["parameters"],
                )
        else:
            cast = cls(key=url.parsed().path.split("/")[-1], url=url, version=version)

        # Fill in the default version last. This allows the footing config to specify
        # a version without it being overwritten
        cast.version = cast.version or _get_latest_sha(repo_dir)

        return cast

    def init(self, cwd=None, version=None, parameters=None):
        """Uses cookiecutter to generate files for the project.

        Monkeypatches cookiecutter's "run_hook" to ensure that the footing.yaml file is
        generated before any hooks run. This is important to ensure that hooks can also
        perform any actions involving footing.yaml
        """
        parameters, repo_dir = _get_parameters(
            url=self.url,
            version=version or self.version,
            supplied_parameters=parameters,
        )

        with contextlib.ExitStack() as stack:
            stack.enter_context(footing.util.cd(cwd or os.getcwd()))
            stack.enter_context(
                unittest.mock.patch(
                    "cookiecutter.generate.find_template",
                    side_effect=_patched_find_template,
                )
            )
            stack.enter_context(
                unittest.mock.patch(
                    "cookiecutter.generate.run_hook", side_effect=_patched_run_hook
                )
            )

            cast = Materialized(
                key=self.key,
                url=self.url,
                version=version or self.version,
                parameters=parameters,
            )

            cc_generate.generate_files(
                repo_dir=repo_dir,
                context={
                    "cookiecutter": parameters,
                    "footing": parameters,
                    "cast": cast,
                },
                overwrite_if_exists=False,
                output_dir=".",
            )

            return cast


@dataclasses.dataclass
class Materialized:
    key: str
    url: footing.util.RepoPath
    version: str
    parameters: dict
