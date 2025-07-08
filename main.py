from fastapi import FastAPI
from typing import Any
from pydantic import BaseModel

app = FastAPI()

# test code
@app.get("/")
def home():
    return {"Hello": "World"}

class Item(BaseModel):
    name: str
    price: int
    is_offer: bool | None = None

@app.post("/items/")
def create_item(item: Item):
    return { "item": item }

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None) -> dict[str, Any]:
    return {"item_id": item_id, "q": q or "none"}

