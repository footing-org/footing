import dataclasses

import footing.config
import footing.obj

toolkit_pi, func_pi = footing.config.plugin("toolkit", "func")

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

# Toolkits
poetry = toolkit_pi.Toolkit([toolkit_pi.Conda(packages=("poetry==1.3.0", "python==3.11"))])
black = toolkit_pi.Toolkit([toolkit_pi.Conda(packages=("black==22.12.0", "python==3.11"))])
toolkit = toolkit_pi.Toolkit(
    pre_install_hooks=[
        func_pi.Func(
            condition=func_pi.FilesChanged([footing.obj.File("pyproject.toml")]),
            cmd="poetry lock --no-update",
            toolkit=poetry,
        ),
    ],
    installers=[
        toolkit_pi.Conda(packages=["python==3.11"]),
        func_pi.Func(
            condition=func_pi.FilesChanged([footing.obj.File("poetry.lock")]),
            cmd=func_pi.Join(poetry, "poetry install"),
        ),
    ],
)

# Tasks
fmt = func_pi.Func(cmd="black .", toolkit=black)

tests = func_pi.Func(
    cmd="pytest",
    toolkit=toolkit,
)

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
