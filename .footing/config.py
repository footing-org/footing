import footing.config as footing


tools, k8s = footing.module("tools", "k8s")

# Toolkits
black = tools.toolkit("black==22.12.0", "python==3.11")
poetry = tools.toolkit("poetry==1.3.0", "python==3.11")
lock = footing.sh(
    poetry.sh("poetry lock --no-update"), input="pyproject.toml", output="poetry.lock"
)
tk = tools.toolkit("python==3.11", poetry.bin("poetry install", input=lock))

# Tasks
fmt = black.sh("black .", entry=True)

# Artifacts
wheel = footing.sh(poetry.sh("sh build.sh"), input="**", output="*.whl")
docker_core = footing.sh(
    "docker buildx build -f docker/core/Dockerfile -t footingorg/core --platform linux/arm64/v8,linux/amd64 . --push",
    input=[wheel, "docker/core/*"],
)
docker_footing = footing.sh(
    "docker buildx build -f docker/footing/Dockerfile -t footingorg/footing --platform linux/arm64/v8,linux/amd64 . --push",
    input=[docker_core, "docker/footing/*"],
)
docker_runner = footing.sh(
    "docker buildx build -f docker/runner/Dockerfile -t footingorg/runner --platform linux/arm64/v8,linux/amd64 . --push",
    input=[docker_core, "docker/runner/*"],
)
docker_postgres = footing.sh(
    "docker buildx build -f docker/postgres/Dockerfile -t footingorg/postgres:14.7.0 --platform linux/arm64/v8,linux/amd64 . --push",
    input=["docker/postgres/*"],
)
docker_actions = footing.sh(
    "docker buildx build -f docker/actions/Dockerfile -t footingorg/actions --platform linux/arm64/v8,linux/amd64 . --push",
    input=[docker_core, "docker/actions/*"],
)

# Runners
dev_pod = k8s.git_runner()
rfmt = dev_pod / fmt
