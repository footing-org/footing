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
#    pod.Container("postgres:14.1"),
#    env=env.Env(
#        DATABASE_URL="postgres://localhost:5432/hello"
#    )
# )

# Variables
# env = footing.core.Var(name="env", label="Environment", description="Hello", type=str)

# Toolkits
poetry = toolkit_m.Toolkit([toolkit_m.Conda(packages=("poetry==1.3.0", "python==3.11"))])
black = toolkit_m.Toolkit([toolkit_m.Conda(packages=("black==22.12.0", "python==3.11"))])
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

tests = func_m.Func(
    cmd="pytest",
    toolkit=toolkit,
)

wheel = func_m.Func(
    cmd="bash -c 'sh build.sh && git add -u && git commit -m \"new release\" && git push origin mvp'",
    toolkit=poetry,
)

docker = func_m.Func(
    cmd="bash -c 'docker buildx build -t wesleykendall/footing --no-cache --platform linux/amd64,linux/arm64/v8 . --push'",
)

# Runners
dev_pod = k8s_m.GitPod()
