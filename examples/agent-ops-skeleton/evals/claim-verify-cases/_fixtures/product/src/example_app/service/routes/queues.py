"""Queue routes (FastAPI)."""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/queues")


@router.post("")
async def create_queue(req):            # partitions optional since v0.33.0
    ...


@router.post("/{name}/pause")
async def pause_queue(name: str):
    ...


@router.post("/{name}/users")
async def create_user_tokens(name: str, req):
    ...


@router.get("/{name}/users")
async def list_user_tokens(name: str):
    ...


@router.delete("/{name}/users/{user_id}")
async def delete_user_tokens(name: str, user_id: str):
    ...
