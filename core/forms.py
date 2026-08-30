from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from .models import Ticket, Comentario


_PASSWORD_INPUT_CSS = (
    "w-full text-sm bg-white dark:bg-slate-700 text-gray-800 dark:text-gray-100 "
    "border border-gray-300 dark:border-slate-600 rounded px-3 py-1.5 "
    "focus:outline-none focus:ring-1 focus:ring-brand-500"
)


class CambioPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Repetí la nueva contraseña"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = _PASSWORD_INPUT_CSS
            campo.help_text = ""


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["sistema", "titulo", "descripcion_original"]
        widgets = {
            "descripcion_original": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un solicitante solo puede elegir entre los sistemas a los que tiene acceso.
        # El superuser ve todos los sistemas (mismo bypass que en listado/detalle).
        if usuario is not None and not usuario.is_superuser:
            self.fields["sistema"].queryset = self.fields["sistema"].queryset.filter(
                usuariosistema__usuario=usuario
            )


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ["cuerpo"]
        widgets = {
            "cuerpo": forms.Textarea(attrs={"rows": 3, "placeholder": "Escriba una respuesta..."}),
        }
