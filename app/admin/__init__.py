"""SQLAdmin panel paketi — view'lar otomatik register edilir."""

import inspect

from sqladmin import ModelView

from app.admin import views as _views_module

_ABSTRACT_VIEWS = {"PermissionScopedModelView"}


def get_all_views() -> list[type[ModelView]]:
    """app.admin.views modulundeki tum ModelView siniflarini toplar."""
    return [
        cls
        for _, cls in inspect.getmembers(_views_module, inspect.isclass)
        if issubclass(cls, ModelView)
        and cls is not ModelView
        and cls.__name__ not in _ABSTRACT_VIEWS
    ]
