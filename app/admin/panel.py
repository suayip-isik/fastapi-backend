"""Permission-aware SQLAdmin wrapper."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl

from fastapi import HTTPException
from sqladmin import Admin
from starlette.datastructures import URL, MultiDict
from starlette.responses import RedirectResponse, Response

from app.admin.views import PermissionScopedModelView

if TYPE_CHECKING:
    from starlette.requests import Request


class PermissionAwareAdmin(Admin):
    """SQLAdmin routes that evaluate request-scoped action permissions."""

    def _action_flags(
        self, model_view: PermissionScopedModelView, request: Request
    ) -> dict[str, bool]:
        return {
            "can_create": model_view.can_create_for_request(request),
            "can_edit": model_view.can_edit_for_request(request),
            "can_delete": model_view.can_delete_for_request(request),
            "can_view_details": model_view.can_view_details_for_request(request),
            "can_export": model_view.can_export_for_request(request),
        }

    def _guard(self, request: Request, action: str) -> PermissionScopedModelView:
        model_view = self._find_model_view(request.path_params["identity"])
        if not isinstance(model_view, PermissionScopedModelView):
            raise HTTPException(status_code=500, detail="Unsupported admin view type")
        if not model_view.is_action_accessible(request, action):
            raise HTTPException(status_code=403)
        return model_view

    async def list(self, request: Request) -> Response:
        model_view = self._guard(request, "list")
        pagination = await model_view.list(request)
        pagination.add_pagination_urls(request.url)

        if pagination.page * pagination.page_size > pagination.count + pagination.page_size:
            raise HTTPException(status_code=400, detail="Invalid page or pageSize parameter")

        context: dict[str, Any] = {
            "model_view": model_view,
            "pagination": pagination,
            **self._action_flags(model_view, request),
        }
        return await self.templates.TemplateResponse(request, model_view.list_template, context)

    async def details(self, request: Request) -> Response:
        model_view = self._guard(request, "details")
        model = await model_view.get_object_for_details(request.path_params["pk"])
        if not model:
            raise HTTPException(status_code=404)

        context: dict[str, Any] = {
            "model_view": model_view,
            "model": model,
            "title": model_view.name,
            **self._action_flags(model_view, request),
        }
        return await self.templates.TemplateResponse(request, model_view.details_template, context)

    async def delete(self, request: Request) -> Response:
        model_view = self._guard(request, "delete")
        identity = request.path_params["identity"]

        params = request.query_params.get("pks", "")
        pks = params.split(",") if params else []
        for pk in pks:
            model = await model_view.get_object_for_delete(pk)
            if not model:
                raise HTTPException(status_code=404)
            await model_view.delete_model(request, pk)

        referer_url = URL(request.headers.get("referer", ""))
        referer_params = MultiDict(parse_qsl(referer_url.query))
        url = URL(str(request.url_for("admin:list", identity=identity))).include_query_params(
            **referer_params
        )
        return Response(content=str(url))

    async def create(self, request: Request) -> Response:
        model_view = self._guard(request, "create")

        form_cls = await model_view.scaffold_form()
        model_view._validate_form_class(model_view._form_create_rules, form_cls)
        form_data = await self._handle_form_data(request)
        form = form_cls(form_data)

        context: dict[str, Any] = {
            "model_view": model_view,
            "form": form,
            **self._action_flags(model_view, request),
        }

        if request.method == "GET":
            return await self.templates.TemplateResponse(
                request, model_view.create_template, context
            )

        if not form.validate():
            return await self.templates.TemplateResponse(
                request, model_view.create_template, context, status_code=400
            )

        form_data_dict = self._denormalize_wtform_data(form.data, model_view.model)
        try:
            obj = await model_view.insert_model(request, form_data_dict)
        except Exception as exc:
            context["error"] = str(exc)
            return await self.templates.TemplateResponse(
                request, model_view.create_template, context, status_code=400
            )

        url = self.get_save_redirect_url(
            request=request,
            form=form_data,
            obj=obj,
            model_view=model_view,
        )
        return RedirectResponse(url=url, status_code=302)

    async def edit(self, request: Request) -> Response:
        model_view = self._guard(request, "edit")
        model = await model_view.get_object_for_edit(request)
        if not model:
            raise HTTPException(status_code=404)

        form_cls = await model_view.scaffold_form()
        model_view._validate_form_class(model_view._form_edit_rules, form_cls)
        context: dict[str, Any] = {
            "obj": model,
            "model_view": model_view,
            "form": form_cls(obj=model, data=self._normalize_wtform_data(model)),
            **self._action_flags(model_view, request),
        }

        if request.method == "GET":
            return await self.templates.TemplateResponse(request, model_view.edit_template, context)

        form_data = await self._handle_form_data(request, model)
        form = form_cls(form_data)
        if not form.validate():
            context["form"] = form
            return await self.templates.TemplateResponse(
                request, model_view.edit_template, context, status_code=400
            )

        form_data_dict = self._denormalize_wtform_data(form.data, model)
        try:
            obj = await model_view.update_model(
                request, pk=request.path_params["pk"], data=form_data_dict
            )
        except Exception as exc:
            context["error"] = str(exc)
            return await self.templates.TemplateResponse(
                request, model_view.edit_template, context, status_code=400
            )

        url = self.get_save_redirect_url(
            request=request,
            form=form_data,
            obj=obj,
            model_view=model_view,
        )
        return RedirectResponse(url=url, status_code=302)

    async def export(self, request: Request) -> Response:
        model_view = self._guard(request, "export")
        export_type = request.path_params["export_type"]
        if export_type not in model_view.export_types:
            raise HTTPException(status_code=404)

        rows = await model_view.get_model_objects(request=request, limit=model_view.export_max_rows)
        return await model_view.export_data(rows, export_type=export_type)
