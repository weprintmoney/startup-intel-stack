"""Index routes (FastAPI)."""

from fastapi import APIRouter

router = APIRouter(prefix="/v1/indexes")


@router.post("")
async def create_index(req):            # dimension optional since v0.17.0
    ...


@router.post("/{name}/train")
async def train_index(name: str):
    ...


@router.post("/{name}/users")
async def create_user_keys(name: str, req):
    ...


@router.get("/{name}/users")
async def list_user_keys(name: str):
    ...


@router.delete("/{name}/users/{user_id}")
async def delete_user_keys(name: str, user_id: str):
    ...
