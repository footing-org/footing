import footing.config as footing


tools = footing.module("tools")

# Toolkits
black = tools.toolkit("black==22.12.0", "python==3.11")
poetry = tools.toolkit("poetry==1.3.0", "python==3.11")

lock = footing.task(
    poetry / "poetry lock --no-update", input="pyproject.toml", output="poetry.lock"
)
tk = tools.toolkit("python==3.11", poetry.bin / "poetry install", input=lock)

# Tasks
fmt = black / "black ."

# _poetry = tools_m.Toolkit([tools_m.Install(packages=["poetry==1.3.0", "python==3.11"])])

"""
lock = core_m.Task(
    [_poetry / "poetry lock --no-update"],
    input=[core_m.File("pyproject.toml")],
    output=[core_m.File("poetry.lock")],
)
tools = tools_m.Toolkit(
    [
        tools_m.Install(packages=["python==3.11"]),
        _poetry.bin / "poetry install",
    ],
    input=[lock],
)
"""

"""
# Dev tasks
format = _black / "black ."

# Runners
dev_pod = k8s_m.RunnerPod(
    runner=k8s_m.RSyncRunner(),
    services=[
        k8s_m.Service(
            name="db",
            image="postgres:15.1",
            env=[
                k8s_m.Env(name="POSTGRES_PASSWORD", value="postgres"),
                k8s_m.Env(name="POSTGRES_USER", value="postgres"),
            ],
            ports=[k8s_m.Port(container_port=5432)],
        )
    ],
)
"""

"""
# Toolkits
poetry = toolkit_m.Toolkit([toolkit_m.Conda(packages=["poetry==1.3.0", "python==3.11"])])
black = toolkit_m.Toolkit([toolkit_m.Conda(packages=["black==22.12.0", "python==3.11"])])

fmt2 = (
    tools_m.Toolkit([tools_m.Install(packages=["black==22.12.0", "python==3.11"])]).bin / "black ."
)


toolkit = toolkit_m.Toolkit(
    pre_install_hooks=[
        func_m.Func(
            condition=func_m.FilesChanged([obj_m.File("pyproject.toml")]),
            cmd="poetry lock --no-update",
            toolkit=poetry,
        ),
    ],
    installers=[
        toolkit_m.Conda(packages=["python==3.11"]),
        func_m.Func(
            condition=func_m.FilesChanged([obj_m.File("poetry.lock")]),
            cmd=func_m.Join(poetry, "poetry install"),
        ),
    ],
)

# Tasks
fmt = func_m.Func(cmd="black .", toolkit=black)

wheel = func_m.Func(
    cmd="sh build.sh",
    toolkit=poetry,
)

docker_core = func_m.Func(
    cmd="docker buildx build -f docker/core/Dockerfile -t footingorg/core --platform linux/arm64/v8 . --push",
)

docker_footing = func_m.Func(
    cmd="docker buildx build -f docker/footing/Dockerfile -t footingorg/footing --platform linux/arm64/v8 . --push",
)

docker_runner = func_m.Func(
    cmd="docker buildx build -f docker/runner/Dockerfile -t footingorg/runner --platform linux/arm64/v8 . --push",
)

docker_postgres = func_m.Func(
    cmd="docker buildx build -f dockder/postgres/Dockerfile -t footingorg/postgres:15.1 --platform linux/arm64/v8 . --push",
)

docker_actions = func_m.Func(
    cmd="docker buildx build -f docker/actions/Dockerfile -t footingorg/actions --platform linux/arm64/v8 . --push",
)

# Runners
dev_pod = k8s_m.FootingPod(
    runner=k8s_m.RSyncRunner(),
    services=[
        k8s_m.Service(
            name="db",
            image="postgres:15.1",
            env=[
                k8s_m.Env(name="POSTGRES_PASSWORD", value="postgres"),
                k8s_m.Env(name="POSTGRES_USER", value="postgres"),
            ],
            ports=[k8s_m.Port(container_port=5432)],
        )
    ],
)

# Other cluster pods
ga_pod = k8s_m.GithubActionsPod()
"""
