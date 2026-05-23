"""BSC Forge — Ürün Router'ı"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.product_store import product_store

router = APIRouter()


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = "🤖"
    system_prompt: str | None = None
    tools_enabled: list[str] = []
    preferred_provider: str = "auto"
    preferred_model: str = "auto"


@router.get("/products")
async def list_products():
    products = await product_store.list_products()
    return {"products": products}


@router.get("/products/{product_id}")
async def get_product(product_id: str):
    product = await product_store.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return product


@router.post("/products")
async def create_product(body: ProductCreate):
    return await product_store.create_product(body.model_dump())


@router.delete("/products/{product_id}")
async def delete_product(product_id: str):
    product = await product_store.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    if product["is_builtin"]:
        raise HTTPException(status_code=403, detail="Yerleşik ürünler silinemez")
    await product_store.delete_product(product_id)
    return {"status": "silindi"}
