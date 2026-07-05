from fastapi import APIRouter

from backend.app.runners.docker_r_env_checker import DockerREnvironmentChecker
from backend.app.runners.r_env_checker import REnvironmentChecker


router = APIRouter(tags=["system"])


@router.get("/system/r-env")
def get_r_environment() -> dict:
    return REnvironmentChecker().check()


@router.get("/system/docker-r-env")
def get_docker_r_environment() -> dict:
    return DockerREnvironmentChecker().check()
