from typing import Dict

from pydantic import BaseModel


class BaseFont(BaseModel):
    family: str


class Typography(BaseModel):
    base: BaseFont


class BrandColor(BaseModel):
    palette: Dict[str, str]
    primary: str


class Brand(BaseModel):
    color: BrandColor
    typography: Typography


class ThemeModel(BaseModel):
    brand: Brand
