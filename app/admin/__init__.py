"""SQLAdmin panel paketi — view'lar otomatik register edilir."""

import inspect
from sqladmin import ModelView
from app.admin import views as _views_module


def get_all_views() -> list[type[ModelView]]:
    return [
        cls
        for _, cls in inspect.getmembers(_views_module, inspect.isclass)
        if issubclass(cls, ModelView) and cls is not ModelView
    ]
