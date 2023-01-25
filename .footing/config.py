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

wheel = func_m.Func(cmd="bash -c 'sh build.sh && git add -u && git commit -m \'new release\' && git push'", toolkit=poetry)

# Runners
dev_pod = k8s_m.Pod()

###
# Example commands
#
# footing build ci_cluster  # Start the CI cluster
# footing build db_pod -c ci_cluster -r local_repo  # Start a db_pod on the CI cluster with the local repository mirrored
# footing build db_pod -c ci_cluster -r origin_repo -b hello  # Start a db_pod on the CI cluster with the remote repo checked out on branch "hello"
#
# footing run fmt  # Run code formatting locally
# footing run fmt -c ci_cluster -r local_repo  # Run code formatting remotely over repo (this example is nonsensical)
# footing run tests  # Run tests locally
