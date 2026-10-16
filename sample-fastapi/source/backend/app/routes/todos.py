from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Todo

router = APIRouter(prefix="/api/todos", tags=["todos"])


class TodoIn(BaseModel):
    text: str = Field(min_length=1, max_length=255)


class TodoOut(BaseModel):
    id: int
    text: str
    done: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[TodoOut])
async def list_todos(session: AsyncSession = Depends(get_session)) -> list[Todo]:
    result = await session.execute(select(Todo).order_by(Todo.id.desc()))
    return list(result.scalars())


@router.post("", response_model=TodoOut, status_code=201)
async def create_todo(payload: TodoIn, session: AsyncSession = Depends(get_session)) -> Todo:
    todo = Todo(text=payload.text)
    session.add(todo)
    await session.commit()
    await session.refresh(todo)
    return todo


@router.delete("/{todo_id}", status_code=204)
async def delete_todo(todo_id: int, session: AsyncSession = Depends(get_session)) -> None:
    result = await session.execute(delete(Todo).where(Todo.id == todo_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="not found")
    await session.commit()
