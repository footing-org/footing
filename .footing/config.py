import footing.config


toolkit_m, func_m, obj_m, k8s_m = footing.config.module("toolkit", "func", "obj", "k8s")

# Repository
# origin_repo = repo.Remote(
#    name="origin",
#    url="github.com/Opus10/hello-world"
# )
# local_repo = repo.Local()

# Cluster and runner definitions
# ci_cluster = cluster.DitigalOceanCluster("canal-ci-cluster")
# db_pod = pod.Runner(
#    pod.Service("postgres:14.1"),
#    env=env.Env(
#        DATABASE_URL="postgres://localhost:5432/hello"
#    )
# )

# Variables
# env = footing.core.Var(name="env", label="Environment", description="Hello", type=str)

# Toolkits
poetry = toolkit_m.Toolkit([toolkit_m.Conda(packages=["poetry==1.3.0", "python==3.11"])])
black = toolkit_m.Toolkit([toolkit_m.Conda(packages=["black==22.12.0", "python==3.11"])])
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
